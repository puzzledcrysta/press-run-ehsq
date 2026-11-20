from fastapi import APIRouter
from app.inputs import Handover, VerifyNote
from . import service

router = APIRouter()


@router.get('/api/runs/{run_id}/handover')
def handover_state(run_id: str):
    return service.status(run_id)


@router.post('/api/runs/{run_id}/handover')
def handover_commit(run_id: str, request: Handover):
    return service.apply(run_id, request.mode)


@router.post('/api/runs/{run_id}/handover/verify')
def handover_verify(run_id: str, request: VerifyNote):
    return service.verify(run_id, request.line, request.note)


@router.post('/api/runs/{run_id}/handover/reveal')
def handover_reveal(run_id: str):
    return service.reveal(run_id)
