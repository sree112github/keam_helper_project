package database

import (
	"context"
	"fmt"
	"log"
	"net/url"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"keam-rank-finder/internal/config"
)

// Pool is the singleton database connection pool.
var Pool *pgxpool.Pool

// ConnectDB creates and configures a new pgxpool.Pool and pings the database to ensure connection.
func ConnectDB(cfg *config.Config) (*pgxpool.Pool, error) {
	// Build connection string. URL-encode the password to handle special characters.
	connStr := fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=%s",
		cfg.DBUser,
		url.QueryEscape(cfg.DBPassword),
		cfg.DBHost,
		cfg.DBPort,
		cfg.DBName,
		cfg.DBSSLMode,
	)

	poolConfig, err := pgxpool.ParseConfig(connStr)
	if err != nil {
		return nil, fmt.Errorf("unable to parse database config: %w", err)
	}

	// Supabase Free Tier configuration limits
	poolConfig.MaxConns = 5
	poolConfig.MinConns = 1
	poolConfig.MaxConnLifetime = 1 * time.Hour
	poolConfig.MaxConnIdleTime = 30 * time.Minute
	poolConfig.HealthCheckPeriod = 1 * time.Minute

	// Establish connection pool with retries to handle cold starts (e.g. Supabase wake-up)
	var pool *pgxpool.Pool
	maxAttempts := 10
	var lastErr error

	for attempt := 1; attempt <= maxAttempts; attempt++ {
		if attempt > 1 {
			log.Printf("Retrying database connection (attempt %d/%d) in 5 seconds...", attempt, maxAttempts)
			time.Sleep(5 * time.Second)
		}

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		
		var err error
		pool, err = pgxpool.NewWithConfig(ctx, poolConfig)
		if err != nil {
			lastErr = fmt.Errorf("unable to create connection pool: %w", err)
			cancel()
			log.Printf("Database pool creation failed on attempt %d: %v", attempt, err)
			continue
		}

		// Ping database to verify connection
		if err := pool.Ping(ctx); err != nil {
			pool.Close()
			lastErr = fmt.Errorf("unable to ping database: %w", err)
			cancel()
			log.Printf("Database ping failed on attempt %d: %v", attempt, err)
			continue
		}

		cancel()
		log.Printf("Successfully connected to database %s at %s:%s on attempt %d\n", cfg.DBName, cfg.DBHost, cfg.DBPort, attempt)
		Pool = pool
		return pool, nil
	}

	return nil, fmt.Errorf("database connection failed after %d attempts: %w", maxAttempts, lastErr)
}
