from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.saju.router import router as saju_router

app = FastAPI(
    title="Fortune Telling API",
    description="한국식 사주명리부터 시작하는 멀티 운세 API",
    version="0.1.0",
)

app.include_router(saju_router, prefix="/saju", tags=["saju"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
