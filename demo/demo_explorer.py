"""
HieraChain Explorer Dashboard Server.

This module provides a FastAPI-based web server for the HieraChain Supply Chain
Explorer dashboard. It serves both the frontend interface and REST API endpoints
that read pre-generated JSON data from static files.

Endpoints:
    - GET /: Serves the main index.html frontend
    - GET /api/explorer: Returns blockchain overview data (blocks, transactions, nodes)
    - GET /api/trace: Returns traceability data for a specific entity ID

Usage:
    Run this server after demo.py has generated the static data files:
        python demo/demo_explorer.py

    Then open http://127.0.0.1:8000 in your browser.
"""

import os
import json
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Environmental Declaration
os.environ["HRC_ENV"] = "dev"
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Web Server Initialization (FastAPI)
app = FastAPI(title="HieraChain Supply Chain Dashboard")

# Allow file:// and any origin to call the API (required when opening a live index.html)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# --- ENDPOINT APIS PROVIDE JSON DATA (READ FROM STATIC FILES) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPLORER_FILE = os.path.join(BASE_DIR, "demo", "data", "explorer_data.json")
TRACE_FILE = os.path.join(BASE_DIR, "demo", "data", "trace_data.json")

@app.get("/api/explorer")
async def get_explorer_data():
    """Read the JSON Overview Dashboard that has been rendered by demo.py"""
    try:
        with open(EXPLORER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "There is no static data yet. Please run: python demo/demo.py first!"}
    except Exception as e:
        return {"error": f"JSON read error: {str(e)}"}

@app.get("/api/trace")
async def get_trace_data(entity_id: str):
    """The trace endpoint retrieves the static log from the trace_data.json"""
    try:
        if not os.path.exists(TRACE_FILE):
            return {"error": "There is no JSON trace file yet. Let's run demo.py first"}

        with open(TRACE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get(entity_id, {"error": "No facts found."})
    except Exception as e:
        return {"error": f"Python Error: {str(e)}"}


# --- ENDPOINT SERVING INTERFACE (READ FROM demo/index.html) ---
_FRONTEND_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

@app.get("/explorer", response_class=HTMLResponse)
async def serve_frontend():
    """Serve index.html from the demo folder/"""
    try:
        with open(_FRONTEND_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>No index.html found. Please make sure the file exists in the demo folder/</h3>"


if __name__ == "__main__":
    print("=========================================================")
    print("🚀 HieraChain API Server is running...")
    print("   Please run: python demo/demo.py first!")
    print("")
    print("   Dashboard: http://127.0.0.1:8000/explorer")
    print("   API docs:  http://127.0.0.1:8000/docs")
    print("   Or straight open: demo/index.html")
    print("=========================================================")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
