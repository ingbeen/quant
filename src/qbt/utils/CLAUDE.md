# 유틸리티 패키지 가이드

> 이 문서는 `src/qbt/utils/` 패키지에 대한 가이드입니다.

## 폴더 목적

도메인에 속하지 않는 기술 기능만 담당한다 — 로깅 · CSV 로딩 · 병렬 실행 · 표 출력. `backtest` 를 import 하지 않는다. 시세 받기 · 합성은 데이터 저장소 quant-data 가 한다.

---

## 모듈 지도

함수 · 시그니처는 각 모듈 docstring 이 정본입니다.

- `logger.py` — 프로젝트 전역 로거 (DEBUG 레벨 고정, 클릭 가능한 `파일:줄번호` 포맷)
- `data_loader.py` — 시세 CSV 로딩(`load_stock_data` — 합성 파일이 짝 실물보다 먼저 끝나면 멈춘다)과 시세 표 검사(`validate_price_series`), 두 표의 겹치는 기간 추출, 시세 파일 경로의 티커(`ticker_from_stock_path`)
- `cli_helpers.py` — CLI 예외 처리 데코레이터 `@cli_exception_handler` (규칙은 `scripts/CLAUDE.md` 「예외 처리」)
- `parallel_executor.py` — 병렬 실행 `execute_parallel_with_kwargs` (규칙은 `src/qbt/CLAUDE.md` 「병렬 처리」). 예외가 나면 `executor.shutdown(cancel_futures=True)` 로 끊는다 — `wait=False` 로 끊으면 `with` 블록의 종료가 취소 요청을 되돌려 남은 작업이 뒤에서 전부 돈다
- `formatting.py` — 한글 폭을 계산하는 터미널 표 `TableLogger`. 출력은 `print_table` 하나다 — 로그 포맷이 함수 이름을 넣어, 헤더와 행을 다른 메서드가 찍으면 열이 어긋난다

---

## 규칙

- **시세는 지우거나 메우지 않는다(보간 금지)**: 중복 날짜 · 가격 결측 · 0 · 음수는 ValueError 로 멈춘다
