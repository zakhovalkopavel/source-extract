"""Review REST surface — sessions, edits, analyze, confirm, guidance."""

from __future__ import annotations

from fastapi import APIRouter

from source_extract.api.routers import review_analyze, review_edits, review_sessions

router = APIRouter(prefix="/review", tags=["review"])
router.include_router(review_sessions.router)
router.include_router(review_edits.router)
router.include_router(review_analyze.router)
