package main

import (
	"fmt"
	"net/http"
	"os"
	"runtime"
	"time"

	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
)

var startTime = time.Now()

type Service struct {
	Name        string `json:"name"`
	Version     string `json:"version"`
	Description string `json:"description"`
	Framework   string `json:"framework"`
}

type System struct {
	Hostname        string `json:"hostname"`
	Platform        string `json:"platform"`
	PlatformVersion string `json:"platform_version"`
	Architecture    string `json:"architecture"`
	CPUCount        int    `json:"cpu_count"`
	GoVersion       string `json:"go_version"`
}

type Runtime struct {
	UptimeSeconds int    `json:"uptime_seconds"`
	UptimeHuman   string `json:"uptime_human"`
	CurrentTime   string `json:"current_time"`
	Timezone      string `json:"timezone"`
}

type Request struct {
	ClientIP  string `json:"client_ip"`
	UserAgent string `json:"user_agent"`
	Method    string `json:"method"`
	Path      string `json:"path"`
}

type Endpoint struct {
	Path        string `json:"path"`
	Method      string `json:"method"`
	Description string `json:"description"`
}

type ServiceInfo struct {
	Service   Service    `json:"service"`
	System    System     `json:"system"`
	Runtime   Runtime    `json:"runtime"`
	Request   Request    `json:"request"`
	Endpoints []Endpoint `json:"endpoints"`
}

type HealthResponse struct {
	Status       string `json:"status"`
	Timestamp    string `json:"timestamp"`
	UptimeSeconds int  `json:"uptime_seconds"`
}

func getUptime() (int, string) {
	delta := time.Since(startTime)
	seconds := int(delta.Seconds())
	hours := seconds / 3600
	minutes := (seconds % 3600) / 60

	var parts []string
	if hours > 0 {
		if hours == 1 {
			parts = append(parts, fmt.Sprintf("%d hour", hours))
		} else {
			parts = append(parts, fmt.Sprintf("%d hours", hours))
		}
	}
	if minutes == 1 {
		parts = append(parts, fmt.Sprintf("%d minute", minutes))
	} else {
		parts = append(parts, fmt.Sprintf("%d minutes", minutes))
	}

	human := parts[0]
	if len(parts) > 1 {
		human = parts[0] + ", " + parts[1]
	}

	return seconds, human
}

func getSystemInfo() System {
	hostname, _ := os.Hostname()
	return System{
		Hostname:        hostname,
		Platform:        runtime.GOOS,
		PlatformVersion: runtime.GOOS + " " + runtime.GOARCH,
		Architecture:    runtime.GOARCH,
		CPUCount:        runtime.NumCPU(),
		GoVersion:       runtime.Version(),
	}
}

func mainHandler(c echo.Context) error {
	uptimeSeconds, uptimeHuman := getUptime()
	systemInfo := getSystemInfo()

	clientIP := c.RealIP()
	if clientIP == "" {
		clientIP = c.Request().RemoteAddr
	}

	info := ServiceInfo{
		Service: Service{
			Name:        "devops-info-service",
			Version:     "1.0.0",
			Description: "DevOps course info service",
			Framework:   "Go (Echo)",
		},
		System: systemInfo,
		Runtime: Runtime{
			UptimeSeconds: uptimeSeconds,
			UptimeHuman:   uptimeHuman,
			CurrentTime:   time.Now().UTC().Format(time.RFC3339),
			Timezone:      "UTC",
		},
		Request: Request{
			ClientIP:  clientIP,
			UserAgent: c.Request().UserAgent(),
			Method:    c.Request().Method,
			Path:      c.Request().URL.Path,
		},
		Endpoints: []Endpoint{
			{Path: "/", Method: "GET", Description: "Service information"},
			{Path: "/health", Method: "GET", Description: "Health check"},
		},
	}

	return c.JSON(http.StatusOK, info)
}

func healthHandler(c echo.Context) error {
	uptimeSeconds, _ := getUptime()
	response := HealthResponse{
		Status:       "healthy",
		Timestamp:    time.Now().UTC().Format(time.RFC3339),
		UptimeSeconds: uptimeSeconds,
	}

	return c.JSON(http.StatusOK, response)
}

func main() {
	e := echo.New()

	e.Use(middleware.Logger())
	e.Use(middleware.Recover())

	e.GET("/", mainHandler)
	e.GET("/health", healthHandler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	host := os.Getenv("HOST")
	if host == "" {
		host = "0.0.0.0"
	}

	addr := fmt.Sprintf("%s:%s", host, port)
	fmt.Printf("Starting DevOps Info Service on %s\n", addr)
	e.Logger.Fatal(e.Start(addr))
}
