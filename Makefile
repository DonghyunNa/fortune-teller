PYTHON  ?= .venv/bin/python
PIP     ?= $(PYTHON) -m pip
UVICORN ?= $(PYTHON) -m uvicorn
PYTEST  ?= $(PYTHON) -m pytest

.DEFAULT_GOAL := help
.PHONY: help venv install dev run test clean

help:
	@echo "사용 가능한 명령어:"
	@echo "  make install   - .venv 생성(없으면) + 의존성 설치"
	@echo "  make dev       - 개발 서버 (코드 변경 시 자동 reload)"
	@echo "  make run       - 운영 모드 서버 (0.0.0.0:8000)"
	@echo "  make test      - 테스트 실행"
	@echo "  make clean     - __pycache__·빌드 산출물 제거"

.venv:
	python3 -m venv .venv

venv: .venv

install: .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@echo "설치 완료. 'make dev' 로 서버를 띄우세요."

dev:
	$(UVICORN) app.main:app --reload

run:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000

test:
	$(PYTEST)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf *.egg-info .pytest_cache .ruff_cache build dist
