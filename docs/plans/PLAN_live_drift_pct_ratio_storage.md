# Implementation Plan: drift_pct RTDB 저장 스케일 0~1 ratio 통일 + 설계서 갱신

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

**작성일**: 2026-04-14 00:50
**마지막 업데이트**: 2026-04-14 00:50
**관련 범위**: live
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md), [루트 CLAUDE.md](../../CLAUDE.md)

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

- [x] 목표 1: [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py) 의 `/latest/portfolio` 및 `/history/summary/{date}` 저장 시 `drift_pct` 를 **0~1 ratio** 로 통일한다 (기존 `× 100` 퍼센트 변환 제거).
- [x] 목표 2: 프로젝트 네이밍 관례 ([루트 CLAUDE.md](../../CLAUDE.md) "비율 표기 규칙": `_pct` 접미사는 0~1 ratio) 에 따라 내부 계산 / 저장 / Git 정본 모든 경로에서 `drift_pct` 스케일을 단일화한다.
- [x] 목표 3: [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) §8.2.1, §8.2.2, §12 의 `drift_pct × 100 스케일` 기술을 `0~1 ratio` 로 갱신한다.
- [x] 목표 4: `drift_pct` 저장 스케일에 대한 회귀 테스트를 추가/갱신한다.

## 2) 비목표(Non-Goals)

