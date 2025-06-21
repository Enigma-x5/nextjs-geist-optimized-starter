import os
import json
import logging
import asyncio
import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from aio_pika import connect_robust, Message, DeliveryMode, Connection, Channel
from paddleocr import PaddleOCR
from tenacity import retry, stop_after_attempt, wait_exponential
import re

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ocr_service")

# Environment variables with defaults
AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@rabbitmq/")
QUEUE_IN = os.getenv("QUEUE_IN", "detections")
QUEUE_OUT = os.getenv("QUEUE_OUT", "ocr_results")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
USE_GPU = os.getenv("USE_GPU", "true").lower() == "true"

@dataclass
class OCRResult:
    text: str
    confidence: float
    bbox: List[float]
    timestamp: str
    camera_id: str
    plate_crop: str

class OCRError(Exception):
    """Custom exception for OCR-related errors"""
    pass

class OCRService:
    def __init__(self):
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self.queue_in: Optional[str] = None
        self.queue_out: Optional[str] = None
        self.ocr: Optional[PaddleOCR] = None
        self.retry_queue: Dict[str, int] = {}  # Track retry attempts
        
        # Initialize metrics
        self.total_processed = 0
        self.successful_reads = 0
        self.failed_reads = 0

    async def initialize(self) -> None:
        """Initialize PaddleOCR with GPU support"""
        try:
            logger.info("Initializing PaddleOCR...")
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang='en',
                use_gpu=USE_GPU,
                show_log=False
            )
            logger.info(f"PaddleOCR initialized (GPU: {USE_GPU})")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
            raise OCRError(f"OCR initialization failed: {str(e)}")

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

    def preprocess_image(self, img_bytes: str) -> np.ndarray:
        """Enhanced image preprocessing for better OCR accuracy"""
        try:
            # Decode image from hex string
            nparr = np.frombuffer(bytes.fromhex(img_bytes), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise OCRError("Failed to decode image")

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply adaptive thresholding
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(thresh, None, 30, 7, 21)
            
            # Increase contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            return enhanced
        except Exception as e:
            raise OCRError(f"Image preprocessing failed: {str(e)}")

    def validate_plate_format(self, text: str) -> bool:
        """Validate license plate format using regex patterns"""
        # Remove spaces and convert to uppercase
        text = text.replace(" ", "").upper()
        
        # Common plate format patterns (adjust based on your region)
        patterns = [
            r'^[A-Z]{2}\d{2}[A-Z]{2}\d{4}$',  # Format: AB12CD3456
            r'^[A-Z]{2}\d{4}$',                # Format: AB1234
            r'^[A-Z]{3}\d{3}$',                # Format: ABC123
            r'^[A-Z]{3}\d{4}$',                # Format: ABC1234
            r'^[A-Z]{2}\d{3}[A-Z]{2}$'         # Format: AB123CD
        ]
        
        return any(re.match(pattern, text) for pattern in patterns)

    async def process_ocr(self, image: np.ndarray, retry_count: int = 0) -> Optional[Tuple[str, float]]:
        """Process OCR with retry mechanism for low confidence results"""
        try:
            result = self.ocr.ocr(image, cls=True)
            if not result or not result[0]:
                return None

            text = result[0][0][1][0]  # Extract text
            confidence = float(result[0][0][1][1])  # Extract confidence

            # If confidence is low and retries are available, try with different preprocessing
            if confidence < CONFIDENCE_THRESHOLD and retry_count < MAX_RETRIES:
                # Apply additional preprocessing techniques
                if retry_count == 1:
                    # Try with different threshold
                    _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                elif retry_count == 2:
                    # Try with dilation
                    kernel = np.ones((2,2), np.uint8)
                    image = cv2.dilate(image, kernel, iterations=1)

                return await self.process_ocr(image, retry_count + 1)

            return (text, confidence) if confidence >= CONFIDENCE_THRESHOLD else None

        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            return None

    async def process_message(self, message: Message) -> None:
        """Process incoming message containing plate detections"""
        async with message.process():
            try:
                data = json.loads(message.body)
                results = []

                for detection in data:
                    try:
                        self.total_processed += 1
                        
                        # Extract plate crop and metadata
                        plate_crop = detection.get("plate_crop")
                        if not plate_crop:
                            continue

                        # Preprocess image
                        processed_img = self.preprocess_image(plate_crop)
                        
                        # Perform OCR
                        ocr_result = await self.process_ocr(processed_img)
                        
                        if ocr_result:
                            text, confidence = ocr_result
                            
                            # Validate plate format
                            if not self.validate_plate_format(text):
                                logger.info(f"Invalid plate format: {text}")
                                self.failed_reads += 1
                                continue

                            result = OCRResult(
                                text=text,
                                confidence=confidence,
                                bbox=detection.get("bbox", []),
                                timestamp=detection.get("timestamp", ""),
                                camera_id=detection.get("camera_id", ""),
                                plate_crop=plate_crop
                            )
                            results.append(result.__dict__)
                            self.successful_reads += 1
                        else:
                            self.failed_reads += 1

                    except Exception as e:
                        logger.error(f"Error processing detection: {str(e)}")
                        self.failed_reads += 1
                        continue

                if results:
                    await self.publish_results(results)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

    async def publish_results(self, results: List[Dict[str, Any]]) -> None:
        """Publish OCR results to output queue"""
        try:
            message = Message(
                json.dumps(results).encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            )
            await self.channel.default_exchange.publish(
                message,
                routing_key=QUEUE_OUT
            )
            logger.info(f"Published {len(results)} OCR results")
        except Exception as e:
            logger.error(f"Failed to publish results: {str(e)}")
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
        service = OCRService()
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.critical(f"Service failed to start: {str(e)}")
        raise
