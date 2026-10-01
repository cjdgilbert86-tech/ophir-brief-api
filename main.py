import os
import psycopg2
from fastapi import FastAPI, HTTPException, Header, Query
from typing import Optional

# --- Config ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")
API_KEY = os.environ.get("OPHIR_API_KEY", "")

app = FastAPI(title="Ophir Brief API", docs_url=None, redoc_url=None)

# Stages included in the newsletter feed (First Meeting through Agreement Drafting)
NEWSLETTER_STAGES = {
    "First Meeting",
    "Second Meeting",
    "Diligence",
    "Diligence Follow-up",
    "Data Room Access",
    "Agreement Drafting",
}

# Slim field set for newsletter — covers everything needed for editorial decisions
NEWSLETTER_FIELDS = {
    "Company Name", "Pipeline Stage", "Priority", "Sentiment",
    "Last Meeting Date", "Last Meeting Type", "Last Updated", "Meeting Count",
    "Revenue / ARR", "Growth Rate", "Valuation Expectation",
    "Round Size Sought", "Total Funding Raised",
    "One-Liner", "Industry", "Company Stage", "Location",
    "Strengths", "Concerns / Red Flags", "Latest Summary",
    "Notable Customers", "Founders", "Website",
}


# --- Auth ---
def verify(header_key: Optional[str], query_key: Optional[str]):
    provided = header_key or query_key
    if not API_KEY or provided != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# --- DB helpers ---
def get_connection():
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


def get_tab(tab_name: str) -> list[dict]:
    """Full tab data — all columns, all rows."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT row_idx, col_idx, val FROM sheet_cell WHERE tab = %s ORDER BY row_idx, col_idx",
                (tab_name,),
            )
            rows = cur.fetchall()

        if not rows:
            return []

        min_row = min(r[0] for r in rows)
        headers: dict[int, str] = {}
        for row_idx, col_idx, val in rows:
            if row_idx == min_row:
                headers[col_idx] = val or f"col_{col_idx}"

        data: dict[int, dict] = {}
        for row_idx, col_idx, val in rows:
            if row_idx == min_row:
                continue
            if row_idx not in data:
                data[row_idx] = {}
            col_name = headers.get(col_idx, f"col_{col_idx}")
            data[row_idx][col_name] = val

        return list(data.values())
    finally:
        conn.close()


def get_pipeline_by_stages(stages: set, slim: bool = False, month_prefix: str = None) -> list[dict]:
    """
    Returns pipeline deals filtered to the given stages.
    If slim=True, only returns NEWSLETTER_FIELDS columns.
    If month_prefix is set (e.g. '2026-09'), also filters by Last Updated starting with that string.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT row_idx, col_idx, val FROM sheet_cell WHERE tab = 'Pipeline' ORDER BY row_idx, col_idx"
            )
            rows = cur.fetchall()

        if not rows:
            return []

        min_row = min(r[0] for r in rows)

        headers: dict[int, str] = {}
        for row_idx, col_idx, val in rows:
            if row_idx == min_row:
                headers[col_idx] = val or f"col_{col_idx}"

        stage_col = next((k for k, v in headers.items() if v == "Pipeline Stage"), None)
        updated_col = next((k for k, v in headers.items() if v == "Last Updated"), None)

        # First pass: find rows matching stage filter
        stage_matched: set[int] = set()
        for row_idx, col_idx, val in rows:
            if row_idx == min_row:
                continue
            if col_idx == stage_col and val in stages:
                stage_matched.add(row_idx)

        # Second pass: if month filter, also check Last Updated
        if month_prefix and updated_col is not None:
            month_matched: set[int] = set()
            for row_idx, col_idx, val in rows:
                if row_idx == min_row:
                    continue
                if col_idx == updated_col and val and val.startswith(month_prefix):
                    month_matched.add(row_idx)
            matched_rows = stage_matched & month_matched
        else:
            matched_rows = stage_matched

        # Build output
        data: dict[int, dict] = {}
        for row_idx, col_idx, val in rows:
            if row_idx == min_row or row_idx not in matched_rows:
                continue
            col_name = headers.get(col_idx, f"col_{col_idx}")
            if slim and col_name not in NEWSLETTER_FIELDS:
                continue
            if row_idx not in data:
                data[row_idx] = {}
            data[row_idx][col_name] = val

        return list(data.values())
    finally:
        conn.close()


# --- Endpoints ---
@app.get("/health")
def health():
    db_status = "unknown"
    db_error = None
    api_key_set = bool(API_KEY)
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sheet_cell")
            count = cur.fetchone()[0]
        conn.close()
        db_status = "ok"
        db_rows = count
    except Exception as e:
        db_status = "error"
        db_error = str(e)
        db_rows = None
    return {"status": "ok", "service": "ophir-brief-api", "db": db_status,
            "db_error": db_error, "db_rows": db_rows, "api_key_set": api_key_set}


@app.get("/pipeline")
def pipeline(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    """All pipeline deals including closed/passed."""
    verify(x_api_key, key)
    return get_tab("Pipeline")


@app.get("/newsletter-pipeline")
def newsletter_pipeline(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    """First Meeting through Agreement Drafting — slim fields."""
    verify(x_api_key, key)
    return get_pipeline_by_stages(NEWSLETTER_STAGES, slim=True)


@app.get("/passed-this-month")
def passed_this_month(
    month: str = Query("2026-09", description="Month prefix e.g. 2026-09"),
    x_api_key: Optional[str] = Header(None),
    key: Optional[str] = Query(None),
):
    """Deals passed/rejected in the given month. Default: 2026-09 (September)."""
    verify(x_api_key, key)
    return get_pipeline_by_stages({"Passed"}, slim=True, month_prefix=month)


@app.get("/quotes")
def quotes(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    verify(x_api_key, key)
    return get_tab("Quotes")


@app.get("/themes")
def themes(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    verify(x_api_key, key)
    return get_tab("Themes")


@app.get("/themes-detail")
def themes_detail(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    verify(x_api_key, key)
    return get_tab("ThemesEntries")


@app.get("/meetings")
def meetings(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    verify(x_api_key, key)
    return get_tab("Meetings")


@app.get("/hypotheses")
def hypotheses(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    verify(x_api_key, key)
    return get_tab("Hypotheses")


@app.get("/newsletter")
def newsletter(
    month: str = Query("2026-09", description="Month to pull rejections from, e.g. 2026-09"),
    x_api_key: Optional[str] = Header(None),
    key: Optional[str] = Query(None),
):
    """
    Everything needed for a newsletter issue:
    - Active pipeline (First Meeting → Agreement Drafting)
    - Deals passed/rejected in the given month
    - Quotes, themes, meetings, hypotheses
    """
    verify(x_api_key, key)
    return {
        "active_pipeline": get_pipeline_by_stages(NEWSLETTER_STAGES, slim=True),
        "passed_this_month": get_pipeline_by_stages({"Passed"}, slim=True, month_prefix=month),
        "quotes": get_tab("Quotes"),
        "themes": get_tab("Themes"),
        "meetings": get_tab("Meetings"),
        "hypotheses": get_tab("Hypotheses"),
    }
