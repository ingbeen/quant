# Implementation Plan: 포트폴리오 실험 F-6H / Q-2-2X / Q-2-2XH 제거

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-20 (KST)
**마지막 업데이트**: 2026-04-20 (KST)
**관련 범위**: src/qbt/backtest
**관련 문서**: [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [scripts/CLAUDE.md](../../scripts/CLAUDE.md)

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

- [ ] `PORTFOLIO_CONFIGS`에서 F-6H, Q-2-2X, Q-2-2XH 실험을 제거한다
- [ ] 실험 제거로 인해 불필요해진 import를 정리한다 (`TQQQ_SYNTHETIC_DATA_PATH`, `UGL_DATA_PATH`, `UBT_DATA_PATH`)
- [ ] `portfolio_configs.py` 모듈 docstring을 남은 실험(D, Q-2, Q-2-2XS)에 맞춰 업데이트한다

## 2) 비목표(Non-Goals)

- `storage/results/portfolio/portfolio_f6h/`, `portfolio_q2_2x/`, `portfolio_q2_2xh/` 디렉토리의 실제 삭제 (사용자가 직접 수행)
- 다른 실험 구성 변경 (D-1, Q-2, Q-2-2XS는 그대로 유지)
- `--experiment` CLI choices 로직 변경 (자동으로 `PORTFOLIO_CONFIGS` 기준 갱신되므로 코드 수정 불필요)
- 대시보드 코드 변경 (`_discover_experiments()`가 결과 디렉토리 기반으로 자동 탐색)
- 테스트 추가/변경 (실험 목록은 config 파일의 SSoT — 테스트 영향 없음)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 사용자가 F-6H (TQQQ 합성 데이터 포함), Q-2-2X (2x 전자산 레버리지), Q-2-2XH (2x 혼합 레버리지) 실험을 더 이상 유지하지 않기로 결정
- 실험 수를 줄여 실행 시간 단축 및 결과 혼잡도 감소
- 남은 실험(D-1, Q-2, Q-2-2XS)으로도 비교 목적 달성 가능

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md) (영향 확인 목적)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] `portfolio_configs.py`에서 `_CONFIG_F6H`, `_CONFIG_Q2_2X`, `_CONFIG_Q2_2XH` 블록 삭제
- [ ] `PORTFOLIO_CONFIGS` 리스트에서 위 3개 항목 제거 (남는 순서: `_CONFIG_D1`, `_CONFIG_Q2`, `_CONFIG_Q2_2XS`)
- [ ] 사용되지 않게 된 import (`TQQQ_SYNTHETIC_DATA_PATH`, `UGL_DATA_PATH`, `UBT_DATA_PATH`) 제거
- [ ] 모듈 docstring의 실험 설명을 남은 실험 기준으로 축약 (F 시리즈 섹션 제거, Q 시리즈 레버리지 변형 언급 축소)
- [ ] 섹션 구분 주석 정리 (더 이상 해당 없는 블록 주석 제거)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 필요한 문서 업데이트 (README.md / `docs/COMMANDS.md` / CLAUDE.md — 각각 변경 여부 명시)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [src/qbt/backtest/portfolio_configs.py](../../src/qbt/backtest/portfolio_configs.py)
  - `_CONFIG_F6H`, `_CONFIG_Q2_2X`, `_CONFIG_Q2_2XH` 블록 3개 삭제
  - `PORTFOLIO_CONFIGS` 리스트 항목 3개 제거
  - `TQQQ_SYNTHETIC_DATA_PATH`, `UGL_DATA_PATH`, `UBT_DATA_PATH` import 제거
  - 모듈 docstring 및 섹션 주석 축약
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (실행 명령어 동일 — `--experiment` choices는 런타임에 `PORTFOLIO_CONFIGS` 기준으로 자동 결정)
- CLAUDE.md: 변경 없음 (실험 목록은 본문에 나열되지 않고 "포트폴리오 실험 구성·자산 비중은 변경 빈도가 매우 높으므로 본 문서에 직접 나열하지 않는다" 원칙 유지)

### 데이터/결과 영향

- 출력 스키마: 변경 없음
- 저장된 결과 디렉토리: `storage/results/portfolio/portfolio_f6h/`, `portfolio_q2_2x/`, `portfolio_q2_2xh/`는 그대로 남음
  - **사용자 조치 필요**: 대시보드 `_discover_experiments()`가 `summary.json` 존재 여부로 탭 생성하므로 해당 디렉토리를 삭제하지 않으면 탭에 계속 표시됨
  - 삭제 명령어(사용자가 직접 판단 후 실행): `rm -rf storage/results/portfolio/portfolio_f6h storage/results/portfolio/portfolio_q2_2x storage/results/portfolio/portfolio_q2_2xh`
- 다음 실행 시: `run_portfolio_backtest.py`는 남은 3개 실험만 실행. QQQ 벤치마크의 `min_start_date`는 남은 실험 기준으로 재산출됨 (이전 plan 결과)

## 6) 단계별 계획(Phases)

### Phase 1 — `portfolio_configs.py` 수정

**작업 내용**:

- [ ] 모듈 docstring 수정 (F 시리즈 섹션 삭제, Q 시리즈 설명 축약)
- [ ] import 섹션에서 `TQQQ_SYNTHETIC_DATA_PATH`, `UGL_DATA_PATH`, `UBT_DATA_PATH` 제거
- [ ] `_CONFIG_F6H` 블록 전체 삭제
- [ ] `_CONFIG_Q2_2X` 블록 전체 삭제
- [ ] `_CONFIG_Q2_2XH` 블록 전체 삭제
- [ ] Q 시리즈 섹션 헤더 주석 축약 (레버리지 변형 관련 설명 간결화)
- [ ] `PORTFOLIO_CONFIGS` 리스트에서 세 항목 제거, 남는 순서: `[_CONFIG_D1, _CONFIG_Q2, _CONFIG_Q2_2XS]`

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] CLAUDE.md 문구 재확인 (실험 목록 직접 나열 없음 — 변경 불요)
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 실험 F-6H·Q-2-2X·Q-2-2XH 제거
2. 백테스트 / PORTFOLIO_CONFIGS 정리 (레버리지/TQQQ 실험 3종 제거)
3. 백테스트 / 포트폴리오 실험 목록 축소 — D-1/Q-2/Q-2-2XS만 유지
4. 백테스트 / 비활성 포트폴리오 실험 3종 제거 및 미사용 import 정리
5. 백테스트 / 포트폴리오 config 슬림화 (F-6H, Q-2-2X, Q-2-2XH 삭제)

## 7) 리스크(Risks)

- 남은 결과 디렉토리로 인해 대시보드에 삭제된 실험 탭이 계속 표시될 수 있음 → 사용자에게 안내, 본인이 판단하여 삭제
- 다른 코드(특히 live 패키지)가 제거되는 심볼을 직접 참조할 가능성 — 낮지만 validate_project.py의 pyright로 확인

## 8) 메모(Notes)

- 제거 대상 실험이 참조하던 자산 데이터 경로 중 Q-2-2XS가 여전히 사용하는 것(SSO/QLD/GLD/TLT/SPY/QQQ)은 import 유지
- Q-2-2XS가 UGL/UBT를 쓰지 않기 때문에 `UGL_DATA_PATH`, `UBT_DATA_PATH` import는 제거 가능
- F-6H 제거로 `TQQQ_SYNTHETIC_DATA_PATH` import도 제거 가능

### 진행 로그 (KST)

- 2026-04-20: 계획서 초안 작성
