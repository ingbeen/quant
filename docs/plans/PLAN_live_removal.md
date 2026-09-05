# Implementation Plan: live 패키지 제거 — quant 를 백테스트 도구로 되돌린다

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: `/impl-plan` 스킬의 "3) 스킵 및 완료 규칙" 참고
- 위 조건은 `~/.claude/hooks/plan_lint.py`가 저장 시 자동 검사합니다

---

**작성일**: 2026-09-05 18:32
**마지막 업데이트**: 2026-09-05 18:52
**관련 범위**: `src/live/`, `tests/live/`, `.github/workflows/`, 빌드·검증 설정, 문서 전반
**관련 문서**: 루트 [CLAUDE.md](../../CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md), [docs/COMMANDS.md](../COMMANDS.md), [README.md](../../README.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 `/impl-plan` 스킬을 따릅니다.

- 품질 검증 명령은 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: **`src/live/` 5,958줄과 그 테스트를 제거**해 quant 를 백테스트 전용 도구로 되돌린다
- [x] 목표 2: **끊어진 참조를 남기지 않는다** — 빌드 설정·타입 설정·검증 스크립트·문서 전부
- [x] 목표 3: **`qbt` 패키지는 그대로 동작한다** — 삭제가 백테스트 기능을 건드리지 않는다

## 2) 비목표(Non-Goals)

- **`docs/DESIGN_QBT_LIVE_FINAL.md` §14 의 근거 보존** — **이미 완료했다.**
  `quant-notify/docs/DESIGN.md` 로 승격이 끝났으므로 이 계획서는 삭제만 한다
- **quant-notify 구현** — 별도 저장소의 별도 계획서가 다룬다
- **Firebase / GCS 클라우드 자원 삭제** — 콘솔 작업이며 사용자가 직접 한다
- **`qbt-live-app` 저장소 처리** — README 에서 링크만 제거한다. 저장소 자체는 사용자 몫이다
- **`storage/` 데이터 정리** — live 가 쓰던 CSV 가 있더라도 백테스트가 함께 쓰므로 건드리지 않는다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- quant `src/live/` 는 **2026-08-29 부터 수동 중지 상태**다. 워크플로 두 개가 꺼져 있고,
  정본 CSV 에 거래일 공백(2026-08-27·08-28)이 있어 재개하려면 사람이 손대야 한다
- 재개하지 않기로 했다. **알림은 `quant-notify` 로 이사했고**, 그 저장소는 원격에 푸시까지 됐다
  (`ingbeen/quant-notify`)
- 남겨두면 **끊어진 참조**가 된다 — 꺼진 워크플로, 없는 패키지를 가리키는 `pyproject.toml`,
  존재하지 않는 규칙을 강제하는 `CLAUDE.md` 절, 실행 불가 명령이 실린 `COMMANDS.md`
- **근거 승격은 이미 끝났다.** §14 의 사고 기록·발송 지연 실측 61건·탈락안이
  `quant-notify/docs/DESIGN.md` 로 옮겨졌으므로, 이 계획서는 **삭제만** 한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md) — 특히 「계획서 규약 — 이 프로젝트의 설정」 절
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 테스트 구조 규칙
- `.claude/rules/python.md` — 구현 원칙·코딩 표준
- `~/.claude/CLAUDE.md` — 전역 규칙 (특히 「수술적 변경」)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `src/live/` · `tests/live/` · `docs/DESIGN_QBT_LIVE_FINAL.md` · `.github/workflows/` 삭제 완료
- [x] 저장소 전체에서 **`live` 참조가 0건** (`grep` 으로 확인, `vendor/`·`.venv/` 제외)
- [x] `poetry.lock` 이 변경된 의존성과 일치한다
- [x] 회귀/신규 테스트 추가 — **신규 테스트 없음**(삭제 작업이며 기존 `tests/qbt/` 가 회귀를 잡는다)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `README.md` · `docs/COMMANDS.md` · 루트 `CLAUDE.md` · `tests/CLAUDE.md` (각각 변경 여부 명시)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (§14 근거는 `quant-notify/docs/DESIGN.md` 로 이미 승격됨. 이 계획서에는 새로 생기는 근거가 없다)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**통째 삭제**

- `src/live/` — 15개 `.py` + `CLAUDE.md` (5,958줄)
- `tests/live/`
- `docs/DESIGN_QBT_LIVE_FINAL.md` (1,189줄)
- `.github/workflows/` — `daily_run.yml` · `keepalive.yml` 둘뿐이므로 폴더째

**부분 수정**

- `pyproject.toml` — `packages` 의 live 항목 · `[tool.poetry.extras]` 절 ·
  optional 의존성 4개(`firebase-admin`·`exchange-calendars`·`requests`·`python-dotenv`) ·
  `known-first-party` 에서 `"live"` 제거
