package rank

import (
	"time"
)

// KeamCutoffRank represents a row in the keam_cutoff_ranks table.
type KeamCutoffRank struct {
	ID          int64          `db:"id" json:"id"`
	Year        int            `db:"year" json:"year"`
	Round       string         `db:"round" json:"round"`
	Course      string         `db:"course" json:"course"`
	CollegeCode string         `db:"college_code" json:"college_code"`
	CollegeName string         `db:"college_name" json:"college_name"`
	CollegeType string         `db:"college_type" json:"college_type"`
	Ranks       map[string]int `db:"ranks" json:"ranks"`
	CreatedAt   *time.Time     `db:"created_at" json:"created_at,omitempty"`
}
