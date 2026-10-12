# Implementation Plan: 실행 이력(meta.json) 삭제 · utils 정리 — 병렬 실행기 · 표 출력 · 로거 · CLI 핸들러 · 품질 검증 스크립트

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-11 21:44
**마지막 업데이트**: 2026-10-12 18:17
**관련 범위**: utils(`meta_manager.py` · `parallel_executor.py` · `formatting.py` · `logger.py` · `cli_helpers.py` · `data_loader.py` · `__init__.py`), `common_constants.py`, scripts(실행 이력을 쓰던 러너 · 생성 스크립트 10개), `validate_project.py`, backtest(`engines/backtest_engine.py` 의 워커 수 계산 3줄), tests
**관련 문서**: `src/qbt/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`(19절 11단계 tqqq · utils 줄)

---

## 1) 목표(Goal)

- [x] 목표 1: 읽는 코드가 없는 실행 이력 기능(`meta.json` · `meta_manager`)을 통째로 지운다 (점검 보고서 결정 6 · 5-10 · 2-21 · 5-9 · 6-8 의 남은 부분 · 6-9 ⑥ · 13-B D13)
- [x] 목표 2: 병렬 실행기를 함수 하나로 줄이고, 워커 하나가 실패하면 아직 시작하지 않은 작업을 돌리지 않고 멈추게 한다 (5-8 의 `execute_parallel` · 2-3 · 2-6 · 8-6)
- [x] 목표 3: 표 출력의 헤더와 행이 한 칸 어긋나는 것을 없앤다 — 출력 메서드를 하나로 (2-14 · 6-5 의 `formatting.py`)
- [x] 목표 4: 테스트만 타던 대체 경로를 지운다 — 로거 레벨 인자 · CLI 핸들러의 로거 대체 (12-7 · 6-5 의 `logger.py` · 6-18)
- [x] 목표 5: CLI 스크립트를 저장소 루트 밖에서 돌리면 무엇을 해야 하는지 알려 주고 멈춘다 (2-24 · 결정 9)
- [x] 목표 6: 품질 검증 스크립트의 개수 파싱을 줄인다 — 실패인데 `failed=0` 으로 찍히는 모양을 함께 없앤다 (2-15 · 12-10)
- [x] 목표 7: utils 모듈의 문법 설명 주석을 지우고 「왜」만 남긴다 (7-14 · 6-6 의 `utils/__init__.py`)
- [x] 목표 8: 결과 파일이 바뀌지 않는다 — `meta.json` 삭제 말고는 러너 여섯 · 생성 스크립트 다섯의 출력이 그대로다

## 2) 비목표(Non-Goals)

- **tqqq 시뮬레이션 데드코드 · 생성 스크립트의 저장 함수 공용화(5-3 · 7-3) · 반올림 상수 이동(결정 10) · 스프레드 랩(결정 5)** — 11단계 tqqq · utils 줄의 나머지다. 다음 계획서로 한다(그 줄을 한 계획서로 묶으면 항목 번호가 약 40개라 코드 리뷰가 한 번에 볼 범위를 넘는다)
- **`backtest/__init__.py` · `strategies/__init__.py` 의 재노출(6-6 의 나머지)** — 11단계 backtest
- **`src/qbt/backtest/analysis.py` 의 「학습 포인트」 두 블록** — 7-14 의 대상(utils 여섯 모듈 · `common_constants.py`) 밖이다. 11단계 backtest 에서 같은 파일을 고칠 때 함께 한다
- **대시보드(`app_*.py`)의 실행 위치 확인** — 결정 9 는 CLI 공통 핸들러만이다. 대시보드 일곱은 그 핸들러를 쓰지 않는다
- **`freezegun` 의존성 제거** — 이 계획서 뒤에 쓰는 테스트가 0 이 되지만 `pyproject.toml` · lock 파일은 건드리지 않는다(환경 변경은 사용자 몫). 완료 보고에 적는다
- **pytest 의 `error::RuntimeWarning`(결정 15) · `enable_numpy_warnings` 픽스처 · 쓰이지 않는 마커(6-9 ① ③) · 워커 캐시 테스트의 공백(6-17)** — 11단계 tests
- **안내 문서 경량화(18-B · 18-D)와 `COMMANDS.md` 의 `--cov` 설명(13-B D1)** — 12단계. 이번에는 이 변경으로 거짓이 되는 문장만 고친다
- **`ClickableFormatter._find_project_root` 의 「못 찾으면 실행 위치」 대체** — 점검 보고서에 없다
- **대용 시계열의 이음매 날짜 · 스케일을 로그로 남기기** — 실행 이력에만 있던 값이다. 「실물 첫 거래일 종가 ÷ 대용의 그날 종가」로 언제든 다시 계산된다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 11단계(영역별 데드코드 · 단일 출처)의 tqqq · utils 줄 가운데 **utils 와 실행 이력** 부분이다. B 절 결정 20건은 2026-10-09 에 모두 추천안대로 확정됐다(결정 6 = 기능 통째 삭제, 결정 9 = CLI 공통 핸들러에 확인)
- 대상마다 지금 무엇이 문제인가 (2026-10-11 저장소 사본에서 다시 쟀다. 스크래치 `step11a/`)

