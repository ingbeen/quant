# Implementation Plan: download_data 전체 다운로드 기능 추가

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-03-07 14:00
**마지막 업데이트**: 2026-03-07 14:00
**관련 범위**: scripts/data
**관련 문서**: `scripts/CLAUDE.md`, `CLAUDE.md` (루트)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] `scripts/data/download_data.py`에서 인자 없이 실행 시 전체 주식 데이터 다운로드
- [x] 전체 주식 데이터 목록을 상수로 정의

## 2) 비목표(Non-Goals)

- 다운로드 비즈니스 로직 (`stock_downloader.py`) 변경
- 새로운 데이터 소스 추가
- 병렬 다운로드

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 ticker를 필수 인자로 받아 한 번에 1개 종목만 다운로드 가능
- 8개 종목(SPY, IWM, EFA, EEM, GLD, TLT, QQQ, TQQQ)을 다운로드하려면 8번 실행 필요
- 인자 없이 실행하면 전체 목록을 순회 다운로드하도록 개선

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트) - 상수 관리 규칙, 코딩 표준
- `scripts/CLAUDE.md` - CLI 스크립트 규칙, 명령행 인자 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족 (인자 없을 때 전체 다운로드)
- [x] `poetry run python validate_project.py` 통과 (passed=479, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (`scripts/CLAUDE.md` 예외 사례 설명 업데이트)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/data/download_data.py` - 상수 추가, argparse 변경, 전체 다운로드 로직
- `scripts/CLAUDE.md` - 예외 사례 1 설명 업데이트

### 데이터/결과 영향

- 출력 스키마 변경 없음 (기존 `download_stock_data` 함수 그대로 사용)
- 기존 단일 티커 다운로드 동작 유지

## 6) 단계별 계획(Phases)

### Phase 1 — 구현 + 문서 + 검증

**작업 내용**:

- [x] `download_data.py` 상단에 `DEFAULT_TICKERS` 상수 정의 (SPY, IWM, EFA, EEM, GLD, TLT, QQQ, TQQQ)
- [x] argparse `ticker` 인자를 optional로 변경 (`nargs="?"`)
- [x] ticker 미지정 시 `DEFAULT_TICKERS` 전체 순회 다운로드 로직 추가
- [x] docstring 및 사용 예시 업데이트
- [x] `scripts/CLAUDE.md` 예외 사례 1 설명 업데이트
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=479, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. 데이터 / download_data 인자 없이 전체 주식 다운로드 기능 추가
2. 데이터 / 전체 티커 목록 상수화 + 일괄 다운로드 기능
3. 스크립트 / download_data 전체 다운로드 모드 추가 (DEFAULT_TICKERS)
4. 스크립트 / download_data 티커 인자 optional 변경 + 전체 다운로드
5. 데이터 / download_data 개선: 인자 없으면 8개 종목 일괄 다운로드

## 7) 리스크(Risks)

- 낮음: 기존 단일 티커 동작에 영향 없음 (인자 지정 시 기존 동작 유지)
- 낮음: 다운로드 중 1개 종목 실패 시 전체 중단 (`@cli_exception_handler` 예외 전파)

## 8) 메모(Notes)

- 상수 위치: `download_data.py` 상단 (1개 파일에서만 사용 → 로컬 상수 규칙 적용)
- 상수 접두사: `DEFAULT_*` (기본값 파라미터 규칙)

### 진행 로그 (KST)

- 2026-03-07 14:00: 계획서 작성
- 2026-03-07 14:05: 구현 + 문서 업데이트 + 검증 완료 (passed=479, failed=0, skipped=0)
