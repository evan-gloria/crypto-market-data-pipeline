import json
import boto3
import websocket
import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

REGION_NAME = os.getenv('AWS_REGION', 'ap-southeast-2')
STREAM_NAME = os.getenv('FIREHOSE_STREAM_NAME', 'crypto-market-firehose')
SOCKET_URL = os.getenv('BINANCE_WS_URL', 'wss://stream.binance.com:9443/ws/btcusdt@aggTrade')
AWS_PROFILE = os.getenv('AWS_PROFILE', 'default')

# Check if AWS_PROFILE exists in the environment (Local Testing)
if AWS_PROFILE and AWS_PROFILE != 'default':
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION_NAME)
    firehose = session.client('firehose')
else:
    # If no profile is set, let Boto3 automatically find the Fargate IAM Role credentials
    firehose = boto3.client('firehose', region_name=REGION_NAME)

def on_message(ws, message):
    # CRITICAL: Add newline for Athena/PySpark NDJSON parsing
    payload = message + '\n'
    
    try:
        response = firehose.put_record(
            DeliveryStreamName=STREAM_NAME,
            Record={'Data': payload}
        )
        print(f"Sent to Firehose (RecordId: {response['RecordId'][:10]}...)")
    except Exception as e:
        print(f"Failed to send record: {e}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_open(ws):
    print("Connected to Binance. Streaming to {STREAM_NAME} using profile '{AWS_PROFILE}'...")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(SOCKET_URL,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    ws.run_forever()