| 항목 | 지금 | 재현 |
|---|---|---|
| 결정 6 실행 이력 | 스크립트 10개가 `save_metadata` 로 `storage/results/meta.json` 에 이력을 쓰는데 읽는 코드가 0 이다(src · scripts 의 `json.load` 는 `meta_manager` 자신과 대시보드 셋의 `summary.json` 뿐) | 파일의 키 23개 가운데 지금 쓰는 스크립트가 있는 것은 10개이고 13개는 없어진 스크립트의 것이다. `portfolio_backtest` 이력 5칸은 모두 같은 실행(2026-10-11 12:55:22 – 12:55:32)의 실험 5개다 |
| 2-3 병렬 실행기의 실패 전파 | 워커 하나가 예외를 내도 `with ProcessPoolExecutor` 가 남은 작업을 다 돌린 뒤에야 전파한다 | 작업 10개(첫 작업은 바로 실패, 나머지는 0.5초) · 워커 2개: 전파까지 2.87 – 2.91초, 나머지 9개가 모두 실행됨(3회 모두) |
| 2-6 워커 수 | `run_grid_search` 가 `os.cpu_count() - 1` 을 그대로 넘겨 CPU 가 1개면 `max_workers=0` 으로 죽는다. 그리드 러너 둘은 `max(1, …)` 로 따로 막았다 — 같은 계산이 세 곳이다 | `max_workers=0` → `ValueError: max_workers must be greater than 0`. CPU 수를 1 로 둔 그리드 서치 테스트가 지금 코드에서 실패한다 |
| 5-8 `execute_parallel` | 운영 코드는 키워드 인자 판(`execute_parallel_with_kwargs`)만 부른다(3곳 — `run_grid_search` · 그리드 러너 둘). 단일 인자 판은 그 래퍼와 테스트 5곳만 쓴다 | 호출처 집계 |
| 2-14 표 출력 | 헤더는 `print_header`, 행은 `print_row` 가 찍는다. 로그 포맷이 함수 이름을 넣어 두 줄의 시작 위치가 3칸 다르고, 보정용 공백 2칸을 더해도 1칸이 어긋난다 | 실제 로거 포맷으로 찍은 표: 헤더 첫 칸 83열 · 행 첫 칸 82열 |
| 12-7 · 6-18 로거 대체 경로 | `cli_exception_handler` 는 모듈에 `logger` 가 없으면 기본 로거로 바꾸고 경고한다. 스크립트 12개는 모두 `logger` 가 있어 이 경로는 테스트만 탄다 — 그런데 예외 테스트 다섯이 모두 이 대체 경로로만 돈다(테스트 모듈에 `logger` 가 없다). `setup_logger` 의 `level` 인자도 테스트만 넘긴다 | 호출처 집계 — `level` 을 넘기는 곳은 `test_logger.py` 2곳 |
| 2-24 실행 위치 | `STORAGE_DIR = Path("storage")` 가 실행 위치 기준이다 | 다른 폴더에서 단일 백테스트 러너를 돌리면 「파일을 찾을 수 없습니다: storage/stock/QQQ_max.csv」로 멈춘다 — 멈추기는 하지만 무엇을 해야 하는지 말하지 않는다. 다운로더는 읽기 전에 `storage/stock` 을 만들므로(`mkdir(parents=True)`) 받은 시세를 실행 위치 아래에 새로 저장한다(코드로 확인, 네트워크를 쓰므로 돌리지 않았다) |
| 2-15 · 12-10 품질 검증 스크립트 | Ruff · PyRight · Pytest 의 출력에서 개수를 손으로 파싱하고, 파싱에 실패하면 1 로 둔다 | 수집 단계에서 죽는 테스트 파일 하나를 둔 사본: pytest 요약 줄은 「1 error in 1.29s」인데 스크립트는 `[FAIL] Pytest 실패 (passed=0, failed=0, skipped=0)` 를 찍는다 — 실패한 실행의 줄에 `failed=0` 이 나온다 |
| 7-14 설명용 주석 | utils 여섯 모듈과 `common_constants.py` 에 「학습 포인트」 블록과 코드를 그대로 옮긴 줄 주석이 있다(전역 주석 규칙의 「코드를 인간어로 번역」) | 「학습 포인트」 20곳 — `logger.py` 6 · `formatting.py` 5 · `data_loader.py` · `meta_manager.py` · `cli_helpers.py` · `parallel_executor.py` 각 2 · `common_constants.py` 1 |

- 운영 스크립트의 사실(읽기만 함) — `@cli_exception_handler` 를 쓰는 스크립트 12개는 모두 `logger = get_logger(__name__)` 를 모듈 수준에 둔다. `TableLogger` 의 운영 호출 10곳은 모두 `print_table` 이고 `indent` · `Align.CENTER` 를 넘기는 곳은 0 이다. `qbt.utils` 패키지에서 가져오는 이름은 `get_logger`(24곳)뿐이다

### 설계 결정

1. **실행 이력 기능을 통째로 지운다** (결정 6 (가))
   - 지우는 것: `src/qbt/utils/meta_manager.py`, `common_constants.META_JSON_PATH`, 스크립트 10개의 import · 메타데이터 조립 · 저장 호출 · 그 로그, `tests/qbt/test_meta_manager.py`, `storage/results/meta.json`
   - 메타데이터를 만들려고만 있던 코드도 함께 지운다(이 변경이 만든 고아) — 단일 백테스트 러너 저장 함수 넷의 경로 반환, 대용 · 장기 대체 생성 스크립트의 `_describe` 와 `outputs` 목록 · 저장 함수의 반환값 · 그 때문에만 부르던 `compute_seam_scale`, 대체-실물 비교 스크립트의 「자를 실물 파일 이름」 칸, 일별 비교 스크립트의 중복 필드(5-9)
   - 테스트 픽스처 둘(`mock_results_dir` · `mock_storage_paths`)도 지운다(6-9 ⑥) — 경로 상수 패치 가운데 효과가 있던 것은 `meta_manager.META_JSON_PATH` 하나였다(src · scripts 가 경로 상수를 실행 시점에 속성으로 읽는 곳 0). 통합 테스트 둘은 `tmp_path` 를 직접 쓰고, 메타데이터 시각을 고정하던 `freeze_time` 도 뗀다
   - 잃는 것: 스크립트를 언제 어떤 인자로 돌렸는지의 기록, 대용 시계열의 이음매 날짜 · 스케일. 파라미터는 각 `summary.json` 에, 생성 시점은 git 이력에 있고, 이음매 스케일은 다시 계산된다(비목표)
2. **병렬 실행기는 `execute_parallel_with_kwargs` 하나다** (5-8 · 2-3 · 2-6 · 8-6)
   - 단일 인자 판(`execute_parallel`)과 그 사이의 `_unwrap_kwargs` 를 지우고, `executor.submit(func, **kwargs)` 로 바로 넘긴다. 이름은 그대로 둔다 — 운영 호출부 3곳이 안 바뀐다
   - 워커가 예외를 내면 `executor.shutdown(cancel_futures=True)` 뒤 전파한다 — 아직 워커에 넘어가지 않은 작업을 취소한다(이미 넘어간 작업 — 워커 수 + 몇 개 — 은 끝까지 돈다)
   - **점검 보고서와 다르게 가는 것** — 보고서의 제안은 `shutdown(wait=False, cancel_futures=True)` 한 줄이었다. 사본에서 재니 그 형태는 예외를 0.05 – 0.07초에 전파하지만 **아무것도 취소하지 않는다**: 나머지 9개가 뒤에서 모두 실행됐다(3회 모두). `with` 블록의 종료가 `shutdown()` 을 한 번 더 불러 취소 요청을 되돌리기 때문이다. `wait` 를 기본값(True)으로 두면 취소가 처리된 뒤에 돌아온다 — 전파까지 1.58 – 1.61초, 실행된 나머지 작업은 9개 중 5개(워커 2개) · 3개(워커 1개)
   - 워커 수 기본값을 「CPU 수 − 1, 최소 1」로 두고 호출부 3곳(`run_grid_search` · 그리드 러너 둘)의 계산을 지운다. 결과는 입력 순서로 돌려주므로 워커 수는 결과를 바꾸지 않는다
