# Agent Instructions

## Database Operations

*   **NEVER use `TRUNCATE TABLE` or perform full data clears on any database table.**
*   The tables (like `keam_cutoff_ranks`) contain important historical data that must be preserved.
*   If data needs to be removed, ALWAYS use targeted `DELETE` commands with precise `WHERE` clauses.
*   Always verify if a table contains pre-existing data before modifying or removing rows.

## Data Extraction (OCR)
*   The system uses an optimized prompt to extract OCR data from KEAM rank images. 
*   "Other Categories" are extracted directly into the `ranks` json object as key-value pairs (e.g., `"FW": 1234`).
