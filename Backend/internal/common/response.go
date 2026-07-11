package common

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// SuccessResponse defines the standard structure for successful API calls.
type SuccessResponse struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data"`
}

// FailureResponse defines the standard structure for failed API calls.
type FailureResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// SendSuccess sends a HTTP 200 OK success response with data payload.
func SendSuccess(c *gin.Context, data interface{}) {
	c.JSON(http.StatusOK, SuccessResponse{
		Success: true,
		Data:    data,
	})
}

// SendFailure sends a failure response with specified status code and message.
func SendFailure(c *gin.Context, statusCode int, message string) {
	c.JSON(statusCode, FailureResponse{
		Success: false,
		Message: message,
	})
}
