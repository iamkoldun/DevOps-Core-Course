# Lab 1 Submission: DevOps Info Service

## Framework Selection

### Choice: Flask

I selected Flask as the web framework for this project.

### Justification

Flask was chosen because:
1. **Simplicity**: The service requires only two endpoints, making Flask's minimal approach ideal
2. **Learning curve**: Flask's straightforward request/response model is easier for beginners
3. **Flexibility**: No enforced structure allows for clean, focused code
4. **Lightweight**: Minimal dependencies reduce deployment complexity
5. **Industry standard**: Widely used in production environments for microservices

For this DevOps course foundation, Flask provides the right balance of simplicity and functionality without unnecessary complexity.

## Best Practices Applied

### 1. Clean Code Organization

- Clear function names (`get_uptime`, `get_system_info`)
- Logical import grouping (standard library, third-party, local)
- Minimal comments (only where logic needs explanation)
- PEP 8 compliant formatting

### 2. Error Handling

Implemented custom error handlers for 404 and 500 errors:
- Returns JSON responses consistent with API format
- Logs internal errors for debugging
- Provides meaningful error messages

### 3. Logging

Configured structured logging:
- INFO level for normal operations
- DEBUG level for detailed request tracking
- ERROR level with exception details for failures
- Consistent log format with timestamps

### 4. Configuration Management

Environment variables for all configuration:
- `HOST`, `PORT`, `DEBUG` configurable
- Sensible defaults for development
- Easy to override for different environments

### 5. Dependencies Management

- Pinned exact version in `requirements.txt` for reproducibility
- Minimal dependencies (only Flask)
- Easy to recreate environment

### 6. Git Ignore

Comprehensive `.gitignore` covering:
- Python artifacts (`__pycache__`, `*.pyc`)
- Virtual environments
- IDE files
- OS-specific files

## API Documentation

### Endpoint: GET /

**Description:** Returns comprehensive service and system information.

**Request:**
```bash
curl http://localhost:5000/
```

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
    "hostname": "Alexanders-MacBook-Pro.local",
    "platform": "darwin",
    "platform_version": "darwin arm64",
    "architecture": "arm64",
    "cpu_count": 8,
    "go_version": "go1.24.10"
  },
  "runtime": {
    "uptime_seconds": 21,
    "uptime_human": "0 minutes",
    "current_time": "2026-01-28T15:48:27Z",
    "timezone": "UTC"
  },
  "request": {
    "client_ip": "::1",
    "user_agent": "yaak",
    "method": "GET",
    "path": "/"
  },
  "endpoints": [
    {
      "path": "/",
      "method": "GET",
      "description": "Service information"
    },
    {
      "path": "/health",
      "method": "GET",
      "description": "Health check"
    }
  ]
}
```

### Endpoint: GET /health

**Description:** Returns health status and uptime.

**Request:**
```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-28T15:54:43.409877+00:00",
  "uptime_seconds": 17
}
```

### Testing Commands

**Basic test:**
```bash
curl http://localhost:5000/
```

**Formatted output:**
```bash
curl http://localhost:5000/ | jq
```

**Health check:**
```bash
curl http://localhost:5000/health | jq
```

**Custom port:**
```bash
PORT=8080 python app.py
curl http://localhost:8080/
```

## Testing Evidence

### Screenshots

Screenshots demonstrating the working endpoints are located in `docs/screenshots/`:
- `01-main-endpoint.png` - Main endpoint showing complete JSON response
- `02-health-check.png` - Health check endpoint response

### Terminal Output

**Starting the service:**
```
2026-01-28 18:52:27,016 - __main__ - INFO - Starting DevOps Info Service on 0.0.0.0:8080
 * Serving Flask app 'app'
 * Debug mode: off
2026-01-28 18:52:27,026 - werkzeug - INFO - WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8080
 * Running on http://10.8.1.1:8080
2026-01-28 18:52:27,026 - werkzeug - INFO - Press CTRL+C to quit
```

**Main endpoint test:**
```bash
$ curl http://localhost:5000/ | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   679  100   679    0     0  87919      0 --:--:-- --:--:-- --:--:-- 97000
{
  "endpoints": [
    {
      "description": "Service information",
      "method": "GET",
      "path": "/"
    },
    {
      "description": "Health check",
      "method": "GET",
      "path": "/health"
    }
  ],
  "request": {
    "client_ip": "127.0.0.1",
    "method": "GET",
    "path": "/",
    "user_agent": "curl/8.7.1"
  },
  "runtime": {
    "current_time": "2026-01-28T15:55:13.388759+00:00",
    "timezone": "UTC",
    "uptime_human": "0 hours, 0 minutes",
    "uptime_seconds": 47
  },
  "service": {
    "description": "DevOps course info service",
    "framework": "Flask",
    "name": "devops-info-service",
    "version": "1.0.0"
  },
  "system": {
    "architecture": "arm64",
    "cpu_count": 8,
    "hostname": "Alexanders-MacBook-Pro.local",
    "platform": "Darwin",
    "platform_version": "macOS-26.2-arm64-arm-64bit-Mach-O",
    "python_version": "3.13.2"
  }
}
```

**Health check test:**
```bash
$ curl http://localhost:5000/health | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100    88  100    88    0     0  11396      0 --:--:-- --:--:-- --:--:-- 12571
{
  "status": "healthy",
  "timestamp": "2026-01-28T15:55:37.356602+00:00",
  "uptime_seconds": 71
}
```

## Challenges & Solutions

### Challenge 1: Uptime Calculation

**Problem:** Calculating human-readable uptime format with proper pluralization.

**Solution:** Created `get_uptime()` function that calculates hours and minutes, then formats with conditional pluralization for natural language output.

### Challenge 2: Error Handling Consistency

**Problem:** Ensuring error responses match the JSON API format.

**Solution:** Implemented custom error handlers that return JSON responses consistent with successful endpoint responses, maintaining API contract.

### Challenge 3: Timezone Handling

**Problem:** Ensuring consistent UTC timezone across all timestamps.

**Solution:** Used `timezone.utc` consistently and stored `START_TIME` in UTC to ensure all runtime calculations are timezone-aware.

## GitHub Community

Starring repositories in open source serves multiple purposes: it helps bookmark useful projects for future reference, signals appreciation to maintainers, and contributes to project visibility. High star counts help projects gain traction and attract contributors, while also serving as a quality indicator for others discovering the project.

Following developers on GitHub facilitates professional networking and learning. It allows you to discover new projects through their activity, learn from experienced developers' code and problem-solving approaches, and build connections that extend beyond the classroom. In team projects, following classmates helps track their work and build a supportive learning community, while following professors and TAs provides insights into industry practices and emerging tools.
