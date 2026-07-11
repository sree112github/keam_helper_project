package main

import (
	"log"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"keam-rank-finder/internal/config"
	"keam-rank-finder/internal/database"
	"keam-rank-finder/internal/middleware"
	"keam-rank-finder/internal/rank"
)

// CORSMiddleware configures standard CORS headers for development/production.
func CORSMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

// RequestLogger logs basic details about each incoming HTTP request, including status and response time (latency) with ANSI colors.
func RequestLogger() gin.HandlerFunc {
	return func(c *gin.Context) {
		t := time.Now()
		c.Next()
		latency := time.Since(t)

		status := c.Writer.Status()
		statusColor := "\033[32m" // Green
		if status >= 400 {
			statusColor = "\033[31m" // Red
		} else if status >= 300 {
			statusColor = "\033[33m" // Yellow
		}

		method := c.Request.Method
		methodColor := "\033[34m" // Blue (GET, etc.)
		if method == "POST" {
			methodColor = "\033[36m" // Cyan (POST)
		}

		log.Printf("[Request] %s%s\033[0m %s | Status: %s%d\033[0m | Latency: %v | IP: %s\n",
			methodColor, method,
			c.Request.URL.Path,
			statusColor, status,
			latency,
			c.ClientIP(),
		)
	}
}

func main() {
	log.Println("Starting KEAM Last Rank Finder server...")

	// 1. Load Configuration
	cfg := config.LoadConfig()
	log.Printf("Application Port: %s | AI Model Config: %s\n", cfg.Port, cfg.AModel)

	// 2. Establish Database Connection
	dbPool, err := database.ConnectDB(cfg)
	if err != nil {
		log.Fatalf("Database connection failed: %v\n", err)
	}
	defer dbPool.Close()

	// Start IP rate limiter periodic cleanup (runs every 10 seconds, checks for max 1 minute age) to prevent memory growth
	middleware.StartCleanupRateLimiter(10*time.Second, 1*time.Minute)

	// 3. Setup router
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(RequestLogger())
	r.Use(CORSMiddleware())
	r.Use(middleware.RateLimiter(60)) // Limit to 60 requests per minute per IP

	// 4. Initialize layers
	repo := rank.NewRepository(dbPool)
	service := rank.NewService(repo, dbPool)
	controller := rank.NewController(service)

	// 5. Register Routes
	rank.RegisterRoutes(r, controller)

	// 6. Serve static files from Frontend directory
	frontendDir := "../Frontend"
	if _, err := os.Stat(frontendDir); err != nil {
		// Fallback to local subdirectory check
		frontendDir = "Frontend"
	}

	if _, err := os.Stat(frontendDir); err == nil {
		r.StaticFile("/", frontendDir+"/index.html")
		r.StaticFile("/style.css", frontendDir+"/style.css")
		r.StaticFile("/script.js", frontendDir+"/script.js")
		log.Printf("Successfully mounted static frontend files from: %s\n", frontendDir)
	} else {
		log.Println("Warning: Frontend static directory not found, API-only mode active")
	}

	// 7. Start server
	log.Printf("Listening and serving HTTP on :%s\n", cfg.Port)
	if err := r.Run(":" + cfg.Port); err != nil {
		log.Fatalf("Server failed to start: %v\n", err)
	}
}
