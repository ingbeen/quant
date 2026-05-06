# Firebase Cloud Storage 이관 사전 합의 (Pre-Plan Brief)

> 본 문서는 정식 계획서가 아닌 **사전 합의(Pre-Plan)** 문서입니다.
> 다음 세션에서 본 문서를 입력으로 [`docs/plans/`](plans/) 하위에 정식 계획서
> (`PLAN_*.md`)를 작성합니다. 따라서 다른 세션의 작성자가 본 문서만 읽고도
> 맥락을 충분히 잡을 수 있도록 상세하게 기술합니다.

## 메타

- 작성일: 2026-05-06
- 작성 배경: 사용자가 `qbt-live-state` 프라이빗 git 리포를 데이터 저장소로 사용하는 현
  구조를 어뷰징으로 판단하여 대체 방안을 의뢰
- 대상 모듈: [`src/live/git_state.py`](../src/live/git_state.py) 및
  [`src/live/cli.py`](../src/live/cli.py) 의 ephemeral state repo 컨텍스트 (`_ephemeral_state_repo`)
- 후속 작업: 다음 세션에서 [`docs/plans/`](plans/) 하위에 정식 계획서 작성
- 결정 권한: 본 문서의 모든 결정사항은 사용자 승인 완료. 정식 계획서에서는
  결정 자체를 재검토하지 않고 구현 단계만 분해한다.

---

## 1. 배경 및 동기

### 1.1 현재 구조

[`src/live/CLAUDE.md`](../src/live/CLAUDE.md) 의 "ephemeral state repo" 섹션에 정의된
대로, live 도메인의 모든 정본 데이터는 `qbt-live-state` 프라이빗 GitHub 리포에 commit
된다. CLI 는 매 실행마다 다음 흐름을 탄다.

1. 임시 디렉토리(`tempfile.TemporaryDirectory`)에 `--depth 1` shallow clone
2. 명령 수행 (state 읽기 / 쓰기)
3. `git add -A && git commit && git push` (변경사항이 있을 때만)
4. 임시 디렉토리 자동 삭제

### 1.2 git 으로 관리되는 데이터 (총 약 5MB 규모)

| 카테고리 | 파일 / 패턴 | 특성 |
|---|---|---|
| 상태 | `live_state.json` | 작은 단일 JSON, 매일 갱신 (덮어쓰기) |
| 멱등 원장 | `applied_fill_ids.json`, `applied_balance_adjust_ids.json` | 작음, 90일 자동 정리 |
| 시계열 | `data/stock/{TICKER}.csv` | 누적 append, 티커당 수십~수백 KB |
| 일별 스냅샷 | `history/daily/{date}.json`, `history/states/{date}.json` | 매일 1개 추가 (영구 보존) |
| 감사 로그 | `history/{summary,user_trades,signals,balance_adjusts,fill_dismisses}.jsonl` | append-only |
| 차트 슬라이스 | (chart_data.py 가 RTDB 에 직접 write — git 미관리) | RTDB `/charts/...` |

### 1.3 git 사용의 어뷰징 측면

- 매일 CSV 가 변경되어 commit 이력이 누적 → repo bloat (영구 누적, GC 어려움)
- 매 실행마다 clone 트래픽 발생 (depth 1 이지만 0 은 아님)
- 본질적으로 git 은 코드/텍스트 변경 이력 추적 도구이며, "프로그램이 매 실행마다
  파일을 올리고 받는 객체 저장소" 용도로는 의미상 무리

### 1.4 git 의 합리적 측면 (대체 시 보존해야 할 가치)

- 무료 (private repo)
- 로컬 / GitHub Actions 가 동일 코드 경로로 정본에 수렴
- 단일 자격증명 (`STATE_REPO_PAT`) 으로 read/write 모두 처리
- 자동 이력 보존 (장애 시 백업 가치)

---

## 2. 옵션 비교 (검토 내역)

