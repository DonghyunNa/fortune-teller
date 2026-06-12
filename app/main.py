from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app.saju.router import router as saju_router
from app.daily.router import router as daily_router
from app.tarot.router import router as tarot_router

app = FastAPI(
    title="Fortune Telling API",
    description="한국식 사주명리부터 시작하는 멀티 운세 API",
    version="0.1.0",
)

app.include_router(saju_router, prefix="/saju", tags=["saju"])
app.include_router(daily_router, prefix="/daily", tags=["daily"])
app.include_router(tarot_router, prefix="/tarot", tags=["tarot"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# 정적 웹 UI. mount("/")는 모든 경로를 가로채므로 반드시 API 라우터와
# /health 같은 직접 라우트 등록 뒤에 위치해야 한다(라우트 우선순위).
# 경로는 cwd와 무관하게 이 파일 기준으로 해석한다.
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
