package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/jackc/pgx/v5"
	"keam-rank-finder/internal/config"
	"keam-rank-finder/internal/database"
)

type JSONRankEntry struct {
	Year        int            `json:"year"`
	Round       string         `json:"round"`
	Course      string         `json:"course"`
	CollegeCode string         `json:"college_code"`
	Name        string         `json:"name"`
	Type        string         `json:"type"`
	Ranks       map[string]int `json:"ranks"`
}

type ImportSummary struct {
	Inserted int
	Skipped  int
	Failed   int
}

func main() {
	log.Println("Starting Database Importer for 2026 rank allotment...")

	// 1. Load Configuration
	cfg := config.LoadConfig()

	// 2. Establish Database Connection
	dbPool, err := database.ConnectDB(cfg)
	if err != nil {
		log.Fatalf("Database connection failed: %v\n", err)
	}
	defer dbPool.Close()

	ctx := context.Background()

	// 3. Read JSON data
	jsonFilePath := "rank_info_2026_first_allotment.json"
	byteValue, err := os.ReadFile(jsonFilePath)
	if err != nil {
		log.Fatalf("Error reading JSON file %s: %v\n", jsonFilePath, err)
	}

	var entries []JSONRankEntry
	if err := json.Unmarshal(byteValue, &entries); err != nil {
		log.Fatalf("Error parsing JSON file: %v\n", err)
	}

	log.Printf("Found %d entries in JSON file.\n", len(entries))

	// 4. Validate and Filter entries
	var validEntries []JSONRankEntry
	var summary ImportSummary

	for _, entry := range entries {
		if entry.Year == 0 || entry.Round == "" || entry.Course == "" || entry.CollegeCode == "" || entry.Name == "" || len(entry.Ranks) == 0 {
			summary.Failed++
			log.Printf("Warning: Skipped invalid record: %+v\n", entry)
			continue
		}
		validEntries = append(validEntries, entry)
	}

	if len(validEntries) == 0 {
		log.Println("No valid entries found to import.")
		return
	}

	log.Printf("Valid entries to insert: %d. Proceeding with batch insertion...\n", len(validEntries))

	// 5. Run batch insertion in a transaction
	tx, err := dbPool.Begin(ctx)
	if err != nil {
		log.Fatalf("Failed to begin transaction: %v\n", err)
	}
	defer tx.Rollback(ctx)

	chunkSize := 100
	for i := 0; i < len(validEntries); i += chunkSize {
		end := i + chunkSize
		if end > len(validEntries) {
			end = len(validEntries)
		}
		chunk := validEntries[i:end]

		err = insertChunk(ctx, tx, chunk, &summary)
		if err != nil {
			log.Fatalf("Failed inserting chunk starting at index %d: %v\n", i, err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		log.Fatalf("Failed to commit transaction: %v\n", err)
	}

	log.Printf("Import Completed Successfully!\n")
	log.Printf("Summary - Inserted: %d, Skipped (Duplicates): %d, Failed: %d\n", summary.Inserted, summary.Skipped, summary.Failed)
}

func insertChunk(ctx context.Context, tx pgx.Tx, chunk []JSONRankEntry, summary *ImportSummary) error {
	if len(chunk) == 0 {
		return nil
	}

	var valueStrings []string
	var valueArgs []interface{}
	paramIndex := 1

	for _, entry := range chunk {
		ranksJSON, err := json.Marshal(entry.Ranks)
		if err != nil {
			summary.Failed++
			log.Printf("Error marshalling ranks for %s-%s: %v\n", entry.CollegeCode, entry.Course, err)
			continue
		}

		collType := "G"
		if entry.Type != "" {
			collType = string(entry.Type[0])
		}

		valueStrings = append(valueStrings, fmt.Sprintf(
			"($%d, $%d, $%d, $%d, $%d, $%d, $%d)",
			paramIndex, paramIndex+1, paramIndex+2, paramIndex+3, paramIndex+4, paramIndex+5, paramIndex+6,
		))
		valueArgs = append(valueArgs,
			entry.Year,
			entry.Round,
			entry.Course,
			entry.CollegeCode,
			entry.Name,
			collType,
			ranksJSON,
		)
		paramIndex += 7
	}

	if len(valueStrings) == 0 {
		return nil
	}

	query := fmt.Sprintf(
		"INSERT INTO keam_cutoff_ranks (year, round, course, college_code, college_name, college_type, ranks) VALUES %s ON CONFLICT (year, round, course, college_code) DO NOTHING RETURNING id",
		strings.Join(valueStrings, ", "),
	)

	rows, err := tx.Query(ctx, query, valueArgs...)
	if err != nil {
		summary.Failed += len(chunk)
		return fmt.Errorf("chunk insert query failed: %w", err)
	}
	defer rows.Close()

	insertedCount := 0
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err == nil {
			insertedCount++
		}
	}

	summary.Inserted += insertedCount
	summary.Skipped += (len(chunk) - insertedCount)

	return nil
}
