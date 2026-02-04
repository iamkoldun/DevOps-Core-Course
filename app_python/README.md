# DevOps Info Service

## Overview

DevOps Info Service is a web application that provides detailed information about itself and its runtime environment. This service reports system information, runtime statistics, and request metadata through a RESTful API.

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
```bash
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

Run the application with default settings:
```bash
python app.py
```

The service will start on `http://0.0.0.0:5000` by default.

### Custom Configuration

Configure the application using environment variables:

```bash
PORT=8080 python app.py
```

```bash
HOST=127.0.0.1 PORT=3000 python app.py
```

```bash
DEBUG=true python app.py
```

## API Endpoints

### GET /

Returns comprehensive service and system information.

**Response:**
```json
{
  "service": {
    "name": "devops-info-service",
    "version": "1.0.0",
    "description": "DevOps course info service",
    "framework": "Flask"
  },
  "system": {
    "hostname": "my-laptop",
    "platform": "Linux",
    "platform_version": "Ubuntu 24.04",
    "architecture": "x86_64",
    "cpu_count": 8,
    "python_version": "3.13.1"
  },
  "runtime": {
    "uptime_seconds": 3600,
    "uptime_human": "1 hour, 0 minutes",
    "current_time": "2026-01-07T14:30:00.000Z",
    "timezone": "UTC"
  },
  "request": {
    "client_ip": "127.0.0.1",
    "user_agent": "curl/7.81.0",
    "method": "GET",
    "path": "/"
  },
  "endpoints": [
    {"path": "/", "method": "GET", "description": "Service information"},
    {"path": "/health", "method": "GET", "description": "Health check"}
  ]
}
```

### GET /health

Returns health status and uptime information.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T14:30:00.000Z",
  "uptime_seconds": 3600
}
```

**Example:**
```bash
curl http://localhost:5000/health
```

## Testing

Test the endpoints using curl:

```bash
curl http://localhost:5000/
```

```bash
curl http://localhost:5000/health
```

For formatted JSON output, use `jq`:

```bash
curl http://localhost:5000/ | jq
```

## Docker

### Building the image locally

From the `app_python/` directory, build the image:

```bash
docker build -t devops-info-service .
```

Or with a tag including your Docker Hub username:

```bash
docker build -t iamkoldun/devops-info-service:latest .
```

### Running a container

Run the container with port mapping (host:container):

```bash
docker run -p 5000:5000 devops-info-service
```

Or with custom port on host:

```bash
docker run -p 8080:5000 devops-info-service
```

Override environment variables if needed:

```bash
docker run -p 5000:5000 -e PORT=5000 -e HOST=0.0.0.0 devops-info-service
```

### Pulling from Docker Hub

If the image is published to Docker Hub:

```bash
docker pull iamkoldun/devops-info-service:latest
docker run -p 5000:5000 iamkoldun/devops-info-service:latest
```
