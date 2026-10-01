import os
import psycopg2
from fastapi import FastAPI, HTTPException, Header, Query
from typing import Optional

# --- Config ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")
API_KEY = os.environ.get("OPHIR_API_KEY", "")

app = FastAPI(title="Ophir Brief API", docs_url=None, redoc_url=None)

# Pipeline stages to exclude from the newsletter feed
INACTIVE_STAGES = {"Passed", "On Hold", "Funded"}


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
    """
    Reads sheet_cell for the given tab.
    The lowest row_idx is the header row (col_idx -> column name).
    All subsequent rows are returned as dicts keyed by column name.
    """
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


def get_active_pipeline() -> list[dict]:
    """
    Returns only active pipeline deals — excludes Passed, On Hold, Funded.
    Finds the col_idx for 'Pipeline Stage' from the header row, then filters.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Get all pipeline cells
            cur.execute(
                "SELECT row_idx, col_idx, val FROM sheet_cell WHERE tab = 'Pipeline' ORDER BY row_idx, col_idx"
            )
            rows = cur.fetchall()

        if not rows:
            return []

        min_row = min(r[0] for r in rows)

        # Build header map
        headers: dict[int, str] = {}
        for row_idx, col_idx, val in rows:
            if row_idx == min_row:
                headers[col_idx] = val or f"col_{col_idx}"

        # Find the col_idx for 'Pipeline Stage'
        stage_col = next((k for k, v in headers.items() if v == "Pipeline Stage"), None)

        # Find row_idxs where Pipeline Stage is active
        if stage_col is not None:
            active_rows = set()
            for row_idx, col_idx, val in rows:
                if row_idx == min_row:
                    continue
                if col_idx == stage_col and val not in INACTIVE_STAGES:
                    active_rows.add(row_idx)
        else:
            # If we can't find the stage column, return everything
            active_rows = {r[0] for r in rows if r[0] != min_row}

        # Build data for active rows only
        data: dict[int, dict] = {}
        for row_idx, col_idx, val in rows:
            if row_idx == min_row or row_idx not in active_rows:
                continue
            if row_idx not in data:
                data[row_idx] = {}
            col_name = headers.get(col_idx, f"col_{col_idx}")
            data[row_idx][col_name] = val

        return list(data.values())
    finally:
        conn.close()


# --- Endpoints ---
@app.get("/health")
def health():
    """Public health check with DB ping."""
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

    return {
        "status": "ok",
        "service": "ophir-brief-api",
        "db": db_status,
        "db_error": db_error,
        "db_rows": db_rows,
        "api_key_set": api_key_set,
    }


@app.get("/pipeline")
def pipeline(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    """All pipeline deals including closed/passed."""
    verify(x_api_key, key)
    return get_tab("Pipeline")


@app.get("/active-pipeline")
def active_pipeline(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    """Active deals only — excludes Passed, On Hold, Funded. Use this for newsletter prep."""
    verify(x_api_key, key)
    return get_active_pipeline()


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
def newsletter(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    """Everything needed to write an issue — uses active pipeline only."""
    verify(x_api_key, key)
    return {
        "active_pipeline": get_active_pipeline(),
        "quotes": get_tab("Quotes"),
        "themes": get_tab("Themes"),
        "themes_detail": get_tab("ThemesEntries"),
        "meetings": get_tab("Meetings"),
        "hypotheses": get_tab("Hypotheses"),
    }
