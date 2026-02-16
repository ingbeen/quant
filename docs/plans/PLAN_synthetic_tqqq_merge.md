# Implementation Plan: 합성+실제 TQQQ 병합 데이터 생성

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

**작성일**: 2026-02-16 20:30
**마지막 업데이트**: 2026-02-16 21:00
**관련 범위**: tqqq, scripts
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [x] `generate_synthetic.py`를 SoftPlus 동적 스프레드 모델 기반으로 전환
- [x] 합성 TQQQ(1999-03-10 ~ 2010-02-10)와 실제 TQQQ(2010-02-11 ~ 현재)를 가격 스케일링 후 병합
- [x] 병합된 완전한 시계열을 `storage/stock/TQQQ_synthetic_max.csv`에 저장

## 2) 비목표(Non-Goals)

- 시뮬레이션 엔진(`simulate()`) 수정
- 새로운 비용 모델 연구 또는 파라미터 튜닝
- 대시보드/시각화 변경
- 백테스트 전략 코드 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- SoftPlus 동적 스프레드 모델(a=-6.1, b=0.37)이 검증 완료됨 (RMSE 1.05%, 과최적화 진단 통과)
- 기존 `generate_synthetic.py`는 고정 스프레드(`DEFAULT_FUNDING_SPREAD = 0.0034`)로 전체 기간 합성 데이터만 생성
- 2010년 이후 구간은 실제 TQQQ 데이터가 존재하므로, 합성 데이터 대신 실제 데이터를 사용하는 것이 정확
- 1999년부터의 완전한 TQQQ 시계열이 필요 (향후 백테스트 활용)

### 데이터 현황

| 데이터 | 기간 | 비고 |
|--------|------|------|
| QQQ | 1999-03-10 ~ 현재 | 기초자산 |
| TQQQ (실제) | 2010-02-11 ~ 현재 | ETF 상장일 |
| FFR (금리) | 1999-01 ~ 현재 | 전 기간 커버 |
| Expense Ratio | **2010-02** ~ 현재 | 1999~2010 미존재 |

### 핵심 설계 결정

**Expense Ratio 1999~2010 처리**: TQQQ 상장 초기 운용비율(0.0095 = 0.95%)을 고정값으로 적용. 명시적 상수 `DEFAULT_PRE_LISTING_EXPENSE_RATIO`로 정의하여 투명성 확보.

