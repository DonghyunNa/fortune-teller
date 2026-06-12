from dotenv import load_dotenv
from fastapi import FastAPI

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
