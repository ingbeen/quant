# Implementation Plan: 시장 구간별 분석 테이블 UI 개선

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

**작성일**: 2026-03-03 01:30
**마지막 업데이트**: 2026-03-03 01:30
**관련 범위**: scripts/backtest (대시보드 렌더링)
**관련 문서**: src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md

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

- [x] 거래수 0인 구간에서 거래 관련 지표(거래수, 승률, 평균보유기간, 수익팩터)를 "-"로 표시
- [x] 테이블 행 배경색을 홀수/짝수 교대 연회색으로 변경하되, 구간명/유형 컬럼에만 기존 regime 색상 유지

## 2) 비목표(Non-Goals)

- `_render_cagr_bar_chart()` 변경
- `calculate_regime_summaries()` 비즈니스 로직 변경
- CAGR/Calmar 컬럼 제거 또는 조건부 표시 (추후 별도 검토)
- 테이블 컬럼 추가/삭제

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **거래수 0 표기**: 해당 구간에서 신규 매매가 없었음에도 거래수/승률/평균보유기간이 `0`으로 표시되어, "전부 실패"처럼 오해할 수 있음. `profit_factor`만 "-" 처리되어 있고 나머지는 숫자 0으로 표시됨
2. **행 배경색**: 전체 행에 regime 유형별 배경색이 적용되어 있어 숫자 가독성이 떨어짐. 구간명/유형만 색상을 유지하고, 나머지는 홀짝 교대 연회색으로 구분하면 가독성 향상

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md`: Streamlit 앱 규칙 (width 파라미터 등)
- `src/qbt/backtest/CLAUDE.md`: 대시보드 앱 아키텍처

## 4) 완료 조건(Definition of Done)

- [x] 거래수 0인 행에서 거래수/승률/평균보유기간/수익팩터가 모두 "-"로 표시
- [x] 홀수/짝수행 교대 연회색 배경 적용 (데이터 컬럼)
- [x] 구간명/유형 컬럼에 기존 regime 색상 유지
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `scripts/backtest/app_single_backtest.py` | `_render_regime_table()` 내 "-" 표기 로직 추가, `_style_regime_rows()` 스타일링 로직 변경 |

### 데이터/결과 영향

- 출력 스키마 변경 없음 (summary.json, CSV 등 영향 없음)
- 대시보드 UI 렌더링만 변경

## 6) 단계별 계획(Phases)

### Phase 1 — 거래수 0 시 "-" 표기 + 테이블 스타일링 변경

**작업 내용**:

- [x] `_render_regime_table()`에서 거래수 0인 행의 지표를 "-"로 치환

현재 코드 (line 755-756):
```python
# profit_factor 0.0은 "-"로 표시
df["profit_factor"] = df["profit_factor"].apply(lambda x: "-" if x == 0.0 else f"{x:.2f}")
```

변경 후:
```python
# 거래수 0인 행: 거래 관련 지표를 "-"로 표시
no_trades_mask = df["total_trades"] == 0
for col in ["total_trades", "win_rate", "avg_holding_days", "profit_factor"]:
    df[col] = df[col].astype(str)
df.loc[no_trades_mask, "total_trades"] = "-"
df.loc[no_trades_mask, "win_rate"] = "-"
df.loc[no_trades_mask, "avg_holding_days"] = "-"
df.loc[no_trades_mask, "profit_factor"] = "-"
# 거래가 있는 행의 profit_factor: 손실 없으면(0.0) "-"
df.loc[~no_trades_mask, "profit_factor"] = df.loc[~no_trades_mask, "profit_factor"].apply(
    lambda x: "-" if x == "0.0" else x
)
```

- [x] `_style_regime_rows()` 변경: 홀짝 교대 배경 + 구간명/유형만 regime 색상

현재 코드 (line 716-724):
```python
def _style_regime_rows(row: pd.Series) -> list[str]:
    """구간 유형별 행 배경색을 반환한다."""
    regime_type_col = _REGIME_COLUMN_RENAME.get("regime_type", "유형")
    regime_display = row.get(regime_type_col, "")
    for eng_type, kor_display in _REGIME_TYPE_DISPLAY.items():
        if regime_display == kor_display:
            bg = _REGIME_BG_COLORS.get(eng_type, "")
            return [f"background-color: {bg}"] * len(row)
    return [""] * len(row)
```

변경 후:
```python
_ALT_ROW_BG = "background-color: rgba(128, 128, 128, 0.06)"

def _style_regime_rows(row: pd.Series) -> list[str]:
    """구간명/유형은 regime 색상, 나머지는 홀짝 교대 연회색 배경을 반환한다."""
    name_col = _REGIME_COLUMN_RENAME.get("name", "구간명")
    regime_type_col = _REGIME_COLUMN_RENAME.get("regime_type", "유형")

    # regime 색상 결정
    regime_display = row.get(regime_type_col, "")
    regime_bg = ""
    for eng_type, kor_display in _REGIME_TYPE_DISPLAY.items():
        if regime_display == kor_display:
            regime_bg = f"background-color: {_REGIME_BG_COLORS[eng_type]}"
            break

    # 홀수행 교대 배경
    is_odd = int(row.name) % 2 == 1  # type: ignore[arg-type]
    alt_bg = _ALT_ROW_BG if is_odd else ""

    styles: list[str] = []
    for col in row.index:
        if col in (name_col, regime_type_col):
            styles.append(regime_bg)
        else:
            styles.append(alt_bg)
    return styles
```

---

### 마지막 Phase — 포맷 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=432, failed=0, skipped=0)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. 대시보드 / 시장 구간별 테이블 가독성 개선 (거래수 0 표기 + 행 색상)
2. 대시보드 / regime 테이블 UI 개선: 거래없는 구간 "-" 표기 및 홀짝행 배경색 적용
3. 대시보드 / 구간별 분석 테이블 표시 개선 (거래 관련 지표 "-" 표기 + 교대 배경색)
4. 대시보드 / 시장 구간 테이블 렌더링 개선 (zero-trade "-" + alternating row bg)
5. 대시보드 / regime 테이블 가독성 향상: 거래수 0 → "-" 표기, 홀짝행 연회색 구분

## 7) 리스크(Risks)

- pandas Styler의 `row.name`이 DataFrame 인덱스 기반이므로, 인덱스가 0부터 연속이 아닌 경우 홀짝 판별 오류 가능 → `reset_index()` 불필요 (DataFrame 생성 직후라 기본 0-based 인덱스)
- 컬럼을 문자열로 변환 후 정렬/필터링은 불가하나, 이 테이블은 표시 전용이므로 문제 없음

## 8) 메모(Notes)

- 이 변경은 `app_single_backtest.py`의 렌더링 함수만 수정하며, 비즈니스 로직/데이터 영향 없음
- `_render_cagr_bar_chart()`는 변경하지 않음 (기존 regime 색상 유지)
- Phase 0 불필요: 핵심 인바리언트/정책 변경 없는 UI 렌더링 변경

### 진행 로그 (KST)

- 2026-03-03 01:30: 계획서 초안 작성
- 2026-03-03 01:40: 구현 완료 (Phase 1 + 마지막 Phase), validate_project.py 통과 (432 passed, 0 failed, 0 skipped)

---
