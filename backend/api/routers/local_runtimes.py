"""Local runtime lifecycle endpoints (Stage86)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ai.local_runtimes.supervisor import get_supervisor

router = APIRouter(prefix="/api/local-runtimes", tags=["local-runtimes"])

_supervisor = get_supervisor()


class EnableRequest(BaseModel):
    enabled: bool


@router.get("/status")
def status_all():
    return _supervisor.all_status()


@router.get("/status/{name}")
def status_one(name: str):
    try:
        return _supervisor.status(name).__dict__
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.put("/status/{name}/enabled")
def set_enabled(name: str, payload: EnableRequest):
    try:
        return _supervisor.set_enabled(name, payload.enabled).__dict__
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/status/{name}/start")
def start(name: str):
    if name != "kev":
        raise HTTPException(status_code=400, detail="start supported for kev only in this slice")
    return _supervisor.ensure_kev_loaded().__dict__


@router.post("/status/{name}/stop")
def stop(name: str):
    try:
        return _supervisor.stop(name).__dict__
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
