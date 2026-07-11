package config

import (
	"log"
	"os"

	"github.com/joho/godotenv"
)

// Config holds the application configuration parameters.
type Config struct {
	Port       string
	DBHost     string
	DBPort     string
	DBUser     string
	DBPassword string
	DBName     string
	DBSSLMode  string
	AModel     string
}

// LoadConfig initializes the configuration from .env and environment variables.
func LoadConfig() *Config {
	// Only load .env file if it exists (avoids errors when hosted on Render)
	if _, err := os.Stat(".env"); err == nil {
		if err := godotenv.Load(); err != nil {
			log.Println("Note: Error loading .env file:", err)
		}
	}

	cfg := &Config{
		Port:      os.Getenv("PORT"),
		AModel:    os.Getenv("AMODEL"),
		DBSSLMode: os.Getenv("DB_SSLMODE"),
	}

	if cfg.Port == "" {
		cfg.Port = "8080"
	}
	if cfg.DBSSLMode == "" {
		cfg.DBSSLMode = "require"
	}
	if cfg.AModel == "" {
		cfg.AModel = "gpt-4.1"
	}

	// Read primary environment variables from the required .env.example spec
	dbHost := os.Getenv("DB_HOST")
	dbPort := os.Getenv("DB_PORT")
	dbUser := os.Getenv("DB_USER")
	dbPassword := os.Getenv("DB_PASSWORD")
	dbName := os.Getenv("DB_NAME")

	// If DB_HOST is empty, check for pre-existing .env layout
	if dbHost == "" {
		dbHost = os.Getenv("HOST")
		dbPort = os.Getenv("PORT") // In old .env, PORT is the DB port (5432)
		dbUser = os.Getenv("USER")
		dbPassword = os.Getenv("PASSWORD")
		dbName = os.Getenv("DATABASE")

		// If DB_HOST is empty and PORT is the DB port (5432), we must NOT bind the Go web server to 5432.
		// We'll set the server Port to "8080".
		if cfg.Port == dbPort {
			log.Printf("Configuration Warning: PORT env var is set to %q and DB_HOST is empty. Assuming legacy .env where PORT is the database port. Overriding web server port to \"8080\" to prevent conflicts.\n", dbPort)
			cfg.Port = "8080"
		}
	} else {
		log.Printf("Loaded database config using standard DB_HOST environment variables.\n")
	}

	cfg.DBHost = dbHost
	cfg.DBPort = dbPort
	cfg.DBUser = dbUser
	cfg.DBPassword = dbPassword
	cfg.DBName = dbName

	return cfg
}
