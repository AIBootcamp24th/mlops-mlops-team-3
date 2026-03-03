from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="서버 상태 확인",
    description="API 프로세스가 정상 동작 중인지 확인하는 헬스체크 엔드포인트입니다.",
    responses={
        200: {
            "description": "정상 응답",
            "content": {"application/json": {"example": {"status": "ok"}}},
        }
    },
)
def health() -> dict[str, str]:
    return {"status": "ok"}
