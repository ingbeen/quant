# Implementation Plan: live 상수화 + 코드 정리 + 주석 정리

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

**작성일**: 2026-04-12 22:45
**마지막 업데이트**: 2026-04-12 22:45
**관련 범위**: live
**관련 문서**: `live/CLAUDE.md`, `tests/CLAUDE.md`

---

## 0) 고정 규칙

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 매직 넘버 4곳 상수화
- [x] state.py 로컬 frozenset 모듈 레벨 상수로 추출
- [x] 불필요한 fallback 2곳 제거
- [x] 과거 상태/변경 이력 주석 2곳 정리

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경 (Plan 1 에서 완료)
- 소수점 반올림 (Plan 2 에서 완료)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `data_fetcher.py:79` `days=5` 매직 넘버
- `notifier.py:153` `timeout=10` 매직 넘버
- `cli.py:802` `default=10` 매직 넘버
- `state.py:281` 함수 내 로컬 frozenset 중복
- `chart_data.py:90` 도달 불가능 `hasattr` fallback
- `data_validator.py:145` 광범위 Exception catch
- `constants.py:39-40` 스키마 변경 이력 주석 (과거 상태 기재)
- `chart_data.py:16` "200 일 고정 아님" 과거 상태 암시

### 영향받는 규칙

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `live/CLAUDE.md`
- 루트 `CLAUDE.md` (상수 관리 규칙, 주석 작성 원칙)

## 4) 완료 조건(Definition of Done)

- [x] 매직 넘버 4곳 상수화 완료
- [x] state.py _VALID_SIGNAL_STATES 모듈 레벨 추출
- [x] chart_data.py hasattr fallback 제거
- [x] data_validator.py except 구체화
- [x] constants.py 스키마 이력 주석 제거
- [x] chart_data.py 과거 상태 주석 제거
- [x] `poetry run python validate_project.py` 통과
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `live/src/live/constants.py`
- `live/src/live/data_fetcher.py`
- `live/src/live/notifier.py`
- `live/src/live/cli.py`
- `live/src/live/state.py`
- `live/src/live/chart_data.py`
- `live/src/live/data_validator.py`
- `README.md`: 변경 없음

### 데이터/결과 영향

- 동작 변경 없음 (상수 추출, 주석 정리, fallback 정리)

## 6) 단계별 계획(Phases)

### Phase 1 — 상수화 + 코드/주석 정리

**작업 내용**:

- [x] `constants.py`: `DEFAULT_RECENT_FETCH_DAYS: Final[int] = 5` 추가
- [x] `constants.py`: `TELEGRAM_TIMEOUT_SECONDS: Final[int] = 10` 추가
- [x] `constants.py`: `DEFAULT_HISTORY_TAIL_LINES: Final[int] = 10` 추가
- [x] `data_fetcher.py`: `days=5` → `days=DEFAULT_RECENT_FETCH_DAYS`
- [x] `notifier.py`: `timeout=10` → `timeout=TELEGRAM_TIMEOUT_SECONDS`
- [x] `cli.py:802`: `default=10` → `default=DEFAULT_HISTORY_TAIL_LINES`
- [x] `cli.py:587`: `days=5` → `days=DEFAULT_RECENT_FETCH_DAYS`
- [x] `state.py`: `_VALID_SIGNAL_STATES` 를 모듈 레벨 `Final` 로 이동
- [x] `chart_data.py:90`: `hasattr(d, "isoformat")` fallback → `d.isoformat()` 직접 호출
- [x] `data_validator.py:145`: `except Exception` → `except (ValueError, KeyError)` 구체화
- [x] `constants.py:39-40`: `# v2 → v3:` 스키마 변경 이력 주석 제거
- [x] `chart_data.py:16`: `(200 일 고정 아님)` 표현 제거

---

### 마지막 Phase — 최종 검증

- [x] `poetry run black .` 실행
- [x] DoD 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=891, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. live / 매직 넘버 상수화 + 주석·fallback 정리
2. live / 코드 정리: 상수 추출, 불필요한 fallback 제거, 과거 상태 주석 삭제
3. live / 상수화 4건 + state.py frozenset 추출 + 주석 규칙 준수
4. live / 매직 넘버·로컬 상수·fallback·이력 주석 일괄 정리
5. live / 코드 위생: 상수화, fallback 제거, 주석 원칙 적용

## 7) 리스크(Risks)

- 동작 변경 없는 리팩토링이므로 위험 낮음

## 8) 메모(Notes)

- `data_validator.py` 의 `except Exception` 은 exchange-calendars 라이브러리의 예외 다양성 고려
- `chart_data.py` 의 `hasattr` 는 `load_stock_data` 가 항상 `date` 객체를 반환하므로 불필요

### 진행 로그 (KST)

- 2026-04-12 22:45: Plan 작성 완료, 착수
