# Implementation Plan: 백테스트 대시보드 툴팁 개선 및 차트 수정

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

**작성일**: 2026-02-19 23:30
**마지막 업데이트**: 2026-02-19 23:30
**관련 범위**: scripts/backtest, vendor/streamlit-lightweight-charts-v5, src/qbt/tqqq
**관련 문서**: src/qbt/backtest/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md

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

- [x] 목표 1: 캔들스틱 차트 오른쪽 Y축의 현재 수치 레이블 4개(종가, MA, 상단밴드, 하단밴드) 제거
- [x] 목표 2: 툴팁 위치를 아래로 내려 차트 제목이 가려지지 않도록 수정
- [x] 목표 3: 툴팁에 OHLC 가격 + 각각의 전일종가대비 % 표시
- [x] 목표 4: 툴팁에 에쿼티(원), 드로우다운(%) 표시
- [x] 목표 5: 합성 TQQQ 데이터의 High/Low를 0이 아닌 근사값으로 생성 (simulation.py 수정)

## 2) 비목표(Non-Goals)

- 툴팁을 마우스 추적형으로 변경하는 것 (고정 위치 내림으로 결정)
- 에쿼티/드로우다운 pane의 tooltip 별도 구현
- simulation.py의 Volume 생성 로직 변경
- 대시보드 UI 전반 리디자인

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **오른쪽 수치 레이블**: 캔들스틱 차트 오른쪽 Y축에 4개 시리즈의 마지막 값이 겹쳐서 표시됨 (618.57, 601.30, 594.78, 579.98). lightweight-charts의 `lastValueVisible` 기본값이 `true`이기 때문
2. **툴팁 위치**: 현재 `top: 12px; left: 12px;` 고정으로, 차트 제목과 겹침
3. **Buy & Hold 차트 깨짐**: 합성 TQQQ 데이터(1999~2010)에서 `simulate()` 함수가 High=0.0, Low=0.0을 설정하여 캔들스틱이 0까지 늘어짐
4. **툴팁 정보 부족**: 현재 전일대비% 하나만 표시. OHLC 가격, 전일종가대비%, 에쿼티, 드로우다운 정보 누락

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`: 대시보드 앱 아키텍처, Feature Detection, customValues 기반 tooltip
- `src/qbt/tqqq/CLAUDE.md`: simulation 도메인 규칙 (존재 시)
- `scripts/CLAUDE.md`: Streamlit 앱 규칙, 계층 분리 원칙
- `tests/CLAUDE.md`: 테스트 작성 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 캔들스틱 차트 오른쪽 Y축에 현재 수치 레이블이 표시되지 않음
- [x] 툴팁이 차트 제목을 가리지 않는 위치에 표시됨
- [x] 툴팁에 시가/고가/저가/종가 가격과 각각의 전일종가대비% 표시
- [x] 툴팁에 에쿼티(원), 드로우다운(%) 표시
- [x] 합성 구간 캔들스틱이 정상 범위로 표시됨 (High/Low != 0)
- [x] simulation.py High/Low 변경에 대한 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=295, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(README/CLAUDE/plan 등)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/simulation.py`: High/Low 근사값 생성 로직
- `tests/test_tqqq_simulation.py`: High/Low 근사값 검증 테스트 추가
- `scripts/backtest/app_single_backtest.py`: customValues 확장, lastValueVisible 설정
- `vendor/streamlit-lightweight-charts-v5/lightweight_charts_v5/frontend/src/LightweightChartsComponent.tsx`: 툴팁 위치 조정, 확장된 customValues 렌더링
- 프론트엔드 빌드 산출물 (`vendor/.../frontend/build/`)

### 데이터/결과 영향

- `storage/stock/TQQQ_synthetic_max.csv`: High/Low 값 변경 (재생성 필요)
- `storage/results/backtest/buy_and_hold/signal.csv`: High/Low 값 변경 (재실행 필요)
- 기존 백테스트 결과의 성과 지표(equity, CAGR 등)에는 영향 없음 (High/Low는 성과 계산에 미사용)

## 6) 단계별 계획(Phases)

### Phase 1 — simulation.py High/Low 근사값 생성

**작업 내용**:

- [x] `src/qbt/tqqq/simulation.py` 841-843행 수정
  - 변경 전: `df[COL_HIGH] = 0.0` / `df[COL_LOW] = 0.0`
  - 변경 후: `df[COL_HIGH] = df[[COL_OPEN, COL_CLOSE]].max(axis=1)` / `df[COL_LOW] = df[[COL_OPEN, COL_CLOSE]].min(axis=1)`
  - 주석 업데이트: "합성 데이터이므로 Open/Close 기반 근사값 사용"
- [x] `tests/test_tqqq_simulation.py`에 High/Low 근사값 검증 테스트 추가
  - `test_high_low_approximation_for_synthetic_data`: High >= max(Open, Close), Low <= min(Open, Close) 검증
  - `test_high_low_relationship`: High >= Low 불변조건 검증

