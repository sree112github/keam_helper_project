package rank

import (
	"github.com/gin-gonic/gin"
)

// RegisterRoutes registers all route handlers for the rank search API.
func RegisterRoutes(r *gin.Engine, ctrl *Controller) {
	r.POST("/api/import", ctrl.Import)
	r.GET("/api/years", ctrl.GetYears)
	r.GET("/api/rounds", ctrl.GetRounds)
	r.GET("/api/colleges", ctrl.GetColleges)
	r.GET("/api/courses", ctrl.GetCourses)
	r.GET("/api/categories", ctrl.GetCategories)
	r.GET("/api/rank", ctrl.GetRank)
}
