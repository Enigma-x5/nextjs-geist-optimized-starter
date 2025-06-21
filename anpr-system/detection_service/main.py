import os
import json
import logging
import asyncio
import torch
import cv2
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from aio_pika import connect_robust, Message, DeliveryMode, Connection, Channel
from ultralytics import YOLO
from tenacity import retry, stop_after_attempt, wait_exponential

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("detection_service")

# Environment variables with defaults
AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@rabbitmq/")
QUEUE_IN = os.getenv("QUEUE_IN", "frame_batches")
QUEUE_OUT = os.getenv("QUEUE_OUT", "detections")
MODEL_PATH = os.getenv("MODEL_PATH", "yolov8.pt")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "4"))  # Batch size for inference
DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")

@dataclass
class Detection:
    bbox: List[float]
    confidence: float
    class_id: int
    plate_crop: Optional[str] = None  # Base64 encoded image if class_id is plate

class DetectionError(Exception):
    """Custom exception for detection-related errors"""
    pass

class DetectionService:
    def __init__(self):
        self.model: Optional[YOLO] = None
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self.queue_in: Optional[str] = None
        self.queue_out: Optional[str] = None
        self.device = DEVICE
        self.batch_size = BATCH_SIZE
        
        # Initialize metrics
        self.total_frames_processed = 0
        self.total_detections = 0
        self.total_errors = 0

    async def initialize(self) -> None:
        """Initialize the YOLO model and verify GPU availability"""
        try:
            logger.info(f"Initializing YOLO model from {MODEL_PATH} on {self.device}")
            self.model = YOLO(MODEL_PATH)
            
            # Move model to appropriate device
            self.model.to(self.device)
            
            # Log device information
            if self.device == "cuda":
                logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
                logger.info(f"Available GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
            
            # Warmup run
            dummy_input = torch.zeros((1, 3, 640, 640)).to(self.device)
            self.model(dummy_input)
            logger.info("Model initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize YOLO model: {str(e)}")
            raise DetectionError(f"Model initialization failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def connect(self) -> None:
        """Establish connection to RabbitMQ with retry mechanism"""
        try:
            logger.info("Connecting to RabbitMQ...")
            self.connection = await connect_robust(AMQP_URL)
            self.channel = await self.connection.channel()
            
            # Declare queues
            self.queue_in = await self.channel.declare_queue(QUEUE_IN, durable=True)
            self.queue_out = await self.channel.declare_queue(QUEUE_OUT, durable=True)
            
            logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise

    def preprocess_frame(self, frame_bytes: bytes) -> np.ndarray:
        """Preprocess frame for YOLO inference"""
        try:
            # Decode frame
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                raise DetectionError("Failed to decode frame")
            
            # Convert BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return frame
        except Exception as e:
            raise DetectionError(f"Frame preprocessing failed: {str(e)}")

    def process_detections(self, results: Any, frame: np.ndarray) -> List[Detection]:
        """Process YOLO detection results"""
        detections = []
        try:
            for det in results.boxes.data.cpu().numpy():
                x1, y1, x2, y2, score, class_id = det
                if score < CONFIDENCE_THRESHOLD:
                    continue
                
                detection = Detection(
                    bbox=[float(x1), float(y1), float(x2), float(y2)],
                    confidence=float(score),
                    class_id=int(class_id)
                )
                
                # If detection is a license plate, add cropped image
                if int(class_id) == 1:  # Assuming 1 is license plate class
                    crop = frame[int(y1):int(y2), int(x1):int(x2)]
                    _, jpeg = cv2.imencode('.jpg', crop)
                    detection.plate_crop = jpeg.tobytes().hex()
                
                detections.append(detection)
                self.total_detections += 1
                
            return detections
        except Exception as e:
            self.total_errors += 1
            raise DetectionError(f"Detection processing failed: {str(e)}")

    async def process_message(self, message: Message) -> None:
        """Process incoming message containing frame batch"""
        async with message.process():
            try:
                batch = json.loads(message.body)
                frames = []
                frame_data = []
                
                # Prepare batch for processing
                for frame_info in batch["frames"]:
                    try:
                        frame_bytes = bytes.fromhex(frame_info)
                        frame = self.preprocess_frame(frame_bytes)
                        frames.append(frame)
                        frame_data.append({
                            "timestamp": batch.get("timestamp"),
                            "stream_url": batch.get("stream_url")
                        })
                    except Exception as e:
                        logger.warning(f"Skipping invalid frame: {str(e)}")
                        continue

                if not frames:
                    logger.warning("No valid frames in batch")
                    return

                # Process frames in batches
                for i in range(0, len(frames), self.batch_size):
                    batch_frames = frames[i:i + self.batch_size]
                    batch_data = frame_data[i:i + self.batch_size]
                    
                    # Run inference
                    results = self.model(batch_frames, verbose=False)
                    
                    # Process results
                    all_detections = []
                    for idx, result in enumerate(results):
                        detections = self.process_detections(result, batch_frames[idx])
                        if detections:
                            detection_data = {
                                "detections": [d.__dict__ for d in detections],
                                "timestamp": batch_data[idx]["timestamp"],
                                "stream_url": batch_data[idx]["stream_url"]
                            }
                            all_detections.append(detection_data)
                    
                    # Publish results
                    if all_detections:
                        await self.publish_detections(all_detections)
                    
                    self.total_frames_processed += len(batch_frames)

            except json.JSONDecodeError as e:
                self.total_errors += 1
                logger.error(f"Failed to decode message: {str(e)}")
            except Exception as e:
                self.total_errors += 1
                logger.error(f"Error processing message: {str(e)}")

    async def publish_detections(self, detections: List[Dict[str, Any]]) -> None:
        """Publish detection results to output queue"""
        try:
            message = Message(
                json.dumps(detections).encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            )
            await self.channel.default_exchange.publish(message, routing_key=QUEUE_OUT)
            logger.info(f"Published {len(detections)} detection results")
        except Exception as e:
            self.total_errors += 1
            logger.error(f"Failed to publish detections: {str(e)}")
            # Attempt to reconnect
            await self.connect()

    async def run(self) -> None:
        """Main service loop"""
        try:
            await self.initialize()
            await self.connect()
            
            # Start consuming messages
            await self.queue_in.consume(self.process_message)
            
            # Keep the service running
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.critical(f"Critical error in service: {str(e)}")
            raise
        finally:
            if self.connection:
                await self.connection.close()

if __name__ == "__main__":
    try:
        service = DetectionService()
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.critical(f"Service failed to start: {str(e)}")
        raise
