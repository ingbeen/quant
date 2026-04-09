# Implementation Plan: 포트폴리오 대시보드 색상 동적 할당

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

**작성일**: 2026-04-09 15:00
**마지막 업데이트**: 2026-04-09 15:30
**관련 범위**: scripts (backtest dashboard)
**관련 문서**: scripts/CLAUDE.md, tests/CLAUDE.md, src/qbt/utils/CLAUDE.md

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

- [x] `scripts/backtest/app_portfolio_backtest.py`의 자산/실험 색상 하드코딩 제거
- [x] 자산 및 실험 ID에 대해 "정렬 기반 인덱스 팔레트"로 색상을 동적으로 할당
- [x] 신규 자산/실험이 추가되어도 코드 수정 없이 서로 다른 색으로 구분되도록 한다

## 2) 비목표(Non-Goals)

- 시그널 차트의 OHLC/MA/밴드/마커 색상(`_COLOR_UP`, `_COLOR_MA_LINE` 등)은 변경 대상 아님
- 다른 대시보드(`app_single_backtest.py`, `app_walkforward.py` 등)의 색상 정책 변경
- 팔레트 커스터마이즈 UI 추가
- 색상 저장/영속화(세션 간 일관성)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `app_portfolio_backtest.py`의 `_ASSET_COLORS`(8개)와 `_EXPERIMENT_COLORS`(시리즈별 그룹)가 하드코딩되어 있다.
- 매핑되지 않은 자산/실험은 모두 fallback 회색(`#888888`)으로 표시되어 **서로 구분되지 않는다**.
- `PORTFOLIO_CONFIGS`에 실험이 추가될 때마다 딕셔너리를 수동 갱신해야 한다.
- 사용자가 "전략이든 자산이든 색상 구분되게"를 요청함.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md`
- `tests/CLAUDE.md` (테스트가 필요한 경우)
- `src/qbt/utils/CLAUDE.md`
- 루트 `CLAUDE.md`의 "상수 관리(3계층)", "코딩 표준", "로깅 정책"

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `_ASSET_COLORS`, `_EXPERIMENT_COLORS`, `_ASSET_COLOR_FALLBACK`, `_EXPERIMENT_COLOR_FALLBACK` 제거
- [x] 정렬 기반 인덱스 팔레트 함수 구현 (`_build_color_map`)
- [x] `_get_asset_color` / `_get_experiment_color`가 동적 맵 기반으로 동작
- [x] 동적 맵은 `@st.cache_data`로 캐시되어 동일 ID tuple에 대해 결정적으로 동일한 결과 반환
- [x] 모든 기존 호출부가 새 인터페이스로 수정되어 회귀 없음
- [x] `poetry run python validate_project.py` 통과 (passed=495, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/app_portfolio_backtest.py` (유일한 편집 파일)
- `README.md`: **변경 없음**

### 데이터/결과 영향

- 출력 CSV/JSON 스키마 변경 없음
- 시각적 변화만 발생 (기존 고정 색상이 팔레트 기반 색상으로 바뀜)
- 동일 입력 세트에 대해서는 결정적(정렬 기반)으로 동일한 색상이 할당됨

## 6) 단계별 계획(Phases)

### Phase 1 — 동적 색상 할당 유틸리티 구현 및 적용

**설계**:

1. 팔레트 소스: `plotly.colors.qualitative.Light24` (24색, hex 문자열 리스트)
2. 헬퍼 함수 `_build_color_map(ids: Sequence[str]) -> dict[str, str]`:
   - 입력 ID 리스트를 `sorted()`로 정렬
   - 인덱스 `i % len(palette)`로 팔레트에서 색상 선택 (wrap-around)
   - 반환: `{id: hex_color}`
3. 호출부 구조 변경:
   - 기존 `_get_asset_color(asset_id)` → 전역 딕셔너리 `_ASSET_COLOR_MAP`를 찾도록 수정
   - 대신 앱 진입부에서 전체 자산/실험 ID 집합으로부터 색상 맵을 만든 후, 각 차트 함수에 전달하는 방식으로 변경