3. **표 출력은 `print_table` 하나다** (2-14 · 6-5)
   - 헤더 · 행 · 구분선을 `print_table` 한 함수 안에서 찍는다 — 로그 포맷의 함수 이름이 같아져 시작 위치가 맞고, 보정용 공백이 필요 없다
   - `print_header` · `print_row` · `print_footer` 는 지운다(운영 호출 0). 행 길이 검사는 그대로이고, 이제 어느 줄도 찍기 전에 한다(전에는 헤더를 찍은 뒤 멈췄다)
   - 쓰이지 않는 `Align.CENTER` 와 `indent` 인자를 지운다(늘 2칸)
4. **로거 · CLI 핸들러** (12-7 · 6-5 · 6-18 · 2-24)
   - `setup_logger` 의 `level` 인자를 지운다(늘 DEBUG — 모르는 레벨 이름을 DEBUG 로 바꾸던 대체도 함께 없어진다)
   - `cli_exception_handler` 는 함수가 정의된 모듈의 `logger` 를 직접 읽는다(`sys.modules[func.__module__].logger`). 없으면 AttributeError 로 멈춘다(스크립트의 규약 위반). 테스트 모듈에 `logger` 를 두어 테스트가 실제 경로를 타게 한다 (2026-10-11 조정 — 함수의 전역 이름공간 `func.__globals__["logger"]` 에서 읽고 없으면 KeyError, 코드 리뷰 1회차, 진행 로그)
   - 같은 핸들러가 실행 전에 `STORAGE_DIR` 폴더가 실행 위치에 있는지 본다 — 없으면 함수를 실행하지 않고 「저장소 루트에서 실행하세요 — 현재 위치(…)에 'storage' 폴더가 없습니다」로 멈춘다(종료 코드 1). `STORAGE_DIR` 를 `__file__` 기준으로 바꾸지 않는 까닭은 결과 파일의 경로 문자열(`summary.json` 등)이 절대경로가 돼 공개 저장소에 로컬 경로가 실리기 때문이다 — 그 이유를 상수 주석에 남긴다
5. **`qbt.utils` 패키지는 `get_logger` 만 다시 내보낸다** (6-6 의 utils 부분)
   - 나머지 재노출(`setup_logger` · `Align` · `extract_overlap_period` · 병렬 실행 함수)은 쓰는 곳이 0 이다. 지우면 `import qbt.utils` 가 pandas 와 프로세스 풀 모듈을 끌어오지 않고(사본 실측 0.243초 → 0.005초), `parallel_executor` 가 패키지 초기화 순서에 기대던 것(8-6)도 없어진다
6. **품질 검증 스크립트** (2-15 · 12-10)
   - Ruff · PyRight 의 개수 파싱과 「총 오류/경고」 줄을 지운다 — 두 도구가 자기 출력에 개수를 찍고, 통과 판정은 종료 코드로 한다
   - **점검 보고서와 다르게 가는 것** — 보고서는 개수 파싱을 모두 지우자고 했다. Pytest 의 `passed / failed / skipped` 줄은 남긴다: 계획서의 Validation 줄이 그 세 수를 그대로 받아 적고(Done 조건), 지우면 pytest 요약 줄에서 「없는 것 = 0」으로 추론해 적어야 한다. 대신 **통과한 실행에만** 찍는다 — 종료 코드 0 이면 `failed` 는 0 이고 `passed` · `skipped` 는 마지막 요약 줄에서 읽는다. 실패한 실행은 개수 없이 `[FAIL]` 만 찍는다(수집 오류 때 `failed=0` 이 찍히던 모양이 없어진다)
7. **설명용 주석** (7-14)
   - 「학습 포인트」 블록과 코드를 그대로 옮긴 줄 주석을 지운다. 「왜」(spawn 을 쓰는 이유 · 전파를 끄는 이유 · 실행 위치 기준 경로의 이유)는 현재형으로 남긴다. 「연간 영업일」 아래 365.25 가 있던 주석(13-C C7 의 `common_constants.py`)과 없는 호출부를 든 예시(같은 항목의 `parallel_executor.py`)는 같은 자리라 함께 고친다
   - 실행 코드는 바뀌지 않는다 — 주석 · docstring 을 뺀 AST 로 확인한다(설계 결정 1 – 6 이 바꾸는 자리는 따로)

### 사본 재현 (착수 전 확인, 2026-10-11)

저장소 밖 사본(스크래치 `step11a/`)에 이 계획서의 변경을 그대로 적용해 전제를 확인했다. 저장소 코드와 `storage/` 는 건드리지 않았다.

