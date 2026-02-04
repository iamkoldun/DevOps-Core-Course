# DevOps Info Service (Go)

## Overview

DevOps Info Service implemented in Go - a compiled language version providing the same functionality as the Python implementation. This service reports system information, runtime statistics, and request metadata through a RESTful API.

## Prerequisites

- Go 1.21 or higher
- Git (for dependency management)

## Installation

1. Clone or navigate to the project directory:
```bash
cd app_go
```

2. Initialize Go modules (if needed):
```bash
go mod init devops-info-service
```

3. Download dependencies:
```bash
go mod download
```

Or let Go download them automatically when building:
```bash
go build -o devops-info-service main.go
```

## Building

### Build the application:
```bash
go build -o devops-info-service main.go
```

### Build for different platforms:
```bash
GOOS=linux GOARCH=amd64 go build -o devops-info-service-linux main.go
GOOS=darwin GOARCH=amd64 go build -o devops-info-service-macos main.go
GOOS=windows GOARCH=amd64 go build -o devops-info-service.exe main.go
```

## Running the Application

### Run directly (development):
```bash
go run main.go
```

### Run compiled binary:
```bash
./devops-info-service
```

The service will start on `http://0.0.0.0:8080` by default.

### Custom Configuration

Configure using environment variables:

```bash
PORT=5000 go run main.go
```

```bash
HOST=127.0.0.1 PORT=3000 go run main.go
```

```bash
HOST=0.0.0.0 PORT=8080 ./devops-info-service
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
    "framework": "Go (Echo)"
  },
  "system": {
    "hostname": "my-laptop",
    "platform": "linux",
    "platform_version": "linux amd64",
    "architecture": "amd64",
    "cpu_count": 8,
    "go_version": "go1.21.5"
  },
  "runtime": {
    "uptime_seconds": 3600,
    "uptime_human": "1 hours, 0 minutes",
    "current_time": "2026-01-28T12:30:00Z",
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
  "timestamp": "2026-01-28T12:30:00Z",
  "uptime_seconds": 3600
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Host address to bind to |
| `PORT` | `8080` | Port number to listen on |

## Binary Size Comparison

- **Python**: Requires Python runtime (~50-100MB) + dependencies
- **Go**: Single compiled binary (~5-10MB), no runtime needed

## Testing

Test the endpoints using curl:

```bash
curl http://localhost:8080/
```

```bash
curl http://localhost:8080/health
```

For formatted JSON output:

```bash
curl http://localhost:8080/ | jq
```

## Docker (Multi-Stage Build)

### Building the image

From the `app_go/` directory:

```bash
docker build -t devops-info-service-go .
```

### Running a container

```bash
docker run -p 8080:8080 devops-info-service-go
```

Test endpoints:

```bash
curl http://localhost:8080/
curl http://localhost:8080/health
```