4. 구체 전략:
   - `@st.cache_data`로 감싼 `_build_color_map` 헬퍼를 모듈 레벨에 두고, `_get_asset_color(asset_id, asset_ids: tuple[str, ...])` / `_get_experiment_color(exp_name, exp_names: tuple[str, ...])` 시그니처로 변경
   - 캐시 키는 정렬된 tuple이므로 동일 입력에 대해 결정적
   - 호출부는 이미 asset_ids/experiment_names를 알고 있으므로 tuple 형태로 전달

**작업 내용**:

- [x] `_ASSET_COLORS`, `_EXPERIMENT_COLORS`, `_ASSET_COLOR_FALLBACK`, `_EXPERIMENT_COLOR_FALLBACK` 상수 삭제
- [x] `plotly.colors as pc` import 추가, `_COLOR_PALETTE` 단일 팔레트 상수 정의 (`pc.qualitative.Light24`, 자산/실험 공유)
- [x] `_build_color_map(ids: tuple[str, ...]) -> dict[str, str]` 구현 (정렬 기반 인덱스 할당, wrap-around, `@st.cache_data` 적용)
- [x] `_get_asset_color(asset_id, asset_ids)` / `_get_experiment_color(exp_name, exp_names)` 시그니처 변경
- [x] 기존 호출부를 모두 확인하여 asset_ids/experiment_names 컨텍스트를 전달하도록 수정
  - 자산 색상 호출부 (총 7곳): holdings 도넛 / rebalancing 비중 변화 바차트 / contribution 분기별 바차트 / contribution 누적 면적 / contribution legacy 면적 / weight chart 스택 / weight chart 목표비중 라인
  - 실험 색상 호출부 (총 2곳): 전체 비교 에쿼티 곡선 / 드로우다운 비교 (둘 다 `experiments` 전체 기준 컨텍스트로 고정)
- [x] 컨텍스트 tuple은 호출부 함수가 이미 보유한 asset_ids 또는 weight_cols로부터 도출 (추가 인자 전달 없음, 최소 침습 달성)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `README.md` 변경 없음 (명시 완료)
- [x] `poetry run black scripts/backtest/app_portfolio_backtest.py` 실행 (1 file left unchanged)
- [x] 전체 앱 임포트/타입체크 무결성 확인 (PyRight 통과)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=495, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / 포트폴리오 색상 하드코딩 제거 및 동적 팔레트 적용
2. 대시보드 / 자산·실험 색상을 정렬 기반 인덱스 팔레트로 전환
3. 대시보드 / 포트폴리오 색상 fallback 회색 문제 해결 (동적 할당)
4. 대시보드 / _ASSET_COLORS·_EXPERIMENT_COLORS 제거 + Light24 팔레트 기반 동적 매핑
5. 대시보드 / 신규 자산·실험 자동 색상 구분 지원

## 7) 리스크(Risks)

- 기존 사용자가 익숙한 고정 색상(qqq=파랑, tqqq=주황 등)이 바뀌어 인지 비용이 발생할 수 있음 → 사용자가 명시적으로 요청한 변경이므로 수용
- 색상 할당이 ID 집합에 의존하므로, 일부 차트에서 asset_ids를 전달받지 못하면 색상 맵이 달라질 위험 → 모든 호출부에서 동일한 정렬된 tuple을 사용하도록 강제

## 8) 메모(Notes)

- 팔레트 선택: `plotly.colors.qualitative.Light24` (24색). 현재 자산 8개 + 실험 6개 모두 여유롭게 커버하며 추후 확장에도 wrap-around로 대응.
- 정렬 기준: Python `sorted()` 기본(사전식). 같은 자산은 앱 실행마다 항상 같은 색상.
- 컨텍스트 전달 설계가 부담되는 호출부가 있다면, 모듈 레벨에 `_ASSET_COLOR_MAP: dict[str, str] | None = None` 캐시를 두고 첫 생성 시 초기화하는 방법도 대안.

### 진행 로그 (KST)

- 2026-04-09 15:00: 초안 작성
- 2026-04-09 15:15: Phase 1 구현 완료 (상수 제거, _build_color_map 추가, 9개 호출부 업데이트)
- 2026-04-09 15:25: black 포맷 + validate_project.py 통과 (passed=495, failed=0, skipped=0)
- 2026-04-09 15:30: 상태 Done 처리
