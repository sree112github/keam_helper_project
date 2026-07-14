package main

import (
	"context"
	"fmt"
	"log"

	"keam-rank-finder/internal/config"
	"keam-rank-finder/internal/database"
)

func main() {
	log.Println("Starting database verification...")
	cfg := config.LoadConfig()
	dbPool, err := database.ConnectDB(cfg)
	if err != nil {
		log.Fatalf("Database connection failed: %v\n", err)
	}
	defer dbPool.Close()

	var count int
	err = dbPool.QueryRow(context.Background(), "SELECT COUNT(*) FROM keam_cutoff_ranks WHERE year = 2026").Scan(&count)
	if err != nil {
		log.Fatalf("Query failed: %v\n", err)
	}

	fmt.Printf("Database verification complete: Found %d records for year = 2026.\n", count)
}
