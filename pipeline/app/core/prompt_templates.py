"""
OCR prompt templates for minicpm-v:8b.
Kept in one module for easy iteration and testing.
"""

# Primary extraction prompt — sent with each page image
EXTRACTION_PROMPT = """You are a precise data extraction system for KEAM (Kerala Engineering Admission) documents.

Extract ALL college rows and ALL category cutoff ranks from this table image.

DOCUMENT STRUCTURE:
- Header contains: year (e.g. "KEAM 2026") and round (e.g. "First Phase Allotment")
- Course headings (often red/colored text) appear above groups of college rows
- Each course heading applies to ALL rows below it until the next heading
- Each row = one college entry

FOR EACH ROW EXTRACT:
- year: integer (from document header, e.g. 2026)
- round: string (from document header, e.g. "First Phase Allotment")
- course: string (from the nearest preceding course heading above this row)
- college_code: string (3-letter code in first column, e.g. "KKE", "TVE", "TCR")
- name: string (full name of the college)
- type: string ("G" for Government, "S" for Self-financing)
- ranks: object mapping the standard category codes (SM, EZ, MU, BH, LA, DV, VK, BX, KN, KU, SC, ST, EW) to their integer rank values
- other_categories: string (exact raw text from the "Other Categories" column, e.g., "FW:7355, SD:13549"). Use empty string "" if the column is blank.

CATEGORY CODES (in exact order from left to right):
SM, EZ, MU, BH, LA, DV, VK, BX, KN, KU, SC, ST, EW, Other Categories

CRITICAL RULES:
1. The columns appear in this exact order: Name of College, Type, SM, EZ, MU, BH, LA, DV, VK, BX, KN, KU, SC, ST, EW, Other Categories.
2. If a column has "-" or is empty, output null for that category (or empty string for other_categories). Do NOT shift values into the wrong column.
3. Remove commas from numbers: "8,302" → 8302
4. All rank values in "ranks" must be integers or null
5. The "Other Categories" column contains comma-separated text like "FW:7355, SD:13549". Extract it exactly as it appears into the "other_categories" string field. Do NOT put these special categories inside the "ranks" object.
6. college_code is always a 3-letter uppercase code in the first data column
7. type: look for "G" or "Government" → "G", "S" or "Self" → "S"
8. Extract EVERY row — do not skip any college
9. Extract EVERY rank column — do not skip any categories! Look at the header row closely.
10. ANTI-HALLUCINATION: If a number is blurry, illegible, or you are unsure of the exact value, output null. DO NOT guess or hallucinate numbers. It is strictly better to have missing data (null) than incorrect data.

Return ONLY a valid JSON array. No markdown fences. No explanation. No extra text.

Example output format:
[
  {
    "year": 2026,
    "round": "First Phase Allotment",
    "course": "Applied Electronics & Instrumentation",
    "college_code": "KKE",
    "name": "Government Engineering College, Kozhikkode",
    "type": "G",
    "ranks": {"SM": 8302, "EZ": 13955, "MU": 10143, "BH": 12238, "LA": 39051, "DV": 53411, "VK": 12467, "BX": 30724, "KN": null, "KU": null, "SC": 54976, "ST": null, "EW": 26454},
    "other_categories": "FW:7355, SD:13549"
  }
]"""


# Repair prompt — sent when first attempt produces invalid JSON
REPAIR_PROMPT_TEMPLATE = """Your previous response was not valid JSON.

Parse error: {error}

Previous response (first 800 chars):
{raw_response}

Fix the JSON and return ONLY the corrected JSON array.
Rules reminder:
- Return a JSON array [...] 
- No markdown, no explanation
- "-" → null, commas in numbers removed
- All rank values: integer or null"""


def build_repair_prompt(error: str, raw_response: str) -> str:
    """Build a repair prompt from a failed OCR response."""
    return REPAIR_PROMPT_TEMPLATE.format(
        error=error,
        raw_response=raw_response[:800],
    )