**접합점 처리**: 가격 스케일링 방식 채택.
- simulate()로 QQQ 전체 기간을 시뮬레이션
- 접합일(2010-02-11)에서 시뮬레이션 종가와 실제 TQQQ 종가의 비율(scale_factor)을 계산
- 합성 구간(< 접합일) 전체 가격에 scale_factor 적용
- 일일 수익률이 완벽히 보존되면서 가격이 연속적으로 이어짐

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 프로젝트 공통 규칙
- `src/qbt/tqqq/CLAUDE.md`: 시뮬레이션 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙
- `src/qbt/utils/CLAUDE.md`: 유틸리티 규칙
- `tests/CLAUDE.md`: 테스트 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `generate_synthetic.py`가 SoftPlus 동적 스프레드로 합성 데이터 생성
- [x] 합성 구간(~2010-02-10)이 가격 스케일링되어 실제 TQQQ 첫날과 연속
- [x] 합성 + 실제 TQQQ가 병합되어 `TQQQ_synthetic_max.csv`에 저장
- [x] 운용비율 미존재 구간(1999~2010)에 대한 fallback 처리
- [x] 메타데이터(`meta.json`)에 합성/실제 구분 정보 포함
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=271, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/tqqq/constants.py` | `DEFAULT_PRE_LISTING_EXPENSE_RATIO` 상수 추가 + `__all__` 업데이트 |
| `scripts/tqqq/generate_synthetic.py` | SoftPlus 적용, 실제 TQQQ 병합, 가격 스케일링, 메타데이터 저장 |

### 재사용하는 기존 함수 (수정 없음)

| 함수 | 위치 | 용도 |
|------|------|------|
| `simulate()` | `simulation.py:706` | QQQ → 합성 TQQQ 시뮬레이션 |
| `build_monthly_spread_map()` | `simulation.py:178` | FFR → softplus 월별 스프레드 맵 |
| `create_expense_dict()` | `data_loader.py:265` | expense_df → dict 변환 |
| `load_stock_data()` | `utils/data_loader.py` | QQQ/TQQQ CSV 로딩 |
| `load_ffr_data()` | `tqqq/data_loader.py` | FFR 데이터 로딩 |
| `load_expense_ratio_data()` | `tqqq/data_loader.py` | Expense Ratio 데이터 로딩 |
| `save_metadata()` | `utils/meta_manager.py` | 메타데이터 저장 |

### 데이터/결과 영향

- 출력 파일: `storage/stock/TQQQ_synthetic_max.csv` (기존 파일 덮어쓰기)
  - 기존: 고정 스프레드로 전체 기간 합성 (1999-03-10 ~ 2025-11-28)
  - 변경: SoftPlus 합성(1999-03-10 ~ 2010-02-10) + 실제 TQQQ(2010-02-11 ~ 현재)
- 스키마 변경 없음: 기존 OHLCV 동일

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 추가 + 스크립트 개선

**작업 내용**:

#### 1-1. constants.py 상수 추가

- [x] `DEFAULT_PRE_LISTING_EXPENSE_RATIO` 상수 추가 (0.0095 = 0.95%)
- [x] `__all__`에 추가

```python
# 비용 모델 파라미터 섹션에 추가
DEFAULT_PRE_LISTING_EXPENSE_RATIO: Final = 0.0095  # TQQQ 상장 이전 운용비율 가정값 (0.0095 = 0.95%)
```

#### 1-2. generate_synthetic.py 전면 개선

- [x] docstring 업데이트 (합성+실제 병합 설명)
- [x] SoftPlus 스프레드 맵 생성 적용
- [x] expense_dict 확장 로직 구현
- [x] 시뮬레이션 실행 (softplus spread + 확장된 expense_dict)
- [x] 접합점 계산 및 가격 스케일링
- [x] 합성 + 실제 TQQQ 병합
- [x] CSV 저장 + 메타데이터 저장
- [x] 결과 출력 로그

**핵심 로직 흐름**:

```
1. 데이터 로드: QQQ, TQQQ(실제), FFR, Expense Ratio
2. softplus 스프레드 맵 생성 (build_monthly_spread_map)
3. expense_dict 확장:
   - create_expense_dict(expense_df)로 기존 dict 생성
   - 1999-01 ~ expense_df 최초월 직전까지 DEFAULT_PRE_LISTING_EXPENSE_RATIO로 채움
4. simulate() 실행:
   - underlying_df=qqq_df (전체 기간)
   - funding_spread=spread_map (softplus dict)
   - expense_dict=확장된 expense_dict (사전 구축된 dict 전달)
   - ffr_df=ffr_df
   - initial_price=DEFAULT_SYNTHETIC_INITIAL_PRICE
5. 접합점 계산:
   - overlap_date = tqqq_df[COL_DATE].min() (= 2010-02-11)
   - synthetic_at_overlap = synthetic_df에서 overlap_date의 Close 값
   - actual_at_overlap = tqqq_df에서 overlap_date의 Close 값
   - scale_factor = actual_at_overlap / synthetic_at_overlap
6. 합성 구간 스케일링:
   - synthetic_df[date < overlap_date]의 PRICE_COLUMNS × scale_factor
7. 병합:
   - pd.concat([스케일링된 합성(< overlap_date), 실제 TQQQ(>= overlap_date)])
   - 날짜순 정렬, 인덱스 리셋
