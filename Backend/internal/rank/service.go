package rank

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Service encapsulates the business logic for the rank module.
type Service struct {
	repo *Repository
	db   *pgxpool.Pool
}

// NewService creates a new instance of Service.
func NewService(repo *Repository, db *pgxpool.Pool) *Service {
	return &Service{
		repo: repo,
		db:   db,
	}
}

// GetYears retrieves distinct years.
func (s *Service) GetYears(ctx context.Context) ([]int, error) {
	return s.repo.GetYears(ctx)
}

// GetRounds retrieves distinct rounds for a specific year.
func (s *Service) GetRounds(ctx context.Context, year int) ([]string, error) {
	return s.repo.GetRounds(ctx, year)
}

// GetColleges retrieves distinct colleges for a year and round, optionally filtered by course.
func (s *Service) GetColleges(ctx context.Context, year int, round string, course string) ([]CollegeDTO, error) {
	return s.repo.GetColleges(ctx, year, round, course)
}

// GetCourses retrieves distinct courses for a year and round, optionally filtered by college.
func (s *Service) GetCourses(ctx context.Context, year int, round string, collegeCode string) ([]string, error) {
	return s.repo.GetCourses(ctx, year, round, collegeCode)
}

// GetRank looks up cutoff rank for specified selection.
func (s *Service) GetRank(ctx context.Context, year int, round string, collegeCode string, course string, category string) (*RankResponse, error) {
	return s.repo.GetRank(ctx, year, round, collegeCode, course, category)
}

// GetCategories dynamically loads category listings from category_info.json file.
func (s *Service) GetCategories(ctx context.Context) ([]CategoryDTO, error) {
	// Try reading category_info.json from multiple possible relative paths
	paths := []string{
		"category_info.json",
		"data/category_info.json",
		"Backend/category_info.json",
		"Backend/data/category_info.json",
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
		return nil, fmt.Errorf("unable to open category_info.json in any of %v: %w", paths, err)
	}
	defer file.Close()

	byteValue, err := io.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("error reading category_info.json: %w", err)
	}

	var data struct {
		Category []CategoryDTO `json:"Category"`
	}

	if err := json.Unmarshal(byteValue, &data); err != nil {
		return nil, fmt.Errorf("error parsing category_info.json: %w", err)
	}

	return data.Category, nil
}

// ImportData triggers the JSON file import for a selected year.
func (s *Service) ImportData(ctx context.Context, year int) (ImportSummary, error) {
	return ImportRanks(ctx, s.db, year)
}
