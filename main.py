import os
import psycopg2
from fastapi import FastAPI, HTTPException, Header, Query
from typing import Optional

# --- Config ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")
API_KEY = os.environ.get("OPHIR_API_KEY", "")

app = FastAPI(title="Ophir Brief API", docs_url=None, redoc_url=None)


# --- Auth ---
# Accepts the key via header (x-api-key: ...) or query param (?key=...)
def verify(header_key: Optional[str], query_key: Optional[str]):
    provided = header_key or query_key
    if not API_KEY or provided != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# --- DB helpers ---
def get_connection():
    # Railway sometimes issues postgres:// — psycopg2 needs postgresql://
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


def get_tab(tab_name: str) -> list[dict]:
    """
    Reads sheet_cell for the given tab.
    The lowest row_idx is treated as the header row (col_idx -> column name).
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

        # The first row_idx holds the column headers
        min_row = min(r[0] for r in rows)

        # Build header map: col_idx -> column name
        headers: dict[int, str] = {}
        for row_idx, col_idx, val in rows:
            if row_idx == min_row:
                headers[col_idx] = val or f"col_{col_idx}"

        # Build data rows, skipping the header row
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


# --- Endpoints ---
@app.get("/health")
def health():
    """Public health check - no auth required."""
    return {"status": "ok", "service": "ophir-brief-api"}


@app.get("/pipeline")
def pipeline(x_api_key: Optional[str] = Header(None), key: Optional[str] = Query(None)):
    verify(x_api_key, key)
    return get_tab("Pipeline")


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
    """
    Single endpoint that returns everything needed to write an issue.
    Fetch this at the start of each newsletter session.
    """
    verify(x_api_key, key)
    return {
        "pipeline": get_tab("Pipeline"),
        "quotes": get_tab("Quotes"),
        "themes": get_tab("Themes"),
        "themes_detail": get_tab("ThemesEntries"),
        "meetings": get_tab("Meetings"),
        "hypotheses": get_tab("Hypotheses"),
    }
