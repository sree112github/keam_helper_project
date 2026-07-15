package rank

// ImportRequest represents the JSON request payload for triggering imports.
type ImportRequest struct {
	Year int `json:"year" binding:"required"`
}

// ImportSummary holds the count of processed, skipped, and failed records for an import operation.
type ImportSummary struct {
	Inserted int `json:"inserted"`
	Skipped  int `json:"skipped"`
	Failed   int `json:"failed"`
}

// CollegeDTO represents a college code and name keypair.
type CollegeDTO struct {
	CollegeCode string `json:"college_code"`
	CollegeName string `json:"college_name"`
}

// RankResponse represents the detailed results displayed on rank search query.
type RankResponse struct {
	Year        int    `json:"year"`
	Round       string `json:"round"`
	CollegeCode string `json:"college_code"`
	CollegeName string `json:"college_name"`
	Course      string `json:"course"`
	Category    string `json:"category"`
	Rank        int    `json:"rank"`
}

// CategoryDTO matches the category code and description mapping structure.
type CategoryDTO struct {
	Code string `json:"code"`
	Name string `json:"name"`
}

// PredictionDTO represents a predicted college and its cutoff rank.
type PredictionDTO struct {
	CollegeCode string `json:"college_code"`
	CollegeName string `json:"college_name"`
	Round       string `json:"round"`
	CutoffRank  int    `json:"cutoff_rank"`
}

