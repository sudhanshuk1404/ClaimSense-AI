"""ClaimSense AI — FastAPI application.

Startup flow (lifespan):
  1. Load all claims from the synthetic dataset into memory
  2. Initialise the OpenAI LLM client
  3. Pre-index historical claims for the PatternMatcher (embeds every claim
     once so individual requests don't pay the embedding cost)
  4. Expose the shared objects through FastAPI dependency injection
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.dependencies import AppState, get_app_state
from api.routers import batch, claims, patterns


# ---------------------------------------------------------------------------
# Lifespan — runs once at startup and again at shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise heavy objects once at startup; release on shutdown."""
    state = get_app_state()
    await state.initialise()          # load claims + embed index (blocking I/O in thread)
    yield
    await state.teardown()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(
    title="ClaimSense AI",
    description=(
        "AI-powered healthcare claim denial analysis.\n\n"
        "**Three core capabilities:**\n"
        "- **Problem 1** `/claims` — Root cause analysis per denied claim\n"
        "- **Problem 2** `/patterns` — Historical pattern matching & appeal strategy\n"
        "- **Problem 3** `/batch` — Denial clustering & batch intelligence report"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow all origins for local development; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(claims.router,   prefix="/api/v1/claims",   tags=["Problem 1 — Root Cause Analysis"])
app.include_router(patterns.router, prefix="/api/v1/patterns", tags=["Problem 2 — Pattern Matching"])
app.include_router(batch.router,    prefix="/api/v1/batch",     tags=["Problem 3 — Batch Intelligence"])


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root():
    """Redirect bare root to interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Health"])
async def health():
    """Liveness probe — returns service status and dataset stats."""
    state = get_app_state()
    return {
        "status": "ok",
        "model": state.llm.model,
        "total_claims_loaded": len(state.all_claims),
        "denied_claims": len([c for c in state.all_claims if c.is_denied]),
        "paid_claims":   len([c for c in state.all_claims if not c.is_denied]),
        "index_ready": state.index_ready,
    }