- `poetry.lock` — 의존성 변경 반영
- `pyrightconfig.json` — `executionEnvironments` 의 `tests/live` 블록 제거
- `validate_project.py` — `--cov=src/live` 한 줄 제거
- 루트 `CLAUDE.md` — 「패키지 간 의존 관계」·「QBT 본체 수정 제한」 절 · 프로젝트 개요 · 디렉토리 구조 · 규칙 참고 순서 · 개발 원칙의 live 언급
- `tests/CLAUDE.md` — live 관련 서술 전부
- `README.md`: **변경 있음** — 「live」 절 · 「관련 저장소」의 Android 앱 링크 · 「관련 문서」의 `src/live/CLAUDE.md`
- `docs/COMMANDS.md`: **변경 있음** — live 설치·실행·테스트·커버리지 명령 전부

### 데이터/결과 영향

- **백테스트 결과에 영향 없음** — `storage/` 를 건드리지 않고 `src/qbt/` 를 수정하지 않는다
- **CI 가 사라진다** — `.github/workflows/` 삭제로 이 저장소의 자동 실행이 없어진다.
  원래 daily_run 은 live 전용이었고 keepalive 는 그 부수 설비였으므로 잃는 기능이 없다

## 6) 단계별 계획(Phases)

### Phase 1 — 삭제와 빌드·검증 설정 수정(그린 유지)

> **삭제와 설정 수정을 한 Phase 로 묶는다.** 나누면 그 사이 구간에서 `pyproject.toml` 이
> 존재하지 않는 패키지를 가리켜 **의도적으로 레드가 된다.** Phase 1 부터 그린 유지가 원칙이다.

**작업 내용**:

- [x] `src/live/` 삭제
- [x] `tests/live/` 삭제
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 삭제
- [x] `.github/workflows/` 삭제 (`daily_run.yml` · `keepalive.yml`)
- [x] `pyproject.toml` — packages · extras · optional 의존성 4개 · isort known-first-party 정리
- [x] `pyrightconfig.json` — `tests/live` executionEnvironment 블록 제거
- [x] 품질 검증 스크립트 — `--cov=src/live` 옵션 제거
- [x] `poetry.lock` 갱신 — `poetry lock` (**네트워크가 필요하면 사용자에게 알린다**)
- [x] `__pycache__` 잔재 확인 — 삭제한 모듈의 `.pyc` 가 남아 import 가 살아 있는 것처럼 보이지 않게 한다

---

### Phase 2 — 문서 정리(그린 유지)

> **문서를 코드와 같은 Phase 에 넣지 않는다.** 삭제 diff 와 문서 diff 가 섞이면
> 무엇이 왜 지워졌는지 읽기 어려워진다.

**작업 내용**:

- [x] 루트 `CLAUDE.md` — 「패키지 간 의존 관계」 절과 「QBT 본체 수정 제한」 절을 통째로 제거.
      프로젝트 개요·디렉토리 구조·규칙 참고 순서·개발 원칙에서 live 언급 제거
- [x] `tests/CLAUDE.md` — live 디렉토리·픽스처·탐색 경로 서술 제거
- [x] `README.md` — 「live」 절 제거, 「관련 저장소」에서 Android 앱 링크 제거,
      「관련 문서」에서 `src/live/CLAUDE.md` 링크 제거
- [x] `docs/COMMANDS.md` — live 설치(`-E live`)·실행(`python -m live ...`)·테스트·커버리지 명령 제거
- [x] **`grep -rn "live"` 로 잔여 참조 0건 확인** (`vendor/`·`.venv/`·`alive` 같은 오탐 제외)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (`README.md` · `docs/COMMANDS.md` 포함 — Phase 2 에서 완료됨을 확인)
- [x] 자동 포맷 적용 — `poetry run black .`
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=524, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 하네스 / live 패키지 제거 — quant 를 백테스트 전용으로 환원
2. 하네스 / 실매매 알림 코드·워크플로 삭제 및 빌드 설정 정리
3. 문서 / live 제거에 따른 규칙·명령어·README 정리
4. 하네스 / src/live 5,958줄 삭제 + 끊어진 참조 정리
5. 하네스 / 알림 시스템 quant-notify 이관에 따른 live 제거

## 7) 리스크(Risks)

| 리스크 | 완화 |
| --- | --- |
| **`qbt` 가 `live` 를 참조하고 있었다** | 루트 `CLAUDE.md` 가 「qbt → live import 금지」를 규칙으로 두었으므로 없어야 한다. **Phase 2 의 grep 이 이것까지 잡는다.** 만약 나오면 삭제를 멈추고 사용자에게 보고한다 |
| **`poetry lock` 이 네트워크를 요구한다** | 오프라인이면 lock 갱신을 마지막 Phase 로 미루고, 그 사실을 Notes 에 남긴다. lock 이 낡아도 `validate_project.py` 는 기존 `.venv` 로 돌아간다 |
| **삭제한 모듈의 `.pyc` 가 남아 테스트가 통과한다** | Phase 1 에서 `__pycache__` 를 확인한다. 거짓 그린은 다음 사람이 치른다 |
| **되돌리기** | git 이력에 남아 있으므로 복구 가능하다. **다만 커밋 전에는 작업 트리에서만 사라지므로**, 사용자가 커밋하기 전에 `git status` 로 삭제 범위를 확인할 수 있게 보고한다 |
| **`docs/COMMANDS.md` 에서 다른 명령까지 지운다** | live 명령만 지운다. 백테스트·데이터·대시보드 명령은 그대로 둔다 |