| 옵션 | 변경 비용 | 인프라 추가 | 무료 한도 | 데이터 적합성 | 비고 |
|---|---|---|---|---|---|
| **A. GCS 단독** | 낮음 | 없음 (이미 Firebase 프로젝트 보유) | 5GB / 1GB-day | 매우 높음 | 파일 단위 1:1 매핑 |
| B. RTDB(작은 상태) + GCS(큰 파일) 하이브리드 | 중간 | 없음 | RTDB 1GB + GCS 5GB | 높음 | 정본 위치 분산 |
| C. RTDB 단독 | 높음 | 없음 | 1GB / 10GB-month | 낮음 | CSV 누적/JSONL 부적합 |
| D. Cloudflare R2 | 중간 | 새 계정 / boto3 | 10GB / egress 무한 | 매우 높음 | Firebase 외부 |
| 현행 git 유지 | 0 | 없음 | 무료 | 어뷰징 | 결정적 단점 |

### 2.1 Firebase 무료 정책 변동 (검토 시점에 발견)

[공식 FAQ](https://firebase.google.com/docs/storage/faqs-storage-changes-announced-sept-2024)
에 따라:

- **2026-02-03 부터 Spark(완전 무료) 플랜에서 Cloud Storage 사용 불가**
- 사용하려면 **Blaze(종량제) 플랜으로 업그레이드** (결제수단 등록) 필수
- Blaze 로 업그레이드해도 무료 한도(legacy `*.appspot.com` 버킷 기준)는 그대로 유지:
  - 5 GB 저장
  - 1 GB / 일 다운로드
  - 20,000 / 일 업로드 작업
  - 50,000 / 일 다운로드 작업
- Blaze 는 "한도 안에서는 0원, 초과한 만큼만 결제" 방식. 결제수단 등록 자체는 청구가 아님.

---

## 3. 결정된 사항

### 3.1 데이터 저장소 선택

**옵션 A — Firebase Cloud Storage(GCS) 단독으로 이관**

근거:
1. 이미 보유한 Firebase 프로젝트 (`qbt-live`) / 자격증명
   (`GOOGLE_APPLICATION_CREDENTIALS`) 을 그대로 재활용
   → `STATE_REPO_PAT` 환경변수 제거로 운영 단순화
2. 현재 데이터가 모두 "파일" 형태라 객체 스토리지가 가장 자연스러운 매핑
   (구조 변경 없이 옮길 수 있음)
3. 데이터 규모(~5MB)가 작아 Spark/Blaze 무료 한도 대비 1/1000 미만
4. `git_state.py` → 신규 `storage_gateway.py` 교체로 변경 범위 국지적
5. atomic 다중-객체 트랜잭션 부재 우려는 (a) write 순서를 마지막에
   `live_state.json` 으로 두고 (b) generation precondition (`if_generation_match`)
   으로 충돌 감지하면 충분히 완화 가능

### 3.2 백업 강도 선택

**Soft Delete 30일만 ON (Object Versioning 은 사용하지 않음)**

근거:
- 일별 이력은 이미 애플리케이션 레이어 (`history/states/{date}.json`,
  `history/daily/{date}.json`, `history/*.jsonl`) 에서 영구 보존하고 있어,
  git 의 commit 이력은 **재해 복구 관점에서 중복**이다.
- git 만이 보호하던 시나리오는 다음 두 가지로 좁혀진다:
  1. history 파일 자체가 깨지거나 지워지는 경우
  2. 버킷 / 리포 통째 실수 삭제
- 이 두 케이스는 GCS Soft Delete 30일로 충분히 커버된다 (콘솔 클릭 한 번에 복원).
- Object Versioning 은 "잘못된 내용으로 덮어쓰는 사고" 를 추가로 막지만,
  사용자 요구 ("혹시 모를 백업") 범위를 넘어선다 → 단순성 우선 (YAGNI).
- 30일 윈도우는 사고 인지 → 복원에 충분하며, 5GB 무료 한도 대비 비용 영향 무시 가능.

### 3.3 리전 선택

**`us-central1`**

근거:
- 무료 한도 적용 리전: `us-central1`, `us-west1`, `us-east1`
- 데이터 규모(~5MB)가 작아 latency 차이 무시 가능
- GitHub Actions 의 기본 러너도 us 권역이라 자연스러움

### 3.4 인증 / 자격증명

**기존 `GOOGLE_APPLICATION_CREDENTIALS` (Firebase Admin SDK service account) 재사용**

- RTDB 와 동일 자격증명에 GCS 접근 권한이 자동 포함된다 (Firebase Admin SDK 기본 역할)
- `STATE_REPO_PAT` 는 GCS 이관 후 **제거**
- 새 환경변수 도입은 없음 (버킷 이름은 코드 상수로 관리)

---

## 4. 사용자가 직접 해야 할 일 (Pre-Code Setup)

> 본 섹션은 사용자가 Firebase / Google Cloud 콘솔에서 직접 수행해야 하는 작업이다.
> 코드 변경에 앞서 5단계가 모두 완료되어야 한다.
> 각 단계는 **액션(클릭 흐름)** 과 **결과(완료 후 상태)** 형식으로 기술한다.

### 1단계 — Blaze 플랜 업그레이드

**액션**:

1. [Firebase Console](https://console.firebase.google.com/) 접속 → 프로젝트 `qbt-live` 선택
2. 좌측 메뉴 하단 **"업그레이드"** 버튼 클릭
   (또는 좌측 톱니 아이콘 → "사용량 및 결제" → "요금제 변경")
3. **"Blaze - 사용한 만큼만 지불"** 선택
4. **Google Cloud 결제 계정 연결** (신용카드 등록)
5. 업그레이드 확인 클릭

**결과**:

- 프로젝트 요금제가 `Spark` → `Blaze` 로 변경됨
- Firebase Console 좌측 하단에 `Blaze (사용한 만큼만 지불)` 표시
- Cloud Storage 메뉴 사용 가능 상태로 전환됨
- 무료 한도(5GB / 1GB-day) 내에서는 청구 없음

**주의**:

- 결제수단 등록 자체는 청구가 아니다. 무료 한도 초과 시에만 결제.
- 이후 단계 (4단계 예산 알림) 까지 진행하면 사고 위험을 사실상 제로화.

---

### 2단계 — Cloud Storage 활성화 + 버킷 생성

**액션**:

1. [Firebase Console](https://console.firebase.google.com/) → 프로젝트 `qbt-live` → 좌측 메뉴 **"빌드 > Storage"** 클릭
2. 화면 중앙의 **"시작하기"** 버튼 클릭
3. 다이얼로그 1 — 보안 규칙: **"잠금 모드(production mode)"** 선택 → 다음
   (live 는 서버사이드 Admin SDK 로만 접근하므로 클라이언트 전체 차단이 맞다)
4. 다이얼로그 2 — Cloud Storage 위치(리전) 선택: **`us-central1` (Iowa)** 선택 → 완료
5. 버킷 생성 완료 후 화면 상단에 표시되는 **버킷 이름** 메모 (예: `qbt-live.appspot.com` 또는 `qbt-live.firebasestorage.app`)

**결과**:

- 프로젝트에 기본 Cloud Storage 버킷 1개 생성됨
- 버킷 리전: `us-central1` (무료 한도 적용 리전)
- 보안 규칙: 클라이언트 SDK 직접 접근 차단 (Admin SDK 는 영향 없음)
- 버킷 이름이 명확히 식별됨 (다음 세션에 공유 필요)

**주의**:

- 리전은 한 번 정하면 변경 불가. `us-central1` 외에 한국 리전(`asia-northeast3` 등)을
  선택하면 무료 한도 미적용 → 반드시 `us-central1` 로 설정.
- 버킷 이름 형식 (`*.appspot.com` vs `*.firebasestorage.app`) 은 프로젝트 생성 시점에
  따라 다를 수 있다. 어느 쪽이든 동작은 동일하나 **정확한 이름을 메모해 다음 세션에
  공유**해야 한다 (코드 상수로 사용).

---

### 3단계 — Soft Delete 보관 기간을 30일로 연장

**액션**:

1. [Google Cloud Console](https://console.cloud.google.com/) 접속 → 상단 프로젝트 선택기에서 `qbt-live` 선택
2. 좌측 메뉴 (또는 검색창에서 검색) → **"Cloud Storage > 버킷"** 진입
3. 2단계에서 만든 버킷 클릭 (예: `qbt-live.appspot.com`)
4. 상단 탭 메뉴에서 **"보호(Protection)"** 클릭
5. **"Soft delete policy"** 항목의 **연필(편집) 아이콘** 클릭
6. 보관 기간을 **30일** 로 변경 → **저장**

**결과**:

- 버킷의 Soft Delete 보관 기간이 기본 7일에서 **30일** 로 변경됨
- 이후 누가 / 무엇이 객체를 삭제해도 30일 동안 자동 보관 → 콘솔에서 클릭 한 번에 복원
- 보호 범위: 실수 삭제, 코드 버그로 인한 삭제, 악성 삭제

**주의**:

- 이 설정은 Google Cloud Console 에서만 가능하다 (Firebase Console 의 Storage
  메뉴에는 동일 옵션 없음).
- Soft Delete 는 **삭제** 만 보호한다. **덮어쓰기** 는 보호하지 않는다 — 본 사례에서는
  의도적으로 Object Versioning 을 켜지 않는다 (3.2 결정 사유 참고).

---

### 4단계 — 예산 알림(Budget Alert) 설정

**액션**:

1. [Google Cloud Console](https://console.cloud.google.com/) → 좌측 메뉴 **"결제(Billing)"** 진입
2. 결제 계정 선택 (1단계에서 연결한 계정)
3. 좌측 메뉴 **"예산 및 알림(Budgets & alerts)"** 클릭
4. **"예산 만들기(Create budget)"** 클릭
5. 다음 값으로 입력:
   - 이름: `qbt-live-monthly`
   - 적용 범위(scope): 프로젝트 `qbt-live` 만 선택
   - 예산 금액: `$1` USD (현재 사용량 기준 절대 도달하지 않을 금액)
   - 알림 임계값: `50%`, `90%`, `100%`
   - 알림 수신: 결제 관리자에게 이메일 (`dbzoqltm@gmail.com`)
6. 저장

**결과**:

- 월 $1 USD 예산이 설정됨
- 50% / 90% / 100% 도달 시 자동으로 본인 이메일로 알림 발송
- 한도 초과 사고를 조기 감지 가능

**주의**:

- 예산 알림은 **알림만** 한다. 자동 차단(예: 한도 초과 시 서비스 중단) 은 하지 않는다.
  자동 차단을 원하면 별도로 "Pub/Sub + Cloud Functions" 설정이 필요하나, 본 사례
  데이터 규모상 불필요.

---

### 5단계 — Service Account 권한 확인

**액션**:

1. [Google Cloud Console](https://console.cloud.google.com/) → 프로젝트 `qbt-live` 선택
2. 좌측 메뉴 **"IAM 및 관리자(IAM & Admin) > IAM"** 진입
3. 본인의 Firebase Admin SDK service account 찾기
   - 이름 패턴: `firebase-adminsdk-XXXXX@qbt-live.iam.gserviceaccount.com`
4. 해당 행의 "역할(Role)" 컬럼 확인

**결과 (정상 케이스)**:

- 다음 중 하나 이상이 보이면 OK:
  - **"Firebase Admin SDK 관리자 서비스 에이전트"**
  - **"Firebase Admin SDK Administrator Service Agent"**
  - **"Storage 관리자 (Storage Admin)"**
  - **"Storage 객체 관리자 (Storage Object Admin)"**
- 위 역할이 보이면 추가 작업 없음. 코드 작업으로 진행 가능.

**결과 (이상 케이스)**:

- Storage 관련 역할이 **하나도 보이지 않으면** 다음 세션에 알리고 권한 추가가 필요하다.
  추가 시 `Storage Object Admin` 역할만 부여하면 충분 (최소 권한 원칙).

**주의**:

- Firebase Admin SDK 자격증명은 **대부분의 경우 Storage 권한이 자동 포함**되어 있다.
  이 단계는 확인용이며, 실제 작업이 필요한 경우는 드물다.

---

## 5. 사용자가 다음 세션에 공유할 정보

5단계가 모두 완료된 후, 다음 세션의 작성자에게 다음 정보를 공유한다.

| 항목 | 형식 | 비고 |
|---|---|---|
| Blaze 업그레이드 완료 여부 | 예 / 아니오 | 1단계 결과 |
| 버킷 이름 | `qbt-live.appspot.com` 또는 `qbt-live.firebasestorage.app` | 2단계 결과, 정확한 문자열 |
| 버킷 리전 | `us-central1` | 2단계에서 잘 설정되었는지 재확인 |
| Soft Delete 30일 적용 여부 | 예 / 아니오 | 3단계 결과 |
| Service Account Storage 권한 | 자동 포함 / 추가 부여 필요 | 5단계 결과 |
| 예산 알림 설정 여부 | 예 / 아니오 | 4단계 결과 (선택사항이지만 권장) |

---

## 6. 소스 구현의 큰 방향성

> 본 섹션은 **방향성** 만 제시한다. 구체적 함수 시그니처 / 단계 분해 / 테스트 설계는
> 다음 세션의 정식 계획서에서 작성한다.

### 6.1 신설 모듈

#### `src/live/storage_gateway.py`

GCS 객체 read / write / list / delete 를 담는 얇은 래퍼. `git_state.py` 의 역할을 대체한다.

- 책임:
  - 버킷 핸들 초기화 (Firebase Admin SDK 의 `storage.bucket()` 사용)
  - 단일 객체 업/다운로드 (Path ↔ blob 매핑)
  - prefix list (디렉토리 시뮬레이션)
  - 단일 객체 삭제 (Soft Delete 가 자동으로 보호)
  - generation precondition 기반 optimistic concurrency (필요 시)
- 비책임:
  - 고수준 비즈니스 로직 (LiveState 스키마 / history append 등은 기존 모듈 그대로)
- 예외 정책: 실패 시 `RuntimeError` 전파 (`git_state.py` 와 동일 — 자동 복구 금지 원칙)
- 인증: `firebase_admin.initialize_app()` 가 이미 호출된 상태에서 `storage.bucket()`
  호출 (RTDB 와 동일 패턴)

### 6.2 변경 모듈

#### `src/live/cli.py`

- `_ephemeral_state_repo` 컨텍스트를 GCS 동등물로 교체
  - 이름 후보: `_local_state_workspace` 또는 `_state_workspace`
  - 흐름: tempdir 생성 → GCS 에서 사용 파일을 tempdir 로 download → 명령 수행 →
    변경된 파일만 GCS 로 upload → tempdir 자동 삭제
  - 변경 감지: 다운로드 시점의 파일 mtime / 해시를 기록해두고, 컨텍스트 종료 시
    실제 변경된 파일만 업로드 (불필요한 트래픽 / 작업 횟수 절감)
- `import` 정리: `git_state` 제거, `storage_gateway` 추가
- 커밋 메시지 생성 로직 (`_now_kst_for_commit`) 은 더 이상 필요 없음 — 제거
- read-only 명령 (`drift`, `history`) 은 download 만 수행하고 upload skip

#### `src/live/constants.py`

- 제거:
  - `STATE_REPO_URL`
  - `STATE_REPO_PAT_ENV_KEY`
  - `GIT_BOT_NAME`, `GIT_BOT_EMAIL`
- 추가:
  - 버킷 이름 상수 (예: `STATE_BUCKET_NAME: Final[str] = "qbt-live.appspot.com"` —
    실제 이름은 사용자 공유 후 확정)
  - GCS 내부 객체 키 prefix 가 필요한 경우 정의
- 그대로:
  - `DEFAULT_DATA_STOCK_SUBDIR`, `DEFAULT_LIVE_STATE_FILENAME`,
    `DEFAULT_APPLIED_*_FILENAME`, `HISTORY_*_SUBDIR`, `HISTORY_*_FILENAME` 등
    파일명 / 경로 구조는 GCS 객체 키로 그대로 재사용

### 6.3 제거 모듈

#### `src/live/git_state.py`

전체 제거. 모든 호출처를 `storage_gateway` 로 교체한 뒤 마지막 단계에서 삭제.

### 6.4 데이터 모델 / 파일 구조

**변경 없음**. GCS 객체 키 구조는 git 리포 디렉토리 구조를 1:1 미러링한다.

```
git: qbt-live-state/live_state.json
GCS: gs://qbt-live.appspot.com/live_state.json

git: qbt-live-state/data/stock/SPY.csv
GCS: gs://qbt-live.appspot.com/data/stock/SPY.csv

git: qbt-live-state/history/states/2026-05-06.json
GCS: gs://qbt-live.appspot.com/history/states/2026-05-06.json
```

### 6.5 동시성 처리

GCS 는 다중-객체 atomic 트랜잭션이 없다. 다음 두 가지 보호 장치를 둔다:

1. **쓰기 순서**: 명령 종료 시 `live_state.json` 을 **마지막에** 업로드.
   부분 실패 시 LiveState 의 최신성이 늦춰질 뿐, 잘못된 상태로 갱신되지는 않음.
2. **Optimistic concurrency** (선택): `live_state.json` 업로드 시
   `if_generation_match=expected_generation` precondition 사용. 다른 실행이 동시에
   덮어썼다면 412 Precondition Failed → `RuntimeError` 전파.
   - 실제로는 GitHub Actions 가 매일 1회 + 사용자 수동 명령이 동시에 도는 경우가
     드물어 우선순위는 낮다. 정식 계획서에서 필요 여부 재검토.

### 6.6 일괄 데이터 이관 (1회성)

기존 `qbt-live-state` git 리포에 있는 모든 파일을 GCS 버킷으로 1회 이관해야 한다.

- 형태: 별도 마이그레이션 스크립트 (예: `scripts/migrate/git_state_to_gcs.py`)
  - 위치는 `scripts/` 의 도메인 분류 규칙을 따른다 (live 전용이라면 신규
    `scripts/live/` 또는 단발성을 명시하는 폴더 검토).
- 실행 주체: 사용자 (CLAUDE.md 의 "스크립트 실행 규칙" 에 따라 AI 모델은 직접 실행 X)
- 실행 시점: 코드 이관 완료 + 사용자 인프라 설정 완료 후, GitHub Actions cutover 직전
- 흐름:
  1. 기존 git 리포를 일반 clone (depth 미지정 — 전체 데이터)
  2. 모든 파일을 GCS 버킷에 업로드 (디렉토리 구조 그대로)
  3. 업로드 검증 (객체 수 / 사이즈 비교)
- 1회 실행 후 폐기 (또는 `docs/archive/` 에 기록만 남김)

### 6.7 GitHub Actions workflow

- `.github/workflows/` 의 daily run 워크플로우에서 `STATE_REPO_PAT` secret 사용 제거
- 자격증명은 기존 `GOOGLE_APPLICATION_CREDENTIALS` 만 유지 (`secrets.FIREBASE_CRED_JSON`
  등 기존 패턴 유지)
- 워크플로우 yaml 의 `env:` 블록 정리

### 6.8 환경변수 / 시크릿 변화

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| `STATE_REPO_PAT` | 필수 | **제거** |
| `GOOGLE_APPLICATION_CREDENTIALS` | 필수 | 그대로 유지 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 필수 | 그대로 유지 |

### 6.9 테스트 변화

- `tests/live/test_git_state.py` 제거 (해당 모듈 자체가 사라짐)
- `tests/live/test_storage_gateway.py` 신설 — GCS Admin SDK 를 mock 하여
  업/다운로드 / list / 삭제 / generation precondition 동작 검증
- `tests/live/conftest.py` 의 mock 픽스처에 `firebase_admin.storage` 모킹 추가
- 기존 통합 테스트 (`test_cli_*.py`, 회귀 테스트 `test_regression.py`) 는
  ephemeral 컨텍스트 mock 만 storage 버전으로 교체. 비즈니스 로직 검증 부분 영향 없음.

---

## 7. 영향 범위 (다음 세션 계획서의 Scope 절 입력)

### 7.1 변경 대상 파일 (예상)

| 카테고리 | 파일 | 변경 형태 |
|---|---|---|
| 신설 | `src/live/storage_gateway.py` | 신규 작성 |
| 신설 | `tests/live/test_storage_gateway.py` | 신규 작성 |
| 신설 | `scripts/migrate/git_state_to_gcs.py` (또는 동등) | 신규 작성 (1회성) |
| 수정 | `src/live/cli.py` | ephemeral 컨텍스트 교체, import 정리 |
| 수정 | `src/live/constants.py` | git 관련 상수 제거, 버킷 상수 추가 |
| 수정 | `src/live/CLAUDE.md` | "ephemeral state repo" 섹션 → "GCS 버킷" 섹션으로 갱신 |
| 수정 | `tests/live/conftest.py` | storage mock 픽스처 추가 |
| 수정 | `.github/workflows/*.yml` (daily run) | `STATE_REPO_PAT` 사용 제거 |
| 수정 | `README.md` | live 섹션의 인프라 설명 갱신 |
| 수정 | `docs/COMMANDS.md` | live 워크플로우 환경변수 안내 갱신 |
| 수정 | `docs/DESIGN_QBT_LIVE_FINAL.md` | git 정본 → GCS 정본 기술 변경 (관련 절만) |
| 제거 | `src/live/git_state.py` | 전체 삭제 |
| 제거 | `tests/live/test_git_state.py` | 전체 삭제 |

### 7.2 검증 (Definition of Done 후보 — 정식 계획서에서 확정)

- `poetry run python validate_project.py` 가 `failed=0 skipped=0` 통과
- live `run-daily` 명령이 GCS 정본으로 정상 동작 (로컬 dry-run)
- 회귀 테스트 (`test_regression.py`) 통과 — equity / positions / cash 일치
- GitHub Actions daily run 1회 이상 성공
- `qbt-live-state` git 리포의 데이터가 GCS 버킷에 100% 미러링됨 (객체 수 / 사이즈 검증)

---

## 8. 리스크 및 완화

| 리스크 | 발생 시나리오 | 완화책 |
|---|---|---|
| 부분 업로드로 LiveState 일관성 깨짐 | 명령 중간에 네트워크/프로세스 장애 | `live_state.json` 을 마지막에 업로드. 다음 실행 시 download 로 정합 복원 |
| 동시 실행 (Actions + 수동) 으로 덮어쓰기 충돌 | 사용자가 GH Actions 도는 시각에 수동 명령 실행 | `if_generation_match` precondition (선택). 1차로는 운영 가이드로 회피 |
| Blaze 한도 초과로 청구 발생 | 코드 버그로 무한 루프 업로드 | 4단계 예산 알림 + GCS 작업 횟수 한도 인지 + 코드 리뷰 |
| Service Account 권한 부족 | 자동 권한 부여가 안 된 케이스 | 5단계 사전 확인. 부족 시 `Storage Object Admin` 부여 |
| 데이터 이관 누락 | 마이그레이션 스크립트가 일부 파일 빠뜨림 | 이관 후 객체 수 / 총 사이즈 비교 검증 단계 필수 |
| Soft Delete 만으로 복구 불가능한 사고 | 30일 초과 후 발견되는 corruption | 일별 스냅샷 (`history/states/{date}.json`) 이 1차 복구 수단 — 그대로 보존 |
| GitHub Actions 의 OIDC vs key-file 인증 충돌 | 인증 방식 변경 영향 | 현재 `GOOGLE_APPLICATION_CREDENTIALS` 방식 그대로 유지 |

---

## 9. 본 결정에서 제외한 사항 (Non-Goals)

다음은 본 이관과 함께 처리하지 **않는다**. 필요 시 별도 plan 으로 추진.

- chart_data 가 RTDB 에 직접 write 하는 부분의 GCS 이관 (RTDB 적합성 유지)
- Object Versioning 활성화
- 다중 리전 / cross-region 백업
- GCS lifecycle 규칙 (현 단계에서는 Soft Delete 30일만으로 충분)
- 외부 객체 스토리지 (R2 등) 도입
- `qbt-live-state` git 리포 자체의 archive / 삭제 처리 (이관 검증 후 사용자가 수동
  결정)

---

## 10. 다음 세션을 위한 메모

### 10.1 참고 문서 (계획서 작성 시 반드시 읽어야 함)

- [루트 CLAUDE.md](../CLAUDE.md) — 프로젝트 전반 규칙 / 코딩 표준
- [docs/CLAUDE.md](CLAUDE.md) — 계획서 작성 / 운영 규칙 (필수)
- [docs/plans/_template.md](plans/_template.md) — 계획서 템플릿
- [src/live/CLAUDE.md](../src/live/CLAUDE.md) — live 도메인 SoT (특히 "ephemeral state
  repo" 섹션은 본 이관으로 사라짐)
- [src/live/git_state.py](../src/live/git_state.py) — 제거 대상의 현행 구현
- [src/live/cli.py](../src/live/cli.py) — `_ephemeral_state_repo` 컨텍스트 정의 위치
- [src/live/constants.py](../src/live/constants.py) — 영향 받는 상수 목록
- [docs/DESIGN_QBT_LIVE_FINAL.md](DESIGN_QBT_LIVE_FINAL.md) — git 정본 기술 부분
  (해당 절 갱신 필요 여부 검토)

### 10.2 필요한 사전 정보 (사용자 공유 대기)

§5 의 표에 따라 사용자가 다음 정보를 공유해야 정식 계획서 / 코드 작업 시작 가능:

1. Blaze 업그레이드 완료 여부
2. 버킷 이름 (정확한 문자열)
3. 버킷 리전 재확인
4. Soft Delete 30일 적용 여부
5. Service Account Storage 권한 상태

### 10.3 계획서 작성 시 주의사항

- [docs/CLAUDE.md](CLAUDE.md) 의 "계획서 운영 규칙(SoT)" 섹션을 그대로 따른다.
- 본 문서의 §6, §7 을 "Scope" / "Phases" 절의 입력으로 활용하되, 계획서는
  **Phase 단위 분해 + Validation** 까지 포함해야 한다.
- 본 문서의 §3 "결정된 사항" 은 **재검토 대상이 아니다**. 계획서는 결정을 구현으로
  옮기는 단계 분해에 집중한다.
- "Phase 0 (테스트 먼저 작성)" 적용 가능성 검토:
  - `storage_gateway` 인터페이스 / 정책을 테스트로 먼저 고정 가능 여부
- 본 문서의 §4 "사용자가 직접 해야 할 일" 은 코드 작업 외 인프라 작업이므로,
  계획서에서는 **Phase 0 의 사전 조건(Pre-condition)** 으로 다루고 별도 Phase 로
  분해하지 않는다.
- 마지막 Phase 에서 `validate_project.py` 실행 + `black .` 자동 포맷 적용 1회.

### 10.4 짧은 변경 이력 / 결정 흐름 (다음 세션 컨텍스트용)

1. 사용자: "git_state 를 git 외 다른 방식으로 대체하고 싶다 (어뷰징)"
2. AI: 옵션 4종 비교 → A(GCS 단독) 추천
3. 사용자: "Firebase Cloud Storage 가 무료인지" 확인 요구
4. AI: 공식 FAQ 조회 → 2026-02-03 부터 Spark 사용 불가, Blaze 전환 필수, 단 무료 한도
   유지 사실 보고
5. 사용자: "초보자 설명 + 과거 파일 받기 가능 여부" 질문
6. AI: GCS 개념 / Object Versioning / Soft Delete 차이 설명
7. 사용자: "혹시 모를 상황 백업 목적, 일별 기록은 이미 별도 파일에 있다" 명시
8. AI: 일별 이력 중복 확인 → "Soft Delete 30일만" 안 추천
9. 사용자: 소프트 안 채택 + 인프라 사전 작업 안내 요청
10. AI: 사용자가 직접 해야 할 5단계 안내
11. 사용자: 본 사전 합의 문서 작성 의뢰 → **이 문서**

---

## 11. 변경 로그 (본 문서 자체)

- 2026-05-06: 최초 작성 (사전 합의 확정 시점)
