package rank

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"keam-rank-finder/internal/common"
)

// Controller handles HTTP requests for rank search operations.
type Controller struct {
	service *Service
}

// NewController creates a new Controller instance.
func NewController(service *Service) *Controller {
	return &Controller{service: service}
}

// Import triggers data import for a specific year from JSON database files.
func (ctrl *Controller) Import(c *gin.Context) {
	var req ImportRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		common.SendFailure(c, http.StatusBadRequest, "Invalid request body: must provide a 'year' integer field")
		return
	}

	summary, err := ctrl.service.ImportData(c.Request.Context(), req.Year)
	if err != nil {
		common.SendFailure(c, http.StatusInternalServerError, err.Error())
		return
	}

	common.SendSuccess(c, summary)
}

// GetYears retrieves the list of distinct available rank years.
func (ctrl *Controller) GetYears(c *gin.Context) {
	years, err := ctrl.service.GetYears(c.Request.Context())
	if err != nil {
		common.SendFailure(c, http.StatusInternalServerError, "Failed to retrieve years: "+err.Error())
		return
	}
	common.SendSuccess(c, years)
}

// GetRounds retrieves the allotment rounds of a specific year.
func (ctrl *Controller) GetRounds(c *gin.Context) {
	yearStr := c.Query("year")
	if yearStr == "" {
		common.SendFailure(c, http.StatusBadRequest, "Missing required query parameter: year")
		return
	}

	year, err := strconv.Atoi(yearStr)
	if err != nil {
		common.SendFailure(c, http.StatusBadRequest, "Invalid query parameter: year must be an integer")
		return
	}

	rounds, err := ctrl.service.GetRounds(c.Request.Context(), year)
	if err != nil {
		common.SendFailure(c, http.StatusInternalServerError, "Failed to retrieve rounds: "+err.Error())
		return
	}
	common.SendSuccess(c, rounds)
}

// GetColleges retrieves colleges associated with a year and allotment round, optionally filtered by course.
func (ctrl *Controller) GetColleges(c *gin.Context) {
	yearStr := c.Query("year")
	round := c.Query("round")
	course := c.Query("course") // optional course filter

	if yearStr == "" || round == "" {
		common.SendFailure(c, http.StatusBadRequest, "Missing required query parameters: year and round")
		return
	}

	year, err := strconv.Atoi(yearStr)
	if err != nil {
		common.SendFailure(c, http.StatusBadRequest, "Invalid query parameter: year must be an integer")
		return
	}

	colleges, err := ctrl.service.GetColleges(c.Request.Context(), year, round, course)
	if err != nil {
		common.SendFailure(c, http.StatusInternalServerError, "Failed to retrieve colleges: "+err.Error())
		return
	}
	common.SendSuccess(c, colleges)
}

// GetCourses retrieves courses offered under a year and optionally filtered by allotment round and college.
func (ctrl *Controller) GetCourses(c *gin.Context) {
	yearStr := c.Query("year")
	round := c.Query("round")     // now optional
	college := c.Query("college") // now optional

	if yearStr == "" {
		common.SendFailure(c, http.StatusBadRequest, "Missing required query parameter: year")
		return
	}

	year, err := strconv.Atoi(yearStr)
	if err != nil {
		common.SendFailure(c, http.StatusBadRequest, "Invalid query parameter: year must be an integer")
		return
	}

	var courses []string
	if round == "" {
		// If no round provided, fetch all courses for the year
		courses, err = ctrl.service.GetCoursesByYear(c.Request.Context(), year)
	} else {
		courses, err = ctrl.service.GetCourses(c.Request.Context(), year, round, college)
	}

	if err != nil {
		common.SendFailure(c, http.StatusInternalServerError, "Failed to retrieve courses: "+err.Error())
		return
	}
	common.SendSuccess(c, courses)
}

// GetCategories retrieves the list of category codes and full names.
func (ctrl *Controller) GetCategories(c *gin.Context) {
	categories, err := ctrl.service.GetCategories(c.Request.Context())
	if err != nil {
		common.SendFailure(c, http.StatusInternalServerError, "Failed to load categories: "+err.Error())
		return
	}
	common.SendSuccess(c, categories)
}

// GetRank searches for the last cutoff rank.
func (ctrl *Controller) GetRank(c *gin.Context) {
	yearStr := c.Query("year")
	round := c.Query("round")
	college := c.Query("college")
	course := c.Query("course")
	category := c.Query("category")

	if yearStr == "" || round == "" || college == "" || course == "" || category == "" {
		common.SendFailure(c, http.StatusBadRequest, "Missing required query parameters: year, round, college, course, and category")
		return
	}

	year, err := strconv.Atoi(yearStr)
	if err != nil {
		common.SendFailure(c, http.StatusBadRequest, "Invalid query parameter: year must be an integer")
		return
	}

	rankResp, err := ctrl.service.GetRank(c.Request.Context(), year, round, college, course, category)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			common.SendFailure(c, http.StatusNotFound, "No allotment record matches the selected year, round, college, and course")
			return
		}
		if errors.Is(err, ErrCategoryRankNotFound) {
			common.SendFailure(c, http.StatusNotFound, "No last rank cutoff was allotted for the selected category under this course")
			return
		}
		common.SendFailure(c, http.StatusInternalServerError, "Error retrieving rank: "+err.Error())
		return
	}

	common.SendSuccess(c, rankResp)
}

// PredictColleges predicts eligible colleges based on the user's rank.
func (ctrl *Controller) PredictColleges(c *gin.Context) {
	yearStr := c.Query("year")
	course := c.Query("course")
	category := c.Query("category")
	rankStr := c.Query("rank")
	round := c.Query("round") // optional round filter

	if yearStr == "" || course == "" || category == "" || rankStr == "" {
		common.SendFailure(c, http.StatusBadRequest, "Missing required query parameters: year, course, category, and rank")
		return
	}

	year, err := strconv.Atoi(yearStr)
	if err != nil {
		common.SendFailure(c, http.StatusBadRequest, "Invalid query parameter: year must be an integer")
		return
	}

	rank, err := strconv.Atoi(rankStr)
	if err != nil {
		common.SendFailure(c, http.StatusBadRequest, "Invalid query parameter: rank must be an integer")
		return
	}

	predictions, err := ctrl.service.PredictColleges(c.Request.Context(), year, round, course, category, rank)
	if err != nil {
		common.SendFailure(c, http.StatusInternalServerError, "Failed to predict colleges: "+err.Error())
		return
	}

	common.SendSuccess(c, predictions)
}
