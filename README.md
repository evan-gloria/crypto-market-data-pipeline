# Real-Time Market Data Ingestion Pipeline

A Proof of Concept (POC) demonstrating a high-throughput, real-time streaming data pipeline. It ingests unbounded WebSocket tick data, buffers it via a local message broker, and micro-batches it into a serverless data lake architecture for ad-hoc querying.

## 🏗️ Architecture Overview

This pipeline simulates the ingestion of high-velocity financial market data (tick data) using a decoupled, event-driven architecture.

### Phase 1: Local POC (Current State)

This repository contains the functional Proof of Concept, demonstrating the core mechanics of stream buffering, idempotent S3 writes, and Hive-style partitioning.

![Architecture Diagram](assets/crypto-poc-aws-architecture.png)

1. **Data Source:** Public WebSocket API (`wss://stream.binance.com:9443/ws/btcusdt@aggTrade`) streaming live BTC/USDT aggregate trades.
2. **Message Broker:** Confluent Kafka (KRaft mode) running locally to provide durable buffering and handle backpressure.
3. **Producer (`producer.py`):** An asynchronous Python client that reads the continuous WebSocket stream and publishes events to the `crypto_market_trades` Kafka topic.
4. **Consumer/Sink (`consumer.py`):** A Python consumer that reads from Kafka, micro-batches messages into 60-second windows, and flushes newline-delimited JSON (NDJSON) to Amazon S3 using Hive-style partitioning (`year=YYYY/month=MM/day=DD`).
5. **Data Catalog & Analytics (AWS):** An AWS Glue Crawler infers the schema of the S3 data lake and registers it in the AWS Glue Data Catalog, enabling serverless ANSI SQL querying via Amazon Athena.
6. **Silver Layer Processing (AWS Glue ETL):** A serverless PySpark job (`bronze_to_silver_etl.py`) processes the fragmented JSON files, casts schema data types, and compacts the data into optimized Parquet format to solve the "Small File Problem."
 
### Phase 2: Enterprise Target State (Production Design)

To scale this architecture to process millions of events per second with zero data loss, the following managed services represent the target state:
* **Amazon MSK (Managed Streaming for Kafka):** Replaces local Docker for multi-AZ broker resilience and elastic scaling.
* **Apache Flink (Amazon Managed Service for Apache Flink):** Replaces the Python consumer for stateful, exactly-once stream processing and real-time schema normalization (handling late-arriving data via watermarks).
* **Apache Iceberg:** Replaces raw JSON S3 files to solve the "Small File Problem" via background compaction and to enable safe, ACID-compliant schema evolution.

## ⚙️ Prerequisites

* Docker & Docker Compose
* Python 3.10+
* [Poetry](https://python-poetry.org/) (Dependency Management)
* AWS CLI configured with SSO

## 🚀 Deployment & Execution Runbook

### Environment Configuration
This project follows 12-Factor App principles. Copy the example environment file and insert your specific AWS bucket and Kafka details.

```bash
cp .env.example .env
```

### 1. Infrastructure as Code (AWS)
Provision the S3 Data Lake, Glue Database, IAM least-privilege role, and Glue Crawler via the provided CloudFormation template.

```bash
chmod +x deploy.sh
./deploy.sh
```

*(Note: Update the `S3_BUCKET` variable in `.env` file to match the exact bucket name created by this stack).*

### 2. Local Kafka Cluster
Spin up the local single-node Kafka broker (KRaft mode).

```bash
docker-compose up -d
poetry install
```

### 3. Pipeline Execution
Run the pipeline by starting the sink and the stream in separate terminals:

```bash
# Terminal 1: Start the Consumer/Sink
poetry run python src/consumer.py

# Terminal 2: Start the Producer/Stream
poetry run python src/producer.py
```

### 4. Cataloging & Analytics
After 2-3 minutes of data generation, trigger the AWS Glue Crawler manually via the AWS Console or CLI:

```bash
aws glue start-crawler --name crypto_market_crawler --profile your-aws-profile
```

Once complete, navigate to Amazon Athena and query the `crypto_market_db`:

```sql
SELECT 
    event_time as event_time_ms,
    p as price,
    q as quantity
FROM "crypto_market_db"."trades"
WHERE year = '2026' AND month = '03'
ORDER BY event_time_ms DESC
LIMIT 100;
```

### 5. Silver Layer Transformation (AWS Glue PySpark)
Run the serverless ETL job to compact the raw JSON files into optimized Parquet format. This job uses Job Bookmarks to only process new data.

```bash
aws glue start-job-run --job-name crypto_bronze_to_silver_etl --profile your-aws-profile
```

### 6. Analytics (Amazon Athena)
Once the Glue job succeeds, register the Silver table and query the highly optimized columnar data:
```sql

-- Create and  external table to point to the silver table
CREATE EXTERNAL TABLE IF NOT EXISTS crypto_market_db.silver_trades (
  event_time_ms BIGINT,
  trade_price DOUBLE,
  trade_quantity DOUBLE,
  is_market_maker BOOLEAN
)
PARTITIONED BY (
  year STRING,
  month STRING,
  day STRING
)
STORED AS PARQUET
LOCATION 's3://<<S3 Bucket Here>>/silver/trades/'
tblproperties ("parquet.compress"="SNAPPY");

-- Once it succeeds, run this one final command to load the partitions
MSCK REPAIR TABLE crypto_market_db.silver_trades;

-- Test using a Query
SELECT * FROM crypto_market_db.silver_trades;

```

## 🧠 Design Decisions & Trade-Offs
* **Push vs. Poll:** A live WebSocket was chosen over a REST API (like Yahoo Finance) to properly simulate the unbounded, push-based nature of exchange market data (e.g., FIX/ITCH protocols) and to test asynchronous I/O handling.
* **Local Kafka vs. Amazon MSK:** For the scope of this POC, local Kafka via Docker was selected to eliminate cloud infrastructure provisioning latency and VPC routing complexity while maintaining the exact same producer/consumer API contracts as a production MSK cluster.
* **Micro-batching & Partitioning:** The consumer buffers stream data into 60-second windows before flushing to S3. Hive-style partitioning (`year/month/day`) is implemented at the sink to drastically reduce data scanned (and costs) during Athena queries.
* **Small File Problem & Compaction:** Real-time streaming often results in thousands of small files which degrade query performance. I implemented a Glue PySpark job to perform background compaction, merging the raw JSON into larger Parquet files. This reduced S3 metadata overhead and Athena data scanning costs.

## ⚠️ Disclaimer

This project is a Proof of Concept (POC) built strictly for **educational and personal portfolio purposes**. 

* **No Affiliation:** I am not affiliated, associated, authorized, endorsed by, or in any way officially connected with Binance, any cryptocurrency exchange, or any traditional financial institution (banks, brokerages, etc.).
* **Not Financial Advice:** The data ingested and processed by this pipeline is for demonstration purposes only. Nothing in this repository constitutes financial, investment, or trading advice.
* **Use at Your Own Risk:** Real-time market data pipelines can incur significant cloud infrastructure costs if left running. Please ensure you tear down all AWS resources (`aws cloudformation delete-stack`) when you are finished testing.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

⚙️ Engineered by Evan G.