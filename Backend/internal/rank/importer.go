package rank

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// JSONRankEntry maps the JSON structure of a rank record in rank_info.json
type JSONRankEntry struct {
	Year        int            `json:"year"`
	Round       string         `json:"round"`
	Course      string         `json:"course"`
	CollegeCode string         `json:"college_code"`
	Name        string         `json:"name"`
	Type        string         `json:"type"`
	Ranks       map[string]int `json:"ranks"`
}

// ImportRanks parses rank_info.json, filters entries for the selected year,
// validates each row, and inserts them in batches within a transaction.
func ImportRanks(ctx context.Context, db *pgxpool.Pool, targetYear int) (ImportSummary, error) {
	var summary ImportSummary

	// Try reading rank_info.json from multiple possible relative paths
	paths := []string{
		"rank_info.json",
		"data/rank_info.json",
		"Backend/rank_info.json",
		"Backend/data/rank_info.json",
	}

	var file *os.File
	var err error
	for _, p := range paths {
		file, err = os.Open(p)
		if err == nil {
			break
		}
	}

	if err != nil {
		return summary, fmt.Errorf("unable to open rank_info.json in any of %v: %w", paths, err)
	}
	defer file.Close()

	byteValue, err := io.ReadAll(file)
	if err != nil {
		return summary, fmt.Errorf("error reading rank_info.json: %w", err)
	}

	var entries []JSONRankEntry
	if err := json.Unmarshal(byteValue, &entries); err != nil {
		return summary, fmt.Errorf("error parsing rank_info.json: %w", err)
	}

	// Filter and validate records matching the target year
	var validEntries []JSONRankEntry
	for _, entry := range entries {
		// Basic validation
		if entry.Year == 0 || entry.Round == "" || entry.Course == "" || entry.CollegeCode == "" || entry.Name == "" || len(entry.Ranks) == 0 {
			summary.Failed++
			continue
		}

		if entry.Year != targetYear {
			// Skip entries for other years silently
			continue
		}

		validEntries = append(validEntries, entry)
	}

	if len(validEntries) == 0 {
		log.Printf("Import completed: 0 records found to process for year %d\n", targetYear)
		return summary, nil
	}

	// Execute batch insert in transactions of chunk size
	tx, err := db.Begin(ctx)
	if err != nil {
		return summary, fmt.Errorf("failed to begin transaction: %w", err)
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
			return summary, fmt.Errorf("failed inserting chunk: %w", err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return summary, fmt.Errorf("failed to commit transaction: %w", err)
	}

	log.Printf("Import Summary for %d - Inserted: %d, Skipped: %d, Failed: %d\n",
		targetYear, summary.Inserted, summary.Skipped, summary.Failed)

	return summary, nil
}

// insertChunk dynamically builds an insert statement with parameters for a block of entries
// and executes it. It tracks how many rows were inserted or skipped using RETURNING id.
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
			continue
		}

		// Ensure college type fits in character(1)
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
	// The rest in the chunk were skipped due to ON CONFLICT
	summary.Skipped += (len(chunk) - insertedCount)

	return nil
}
