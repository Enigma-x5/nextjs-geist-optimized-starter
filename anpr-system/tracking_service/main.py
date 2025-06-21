import os
import json
import logging
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from aio_pika import connect_robust, Message, DeliveryMode, Connection, Channel
from deep_sort_realtime.deepsort_tracker import DeepSort
from tenacity import retry, stop_after_attempt, wait_exponential

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("tracking_service")

# Environment variables with defaults
AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@rabbitmq/")
QUEUE_IN = os.getenv("QUEUE_IN", "ocr_results")
QUEUE_OUT = os.getenv("QUEUE_OUT", "tracking_events")
MAX_AGE = int(os.getenv("MAX_AGE", "30"))  # Maximum frames to keep track of object
N_INIT = int(os.getenv("N_INIT", "3"))     # Number of frames for track confirmation
MAX_IOU_DISTANCE = float(os.getenv("MAX_IOU_DISTANCE", "0.7"))
MAX_COSINE_DISTANCE = float(os.getenv("MAX_COSINE_DISTANCE", "0.3"))

@dataclass
class TrackingEvent:
    vehicle_id: str
    plate: str
    timestamp: str
    camera_id: str
    bbox: List[float]
    confidence: float
    lat: Optional[float] = None
    lng: Optional[float] = None
    speed: Optional[float] = None
    direction: Optional[str] = None

class TrackingError(Exception):
    """Custom exception for tracking-related errors"""
    pass

class VehicleTracker:
    def __init__(self):
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self.queue_in: Optional[str] = None
        self.queue_out: Optional[str] = None
        self.tracker = self.initialize_tracker()
        
        # Track metrics
        self.total_tracks = 0
        self.active_tracks = 0
        self.total_events = 0
        
        # Store historical positions for speed calculation
        self.track_history: Dict[int, List[Dict[str, Any]]] = {}

    def initialize_tracker(self) -> DeepSort:
        """Initialize DeepSORT tracker with optimized parameters"""
        try:
            tracker = DeepSort(
                max_age=MAX_AGE,
                n_init=N_INIT,
                max_iou_distance=MAX_IOU_DISTANCE,
                max_cosine_distance=MAX_COSINE_DISTANCE,
                nn_budget=100
            )
            logger.info("DeepSORT tracker initialized successfully")
            return tracker
        except Exception as e:
            logger.error(f"Failed to initialize tracker: {str(e)}")
            raise TrackingError(f"Tracker initialization failed: {str(e)}")

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

    def calculate_speed_and_direction(self, track_id: int, bbox: List[float], timestamp: str) -> Tuple[Optional[float], Optional[str]]:
        """Calculate vehicle speed and direction based on historical positions"""
        if track_id not in self.track_history:
            self.track_history[track_id] = []
        
        # Get center point of bbox
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        
        current_pos = {
            'x': center_x,
            'y': center_y,
            'timestamp': datetime.fromisoformat(timestamp)
        }
        
        self.track_history[track_id].append(current_pos)
        
        # Keep only last 5 positions
        self.track_history[track_id] = self.track_history[track_id][-5:]
        
        if len(self.track_history[track_id]) < 2:
            return None, None
            
        # Calculate speed (pixels per second)
        prev_pos = self.track_history[track_id][-2]
        time_diff = (current_pos['timestamp'] - prev_pos['timestamp']).total_seconds()
        if time_diff == 0:
            return None, None
            
        distance = np.sqrt(
            (current_pos['x'] - prev_pos['x'])**2 +
            (current_pos['y'] - prev_pos['y'])**2
        )
        speed = distance / time_diff
        
        # Calculate direction
        dx = current_pos['x'] - prev_pos['x']
        dy = current_pos['y'] - prev_pos['y']
        
        # Convert to cardinal directions
        angle = np.arctan2(dy, dx) * 180 / np.pi
        if -45 <= angle <= 45:
            direction = "E"
        elif 45 < angle <= 135:
            direction = "S"
        elif -135 <= angle < -45:
            direction = "N"
        else:
            direction = "W"
            
        return speed, direction

    async def process_message(self, message: Message) -> None:
        """Process incoming message containing OCR results"""
        async with message.process():
            try:
                data = json.loads(message.body)
                events = []

                for item in data:
                    try:
                        bbox = item.get("bbox", [])
                        if not bbox:
                            continue

                        # Update tracker
                        tracks = self.tracker.update_tracks([bbox], embed=None)
                        self.active_tracks = len([t for t in tracks if t.is_confirmed()])
                        
                        for track in tracks:
                            if not track.is_confirmed():
                                continue

                            self.total_tracks += 1
                            track_id = track.track_id
                            
                            # Calculate speed and direction
                            speed, direction = self.calculate_speed_and_direction(
                                track_id, bbox, item.get("timestamp", "")
                            )

                            # Create tracking event
                            event = TrackingEvent(
                                vehicle_id=str(track_id),
                                plate=item.get("plate", ""),
                                timestamp=item.get("timestamp", ""),
                                camera_id=item.get("camera_id", ""),
                                bbox=bbox,
                                confidence=item.get("confidence", 0.0),
                                speed=speed,
                                direction=direction
                            )
                            events.append(event.__dict__)
                            self.total_events += 1

                    except Exception as e:
                        logger.error(f"Error processing track: {str(e)}")
                        continue

                if events:
                    await self.publish_events(events)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

    async def publish_events(self, events: List[Dict[str, Any]]) -> None:
        """Publish tracking events to output queue"""
        try:
            message = Message(
                json.dumps(events).encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            )
            await self.channel.default_exchange.publish(
                message,
                routing_key=QUEUE_OUT
            )
            logger.info(f"Published {len(events)} tracking events")
        except Exception as e:
            logger.error(f"Failed to publish events: {str(e)}")
            # Attempt to reconnect
            await self.connect()

    def cleanup_old_tracks(self) -> None:
        """Clean up historical data for old tracks"""
        current_tracks = {t.track_id for t in self.tracker.tracks if t.is_confirmed()}
        for track_id in list(self.track_history.keys()):
            if track_id not in current_tracks:
                del self.track_history[track_id]

    async def run(self) -> None:
        """Main service loop"""
        try:
            await self.connect()
            
            # Start consuming messages
            await self.queue_in.consume(self.process_message)
            
            # Periodic cleanup task
            while True:
                await asyncio.sleep(60)  # Clean up every minute
                self.cleanup_old_tracks()
                
        except Exception as e:
            logger.critical(f"Critical error in service: {str(e)}")
            raise
        finally:
            if self.connection:
                await self.connection.close()

if __name__ == "__main__":
    try:
        tracker = VehicleTracker()
        asyncio.run(tracker.run())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.critical(f"Service failed to start: {str(e)}")
        raise
