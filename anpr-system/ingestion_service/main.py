import os
import yaml
import cv2
import time
import json
import logging
import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
from aio_pika import connect_robust, Message, DeliveryMode, Connection, Channel
from tenacity import retry, stop_after_attempt, wait_exponential

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ingestion_service")

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")

@dataclass
class StreamConfig:
    url: str
    name: str = ""
    enabled: bool = True

class ConfigurationError(Exception):
    """Raised when configuration is invalid"""
    pass

class FrameIngestor:
    def __init__(self, config: Dict[str, Any]):
        self.validate_config(config)
        self.streams = [StreamConfig(**s) for s in config.get("streams", [])]
        self.fps = config.get("fps", 1)
        self.batch_size = config.get("batch_size", 5)
        self.amqp_url = config.get("amqp_url", "amqp://guest:guest@rabbitmq/")
        self.queue_name = config.get("queue_name", "frame_batches")
        self.connection: Connection = None
        self.channel: Channel = None
        self.active_streams: Dict[str, bool] = {s.url: True for s in self.streams}
        self.reconnect_delay = 5.0  # Initial reconnect delay in seconds

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
        """Validate configuration parameters"""
        if not isinstance(config, dict):
            raise ConfigurationError("Configuration must be a dictionary")

        required_keys = ["streams", "fps", "batch_size", "amqp_url"]
        for key in required_keys:
            if key not in config:
                raise ConfigurationError(f"Missing required configuration key: {key}")

        if not isinstance(config["streams"], list) or not config["streams"]:
            raise ConfigurationError("'streams' must be a non-empty list")

        for stream in config["streams"]:
            if not isinstance(stream, dict) or "url" not in stream:
                raise ConfigurationError("Each stream must be a dictionary with 'url' key")

        if not isinstance(config["fps"], (int, float)) or config["fps"] <= 0:
            raise ConfigurationError("'fps' must be a positive number")

        if not isinstance(config["batch_size"], int) or config["batch_size"] <= 0:
            raise ConfigurationError("'batch_size' must be a positive integer")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def connect(self) -> None:
        """Establish connection to RabbitMQ with retry mechanism"""
        try:
            logger.info("Connecting to RabbitMQ...")
            self.connection = await connect_robust(self.amqp_url)
            self.channel = await self.connection.channel()
            await self.channel.declare_queue(self.queue_name, durable=True)
            logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise

    async def publish_batch(self, batch: List[bytes], stream_url: str) -> None:
        """Publish a batch of frames to RabbitMQ"""
        try:
            if not self.channel:
                logger.error("No channel available for publishing")
                return

            message_data = {
                "frames": [frame.hex() for frame in batch],
                "timestamp": time.time(),
                "stream_url": stream_url
            }

            message = Message(
                json.dumps(message_data).encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            )
            
            await self.channel.default_exchange.publish(
                message,
                routing_key=self.queue_name
            )
            logger.info(f"Published batch of {len(batch)} frames from {stream_url}")
        except Exception as e:
            logger.error(f"Failed to publish batch from {stream_url}: {str(e)}")
            # Attempt to reconnect on next iteration
            self.channel = None
            await self.connect()

    async def capture_stream(self, stream: StreamConfig) -> None:
        """Capture and process frames from a single stream"""
        logger.info(f"Starting capture for stream: {stream.url}")
        batch: List[bytes] = []
        last_capture_time = 0
        consecutive_failures = 0
        max_failures = 3

        while self.active_streams[stream.url]:
            try:
                cap = cv2.VideoCapture(stream.url)
                if not cap.isOpened():
                    raise RuntimeError(f"Failed to open stream: {stream.url}")

                while cap.isOpened() and self.active_streams[stream.url]:
                    current_time = time.time()
                    if current_time - last_capture_time >= 1.0 / self.fps:
                        ret, frame = cap.read()
                        if not ret:
                            raise RuntimeError("Failed to read frame")

                        # Encode frame as JPEG
                        ret, jpeg = cv2.imencode('.jpg', frame)
                        if not ret:
                            raise RuntimeError("Failed to encode frame")

                        batch.append(jpeg.tobytes())
                        last_capture_time = current_time

                        if len(batch) >= self.batch_size:
                            await self.publish_batch(batch, stream.url)
                            batch = []
                            consecutive_failures = 0  # Reset failure counter on success

                    await asyncio.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in stream {stream.url}: {str(e)}")
                consecutive_failures += 1
                
                if consecutive_failures >= max_failures:
                    logger.error(f"Too many consecutive failures for {stream.url}, temporarily disabling")
                    await asyncio.sleep(30)  # Cool-down period
                    consecutive_failures = 0
                
                if cap:
                    cap.release()
                
                # Exponential backoff for reconnection attempts
                await asyncio.sleep(min(30, 2 ** consecutive_failures))
                continue
            
            finally:
                if cap:
                    cap.release()

    async def run(self) -> None:
        """Main service loop"""
        try:
            await self.connect()
            tasks = [self.capture_stream(stream) for stream in self.streams]
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Critical error in service: {str(e)}")
            raise
        finally:
            if self.connection:
                await self.connection.close()

def load_config(path: str) -> Dict[str, Any]:
    """Load and validate configuration from YAML file"""
    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
            if not config:
                raise ConfigurationError("Empty configuration file")
            return config
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Failed to parse YAML: {str(e)}")
    except FileNotFoundError:
        raise ConfigurationError(f"Configuration file not found: {path}")

if __name__ == "__main__":
    try:
        config = load_config(CONFIG_PATH)
        ingestor = FrameIngestor(config)
        asyncio.run(ingestor.run())
    except Exception as e:
        logger.critical(f"Service failed to start: {str(e)}")
        raise
