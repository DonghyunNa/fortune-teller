import os
from anthropic import Anthropic

# 모델 ID는 Anthropic 공식 ID에 맞춰야 한다. 사용자가 모델 변경을 원하면 ANTHROPIC_MODEL 환경변수로 override.
# 기본값은 변경될 수 있으므로 https://docs.anthropic.com 모델 카탈로그를 확인할 것.
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY 환경변수가 설정되어 있지 않습니다. "
                ".env 파일이나 셸에서 export 하세요."
            )
        _client = Anthropic(api_key=api_key)
    return _client