## 8) 메모(Notes)

### 이미 끝난 것 — 근거 승격

`docs/DESIGN_QBT_LIVE_FINAL.md` §14 의 아래 내용이 `quant-notify/docs/DESIGN.md` 로 옮겨졌다.
**이 저장소에서 삭제해도 잃는 것이 없다.**

- §14.1 거래일 누락 사고 (cron 7시간 45분 지연, job 자체는 55초)
- §14.2 **발송 시각 분포 실측 61건** — 텔레그램 로그 파싱값이라 로그가 사라지면 재현 불가
- §14.3 결정 6건 · §14.4 폐기 대상 · §14.5 탈락안 6건

§0~§13(GCS 정본 · RTDB · Android 앱 · FCM 설계)은 **§14 가 이미 폐기를 결정한 설계**이므로
승격하지 않는다. 필요하면 git 이력에서 읽는다.

### 후속으로 판단할 것 (이 계획서 범위 밖)

- **README 「관련 저장소」에 `quant-notify` 를 추가할지** — 알림이 어디로 갔는지 알려주면
  다음 사람이 찾지 않아도 된다. 다만 요청 범위 밖이라 사용자 판단으로 남긴다
- **`ingbeen/qbt-live-app` 저장소 처리** — 앱을 폐기했으므로 아카이브나 삭제 대상이다
- **Firebase 프로젝트 · GCS 버킷(`qbt-live.firebasestorage.app`) 정리**

### 실행 중 드러난 계획의 전제 어긋남 (사용자 승인 후 조정)

**① `README.md` 의 범위가 Scope 보다 넓었다.** Scope 에는 「live 절 · 앱 링크 · 관련 문서」만
적었으나, 실제로는 **소개 문장 · 「프로젝트 목표」 · 「시스템 아키텍처」 절 전체**가 폐기된 설계
(GCS 정본 · Firebase RTDB · FCM · Android 앱 데이터 흐름도)를 설명하고 있었다.
그대로 두면 README 가 **존재하지 않는 시스템을 설명**하게 되므로, 사용자 승인을 받아
「폐기 설계 제거 + `quant-notify` 포인터」로 조정했다. 「관련 저장소」가 후속 저장소를 가리키므로
알림이 어디로 갔는지의 이력도 남는다.

**② 살아있는 문서 2건이 Scope 에 없었다.** `grep` 이 잡아냈다.

- `.claude/rules/python.md` — "프로젝트 전반(qbt + live)" → 패키지 언급 제거
- `docs/research/QQQ_지연진입_연구.md` 2곳 — `src/live/` 알림 시스템 → `quant-notify`

목표 2(「끊어진 참조를 남기지 않는다」)에 직접 해당하므로 범위 내로 처리했다.

**③ `docs/plans/` 안의 완료된 계획서 3건은 고치지 않았다.** 계획서는 임시 산출물이자
**과거 시점의 기록**이다. 그때 `src/live/` 가 있었던 것은 사실이므로 고치면 기록이 거짓이 된다.

### 실측 기록

- **삭제 규모**: `src/live/` 5,957줄 · `tests/live/` 10,354줄 · `DESIGN_QBT_LIVE_FINAL.md` 1,189줄
  (합 17,500줄) + 워크플로 2개
- **`qbt` → `live` 참조 0건** — 루트 `CLAUDE.md` 의 「qbt → live import 금지」 규칙이 실제로 지켜지고 있었다.
  삭제 전 `grep` 으로 확인했고, 그래서 백테스트 코드를 한 줄도 건드리지 않았다
- **`poetry lock` 은 네트워크 없이 통과**했다 (리스크로 잡아둔 항목이 발현하지 않음)
- **최종 검증**: Ruff · PyRight · Pytest 전부 통과, `passed=524 failed=0 skipped=0`

### 진행 로그 (KST)

- 2026-09-05 18:32: 계획서 작성. 삭제 범위를 `grep` 으로 전수 확인 —
  코드 4곳(`pyproject.toml`·`pyrightconfig.json`·`validate_project.py`)과
  문서 4곳(루트 `CLAUDE.md`·`tests/CLAUDE.md`·`README.md`·`docs/COMMANDS.md`)
- 2026-09-05 18:40: Phase 1 완료 — 삭제 + 빌드/타입/검증 설정 정리 + `poetry lock`
- 2026-09-05 18:50: Phase 2 완료 — 문서 정리. README 범위는 사용자 승인 후 확대
- 2026-09-05 18:52: 최종 검증 통과 → **Done**

---
