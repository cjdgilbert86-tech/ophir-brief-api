import os
import psycopg2
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional

# --- Config ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")
API_KEY = os.environ.get("OPHIR_API_KEY", "")

app = FastAPI(title="Ophir Brief API", docs_url=None, redoc_url=None)


# --- Auth ---
def verify(x_api_key: Optional[str] = Header(None)):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# --- DB helpers ---
def get_connection():
    # Railway sometimes issues postgres:// — psycopg2 needs postgresql://
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


def get_tab(tab_name: str) -> list[dict]:
    """
    Pivots sheet_cell rows into a list of dicts, one per row_idx.
    Each dict has col_name → value pairs.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT row_idx, col_name, value
                FROM sheet_cell
                WHERE tab = %s
                ORDER BY row_idx, col_name
                """,
                (tab_name,),
            )
            rows = cur.fetchall()

        grouped: dict[int, dict] = {}
        for row_idx, col_name, value in rows:
            if row_idx not in grouped:
                grouped[row_idx] = {}
            grouped[row_idx][col_name] = value

        return list(grouped.values())
    finally:
        conn.close()


# --- Endpoints ---
@app.get("/health")
def health():
    """Public health check — no auth required."""
    return {"status": "ok", "service": "ophir-brief-api"}


@app.get("/pipeline")
def pipeline(x_api_key: Optional[str] = Header(None)):
    verify(x_api_key)
    return get_tab("Pipeline")


@app.get("/quotes")
def quotes(x_api_key: Optional[str] = Header(None)):
    verify(x_api_key)
    return get_tab("Quotes")


@app.get("/themes")
def themes(x_api_key: Optional[str] = Header(None)):
    verify(x_api_key)
    return get_tab("Themes")


@app.get("/themes-detail")
def themes_detail(x_api_key: Optional[str] = Header(None)):
    verify(x_api_key)
    return get_tab("ThemesEntries")


@app.get("/meetings")
def meetings(x_api_key: Optional[str] = Header(None)):
    verify(x_api_key)
    return get_tab("Meetings")


@app.get("/hypotheses")
def hypotheses(x_api_key: Optional[str] = Header(None)):
    verify(x_api_key)
    return get_tab("Hypotheses")


@app.get("/newsletter")
def newsletter(x_api_key: Optional[str] = Header(None)):
    """
    Single endpoint that returns everything needed to write an issue.
    Fetch this at the start of each newsletter session.
    """
    verify(x_api_key)
    return {
        "pipeline": get_tab("Pipeline"),
        "quotes": get_tab("Quotes"),
        "themes": get_tab("Themes"),
        "themes_detail": get_tab("ThemesEntries"),
        "meetings": get_tab("Meetings"),
        "hypotheses": get_tab("Hypotheses"),
    }
