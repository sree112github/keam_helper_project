package rank

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository handles database queries for KEAM rank searches.
type Repository struct {
	db *pgxpool.Pool
}

// NewRepository creates a new instance of Repository.
func NewRepository(db *pgxpool.Pool) *Repository {
	return &Repository{db: db}
}

// GetYears retrieves distinct years present in the database.
func (r *Repository) GetYears(ctx context.Context) ([]int, error) {
	rows, err := r.db.Query(ctx, `
		SELECT DISTINCT year 
		FROM keam_cutoff_ranks 
		ORDER BY year DESC
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to query years: %w", err)
	}
	defer rows.Close()

	var years []int
	for rows.Next() {
		var year int
		if err := rows.Scan(&year); err != nil {
			return nil, fmt.Errorf("failed to scan year: %w", err)
		}
		years = append(years, year)
	}
	return years, nil
}

// GetRounds retrieves distinct rounds for a specific year.
func (r *Repository) GetRounds(ctx context.Context, year int) ([]string, error) {
	rows, err := r.db.Query(ctx, `
		SELECT DISTINCT round 
		FROM keam_cutoff_ranks 
		WHERE year = $1 
		ORDER BY round ASC
	`, year)
	if err != nil {
		return nil, fmt.Errorf("failed to query rounds: %w", err)
	}
	defer rows.Close()

	var rounds []string
	for rows.Next() {
		var round string
		if err := rows.Scan(&round); err != nil {
			return nil, fmt.Errorf("failed to scan round: %w", err)
		}
		rounds = append(rounds, round)
	}
	return rounds, nil
}

// GetColleges retrieves distinct college codes and names for a year and round, optionally filtered by course.
func (r *Repository) GetColleges(ctx context.Context, year int, round string, course string) ([]CollegeDTO, error) {
	var rows pgx.Rows
	var err error
	if course != "" {
		rows, err = r.db.Query(ctx, `
			SELECT DISTINCT college_code, college_name 
			FROM keam_cutoff_ranks 
			WHERE year = $1 AND round = $2 AND course = $3 
			ORDER BY college_name ASC
		`, year, round, course)
	} else {
		rows, err = r.db.Query(ctx, `
			SELECT DISTINCT college_code, college_name 
			FROM keam_cutoff_ranks 
			WHERE year = $1 AND round = $2 
			ORDER BY college_name ASC
		`, year, round)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to query colleges: %w", err)
	}
	defer rows.Close()

	var colleges []CollegeDTO
	for rows.Next() {
		var c CollegeDTO
		if err := rows.Scan(&c.CollegeCode, &c.CollegeName); err != nil {
			return nil, fmt.Errorf("failed to scan college: %w", err)
		}
		colleges = append(colleges, c)
	}
	return colleges, nil
}

// GetCourses retrieves distinct courses available for a selected year and round, optionally filtered by college.
func (r *Repository) GetCourses(ctx context.Context, year int, round string, collegeCode string) ([]string, error) {
	var rows pgx.Rows
	var err error
	if collegeCode != "" {
		rows, err = r.db.Query(ctx, `
			SELECT DISTINCT course 
			FROM keam_cutoff_ranks 
			WHERE year = $1 AND round = $2 AND college_code = $3 
			ORDER BY course ASC
		`, year, round, collegeCode)
	} else {
		rows, err = r.db.Query(ctx, `
			SELECT DISTINCT course 
			FROM keam_cutoff_ranks 
			WHERE year = $1 AND round = $2 
			ORDER BY course ASC
		`, year, round)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to query courses: %w", err)
	}
	defer rows.Close()

	var courses []string
	for rows.Next() {
		var course string
		if err := rows.Scan(&course); err != nil {
			return nil, fmt.Errorf("failed to scan course: %w", err)
		}
		courses = append(courses, course)
	}
	return courses, nil
}

// GetRank looks up a specific cutoff rank. It returns ErrNoRows if no record matches.
// It returns an error if the category is not found in the ranks map (meaning no rank exists for category).
var ErrCategoryRankNotFound = errors.New("rank not found for specified category")

func (r *Repository) GetRank(ctx context.Context, year int, round string, collegeCode string, course string, category string) (*RankResponse, error) {
	var collegeName string
	var rankVal *int

	// Query pgxpool for college_name and check if category exists in jsonb
	err := r.db.QueryRow(ctx, `
		SELECT college_name, (ranks->>$1)::integer
		FROM keam_cutoff_ranks 
		WHERE year = $2 AND round = $3 AND college_code = $4 AND course = $5
	`, category, year, round, collegeCode, course).Scan(&collegeName, &rankVal)

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, pgx.ErrNoRows
		}
		return nil, fmt.Errorf("failed to query rank: %w", err)
	}

	if rankVal == nil {
		return nil, ErrCategoryRankNotFound
	}

	return &RankResponse{
		Year:        year,
		Round:       round,
		CollegeCode: collegeCode,
		CollegeName: collegeName,
		Course:      course,
		Category:    category,
		Rank:        *rankVal,
	}, nil
}

// GetCoursesByYear retrieves distinct courses available for a selected year across all rounds.
func (r *Repository) GetCoursesByYear(ctx context.Context, year int) ([]string, error) {
	rows, err := r.db.Query(ctx, `
		SELECT DISTINCT course 
		FROM keam_cutoff_ranks 
		WHERE year = $1 
		ORDER BY course ASC
	`, year)
	if err != nil {
		return nil, fmt.Errorf("failed to query courses by year: %w", err)
	}
	defer rows.Close()

	var courses []string
	for rows.Next() {
		var course string
		if err := rows.Scan(&course); err != nil {
			return nil, fmt.Errorf("failed to scan course: %w", err)
		}
		courses = append(courses, course)
	}
	return courses, nil
}

// PredictColleges returns a list of colleges where the user's rank is eligible based on the cutoff rank.
func (r *Repository) PredictColleges(ctx context.Context, year int, round string, course string, category string, rank int) ([]PredictionDTO, error) {
	var rows pgx.Rows
	var err error

	if round != "" {
		rows, err = r.db.Query(ctx, `
			SELECT college_code, college_name, round, (ranks->>$1)::integer as cutoff_rank
			FROM keam_cutoff_ranks 
			WHERE year = $2 AND round = $3 AND course = $4 AND (ranks->>$1)::integer >= $5
			ORDER BY (ranks->>$1)::integer ASC
		`, category, year, round, course, rank)
	} else {
		rows, err = r.db.Query(ctx, `
			SELECT college_code, college_name, round, (ranks->>$1)::integer as cutoff_rank
			FROM keam_cutoff_ranks 
			WHERE year = $2 AND course = $3 AND (ranks->>$1)::integer >= $4
			ORDER BY (ranks->>$1)::integer ASC
		`, category, year, course, rank)
	}
	
	if err != nil {
		return nil, fmt.Errorf("failed to predict colleges: %w", err)
	}
	defer rows.Close()

	var predictions []PredictionDTO
	for rows.Next() {
		var p PredictionDTO
		var cutoff *int
		if err := rows.Scan(&p.CollegeCode, &p.CollegeName, &p.Round, &cutoff); err != nil {
			return nil, fmt.Errorf("failed to scan prediction: %w", err)
		}
		if cutoff != nil {
			p.CutoffRank = *cutoff
			predictions = append(predictions, p)
		}
	}
	return predictions, nil
}
