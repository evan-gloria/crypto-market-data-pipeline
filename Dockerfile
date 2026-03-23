# Use the official, lightweight Python 3.10 image to match your local setup
FROM python:3.10-slim

# Best Practices for Python in Docker:
# 1. Prevent Python from writing .pyc files
# 2. Keep stdout unbuffered so we can see our print() statements instantly in AWS CloudWatch logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create and set the working directory inside the container
WORKDIR /app

# Copy just the requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install the dependencies cleanly
RUN pip install --no-cache-dir -r requirements.txt

# Copy your producer script into the container
# (Assuming it is sitting in the src/ folder)
COPY src/producer_firehose.py .

# Command to execute when the container boots up
CMD ["python", "producer_firehose.py"]