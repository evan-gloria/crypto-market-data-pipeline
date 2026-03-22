#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Load environment variables from .env
source .env

echo "Starting Deployment Pipeline..."

# Generate a unique hash based on the content of the ETL script
SCRIPT_HASH=$(md5sum src/jobs/*_etl.py | cut -d ' ' -f 1)

# Step 1: Upload the PySpark script to the S3 Data Lake
# We use 'sync' so it only uploads if the file has changed
echo "Syncing ETL scripts to S3..."
aws s3 sync src/jobs/ s3://${S3_BUCKET}/scripts/ --profile ${AWS_PROFILE}

# Step 2: Deploy the CloudFormation Stack
# This will create or update the Glue Job now that the script is safely in S3
echo "Deploying Infrastructure via CloudFormation with Hash: ${SCRIPT_HASH}"
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name crypto-market-data-infra \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile ${AWS_PROFILE}

echo "Deployment Complete!"