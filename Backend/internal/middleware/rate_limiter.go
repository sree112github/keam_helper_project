package middleware

import (
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"keam-rank-finder/internal/common"
)

type clientLimiter struct {
	lastSeen time.Time
	count    int
}

var (
	clients = make(map[string]*clientLimiter)
	mu      sync.Mutex
)

// StartCleanupRateLimiter spawns a background goroutine to periodically clean up expired rate limiter entries
// to prevent memory consumption from growing indefinitely over time.
func StartCleanupRateLimiter(interval, maxAge time.Duration) {
	ticker := time.NewTicker(interval)
	go func() {
		for range ticker.C {
			mu.Lock()
			now := time.Now()
			deleted := 0
			for ip, client := range clients {
				if now.Sub(client.lastSeen) > maxAge {
					delete(clients, ip)
					deleted++
				}
			}
			mu.Unlock()
			if deleted > 0 {
				log.Printf("[RateLimiter] Cleaned up %d inactive client IPs to free memory.\n", deleted)
			}
		}
	}()
}

// RateLimiter returns a Gin middleware that limits requests from any single IP to a maximum count per minute.
func RateLimiter(requestsPerMinute int) gin.HandlerFunc {
	return func(c *gin.Context) {
		ip := c.ClientIP()
		now := time.Now()

		mu.Lock()
		client, exists := clients[ip]
		if !exists {
			clients[ip] = &clientLimiter{
				lastSeen: now,
				count:    1,
			}
			mu.Unlock()
			c.Next()
			return
		}

		// Reset count if more than a minute has passed since the first request of this window
		if now.Sub(client.lastSeen) > time.Minute {
			client.lastSeen = now
			client.count = 1
			mu.Unlock()
			c.Next()
			return
		}

		client.count++
		count := client.count
		client.lastSeen = now // update last seen timestamp
		mu.Unlock()

		if count > requestsPerMinute {
			log.Printf("[RateLimiter] IP %s blocked. Request count: %d (max: %d/min)\n", ip, count, requestsPerMinute)
			common.SendFailure(c, http.StatusTooManyRequests, "Too many requests. Please try again in a minute.")
			c.Abort()
			return
		}

		c.Next()
	}
}