- **수정 전 코드에 새 테스트만 얹으면 9 failed** — CPU 1개의 그리드 서치 1, 모듈 `logger` 없음 · 저장소 루트 밖 실행 2, 표 출력(줄 모양 둘 · 같은 함수에서 찍힘 · 행 길이 불일치 때 출력 없음) 4, 실패 뒤 취소 1, CPU 1개의 워커 수 기본값 1. 지금 동작을 고정하는 둘(모듈 `logger` 로 기록 · CPU 3개의 워커 수 2)은 수정 전에도 통과한다
- **수정 뒤 940 passed** (지금 946 − 지운 17 + 더한 11 — 지운 것: 실행 이력 테스트 7 · 표 출력 8 · 로거 레벨 1 · 로거 대체 경로 1, 더한 것: 표 출력 4 · CLI 핸들러 3 · 병렬 실행기 3 · 그리드 서치 1), Ruff 통과, PyRight 0 errors, `black` 변경 없음
- **변형 확인** — 새로 넣거나 고친 검사에 결함을 한 종씩 넣은 14종을 테스트가 모두 잡는다(취소 줄 삭제 · 취소를 `wait=False` 로 · 워커 수의 최소 1 삭제 · − 1 삭제 · 표의 보정 공백 되살림 · 헤더를 다른 메서드가 찍음 · 행 길이 검사 삭제 · 검사 전에 헤더부터 찍음 · 로거 대체 되살림 · 실행 위치 확인 삭제 · 고정 로거 사용 · 확인을 함수 실행 뒤로 · 로거 레벨 WARNING · 그리드 서치가 워커 0 을 넘김)
- **결과 파일** — 수정 뒤 사본에서 러너 여섯(단일 · 워크포워드 · 고원 · 포트폴리오 · 두 그리드)을 돌려 `storage/results` 274개 파일이 저장소와 같고, 다른 것은 저장소에만 있는 `meta.json` 하나다(러너 여섯 모두 종료 코드 0). 생성 스크립트 다섯(합성 · 일별 비교 · 대용 · 장기 대체 · 대체-실물 비교)은 수정 전 · 후 사본의 출력이 `meta.json` 말고 같다
- **주석만 바꾼 자리** — 수정 전 · 후를 주석 · docstring 을 뺀 AST 로 견주면 `data_loader.py` 는 전체가 같고, `common_constants.py` 는 `META_JSON_PATH` 한 문장만 없어졌고(나머지 순서 · 값 동일), `logger.py` 는 `setup_logger` 만, `parallel_executor.py` 는 `execute_parallel_with_kwargs` 와 지운 둘만, `formatting.py` 는 `Align` · `_format_cell` · `_format_row` · `TableLogger` 만 다르다
- **품질 검증 스크립트** — 같은 가상환경의 도구로 돌린 새 스크립트: 통과하는 사본은 `Pytest:  [OK] 통과 (passed=940, failed=0, skipped=0)` · 종료 코드 0, 수집 오류 · 실패 테스트를 넣은 사본은 `Pytest:  [FAIL] 실패`(개수 없음) · 종료 코드 1
- **변경 규모(포맷 적용 뒤)** — src +91 / −605(실행 이력 모듈 134줄 포함), 스크립트 10개 +38 / −375, `validate_project.py` +45 / −169, 테스트 +267 / −764(실행 이력 테스트 391줄 포함)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 · 「스크립트 실행 규칙」 절
- `src/qbt/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `meta_manager` · `META_JSON_PATH` · `save_metadata` 를 가리키는 코드가 src · scripts · tests 에 0 이고 `storage/results/meta.json` 이 없다
- [x] 러너 여섯 · 생성 스크립트 다섯의 결과 파일이 `meta.json` 말고는 그대로다(사본 재실행)
- [x] 워커 실패가 시작하지 않은 작업을 돌리지 않고 전파된다 · 표의 헤더와 행 시작 위치가 같다 · 저장소 루트 밖 실행이 안내와 함께 멈춘다(재현 테스트가 수정 전 실패 → 수정 후 통과)
- [x] 새로 넣거나 고친 검사마다 결함을 일부러 넣어 테스트가 실패하는 것을 봤다(변형 확인)
- [x] 주석만 바꾼 자리는 실행 코드가 그대로다(주석 · docstring 을 뺀 AST 대조)
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/AUDIT_REPORT.md`, `src/qbt/CLAUDE.md`(결과 위치의 `meta.json` · 병렬 처리의 「두 가지 제공」), `src/qbt/utils/CLAUDE.md`(모듈 구성), `scripts/CLAUDE.md`(메타데이터 관리 절 · 실행 흐름 · 메타데이터 타입 세 줄 · 로거 감지 · 실행 위치), `tests/CLAUDE.md`(픽스처 둘 · 메타데이터 테스트 대상). `docs/COMMANDS.md` · `README.md` 변경 없음 — 실행 명령 · CLI 옵션이 그대로이고 두 문서에 실행 이력 · 개수 줄 언급이 없다 (2026-10-11 조정 — `README.md` 는 기술 스택의 freezegun 한 줄을 지웠다, 코드 리뷰 1회차)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 해당 없음: 새로 옮긴 것 0(미조치 지적은 모두 거르는 기준에 걸리거나 사용자가 받아들였다 — 진행 로그), 이 계획서가 고친 파일 항목 0(남은 1건은 11단계 tests 배정 그대로). 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/utils/meta_manager.py` — 삭제
- `src/qbt/common_constants.py` — `META_JSON_PATH` 삭제, 설명용 주석 정리, `STORAGE_DIR` 주석(실행 위치 기준인 이유)
- `src/qbt/utils/parallel_executor.py` — 함수 하나로, 실패 시 대기 작업 취소, 워커 수 기본값, 로거 import, 주석
- `src/qbt/utils/formatting.py` — `print_table` 하나로, `Align.CENTER` · `indent` 삭제, 주석
- `src/qbt/utils/logger.py` — `level` 인자 삭제, 주석
- `src/qbt/utils/cli_helpers.py` — 모듈 `logger` 직접 읽기, 실행 위치 확인, 주석
- `src/qbt/utils/data_loader.py` — 주석
- `src/qbt/utils/__init__.py` — `get_logger` 만 재노출
- `src/qbt/backtest/engines/backtest_engine.py` — `run_grid_search` 의 워커 수 계산 삭제
- `scripts/backtest/run_single_backtest.py` · `run_walkforward.py` · `run_portfolio_backtest.py` · `run_supplement_grid.py` · `run_combo_grid.py`, `scripts/tqqq/generate_synthetic.py` · `generate_daily_comparison.py`, `scripts/data/generate_proxy_series.py` · `generate_long_proxy_series.py` · `generate_proxy_comparison.py` — 메타데이터 조립 · 저장 삭제(그리드 러너 둘은 워커 수 계산도)
- `validate_project.py` — 개수 파싱 정리
- `tests/qbt/test_meta_manager.py` — 삭제
- `tests/qbt/conftest.py` — 픽스처 둘과 그 import 삭제
- `tests/qbt/test_integration.py` — 메타데이터 단계 삭제, `tmp_path` 사용
- `tests/qbt/test_parallel_executor.py` — 키워드 인자 판으로 다시 쓰고 실패 뒤 취소 · 워커 수 기본값 테스트 추가
- `tests/qbt/test_formatting.py` — `print_table` 기준으로 다시 쓰고 헤더 · 행 정렬 테스트 추가
- `tests/qbt/test_logger.py` — 레벨 인자 테스트 삭제
- `tests/qbt/test_cli_helpers.py` — 모듈 `logger` 경로 · 실행 위치 확인 테스트
- `tests/qbt/test_buffer_zone_run.py` — CPU 1개의 그리드 서치 테스트 추가
- `storage/results/meta.json` — 삭제
- `docs/AUDIT_REPORT.md`, `src/qbt/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md` — 위 DoD 문서 줄
- `docs/COMMANDS.md`: 변경 없음 — 실행 명령 · CLI 옵션 변경 없음(품질 검증 스크립트의 출력 줄만 바뀐다)
- `README.md`: 변경 없음 (2026-10-11 조정 — 기술 스택의 freezegun 한 줄을 지웠다, 코드 리뷰 1회차, 진행 로그)

### 데이터/결과 영향

- `storage/results/meta.json` 이 없어진다. 그 밖의 결과 파일은 바뀌지 않는다 — 저장소에서 러너를 다시 돌리지 않는다
- 저장소 루트 밖에서 CLI 스크립트를 돌리면 입력을 찾기 전에 안내와 함께 멈춘다(의도)

## 6) 단계별 계획(Phases)

### Phase 0 — 재현 테스트(레드)

**작업 내용**:

- [x] 사본에서 검증한 테스트 넷(`test_parallel_executor.py` · `test_formatting.py` · `test_cli_helpers.py` · `test_buffer_zone_run.py`)을 저장소에 넣는다

**Validation**:

- [x] 고칠 동작을 겨냥한 새 테스트 9개가 지금 코드에서 실패한다(사본에서 9 failed) — 저장소에서 9 failed · 40 passed(그 네 파일만)

---

### Phase 1 — 실행 이력 삭제 · utils · 품질 검증 스크립트(그린)

**작업 내용**:

- [x] 설계 결정 1 — 모듈 · 상수 · 스크립트 10개 · 테스트 · `storage/results/meta.json`
- [x] 설계 결정 2 – 7

**Validation**:

- [x] `grep -rn "meta_manager\|META_JSON_PATH\|save_metadata" src scripts tests --include="*.py"` 가 0건
- [x] `poetry run pytest tests/qbt/test_parallel_executor.py tests/qbt/test_formatting.py tests/qbt/test_logger.py tests/qbt/test_cli_helpers.py tests/qbt/test_integration.py tests/qbt/test_buffer_zone_run.py` — 전부 통과(61 passed)

---

### 마지막 Phase — 결과 불변 확인 · 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 저장소의 src · tests · scripts · `validate_project.py` 가 사본에서 검증한 코드와 같은지 `diff -rq` 로 확인한다 — 같으면 사본의 재현(러너 · 생성 스크립트 결과 동일 · 변형 14종 · AST 대조)이 최종 코드의 결과다
- [x] 문서 — `docs/AUDIT_REPORT.md`(처리 표시 · 19절), 안내 문서 넷. `README.md` · `docs/COMMANDS.md` 변경 없음 (2026-10-11 조정 — `README.md` 는 freezegun 한 줄, 코드 리뷰 1회차)
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 14건 — 버그 4 [무거움 3 · 가벼움 1] · 그 외 10 · 조치: 무거움 1 수정(CLI 핸들러의 로거 조회) · 무거움 2 · 가벼움 1 미조치(닿지 않음 · 막는 쪽) · 그 외 3 반영(취소 범위 문구 · freezegun 「사용 중」 · 새 테스트의 타입 표기) · 7 미조치)
- [x] `/code-review xhigh` **2회차** (발견 9건 — 버그 2 [무거움 1 · 가벼움 1] · 그 외 7 · 조치: 고칠 것 0 — 무거움 1(1회차에 고친 자리, 닿지 않음 — 사용자에게) · 가벼움 1 미조치(막는 쪽) · 그 외 7 반영(문서 · 주석 · 테스트 이름 · 경로 타입))
- [x] 수정분 검증 (2회차 수정 11 hunk · 발견 5건 — 무거움 0 · 가벼움 0 · 그 외 5 · 조치: 절차대로 고치지 않음 — 그 외 5 거름(기준 3), 진행 로그)
- [x] `poetry run python validate_project.py` (passed=941, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 공통 / 실행 이력 meta.json 삭제와 utils 정리
2. 공통 / 실행 이력 기능 삭제, 병렬 실행기 단일화와 실패 시 대기 작업 취소, 표 로그 정렬, 저장소 루트 밖 실행 안내
3. 공통 / 읽는 코드가 없던 실행 이력과 테스트만 타던 대체 경로 제거
4. 공통 / 점검 보고서 11단계 실행 이력 · utils 묶음 처리 — 결정 6 · 9, 병렬 실패 전파, 표 정렬, 품질 검증 개수 줄
5. 공통 / meta_manager 삭제, execute_parallel_with_kwargs · TableLogger.print_table 단일화, cli_exception_handler 실행 위치 확인

## 7) 리스크(Risks)

- **실행 이력이 없어진다** — 받아들인다(결정 6). 지금도 이력 5칸이 한 번 실행으로 덮여 출처 기록으로 쓸 수 없다
- **저장소 루트 밖에서 CLI 스크립트를 돌리던 경우 이제 그 문구로 멈춘다** — 지금도 입력 파일을 못 찾아 멈춘다(다운로더만 엉뚱한 곳에 저장한다). 완화: 문구에 현재 위치와 할 일을 적는다
- **모듈에 `logger` 가 없는 스크립트는 실행 시작에서 AttributeError 로 멈춘다** (2026-10-11 조정 — KeyError, 코드 리뷰 1회차) — 지금 스크립트 12개는 모두 `logger` 가 있다. 새 스크립트가 규약을 빠뜨리면 조용히 다른 로거로 가는 대신 바로 드러난다
- **워커 실패 뒤에도 이미 워커에 넘어간 작업은 끝까지 돈다** — 받아들인다. 프로세스를 강제로 끊지 않는다(실측: 워커 2개에서 9개 중 5개)
- **실패한 품질 검증은 개수를 찍지 않는다** — 무엇이 실패했는지는 그 위의 pytest 출력에 있다
- **주석 삭제가 넓어 리뷰 diff 가 크다** — 완화: 주석만 바꾼 자리는 AST 대조로 실행 코드가 그대로임을 기계적으로 확인한다
- **결과 수치를 바꾸지 않는 변경이라 러너 재실행으로는 회귀가 드러나지 않는다** — 완화: 레드 · 그린 · 변형 확인, 사본에서 러너 · 생성 스크립트 재실행 뒤 결과 대조

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 결정 6 · 결정 9 · 5-10 · 2-21 · 5-9 · 6-8 · 6-9 ⑥ · 13-B D13 · 5-8 · 2-3 · 2-6 · 8-6 · 2-14 · 6-5 · 12-7 · 6-18 · 2-24 · 6-6 · 2-15 · 12-10 · 7-14, 19절 11단계
- 점검 보고서의 줄 번호는 기준 커밋(`40011ad`) 값이라 지금 코드와 어긋난다. 이 계획서는 함수 이름으로 가리킨다
- 11단계는 계획서 여럿으로 나눈다 — 이 계획서(실행 이력 · utils) 다음은 tqqq 시뮬레이션 · 생성 스크립트, 스프레드 랩, backtest, 대시보드, tests 순서다
- 이 계획서가 일부만 처리하는 항목: 6-5(`formatting.py` · `logger.py` 만 — tqqq · backtest 의 인자는 남는다) · 6-6(utils 만) · 5-8(`execute_parallel` 만 — `load_wfo_results_from_csv` 는 backtest) · 13-C C7(`common_constants.py` · `parallel_executor.py` 만)

### 진행 로그 (KST)

- 2026-10-11 21:44: 계획서 작성(Draft). 이전 세션 일곱의 로그 · 점검 보고서 · 미룬 지적 파일 · 계획 절차를 읽고, 대상 코드와 호출처를 읽었다
- 2026-10-11 22:11: 초안 보강 — 사본 재현(Context)을 채웠다. 사본에서 두 가지가 점검 보고서의 제안과 달라졌다 — ① 2-3: 제안한 `shutdown(wait=False, cancel_futures=True)` 는 남은 작업을 하나도 취소하지 않았다(실패 뒤 취소 테스트가 나머지 5개 모두 실행된 것을 잡았다). `wait` 를 기본값으로 둔다 ② 2-15: Pytest 개수 줄은 통과한 실행에만 남긴다. 변형 확인 첫 실행에서 M12(확인을 함수 실행 뒤로)가 통과했는데 변형 자체가 동작을 바꾸지 않게 적혀 있었다 — 다시 적어 잡히는 것을 확인했다
- 2026-10-11 22:14: 승인 — 사용자 「승인」(계획서대로 한 커밋), 품질 검증 스크립트의 테스트 개수 줄은 「통과했을 때만 찍음」(설계 결정 6 그대로). 저장소의 src · scripts · tests · `validate_project.py` 가 사본의 기준과 같음을 확인하고(`diff -rq` 차이 0) Phase 0 착수
- 2026-10-11 22:15: Phase 0 — 사본에서 검증한 테스트 넷을 저장소에 넣었다. 수정 전 코드에서 9 failed · 40 passed(그 네 파일만) — 사본에서 잰 9건과 같다
- 2026-10-11 22:16: Phase 1 — 사본에서 달라진 파일 26개를 그대로 넣고 셋(`meta_manager.py` · `test_meta_manager.py` · `storage/results/meta.json`)을 지웠다. 저장소의 src · scripts · tests · `validate_project.py` 가 사본과 같음을 `diff -rq` 로 확인했다(차이 0) — 그래서 사본 재현(러너 여섯의 결과 274개 동일 · 생성 스크립트 다섯의 출력 동일 · 변형 14종 · AST 대조)은 최종 코드의 결과다. 관련 여섯 파일 61 passed, 실행 이력을 가리키는 코드 0건
- 2026-10-11 22:18: 문서 — `docs/AUDIT_REPORT.md`(결정 6 · 9, 2-3 · 2-6 · 2-14 · 2-15 · 2-21 · 2-24 · 5-9 · 5-10 · 6-18 · 7-14 · 8-6 · 12-7 · 12-10 처리 표시, 4-6 · 5-8 · 6-5 · 6-6 · 6-8 · 6-9 · 13-B D9 · D13 · 13-C C7 · 13-T · 14절 · 18-B B9 의 일부 처리, 6-T 세 행, 19절 11단계 tqqq · utils 줄), `src/qbt/CLAUDE.md`(결과 위치의 `meta.json` 삭제 · 병렬 처리 두 줄), `src/qbt/utils/CLAUDE.md`(`meta_manager` 절 삭제 · 핸들러 · 병렬 실행기 · 표 출력), `scripts/CLAUDE.md`(메타데이터 관리 절 · 실행 흐름 · 메타데이터 타입 세 줄 삭제, 로거 · 실행 위치), `tests/CLAUDE.md`(픽스처 둘 · 메타데이터 테스트 대상 삭제, 경로 상수 패치가 닿지 않는 이유 한 줄). `black` 변경 없음(134 files left unchanged), 포맷 뒤에도 코드가 사본과 같다. 리뷰 전 사본은 스크래치 `step11a/r1_before/`
- 2026-10-11 22:20: `/code-review xhigh` 1회차가 사용량 한도로 결과 없이 끊겼다. 작업 트리가 리뷰 전 사본과 같음을 확인하고(리뷰가 바꾼 파일 0) 23:10 에 다시 돌렸다
- 2026-10-11 23:21: `/code-review xhigh` 1회차 — 발견 14건. 버그 4 [무거움 3 · 가벼움 1] · 그 외 10. 리뷰 전 사본은 스크래치 `step11a/r1_before/`, 1회차 수정 전 사본은 `step11a/r1fix_before/`
  - 고친 무거움 1: ① CLI 핸들러가 로거를 `sys.modules[func.__module__]` 에서 찾아, 스크립트를 다른 이름공간으로 실행하는 실행기 아래에서는 `logger` 가 있어도 죽는다 — `python -m cProfile -o … scripts/data/download_data.py --help` 가 `AttributeError: module '__main__' has no attribute 'logger'` 로 끝났다(사본 재현, 수정 전 코드는 대체 로거로 돌았다 — 이번 변경의 회귀). 죽는다 · 닿는다(실행 환경 — 수 분 걸리는 러너를 프로파일러로 돌리는 것). → 함수의 전역 이름공간 `func.__globals__["logger"]` 에서 읽는다(없으면 KeyError — 「없으면 멈춘다」는 그대로). 같은 모양(`sys.modules` · `inspect.getmodule` 로 모듈을 찾아 속성을 읽음)은 diff 안에 이 한 곳뿐이다. 새 테스트 `test_logger_is_read_from_function_globals`(이름공간에만 `logger` 가 있는 함수)와 고친 `test_module_without_logger_raises_key_error` 가 수정 전 코드에서 2 failed · 수정 뒤 통과. 변형 4종을 잡는다 — 수정 전 조회로 되돌림 → 2 failed, 없으면 기본 로거로 대체 → 1, 고정 로거 → 2, 실행 위치 확인 삭제 → 1. 같은 실행이 cProfile 아래에서 종료 코드 0 으로 도움말을 찍는다. 전체 941 passed
  - 반영한 그 외 3: ⑥ `src/qbt/CLAUDE.md` 와 실패 뒤 취소 테스트 docstring 의 「아직 시작하지 않은 작업」을 「아직 워커에 넘어가지 않은 작업(이미 넘어간 작업은 끝까지 돈다)」으로 — 이미 넘어간 시작 전 작업도 돈다 ⑨ `tests/CLAUDE.md` 「사용 중인 플러그인」과 `README.md` 기술 스택의 freezegun — 이번 변경으로 쓰는 곳이 0 이 됐다(DoD 의 「이 변경으로 거짓이 되는 문장」). `pyproject.toml` 의 의존성은 그대로다(비목표) ⑩ 새 테스트 둘의 `caplog` 타입 표기
  - 고치지 않은 버그 3(거르는 기준 1 · 2): ③(무거운 모양) 품질 검증 스크립트가 종료 코드 0 인데 통과 테스트가 0 이면(모두 skip) `KeyError: 'passed'` 로 죽는다 — 테스트 940개 중 skip 0 이고 하나도 없이 수집되면 pytest 종료 코드가 5 라 이 분기에 오지 않는다. 모두 skip 되려면 테스트 전부를 고쳐야 한다(기준 1) ④(무거운 모양) 논리 CPU 64개 이상인 Windows 에서 기본 워커 수가 61 상한을 넘어 죽는다 — 이 저장소를 돌리는 환경은 macOS · WSL(Linux)이고 상한은 Windows 에만 있다. 수정 전 코드(`cpu_count − 1` 을 그대로 넘김)도 같았다(기준 1). 같은 지적의 CPU affinity · 컨테이너 제한 무시는 워커가 많아지는 성능 문제라 「그 외」(기준 3) ⑤(가벼움) 실행 위치 확인을 `storage` 폴더 유무로 한다 — 다른 폴더에 `storage` 가 있으면 통과(그 폴더를 만들어 두고 거기서 돌려야 한다, 기준 1), 저장소 루트에서 `storage` 를 통째로 지운 뒤 다운로더를 돌리면 엉뚱한 안내로 멈춘다(`storage/stock` · `storage/results` 는 git 추적이라 클론에 있다, 기준 2), 루트 밖에서 `--help` 도 막힌다(기준 2). 대안으로 든 「핸들러가 `__file__` 로 루트를 찾아 `os.chdir`」은 결정 9 의 (나)를 바꾸는 설계라 넣지 않았다
  - 반영하지 않은 그 외 7: ② Ctrl+C(KeyboardInterrupt)는 `except Exception` 을 지나 취소 없이 남은 작업을 기다린다 — 중단 뒤 대기 시간 문제이고 수정 전과 같다(성능 · 응답성). 고치려면 `as_completed` 대기까지 감싸는 구조가 필요하다 ⑦ 표 정렬 테스트가 함수 이름만 보고 로그 포맷의 「파일:줄번호」 폭은 보지 않는다(막는 결함이 표시 정렬이라 검사 보강은 「그 외」) ⑧ `STORAGE_DIR` 주석이 전역 「경로 기준은 파일 위치」와 부딪힌다는 지적 — 결정 9 로 정한 예외이고 이유를 그 상수 주석에 적었다 ⑪ 취소 테스트의 고정 대기 1.5초(실행 시간) ⑫ 일별 비교 스크립트가 방금 쓴 CSV 를 다시 읽는다(성능, 점검 보고서 5-9 행에 남긴 결정) ⑬ 품질 검증 스크립트의 `run_ruff` · `run_pyright` 가 같은 세 줄 ⑭ 행 길이 검사 뒤 `zip(strict=True)` 가 같은 조건을 다시 본다
- 2026-10-11 23:30: `/code-review xhigh` 2회차(상한) — 발견 9건. 버그 2 [무거움 1 · 가벼움 1] · 그 외 7. 고칠 것(닿는 버그) 0. 수정 전 사본은 스크래치 `step11a/r2_before/`
  - 고치지 않은 버그 2: ①(무거운 모양 · 1회차에 고친 자리) `functools.wraps` 를 쓰는 다른 모듈의 데코레이터를 `@cli_exception_handler` 아래에 겹치면 `func.__globals__` 가 그 데코레이터 모듈을 가리켜 `KeyError: 'logger'` 로 죽거나 그 모듈의 로거로 기록된다 — `@cli_exception_handler` 를 쓰는 스크립트 12개 중 데코레이터를 겹친 곳 0, 겹치려면 새 데코레이터 코드가 필요하다(기준 1). 같은 자리에서 두 번째라 다시 설계할지(예: `inspect.unwrap(func).__globals__`)는 사용자에게 올린다 ②(가벼움) `logger` 가 없을 때 한글 안내 없이 `KeyError: 'logger'` 만 남는다 — 멈추는 쪽이고 안내만 어색하다(기준 2)
  - 반영한 그 외 7: ③ 점검 보고서 12-7 행의 「없으면 AttributeError」를 KeyError 와 그 이유로 ④ `logger.py` docstring 「(필터링 가능)」과 `src/qbt/utils/CLAUDE.md` 「레벨별 필터링」 — 레벨 인자를 지워 늘 DEBUG 다(`scripts/CLAUDE.md` 의 「로그 레벨 설정」은 이 변경 전부터 코드 0건이라 12단계 18-B B20 에 맡긴다) ⑤ `tests/CLAUDE.md` 의 「파일을 쓰는 테스트는 `tmp_path` 경로를 인자로 넘긴다」 — 경로 인자가 없으면 그 상수를 쓰는 모듈의 이름을 패치한다(`test_stock_downloader` 의 관용 · 전역 python-tests.md)로 ⑥ 테스트 이름 `…not_yet_started` → `…not_yet_handed_to_workers` 와 점검 보고서 D9 행의 취소 범위 문구 ⑦ 계획서의 「`README.md` 변경 없음」 세 곳(1회차 ⑨ 로 바뀌었다 — 조정 표시) ⑧ 취소 테스트 헬퍼의 경로를 문자열 대신 `Path` 로 ⑨ 코드를 말로 옮긴 새 주석 셋(「표의 왼쪽 들여쓰기 칸 수」 · 「(시간을 떼고 date 로)」 · 「— 시세 CSV 의 필수 컬럼」) 삭제
  - 2회차 수정분 검증용 확인: 바뀐 취소 테스트가 변형 둘을 여전히 잡는다 — 취소 줄 삭제 → 1 failed, `wait=False` → 1 failed(사본, 원본 복원 해시 확인)
- 2026-10-11 23:36: 품질 검증 `validate_project.py` — Ruff · PyRight 통과, Pytest passed=941, failed=0, skipped=0(새 스크립트가 찍은 줄 그대로). `black` 변경 없음. 2회차 수정분(11 hunk — 주석 · docstring · 문서 9 · 테스트 2)의 수정분 검증을 서브에이전트에 맡겼다
- 2026-10-11 23:38: 최종 확인 — 러너 여섯 · 생성 스크립트 다섯을 돌린 사본(`step11a/copy`)과 지금 저장소의 src · scripts · `validate_project.py` 를 주석 · docstring 을 뺀 AST 로 대조해 다른 것은 `cli_helpers.cli_exception_handler`(1회차의 로거 조회) 하나다. 결과에 닿지 않는 자리지만 최종 코드로 단일 백테스트 · 포트폴리오 러너와 합성 생성을 사본에서 다시 돌려 `storage/` 전체가 저장소와 같음을 확인했다. 저장소 `storage/` 변경은 `meta.json` 삭제 하나
- 2026-10-11 23:40: 근거 승격 — 실행 이력을 두지 않는 이유(읽는 코드 0 · 이력 5칸이 한 번 실행으로 덮임 · 파라미터는 `summary.json`, 시점은 git)를 `scripts/CLAUDE.md` 「결과 표시」에 한 줄로. 나머지 「왜」는 코드 옆에 있다 — 병렬 실행기가 `wait=False` 로 끊지 않는 이유는 `parallel_executor.py` 주석과 `src/qbt/utils/CLAUDE.md`, 로거를 함수의 전역 이름공간에서 읽는 이유는 `cli_helpers.py` 주석과 같은 문서, `STORAGE_DIR` 를 실행 위치 기준으로 두는 이유는 그 상수 주석, 표를 한 메서드에서 찍는 이유는 `print_table` docstring, 실패한 품질 검증이 개수를 찍지 않는 이유는 `validate_project.py` 주석. 처리 사실과 재현 수치는 점검 보고서 해당 행
- 2026-10-12 00:00: 수정분 검증 결과(2회차 수정 11 hunk) — 무거운 · 가벼운 발견 0. 실행 코드가 바뀐 hunk 는 테스트 셋뿐이고, 바뀐 취소 테스트가 `parallel_executor` 의 변형 셋(취소 줄 삭제 · `wait=False, cancel_futures=True` · `wait=False`)을 사본에서 10회 중 10회 잡는다(수정 전 테스트와 같다 — 실패는 모두 `assert 5 < 5`). 원본은 10회 모두 실행된 나머지 작업 3개 · 전파 0.68 – 0.72초, `wait=False, cancel_futures=True` 는 전파 0.05 – 0.08초 · 1.5초 뒤 5개. 주석 · 문서 hunk 는 실행 코드가 같다(AST). 원인 확인: CPython 3.12 의 `shutdown` 은 부를 때마다 취소 요청 칸을 덮어써, `with` 종료의 두 번째 호출이 첫 호출의 취소를 되돌린다(코드 주석 · 보고서 2-3 행의 설명과 맞다)
  - 거른 그 외 5(기준 3): ① `test_logger.py` 의 `test_creates_logger_with_default_level` — 짝이던 레벨 지정 테스트를 지워 「default」에 대안이 없다(이름만의 문제) ② `logger.py` 의 「핸들러가 없으면 기본 설정으로 초기화」(이번 diff 밖 기존 주석) ③ `scripts/CLAUDE.md` 「로그 레벨 설정」(기존 · 18-B B20 에 등록) ④ 이 계획서 목표 2 · 완료 조건의 「아직 시작하지 않은 작업」(임시 문서) ⑤ 지운 주석과 같은 모양의 기존 주석(`data_loader.py` 「(set 교집합)」, `formatting.py` 정렬 주석, `common_constants.py` 경로 · 컬럼 주석 — diff 밖이라 수술적 변경 원칙대로 남김)
- 2026-10-12 18:13: 사용자 결정 — 2회차 ①(데코레이터를 겹치면 핸들러가 엉뚱한 이름공간을 봄, 1회차에 고친 자리)은 「받아들임」 — 점검 보고서 12-7 행에 받아들인 한계와 다시 고칠 때의 형태(`inspect.unwrap(func).__globals__`)를 적었다. freezegun 의존성은 「그대로 둠」(비목표 그대로)
- 2026-10-12 18:14: 마무리 — 미룬 지적: 새로 옮긴 것 0. 1회차 ③ ④ ⑤ · 2회차 ② 는 기준 1 · 2, 그 외(1회차 7 · 2회차 반영하지 않은 것 0 · 수정분 검증 5)는 기준 3, 2회차 ① 은 사용자가 받아들였다. 미룬 지적 파일의 남은 1건(표시용 열의 테스트 공백)은 이 계획서의 대상이 아니다(11단계 tests). 이 계획서를 지워도 잃는 것이 없다 — 근거 승격(23:40)과 처리 사실 · 재현 수치(점검 보고서 해당 행)

---
