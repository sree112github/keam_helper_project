package rank

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"

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

// GetCoursesByYear retrieves distinct courses for a specific year.
func (s *Service) GetCoursesByYear(ctx context.Context, year int) ([]string, error) {
	return s.repo.GetCoursesByYear(ctx, year)
}

// PredictColleges looks up colleges where the rank is eligible.
func (s *Service) PredictColleges(ctx context.Context, year int, round string, course string, category string, rank int) ([]PredictionDTO, error) {
	return s.repo.PredictColleges(ctx, year, round, course, category, rank)
}

// GetCategories dynamically loads category listings from category_info.json file.
func (s *Service) GetCategories(ctx context.Context) ([]CategoryDTO, error) {
	// Try reading category_info.json from multiple possible relative paths
	paths := []string{
		"category_info.json",
		"data/category_info.json",
		"Backend/category_info.json",
		"Backend/data/category_info.json",
		"../category_info.json",
		"../../category_info.json",
		"../../../category_info.json",
	}

	var file *os.File
	var err error
	var openedPath string
	for _, p := range paths {
		file, err = os.Open(p)
		if err == nil {
			openedPath = p
			break
		}
	}

	// Try relative to the executable path
	if err != nil {
		if execPath, execErr := os.Executable(); execErr == nil {
			execDir := filepath.Dir(execPath)
			dir := execDir
			for i := 0; i < 4; i++ {
				checkPaths := []string{
					filepath.Join(dir, "category_info.json"),
					filepath.Join(dir, "data", "category_info.json"),
					filepath.Join(dir, "Backend", "category_info.json"),
					filepath.Join(dir, "Backend", "data", "category_info.json"),
				}
				for _, cp := range checkPaths {
					file, err = os.Open(cp)
					if err == nil {
						openedPath = cp
						break
					}
				}
				if err == nil {
					break
				}
				parent := filepath.Dir(dir)
				if parent == dir {
					break
				}
				dir = parent
			}
		}
	}

	// Try relative to current working directory climbing up
	if err != nil {
		if cwd, cwdErr := os.Getwd(); cwdErr == nil {
			dir := cwd
			for i := 0; i < 4; i++ {
				checkPaths := []string{
					filepath.Join(dir, "category_info.json"),
					filepath.Join(dir, "data", "category_info.json"),
					filepath.Join(dir, "Backend", "category_info.json"),
					filepath.Join(dir, "Backend", "data", "category_info.json"),
				}
				for _, cp := range checkPaths {
					file, err = os.Open(cp)
					if err == nil {
						openedPath = cp
						break
					}
				}
				if err == nil {
					break
				}
				parent := filepath.Dir(dir)
				if parent == dir {
					break
				}
				dir = parent
			}
		}
	}

	if err != nil {
		return nil, fmt.Errorf("unable to open category_info.json in any checked paths: %w", err)
	}
	defer file.Close()

	byteValue, err := io.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("error reading category_info.json (from %s): %w", openedPath, err)
	}

	var data struct {
		Category []CategoryDTO `json:"Category"`
	}

	if err := json.Unmarshal(byteValue, &data); err != nil {
		return nil, fmt.Errorf("error parsing category_info.json (from %s): %w", openedPath, err)
	}

	return data.Category, nil
}

// ImportData triggers the JSON file import for a selected year.
func (s *Service) ImportData(ctx context.Context, year int) (ImportSummary, error) {
	return ImportRanks(ctx, s.db, year)
}
