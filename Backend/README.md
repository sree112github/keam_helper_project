# KEAM Last Rank Finder

KEAM Last Rank Finder is a lightweight, high-performance Go backend and clean HTML5/CSS3/Vanilla JS web frontend designed to search and analyze KEAM engineering cutoff ranks dynamically.

## Folder Structure

```text
Entrance_helper/
├── Backend/
│   ├── cmd/
│   │   └── server/
│   │       └── main.go           # App Entrypoint
│   ├── internal/
│   │   ├── config/
│   │   │   └── config.go         # Environment Configuration Loader
│   │   ├── database/
│   │   │   └── postgres.go       # pgxpool Connection Manager
│   │   ├── common/
│   │   │   └── response.go       # Standard API Response Types
│   │   └── rank/
│   │       ├── model.go          # Database Cutoff Entities
│   │       ├── dto.go            # Request/Response Data Structures
│   │       ├── repository.go     # SQL Queries & Lookups
│   │       ├── service.go        # Categories JSON parser & Business Logic
│   │       ├── controller.go     # HTTP Request Validations
│   │       ├── routes.go         # HTTP Routing Group
│   │       └── importer.go       # JSON file batch importer
│   ├── category_info.json        # Categories Data Source
│   ├── rank_info.json            # Cutoffs Raw Source
│   ├── .env                      # Active Config (Ignored in Git)
│   ├── .env.example              # Config Template
│   └── go.mod                    # Go Module Dependencies
└── Frontend/
    ├── index.html                # Search UI Structure & Disclaimers
    ├── style.css                 # Slate/Ice Blue Dark CSS Theme
    └── script.js                 # Cascading Form Handlers & Fetch Operations
```

---

## Setup & Run Instructions

### 1. Database Configuration

The application uses an existing PostgreSQL database. Set the connection variables in the environment or `.env` file. The connection pool (`pgxpool`) is configured for **Supabase Free Tier (t3a.nano)**.

*   `MaxConns = 5`
*   `MinConns = 1`
*   `HealthCheckPeriod = 1m`
*   `MaxConnLifetime = 1h`
*   `MaxConnIdleTime = 30m`

### 2. Environment Variables

Create a `.env` file inside the `Backend/` folder. Use the following template:

```env
PORT=8080

# Database configurations
DB_HOST=your-supabase-db-host
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-secure-password
DB_NAME=postgres
DB_SSLMODE=require

# Future AI/LLM models
AMODEL=gpt-4.1
```

> [!NOTE]
> The configuration system is backward-compatible. If `DB_HOST` is not set, it will automatically fallback to reading database parameters from the older format (`HOST`, `PORT`, `USER`, `PASSWORD`, `DATABASE`) present in pre-existing `.env` files.

### 3. Run Backend

Navigate to the `Backend/` directory and start the server:

```powershell
cd Backend
go mod tidy

# Option A: Standard Run
go run cmd/server/main.go

# Option B: Hot-Reloading Run (Air)
air
```

The application logs standard information on start, database connection pool creation, incoming HTTP requests, and errors.

### 4. Run Frontend

Because the Go server is configured to serve static files, the frontend is served out-of-the-box! Just open your browser to:

*   **`http://localhost:8080/`** (or your configured `PORT`)

Alternatively, since CORS is fully enabled on the API, you can open `Frontend/index.html` directly in the browser (`file:///` protocol) or serve it using any simple static host.

---

## API Documentation

All responses follow a standard format.

### Success Envelope
```json
{
  "success": true,
  "data": {}
}
```

### Failure Envelope
```json
{
  "success": false,
  "message": "Error details..."
}
```

---

### Endpoints

#### 1. POST `/api/import`
Trigger JSON file batch import into database for the selected year. Uses transactional batch insert chunks of 100 records and `ON CONFLICT DO NOTHING`.
*   **Request Body**:
    ```json
    {
      "year": 2025
    }
    ```
*   **Response**:
    ```json
    {
      "success": true,
      "data": {
        "inserted": 88,
        "skipped": 0,
        "failed": 0
      }
    }
    ```

#### 2. GET `/api/years`
Fetch list of available cutoff rank years.
*   **Response**:
    ```json
    {
      "success": true,
      "data": [2025]
    }
    ```

#### 3. GET `/api/rounds`
Retrieve allotment rounds containing cutoff records for a selected year.
*   **Parameters**:
    *   `year` (integer, Required)
*   **Response**:
    ```json
    {
      "success": true,
      "data": ["Second Phase Allotment"]
    }
    ```

#### 4. GET `/api/colleges`
Retrieve distinct colleges matching a year and allotment round.
*   **Parameters**:
    *   `year` (integer, Required)
    *   `round` (string, Required)
*   **Response**:
    ```json
    {
      "success": true,
      "data": [
        {
          "college_code": "KKE",
          "college_name": "Government Engineering College, Kozhikkode"
        }
      ]
    }
    ```

#### 5. GET `/api/courses`
Retrieve courses offered by a college under a year and allotment round.
*   **Parameters**:
    *   `year` (integer, Required)
    *   `round` (string, Required)
    *   `college` (string, Required)
*   **Response**:
    ```json
    {
      "success": true,
      "data": ["Applied Electronics \u0026 Instrumentation", "Civil Engineering"]
    }
    ```

#### 6. GET `/api/categories`
Retrieve full list of KEAM reservation category codes and descriptions (dynamically parsed from `category_info.json`).
*   **Response**:
    ```json
    {
      "success": true,
      "data": [
        {
          "code": "SM",
          "name": "State Merit"
        },
        {
          "code": "EZ",
          "name": "Ezhava, Thiyya and Billava"
        }
      ]
    }
    ```

#### 7. GET `/api/rank`
Look up the last allotment cutoff rank matching selectors.
*   **Parameters**:
    *   `year` (integer, Required)
    *   `round` (string, Required)
    *   `college` (string, Required)
    *   `course` (string, Required)
    *   `category` (string, Required)
*   **Response**:
    ```json
    {
      "success": true,
      "data": {
        "year": 2025,
        "round": "Second Phase Allotment",
        "college_code": "KKE",
        "college_name": "Government Engineering College, Kozhikkode",
        "course": "Applied Electronics \u0026 Instrumentation",
        "category": "SM",
        "rank": 12426
      }
    }
    ```
