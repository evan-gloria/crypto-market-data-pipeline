import websocket
import os
from confluent_kafka import Producer
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
TOPIC = os.getenv('KAFKA_TOPIC', 'crypto-trades')

producer = Producer({'bootstrap.servers': KAFKA_BROKER})

def on_message(ws, message):
    producer.produce(TOPIC, message.encode('utf-8'))
    producer.poll(0)

def on_error(ws, error): print(f"Error: {error}")
def on_close(ws, close_status_code, close_msg): producer.flush()
def on_open(ws): print("Streaming live tick data to Kafka...")

if __name__ == "__main__":
    ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws/btcusdt@aggTrade",
                              on_open=on_open, on_message=on_message,
                              on_error=on_error, on_close=on_close)
    ws.run_forever()