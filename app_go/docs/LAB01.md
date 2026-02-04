# Lab 1 Submission: DevOps Info Service (Go)

## Implementation Details

### Architecture

The Go implementation uses the **Echo** web framework, a lightweight and high-performance HTTP framework for Go. Echo provides a clean API similar to Flask/FastAPI while maintaining Go's performance characteristics. The application follows Go best practices with clear struct definitions and handler functions.

### Key Components

1. **Echo Framework**: Lightweight HTTP framework with middleware support
2. **Struct Definitions**: Type-safe data structures for JSON responses
3. **Handler Functions**: `mainHandler` and `healthHandler` for endpoints
4. **Middleware**: Built-in logging and recovery middleware
5. **System Information**: Uses `runtime` and `os` packages
6. **Uptime Tracking**: Global `startTime` variable tracks application lifetime

### Code Structure

```go
- Service, System, Runtime, Request, Endpoint structs
- getUptime() function for runtime calculation
- getSystemInfo() function for system details
- mainHandler() for GET / endpoint
- healthHandler() for GET /health endpoint
- main() function for server setup
```

### Implementation Highlights

**Uptime Calculation:**
```go
func getUptime() (int, string) {
    delta := time.Since(startTime)
    seconds := int(delta.Seconds())
    hours := seconds / 3600
    minutes := (seconds % 3600) / 60
    // Format human-readable string
}
```

**System Information:**
```go
func getSystemInfo() System {
    hostname, _ := os.Hostname()
    return System{
        Hostname:        hostname,
        Platform:        runtime.GOOS,
        Architecture:    runtime.GOARCH,
        CPUCount:        runtime.NumCPU(),
        GoVersion:       runtime.Version(),
    }
}
```

**Echo Handler:**
```go
func mainHandler(c echo.Context) error {
    // Build response
    return c.JSON(http.StatusOK, info)
}
```

**Middleware Setup:**
```go
e := echo.New()
e.Use(middleware.Logger())
e.Use(middleware.Recover())
```

## Build Process

### Compilation

```bash
go build -o devops-info-service main.go
```

**Output:**
- Single binary executable
- No external dependencies
- Ready to run

### Binary Size

- **Compiled binary**: ~5-10MB
- **Python equivalent**: Python runtime (~50-100MB) + dependencies

### Cross-Platform Build

```bash
GOOS=linux GOARCH=amd64 go build -o devops-info-service-linux main.go
GOOS=darwin GOARCH=amd64 go build -o devops-info-service-macos main.go
```

## Testing

### Build Verification

```bash
$ go build -o devops-info-service main.go
$ ls -lh devops-info-service
-rwxr-xr-x  1 user  staff   7.2M Jan 28 12:30 devops-info-service
```

### Running Tests

**Start server:**
```bash
$ ./devops-info-service
Starting DevOps Info Service on 0.0.0.0:8080
```

**Test main endpoint:**
```bash
$ curl http://localhost:8080/ | jq
{
  "service": {
    "name": "devops-info-service",
    "version": "1.0.0",
    "description": "DevOps course info service",
    "framework": "Go"
  },
  ...
}
```

**Test health endpoint:**
```bash
$ curl http://localhost:8080/health | jq
{
  "status": "healthy",
  "timestamp": "2026-01-28T12:30:00Z",
  "uptime_seconds": 45
}
```

## Comparison with Python Version

| Feature | Python | Go |
|---------|--------|-----|
| **Lines of Code** | ~105 | ~150 |
| **Dependencies** | Flask 3.1.0 | Echo v4.12.0 |
| **Startup Time** | ~200ms | ~10ms |
| **Memory Usage** | ~30MB | ~5MB |
| **Binary Size** | N/A | 7-10MB (with Echo) |
| **Deployment** | Source + venv | Single binary |

## Challenges & Solutions

### Challenge 1: Framework Selection

**Problem:** Choosing between standard library `net/http` and a framework like Echo.

**Solution:** Selected Echo framework for better developer experience, built-in middleware, and cleaner API while maintaining small binary size.

### Challenge 2: JSON Struct Tags

**Problem:** Go requires explicit JSON field names using struct tags.

**Solution:** Added `json:"field_name"` tags to all struct fields for proper JSON serialization.

### Challenge 3: Uptime Formatting

**Problem:** Formatting human-readable uptime with proper pluralization.

**Solution:** Used conditional formatting with `fmt.Sprintf` to handle singular/plural forms correctly.

### Challenge 4: Client IP Detection

**Problem:** Getting accurate client IP address, especially behind proxies.

**Solution:** Check `X-Forwarded-For` header first, fallback to `RemoteAddr`.

### Challenge 5: Time Formatting

**Problem:** Matching Python's ISO format exactly.

**Solution:** Used `time.RFC3339` format which produces ISO 8601 compatible timestamps.

## Advantages of Go + Echo Implementation

1. **Single Binary**: No runtime dependencies, easy deployment
2. **Fast Startup**: Compiles to native code, starts in milliseconds
3. **Low Memory**: Efficient memory usage compared to interpreted languages
4. **Cross-Platform**: Easy compilation for different operating systems
5. **Modern Framework**: Echo provides clean API and middleware support
6. **Built-in Features**: Logging and error recovery middleware included
7. **Production Ready**: Used by major DevOps tools (Docker, Kubernetes)
8. **Small Binary**: Even with Echo framework, binary remains ~7-10MB

## Screenshots

Screenshots demonstrating the Go implementation are located in `docs/screenshots/`:
- Build process and binary size
- Running the service
- Endpoint responses
- Comparison with Python version
