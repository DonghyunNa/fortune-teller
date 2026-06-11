# Fortune Telling API

한국식 사주명리부터 시작해 타로·별자리·일일운세 등으로 확장하는 멀티 운세 FastAPI 서비스. Anthropic Claude로 풀이를 생성한다.

## 하네스: fortune-telling

**목표:** 사주명리부터 멀티 운세까지 FastAPI 모듈로 확장 가능한 운세 API를 만들고, 한국식 도메인 룰의 정확성과 계산↔API↔LLM 경계면 정합성을 보장한다.

**트리거:** 운세 API의 신규 빌드·기능 추가·수정·재실행·QA 결함 처리·새 운세 모듈 추가 같은 요청 시 `fortune-telling-build` 스킬을 사용하라. 단순 질문(예: "이 코드 뭐야?")이나 사주 도메인 지식만 묻는 경우는 직접 응답해도 된다.

**변경 이력:**

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-06-11 | 초기 구성 (fortune-engineer + qa-engineer 2명 팀, 스킬 4개) | 전체 | - |
| 2026-06-11 | 사주 API v0.1 초기 구현 + QA 결함 6건 수정 | app/saju, app/_shared/llm.py, README | major: 모델 ID env override·양력 범위 검증·음력 윤달 라운드트립 검증. minor: 데드 코드 정리·README 안내 |
| 2026-06-11 | 통합 엔드포인트 `/saju/reading` 추가 + 풀이용 컨텍스트 필드(age/gender/context) | app/saju (schemas/interpreter/router), README | calc+interpret 한 번에 호출 / LLM 풀이의 인생 단계·맥락 보강 |
| 2026-06-11 | age 필드 제거(birth_date에서 자동 계산), tone을 Enum → 자유 문자열 | app/saju/schemas·interpreter·router, README | 입력 단순화 + 자유 톤 표현 허용 |
