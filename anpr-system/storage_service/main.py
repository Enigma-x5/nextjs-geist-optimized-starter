import os
import hashlib
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from aio_pika import connect_robust, Message, DeliveryMode, Connection, Channel
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, Float, text, func
from geoalchemy2 import Geometry
from tenacity import retry, stop_after_attempt, wait_exponential
import boto3
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("storage_service")

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@db:5432/anpr")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioaccesskey")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "miniosecretkey")
S3_BUCKET = os.getenv("S3_BUCKET", "anpr-plates")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key()).encode()
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
QUEUE_IN = os.getenv("QUEUE_IN", "tracking_events")

app = FastAPI()
Base = declarative_base()

# Initialize encryption
fernet = Fernet(ENCRYPTION_KEY)

class StorageError(Exception):
    """Custom exception for storage-related errors"""
    pass

class Event(Base):
    __tablename__ = 'events'
    
    id = Column(String, primary_key=True)
    plate_hash = Column(String, index=True)
    ts = Column(DateTime, index=True)
    camera_id = Column(String)
    geom = Column(Geometry('POINT', srid=4326))
    confidence = Column(Float)
    vehicle_id = Column(String, index=True)
    speed = Column(Float, nullable=True)
    direction = Column(String, nullable=True)

class EventIn(BaseModel):
    plate: str
    timestamp: datetime
    camera_id: str
    lat: float
    lng: float
    confidence: float
    vehicle_id: str
    speed: Optional[float]
    direction: Optional[str]
    plate_crop: bytes

class StorageService:
    def __init__(self):
        self.engine = create_async_engine(DATABASE_URL, echo=True)
        self.async_session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self.s3_client = self.initialize_s3()
        
        # Initialize metrics
        self.total_stored = 0
        self.failed_operations = 0

    def initialize_s3(self) -> Any:
        """Initialize S3 client with retry mechanism"""
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=S3_ENDPOINT,
                aws_access_key_id=S3_ACCESS_KEY,
                aws_secret_access_key=S3_SECRET_KEY,
                config=boto3.client.Config(signature_version='s3v4')
            )
            # Ensure bucket exists
            try:
                s3_client.head_bucket(Bucket=S3_BUCKET)
            except ClientError:
                s3_client.create_bucket(Bucket=S3_BUCKET)
                # Enable server-side encryption
                s3_client.put_bucket_encryption(
                    Bucket=S3_BUCKET,
                    ServerSideEncryptionConfiguration={
                        'Rules': [
                            {
                                'ApplyServerSideEncryptionByDefault': {
                                    'SSEAlgorithm': 'AES256'
                                }
                            }
                        ]
                    }
                )
            return s3_client
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise StorageError(f"S3 initialization failed: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def connect_rabbitmq(self) -> None:
        """Establish connection to RabbitMQ with retry mechanism"""
        try:
            logger.info("Connecting to RabbitMQ...")
            self.connection = await connect_robust(
                f"amqp://guest:guest@rabbitmq/"
            )
            self.channel = await self.connection.channel()
            await self.channel.declare_queue(QUEUE_IN, durable=True)
            logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise

    async def store_plate_image(self, plate_hash: str, timestamp: str, data: bytes) -> str:
        """Store plate image in S3 with encryption"""
        try:
            # Encrypt data before storing
            encrypted_data = fernet.encrypt(data)
            
            key = f"plates/{plate_hash}/{timestamp}.jpg"
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=S3_BUCKET,
                Key=key,
                Body=encrypted_data,
                ServerSideEncryption='AES256'
            )
            return key
        except Exception as e:
            logger.error(f"Failed to store image: {str(e)}")
            self.failed_operations += 1
            raise StorageError(f"Image storage failed: {str(e)}")

    def hash_plate(self, plate: str) -> str:
        """Create secure hash of license plate number"""
        return hashlib.sha256(plate.encode('utf-8')).hexdigest()

    async def cleanup_old_data(self, background_tasks: BackgroundTasks) -> None:
        """Clean up old data based on retention policy"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
            
            async with self.async_session() as session:
                # Delete old database records
                await session.execute(
                    text(f"DELETE FROM events WHERE ts < :cutoff"),
                    {"cutoff": cutoff_date}
                )
                await session.commit()
            
            # Delete old S3 objects
            objects = await asyncio.to_thread(
                self.s3_client.list_objects_v2,
                Bucket=S3_BUCKET
            )
            
            for obj in objects.get('Contents', []):
                if datetime.fromisoformat(obj['LastModified'].isoformat()) < cutoff_date:
                    await asyncio.to_thread(
                        self.s3_client.delete_object,
                        Bucket=S3_BUCKET,
                        Key=obj['Key']
                    )
            
            logger.info(f"Cleaned up data older than {cutoff_date}")
        except Exception as e:
            logger.error(f"Failed to clean up old data: {str(e)}")
            self.failed_operations += 1

    async def process_message(self, message: Message) -> None:
        """Process incoming tracking events"""
        async with message.process():
            try:
                events = json.loads(message.body)
                background_tasks = BackgroundTasks()
                
                for event_data in events:
                    try:
                        plate = event_data.get('plate', '')
                        plate_hash = self.hash_plate(plate)
                        timestamp = event_data.get('timestamp', '')
                        
                        # Store plate image if available
                        plate_crop = event_data.get('plate_crop')
                        if plate_crop:
                            await self.store_plate_image(
                                plate_hash,
                                timestamp,
                                bytes.fromhex(plate_crop)
                            )
                        
                        # Create database record
                        async with self.async_session() as session:
                            event = Event(
                                id=f"{plate_hash}_{timestamp}",
                                plate_hash=plate_hash,
                                ts=datetime.fromisoformat(timestamp),
                                camera_id=event_data.get('camera_id', ''),
                                geom=func.ST_SetSRID(
                                    func.ST_MakePoint(
                                        event_data.get('lng', 0),
                                        event_data.get('lat', 0)
                                    ),
                                    4326
                                ),
                                confidence=event_data.get('confidence', 0.0),
                                vehicle_id=event_data.get('vehicle_id', ''),
                                speed=event_data.get('speed'),
                                direction=event_data.get('direction')
                            )
                            session.add(event)
                            await session.commit()
                        
                        self.total_stored += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to process event: {str(e)}")
                        self.failed_operations += 1
                        continue
                
                # Schedule cleanup task
                background_tasks.add_task(self.cleanup_old_data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {str(e)}")
                self.failed_operations += 1
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                self.failed_operations += 1

    async def run(self) -> None:
        """Main service loop"""
        try:
            await self.connect_rabbitmq()
            
            # Create database tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Start consuming messages
            queue = await self.channel.declare_queue(QUEUE_IN, durable=True)
            await queue.consume(self.process_message)
            
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
        service = StorageService()
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.critical(f"Service failed to start: {str(e)}")
        raise
