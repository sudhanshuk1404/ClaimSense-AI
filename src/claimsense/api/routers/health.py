from fastapi import APIRouter, Request

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness(request: Request) -> dict[str, object]:
    knowledge_base = request.app.state.knowledge_base
    return {
        "status": "ready",
        "knowledge_files_loaded": {
            "carc": len(knowledge_base.carc_catalog),
            "rarc": len(knowledge_base.rarc_catalog),
            "payer_rules": len(knowledge_base.payer_rules),
        },
    }