---

### Phase 2 — Python 앱: customValues 확장 + lastValueVisible 설정

**작업 내용**:

- [x] `_build_candle_data()` 함수에서 customValues 확장
  - 기존: `pct` (전일대비%), `ma`, `upper`, `lower`
  - 추가: `open`, `high`, `low`, `close` (가격), `open_pct`, `high_pct`, `low_pct`, `close_pct` (전일종가대비%)
  - 추가: `equity`, `dd` (에쿼티/드로우다운)
  - equity/drawdown은 기존 `band_map` 패턴과 동일하게 날짜 기준 매핑 구성
- [x] 전일종가대비% 계산 로직 구현
  - 기존 `change_pct`(종가 기반)를 `prev_close` 시리즈로 변경
  - 각 OHLC에 대해: `(value / prev_close - 1) * 100`
- [x] 캔들스틱 시리즈에 `"lastValueVisible": False` 추가 (384행 options)
- [x] MA 시리즈에 `"lastValueVisible": False` 추가 (407행 options)
- [x] Upper Band 시리즈에 `"lastValueVisible": False` 추가 (424행 options)
- [x] Lower Band 시리즈에 `"lastValueVisible": False` 추가 (439행 options)
- [x] 캔들스틱 시리즈의 `"priceLineVisible": True`를 `False`로 변경 (384행)

---

### Phase 3 — TSX: 툴팁 위치 조정 + 확장된 customValues 렌더링

**작업 내용**:

- [x] `LightweightChartsComponent.tsx` 툴팁 위치 변경
  - 변경 전: `top: 12px; left: 12px;`
  - 변경 후: `top: 55px; left: 12px;` (차트 제목 아래)
- [x] crosshairHandler에서 확장된 customValues 렌더링 로직 구현
  - OHLC 가격 + 전일종가대비% 표시 (예: `시가: 601.30 (+0.52%)`)
  - 에쿼티/드로우다운 표시 (예: `에쿼티: 12,345,678원` / `드로우다운: -5.23%`)
  - 기존 MA/밴드 정보 유지
  - 구분선(`<hr>` 또는 간격)으로 섹션 분리: OHLC | 지표 | 에쿼티
- [x] 프론트엔드 빌드: `cd vendor/streamlit-lightweight-charts-v5/lightweight_charts_v5/frontend && npm run build`

---

### Phase 4 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트
  - `src/qbt/backtest/CLAUDE.md`: customValues 키 목록 업데이트
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=295, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / 툴팁 OHLC+에쿼티 확장 + 합성데이터 High/Low 근사값 생성
2. 대시보드 / 시그널 차트 툴팁 개선 + simulation High/Low 수정
3. 백테스트+TQQQ / 대시보드 툴팁 전면 개선 및 합성데이터 차트 수정
4. 대시보드 / 차트 UX 개선 (툴팁 확장, 위치 조정, 가격 레이블 제거, High/Low 수정)
5. 대시보드+시뮬레이션 / 캔들스틱 차트 정보 표시 개선 및 합성데이터 OHLC 보완

## 7) 리스크(Risks)

- **프론트엔드 빌드 환경**: TSX 수정 후 `npm run build`가 필요하며, Node.js 환경이 정상이어야 함. 빌드 실패 시 vendor fork의 기존 빌드 산출물이 손상될 수 있음
  - 완화: 빌드 전 기존 build 폴더 백업, 빌드 실패 시 복원
- **합성 데이터 재생성**: simulation.py 변경 후 `TQQQ_synthetic_max.csv`와 백테스트 결과를 재생성해야 함
  - 완화: 스크립트 재실행으로 해결 (성과 지표에는 영향 없음)
- **customValues 크기 증가**: 키가 4개 → 12개로 증가하여 JSON 직렬화 데이터량 증가
  - 완화: 값은 짧은 문자열이므로 성능 영향 미미

## 8) 메모(Notes)

### 핵심 결정 사항

- 툴팁 위치: 고정 위치 내림 방식 선택 (마우스 추적형 대신)
- Buy & Hold Low=0: simulation.py 근본 수정 선택 (대시보드 임시 대체 대신)
- 기존 테스트에 High/Low=0 검증하는 assert 없음 확인 → 테스트 호환성 문제 없음

### 기술 분석 결과

- `lastValueVisible` 기본값이 `true`이므로 모든 시리즈에 `false` 명시 필요
- `param.seriesData`는 Map으로 모든 pane/시리즈 데이터 접근 가능하지만, 현재는 customValues 기반 접근이 더 단순
- 에쿼티/드로우다운 데이터는 Python에서 customValues에 포함시켜 전달하는 방식이 TSX 수정 최소화에 유리

### 진행 로그 (KST)

- 2026-02-19 23:30: 계획서 초안 작성 (Draft)
- 2026-02-20 00:15: 전체 Phase 구현 완료, 검증 통과 (Done)

---
