# 유틸리티 패키지 가이드

> 이 문서는 `src/qbt/utils/` 패키지에 대한 가이드입니다.

## 폴더 목적

여러 도메인이 함께 쓰는 기능만 담당한다 — 로깅 · CSV 로딩 · 병렬 실행 · 표 출력 같은 기술 기능과, 백테스트 · 레버리지 시뮬레이션 어느 한쪽에 속하지 않는 시세 수집 · 대용 시세 가공 · 대체 비교. `backtest` · `tqqq` 를 import 하지 않는다.

---

## 모듈 지도

함수 · 시그니처는 각 모듈 docstring 이 정본입니다.

- `logger.py` — 프로젝트 전역 로거 (DEBUG 레벨 고정, 클릭 가능한 `파일:줄번호` 포맷)
- `data_loader.py` — 시세 CSV 로딩(`load_stock_data`)과 시세 표 검사(`validate_price_series`), 두 표의 겹치는 기간 추출
- `cli_helpers.py` — CLI 예외 처리 데코레이터 `@cli_exception_handler` (규칙은 `scripts/CLAUDE.md` 「예외 처리」)
- `parallel_executor.py` — 병렬 실행 `execute_parallel_with_kwargs` (규칙은 `src/qbt/CLAUDE.md` 「병렬 처리」). 예외가 나면 `executor.shutdown(cancel_futures=True)` 로 끊는다 — `wait=False` 로 끊으면 `with` 블록의 종료가 취소 요청을 되돌려 남은 작업이 뒤에서 전부 돈다
- `formatting.py` — 한글 폭을 계산하는 터미널 표 `TableLogger`. 출력은 `print_table` 하나다 — 로그 포맷이 함수 이름을 넣어, 헤더와 행을 다른 메서드가 찍으면 열이 어긋난다
- `stock_downloader.py` — Yahoo Finance 다운로드와 시세 저장 `save_stock_csv`(가격 반올림 → 검사 → 저장). 다운로더와 합성 · 대용 · 장기 대체 생성 스크립트가 같이 쓴다
- `proxy_series.py` — 실물 ETF 상장 전 구간을 대용 시세로 채우는 가공 (이음매 스케일 · 이어 붙이기 · 매일 비율 유지 바스켓 · 금리 누적 시세)
- `proxy_comparison.py` — 대체 시세가 기준 시세를 얼마나 따르는지 재는 비교와 결과 표의 열 이름 · 자릿수 (계산 스크립트와 대시보드가 같이 쓴다)

---

## 규칙

- **시세는 지우거나 메우지 않는다(보간 금지)**: 중복 날짜 · 가격 결측 · 0 · 음수, 날짜가 어긋난 바스켓 구성 종목, 금리 결측은 ValueError 로 멈춘다. 음수 금리는 그대로 쓴다
- **대용 이음매는 실물 첫 거래일이다**: 대용은 그날 종가 비율로 가격만 스케일해 잇는다 (수익률 · 거래량 불변, 대용 구간 거래량 0)
- **비교 구간**: 기준 첫 거래일부터 두 시세가 모두 있는 날만 쓴다 — 시장 달력이 다른 선물 · 펀드의 빈 날을 메우지 않는다
