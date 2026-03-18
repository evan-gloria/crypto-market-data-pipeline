import json
import time
import uuid
import boto3
import os
from datetime import datetime
from confluent_kafka import Consumer
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Safely pull from environment with fallbacks
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
TOPIC = os.getenv('KAFKA_TOPIC', 'crypto-trades')
S3_BUCKET = os.getenv('S3_BUCKET')
S3_PREFIX = os.getenv('S3_PREFIX', 'trades/')
FLUSH_INTERVAL = int(os.getenv('FLUSH_INTERVAL', 60))
AWS_PROFILE = os.getenv('AWS_PROFILE', 'default')

if not S3_BUCKET:
    raise ValueError("CRITICAL: S3_BUCKET environment variable is missing.")

consumer = Consumer({
    'bootstrap.servers': KAFKA_BROKER, 
    'group.id': 's3_sink_group', 
    'auto.offset.reset': 'earliest'
})
consumer.subscribe([TOPIC])
s3 = boto3.Session(profile_name='crypto-poc').client('s3')

def flush(batch):
    if not batch: return
    now = datetime.utcnow()
    # Hive-style partitioning
    key = f"{S3_PREFIX}year={now.year}/month={now.month:02d}/day={now.day:02d}/trades_{now.strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body="\n".join([json.dumps(m) for m in batch]))
    print(f"Flushed {len(batch)} records to s3://{S3_BUCKET}/{key}")

if __name__ == "__main__":
    batch = []
    last_flush = time.time()
    print("Consumer active. Buffering and sinking to S3...")
    try:
        while True:
            msg = consumer.poll(1.0)
            if time.time() - last_flush > FLUSH_INTERVAL:
                flush(batch)
                batch = []
                last_flush = time.time()
            if msg and not msg.error():
                batch.append(json.loads(msg.value().decode('utf-8')))
    except KeyboardInterrupt:
        flush(batch)
    finally:
        consumer.close()