8. CSV 저장 (가격 컬럼 소수점 6자리 라운딩)
9. 메타데이터 저장 (tqqq_synthetic)
```

**expense_dict 확장 구현**:

```python
expense_dict = create_expense_dict(expense_df)
# expense_df 최초월 직전까지 고정값 채우기
earliest_month = min(expense_dict.keys())  # "2010-02"
# 1999-01 ~ 2010-01 범위의 모든 "YYYY-MM" 키에 DEFAULT_PRE_LISTING_EXPENSE_RATIO 할당
```

**simulate() 호출 시 핵심 포인트**:

- `expense_dict` 파라미터를 명시적으로 전달하면 simulate()가 내부에서 expense_df를 dict로 변환하지 않고 직접 사용 (simulation.py:786-791)
- `ffr_df`는 1999-01부터 커버하므로 validate_ffr_coverage() 통과
- `funding_spread`에 softplus spread_map(dict) 전달

**메타데이터 구조**:

```python
metadata = {
    "execution_params": {
        "leverage": DEFAULT_LEVERAGE_MULTIPLIER,
        "funding_spread_mode": "softplus",
        "softplus_a": DEFAULT_SOFTPLUS_A,
        "softplus_b": DEFAULT_SOFTPLUS_B,
        "pre_listing_expense_ratio": DEFAULT_PRE_LISTING_EXPENSE_RATIO,
    },
    "synthetic_period": {
        "start_date": str(합성 시작일),
        "end_date": str(접합일 전날),
        "total_days": int,
        "scale_factor": float,
    },
    "actual_period": {
        "start_date": str(접합일),
        "end_date": str(실제 TQQQ 마지막일),
        "total_days": int,
    },
    "merged_summary": {
        "total_days": int,
        "initial_price": float,
        "final_price": float,
        "cumulative_return_pct": float,
    },
    "csv_info": {
        "path": str(TQQQ_SYNTHETIC_PATH),
        "row_count": int,
        "file_size_bytes": int,
    },
}
```

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 스크립트 실행하여 생성된 CSV 검증
  - 접합점 전후 가격 연속성 확인
  - 합성/실제 구간 행 수 확인
  - 메타데이터 저장 확인
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=271, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / softplus 동적 스프레드 기반 합성 TQQQ 생성 및 실제 데이터 병합
2. TQQQ시뮬레이션 / 1999년부터의 합성+실제 TQQQ 병합 파이프라인 구축
3. TQQQ시뮬레이션 / generate_synthetic을 softplus 모델 + 실제 TQQQ 병합으로 전환
4. TQQQ시뮬레이션 / QQQ 기반 합성(1999~2010) + 실제 TQQQ(2010~) 가격 스케일링 병합
5. TQQQ시뮬레이션 / 합성 TQQQ에 softplus 스프레드 적용하고 실제 데이터와 병합

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| Pre-2010 expense ratio 가정이 실제와 상이 | TQQQ 초기 운용비율(0.95%) 사용으로 합리적 근사. 일일 영향은 0.95%/252 = 0.004%로 미미 |
| 접합점 가격 불연속 | 비례 스케일링으로 일일 수익률 완벽 보존. 접합일은 실제 TQQQ 데이터로 대체 |
| simulate()의 expense fallback이 12개월 제한 | expense_dict를 사전 구축하여 직접 전달하므로 fallback 불필요 (우회) |

## 8) 메모(Notes)

- 검증된 SoftPlus 파라미터: a=-6.1, b=0.37 (RMSE 1.05%, 과최적화 진단 통과)
- 기존 고정 스프레드(0.34%) 대비 RMSE 48% 개선
- 워크포워드 완전 고정(a,b) stitched RMSE: 1.36% (in-sample 1.05%와 근접)
- expense_df 최초 데이터: 2010-02, 값 0.0095 (0.95%)
- TQQQ 실제 데이터 첫 종가: 0.206396 (2010-02-11, 역분할 반영)

### 진행 로그 (KST)

- 2026-02-16 20:30: 계획서 초안 작성
- 2026-02-16 21:00: 전체 Phase 완료 (passed=271, failed=0, skipped=0)

---