- `DriftReport` / `DailyResult` 의 내부 `drift_pct` 값 정의 변경은 범위 외 (이미 0~1 ratio 로 일관됨).
- `notifier.py` / `cli.py` 의 표시 계층 `* 100` 은 UI 표시용이므로 변경 없음.
- DRIFT 임계값 (`DRIFT_WARNING_RATIO` / `DRIFT_CORRECTION_RATIO`) 값 자체 변경은 범위 외.
- Android 앱 쪽 코드 수정 범위 (앱 미개발 전제이므로 호환성 고려 불필요).
- QBT 본체 수정은 범위 외.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **스케일 불일치**: 내부 계산 ([src/live/drift.py:217](../../src/live/drift.py#L217), [src/live/models.py:318,331](../../src/live/models.py#L318)) 은 `drift_pct` 를 `0~1 ratio` 로 유지하고 `ROUND_RATIO` (4자리) 로 반올림한다. 그러나 RTDB 저장 경로 ([src/live/rtdb_gateway.py:237](../../src/live/rtdb_gateway.py#L237), [src/live/rtdb_gateway.py:275](../../src/live/rtdb_gateway.py#L275)) 에서는 `round(result.drift_pct * 100, ROUND_PERCENT)` 로 **백분율 변환** 후 저장한다. 같은 키 이름 `drift_pct` 가 경로에 따라 서로 다른 스케일을 가지게 되어 혼동의 원인이 된다.
- **프로젝트 네이밍 관례 위반**: [루트 CLAUDE.md](../../CLAUDE.md) "비율 표기 규칙" 에 **"변수명 접미사: `_rate`, `_ratio`, `_pct` (모두 0~1 범위)"** 로 명시되어 있다. 즉 `_pct` 접미사는 **0~1 ratio** 가 프로젝트 표준이다. RTDB 에서만 다른 스케일을 쓰는 것은 관례 이탈.
- **매직넘버**: `* 100` 이 2곳에서 반복되고 있으며 상수 없이 직접 쓰여 있다.
- **앱 미개발 전제**: 현재 Android 앱은 개발되지 않은 상태이므로 RTDB 호환성 파괴가 없어 저장 포맷을 자유롭게 정리할 수 있다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] `rtdb_gateway.py` 의 두 저장 경로 (`/latest/portfolio`, `/history/summary/{date}`) 에서 `drift_pct` 를 `ROUND_RATIO` 로 반올림하여 0~1 ratio 그대로 저장
- [x] `* 100` 매직넘버 및 `ROUND_PERCENT` 사용이 `rtdb_gateway.py` 내 drift 저장 블록에서 완전히 제거
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 의 drift_pct 저장 스케일 기술이 0~1 ratio 로 갱신
- [x] 관련 회귀 테스트 (저장 후 실제 값이 0~1 범위인지 검증) 추가/갱신
- [x] `poetry run python validate_project.py` 통과 (passed=919, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `README.md` 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/rtdb_gateway.py` — `write_read_model`, history/summary 저장 블록 수정
- `docs/DESIGN_QBT_LIVE_FINAL.md` — §8.2.1, §8.2.2, §12 drift 저장 스케일 기술 갱신
- `tests/live/test_rtdb_gateway.py` — 저장값이 0~1 ratio 임을 검증하는 assertion 갱신/추가
- `README.md`: 변경 없음

### 데이터/결과 영향

- **RTDB 저장 포맷 변경**: `drift_pct` 키의 스케일이 `× 100` 에서 `0~1 ratio` 로 변경됨. 앱 미개발 전제이므로 소비자 호환성 이슈 없음.
- Git 정본 (`live_state.json`, `history/daily/*.json`) 의 `drift_pct` 는 이미 0~1 ratio 이므로 변화 없음.
- 알림 본문 / CLI 출력은 표시 계층에서 `* 100` 처리하므로 사용자 경험 변화 없음.

## 6) 단계별 계획(Phases)

### Phase 0 — 기존 기대값 테스트 갱신 (레드)

**작업 내용**:

- [x] `tests/live/test_rtdb_gateway.py` 의 기존 `write_read_model` 관련 테스트에서 `drift_pct` 기대값이 × 100 이었다면 0~1 ratio 로 바꿔 레드 상태를 만든다
- [x] 신규 테스트 추가: `drift_pct` 저장값이 `[0, 1]` 범위 내이고 `ROUND_RATIO` 정밀도를 갖는지 확인

---

### Phase 1 — 구현 (그린 전환)

**작업 내용**:

- [x] `src/live/rtdb_gateway.py` `write_read_model` 내 `/latest/portfolio` payload 에서 `round(result.drift_pct * 100, ROUND_PERCENT)` → `round(result.drift_pct, ROUND_RATIO)` 로 변경
- [x] `src/live/rtdb_gateway.py` `write_read_model` 내 `/history/summary/{date}` payload 에서 동일 변경
- [x] 더 이상 사용되지 않으면 `from qbt.backtest.constants import ROUND_PERCENT` 를 `ROUND_RATIO` 로 교체 (파일 내 다른 사용처가 있는지 확인 후 결정)
- [x] Phase 0 테스트 통과 확인

---

### Phase 2 — 설계서 갱신

**작업 내용**:

- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` §8.2.1 의 `drift_pct` 필드 설명을 "0~1 ratio (`ROUND_RATIO = 4` 자리, 예: `0.0350` = 3.5%)" 로 수정
- [x] §8.2.2 의 `/history/summary/{date}` 의 `drift_pct` 필드 설명 동일하게 수정
- [x] §11/§12 의 "앱 호환성을 위해 RTDB 에 × 100 변환" 문단을 "내부 / Git 정본 / RTDB 모두 0~1 ratio 로 통일. 앱 표시 시 × 100 변환은 앱 계층 책임" 으로 수정
- [x] `drift_pct 스케일` 관련 cross-reference (§11 알림 본문) 갱신 여부 확인 — 알림 본문은 `notifier.py` 가 `* 100` 처리하므로 설명 변경 불필요, 단 문구 일관성만 확인

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `README.md` 변경 없음 확인
- [x] `poetry run black .` 실행
- [x] DoD / Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=919, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / drift_pct RTDB 저장 스케일 0~1 ratio 통일 + 설계서 갱신
2. live / drift_pct 내부/저장 스케일 단일화 (× 100 제거)
3. live / `_pct = 0~1` 관례 RTDB 반영 + 설계서 반영
4. live / drift_pct 매직넘버 제거 및 저장 ratio 통일
5. live / drift 저장 경로 ratio 표준화 + 문서 반영

## 7) 리스크(Risks)

- **앱 연동 위험**: 앱 미개발 전제이므로 직접적 호환성 이슈 없음. 향후 앱 개발자가 설계서만 참고하면 되므로 문서 갱신이 필수.
- **테스트 갱신 누락**: `test_rtdb_gateway.py` 의 write_read_model 경로에 기존 `× 100` 기대값이 있다면 반드시 함께 수정해야 한다. Ruff/PyRight 로는 안 잡히므로 pytest 실패로 감지해야 한다 → Phase 0 레드에서 선제적으로 확보.

## 8) 메모(Notes)

- 본 plan 은 전수 분석 결과 파생 4 종 중 세 번째이다. 선행: [PLAN_live_iso_silent_skip_alignment.md](PLAN_live_iso_silent_skip_alignment.md).
- 참고: 기존 쓰기 경로 ([src/live/rtdb_gateway.py:237,275](../../src/live/rtdb_gateway.py#L237)) 와 설계서 §8.2.1/§8.2.2/§11/§12.

### 진행 로그 (KST)

- 2026-04-14 00:50: plan 작성 시작
- 2026-04-14 01:00: rtdb_gateway 저장 경로 2 곳 `× 100` 제거 → `ROUND_RATIO` 로 교체, `ROUND_PERCENT` import 제거
- 2026-04-14 01:05: test_rtdb_gateway 에 0~1 ratio 저장 검증 테스트 추가 (drift_pct=0.0350)
- 2026-04-14 01:10: DESIGN_QBT_LIVE_FINAL.md §8.2 / §12 drift_pct 저장 스케일 기술 갱신
- 2026-04-14 01:15: validate_project.py 통과 (919/0/0), plan Done 처리
