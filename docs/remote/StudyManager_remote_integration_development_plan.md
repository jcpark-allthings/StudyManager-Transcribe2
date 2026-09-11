# StudyManager 연동형 원격 관제 시스템 개발 계획

## 1. 목적

이 문서는 기존 StudyManager v9에 원격 관제·작업 배정·로그인 상태 관리·외부 결과 반입·NAS/STT 연계를 단계적으로 추가하기 위한 개발 계획이다.

기존 StudyManager의 강의 목록 읽기, 자동 재생, 다운로드, 스크랩, MP3 처리, OCR/FFmpeg 등 사이트별 기능은 최대한 유지한다.

새 시스템의 핵심 원칙은 다음과 같다.

1. StudyManager는 실제 사이트 작업을 수행하는 실행 노드다.
2. NUC는 사이트에 로그인하지 않고 중앙 관제만 담당한다.
3. 외부 명령과 상태 확인은 Google Sheets를 사용한다.
4. 외부 결과 파일은 Google Drive Inbox를 사용한다.
5. 학교 사이트 로그인은 특정 StudyManager 노드에 고정한다.
6. 로그인 상태는 Persistent Browser Profile로 유지한다.
7. 작업 중 대용량 파일은 각 노드의 로컬 SSD에서 처리한다.
8. NAS는 최종 저장소와 노드 간 전달 지점으로 사용한다.
9. STT는 Mac mini가 전담한다.
10. Chrome Remote Desktop은 자동화 실패 시 사용자 개입 수단으로 사용한다.

---

# 2. 목표 아키텍처

```text
[외부 사용자]
     │
     ├─ Google Sheets ── 명령 / 상태 확인
     │
     ├─ Google Drive ─── 외부 작업 결과 업로드
     │
     └─ Chrome Remote Desktop ─ 로그인/예외 처리
     │
     ▼
──────────────── 인터넷 ────────────────
     │
     ▼
[NUC Controller]
     │
     ├─ FastAPI
     ├─ SQLite
     ├─ Scheduler
     ├─ Job Queue
     ├─ Node Registry
     ├─ Google Sheets Bridge
     ├─ Google Drive Inbox Watcher
     └─ Telegram
     │
     ▼
──────────────── 집 내부 LAN ───────────
     │
     ├───────────────┐
     ▼               ▼
[StudyManager]   [StudyManager]
NODE8            JINLON
Production       Secondary/Test
     │               │
     └──────┬────────┘
            ▼
        [Synology NAS]
            │
            ▼
       [Mac mini M4]
        STT / Whisper
            │
            ▼
           NAS
```

---

# 3. StudyManager에서 새로 추가할 핵심 구성

StudyManager 내부에 다음 모듈을 추가한다.

```text
studymanager/
├─ existing/
│  ├─ site adapters
│  ├─ playback
│  ├─ download
│  ├─ scrape
│  ├─ ffmpeg
│  └─ ocr
│
├─ agent/
│  ├─ node_agent.py
│  ├─ heartbeat.py
│  ├─ job_client.py
│  ├─ progress_reporter.py
│  └─ capability.py
│
├─ auth/
│  ├─ browser_profile_manager.py
│  ├─ login_state_manager.py
│  └─ credential_store.py
│
├─ remote/
│  ├─ command_adapter.py
│  ├─ status_snapshot.py
│  └─ result_packager.py
│
└─ integration/
   ├─ nas.py
   ├─ drive_package.py
   └─ stt_handoff.py
```

기존 사이트 코드와 중앙 관제 코드를 직접 섞지 않는다.

---

# 4. StudyManager Agent

## 목적

StudyManager를 사람이 직접 실행하는 GUI 프로그램인 동시에 NUC의 작업을 받을 수 있는 Worker Node로 만든다.

Agent는 StudyManager 내부 기능을 직접 구현하지 않는다.

기존 StudyManager 기능을 호출하는 얇은 계층으로 만든다.

예:

```text
NUC Job
  ↓
Node Agent
  ↓
Job Adapter
  ↓
기존 StudyManager 기능
  ↓
결과
  ↓
Progress Reporter
  ↓
NUC
```

---

# 5. Agent 기본 기능

각 StudyManager 노드는 다음 정보를 NUC에 제공한다.

## Node 정보

- node_id
- hostname
- StudyManager version
- OS
- online 상태
- 현재 작업
- CPU 상태
- RAM 사용량
- 로컬 여유 공간
- 마지막 heartbeat 시간

## Capability

예:

### NODE8

```text
U_KNOU
KNOU_LMS
WDU
SDU
DOWNLOAD
SCRAPE
FFMPEG
OCR
MP3_CONVERT
STATUS_CHECK
```

### JINLON

```text
U_KNOU
KNOU_LMS
DOWNLOAD
SCRAPE
FFMPEG_LIGHT
STATUS_CHECK
TEST
```

---

# 6. Node ID 정책

기기 이름과 내부 ID를 분리한다.

예:

```text
NODE8
JINLON
MAC_STT
NUC_CONTROLLER
```

설정 파일 예:

```yaml
node:
  id: NODE8
  role: production
  controller_url: http://nuc.local:8000
```

향후 기기를 바꾸더라도 `NODE8`이라는 논리 역할을 유지할 수 있도록 한다.

---

# 7. NUC Controller 개발 구조

NUC에는 StudyManager 본체를 설치하지 않는다.

별도 Controller 프로젝트로 분리한다.

```text
sm-controller/
├─ app/
│  ├─ api/
│  ├─ db/
│  ├─ jobs/
│  ├─ nodes/
│  ├─ dispatcher/
│  ├─ scheduler/
│  ├─ google_sheets/
│  ├─ google_drive/
│  ├─ telegram/
│  ├─ auth/
│  └─ services/
│
├─ config/
├─ logs/
├─ data/
│  └─ controller.db
└─ main.py
```

권장 기술:

- Python
- FastAPI
- SQLite
- APScheduler
- Google Sheets API
- Google Drive API

초기에는 Redis/PostgreSQL을 사용하지 않는다.

---

# 8. Job 모델

모든 원격 명령을 Job으로 통일한다.

예:

```json
{
  "job_id": "JOB-20260911-0001",
  "type": "STATUS_CHECK",
  "site": "SDU",
  "course_id": "COURSE-001",
  "lecture_id": null,
  "preferred_node": "NODE8",
  "priority": 50,
  "payload": {},
  "status": "QUEUED"
}
```

---

# 9. Job Type 정의

초기 지원 Job Type은 다음과 같이 제한한다.

## 조회

```text
STATUS_CHECK
LIST_REFRESH
CHECK_PROGRESS
CHECK_DOWNLOAD
CHECK_UPLOAD
CHECK_LOGIN
```

## 실행

```text
START_LECTURE
DOWNLOAD_VIDEO
DOWNLOAD_MP3
SCRAPE_NOTE
CONVERT_MP3
RUN_OCR
UPLOAD_RESULT
RETRY_JOB
STOP_JOB
```

## 시스템

```text
NODE_HEALTH
SYNC_DICTIONARY
SYNC_CONFIG
STT_HANDOFF
```

기능을 처음부터 지나치게 세분화하지 않는다.

---

# 10. Job 상태

상태는 전 시스템에서 동일한 문자열을 사용한다.

```text
QUEUED
ASSIGNED
RUNNING
WAITING_LOGIN
WAITING_USER
UPLOADING
COMPLETED
FAILED
CANCELLED
RETRY_PENDING
```

---

# 11. Pull 방식

작업 노드가 NUC에서 Job을 가져오는 구조로 한다.

예:

```http
GET /api/v1/jobs/next?node_id=NODE8
```

NUC가 작업을 반환한다.

StudyManager Agent가 실행 후 상태를 보고한다.

```http
POST /api/v1/jobs/{job_id}/progress
POST /api/v1/jobs/{job_id}/complete
POST /api/v1/jobs/{job_id}/fail
```

장점:

- 작업 노드 IP 변경 영향이 작음
- 노드가 꺼져 있어도 Queue 유지
- 방화벽 구성 단순
- 여러 노드 확장 용이

---

# 12. Heartbeat

각 StudyManager Agent는 일정 주기로 NUC에 상태를 보고한다.

초기 권장:

- 30~60초 간격
- 작업 중에는 progress 이벤트 별도 보고

Heartbeat 예:

```json
{
  "node_id": "NODE8",
  "state": "IDLE",
  "current_job": null,
  "free_disk_gb": 312,
  "capabilities": ["SDU", "WDU", "FFMPEG"],
  "login_states": {
    "WDU": "LOGIN_OK",
    "SDU": "LOGIN_OK"
  }
}
```

---

# 13. Persistent Browser Profile

기존 StudyManager 브라우저 자동화와 가장 먼저 연결해야 하는 부분이다.

사이트별 프로필을 고정한다.

```text
profiles/
├─ uknou/
├─ knou_lms/
├─ wdu/
└─ sdu/
```

StudyManager가 사이트를 열 때 항상 해당 프로필을 사용한다.

브라우저 세션은 작업 노드 로컬에서만 유지한다.

다른 기기로 쿠키를 복사하지 않는다.

---

# 14. Login State Manager

StudyManager에서 로그인 상태를 표준화한다.

```text
LOGIN_OK
SESSION_EXPIRED
LOGIN_REQUIRED
MFA_REQUIRED
LOGIN_FAILED
ACCOUNT_LOCKED
UNKNOWN
```

사이트 Adapter는 사이트별 로그인 판별 방법을 구현한다.

예:

```python
adapter.get_login_state()
```

Agent는 사이트 구조를 몰라도 표준 Login State만 NUC에 전달한다.

---

# 15. 로그인 처리 순서

```text
Job 수신
 ↓
Login State 확인
 ↓
LOGIN_OK ?
 ├─ Yes → 작업 실행
 └─ No
      ↓
 기존 세션 복구 가능?
      ├─ Yes → 재확인
      └─ No
           ↓
 자동 로그인 가능?
           ├─ Yes → 로그인 시도
           └─ No
                ↓
 WAITING_LOGIN
                ↓
 NUC 보고
                ↓
 Google Sheets + Telegram 알림
                ↓
 사용자 Chrome Remote Desktop 접속
```

사용자 개입 후 Agent가 다시 로그인 상태를 확인하고 작업을 재개할 수 있도록 한다.

---

# 16. Chrome Remote Desktop의 역할

Chrome Remote Desktop은 자동 관제 통신에 사용하지 않는다.

용도는 다음으로 제한한다.

- 로그인 세션 복구
- CAPTCHA/MFA
- 사이트 UI 변경 확인
- StudyManager 오류 직접 확인
- 수동 복구

즉 Fail-safe Human Intervention 도구다.

---

# 17. Google Sheets 연동

Google Sheets는 Controller DB가 아니다.

외부 사용자 UI로만 사용한다.

권장 시트:

```text
COMMANDS
STATUS
JOBS
NODES
ERRORS
```

---

# 18. COMMANDS 시트

예:

| command_id | command | site | course | target | status |
|---|---|---|---|---|---|
| CMD-001 | STATUS_CHECK | ALL | | | RECEIVED |
| CMD-002 | CONVERT_MP3 | SDU | 과목A | REMAINING | RECEIVED |

NUC가 읽은 뒤 내부 Job으로 변환한다.

Google Sheets 행 자체를 Job DB로 사용하지 않는다.

---

# 19. STATUS 시트

사람이 읽기 쉬운 형태로 만든다.

예:

| 사이트 | 과목 | 진도 | 영상 | MP3 | 학습노트 | STT | 로그인 |
|---|---|---:|---:|---:|---:|---:|---|
| SDU | 과목A | 70% | 10/12 | 8/12 | - | 5/8 | 정상 |

---

# 20. Google Drive Inbox

외부 작업 결과를 받는 용도다.

권장 구조:

```text
StudyManager-Inbox/
├─ incoming/
├─ accepted/
└─ error/
```

외부 PC는 `incoming`에 업로드한다.

업로드 중에는:

```text
job.zip.uploading
```

완료 후:

```text
job.zip
```

NUC는 `.uploading`을 무시한다.

---

# 21. 외부 결과 패키지

표준 패키지를 정의한다.

```text
JOB-20260911-001/
├─ manifest.json
├─ source/
├─ metadata/
├─ dictionary/
└─ result/
```

manifest 예:

```json
{
  "job_id": "JOB-20260911-001",
  "site": "SDU",
  "course": "과목A",
  "source_node": "EXTERNAL_PC",
  "created_at": "2026-09-11T09:00:00+09:00",
  "requires_stt": true,
  "requires_ocr": false,
  "files": []
}
```

---

# 22. NAS 연동

NAS는 작업 중간 저장소가 아니다.

StudyManager에서 작업이 완료되면 NAS에 업로드한다.

권장 구조:

```text
NAS/
├─ incoming/
├─ source/
├─ audio/
├─ notes/
├─ ocr/
├─ stt_queue/
├─ completed/
├─ dictionary/
├─ logs/
└─ backup/
```

---

# 23. STT Handoff

StudyManager 또는 NUC가 STT 필요 여부를 판단한다.

```text
StudyManager 작업 완료
 ↓
NAS 저장
 ↓
STT 필요?
 ├─ No → COMPLETED
 └─ Yes
      ↓
 /stt_queue Job 생성
      ↓
 Mac mini 감지
      ↓
 로컬 SSD 복사
      ↓
 Whisper
      ↓
 후처리
      ↓
 NAS /completed
      ↓
 NUC 상태 갱신
```

Mac mini는 학교 사이트에 접속하지 않는다.

---

# 24. SDU 전용 처리

SDU는 MP3 변환 단계가 필요하다.

```text
SDU 영상 다운로드
 ↓
NODE8 로컬 SATA SSD
 ↓
다운로드 완료 확인
 ↓
FFmpeg MP3 변환
 ↓
MP3 품질/크기 확인
 ↓
NAS 업로드
 ↓
STT Queue
```

중간 영상 파일은 NAS에서 직접 변환하지 않는다.

---

# 25. WDU 전용 처리

WDU는 강의량이 많으므로 NODE8을 기본 노드로 한다.

수집 대상:

- 출석 인정기간
- 강의 목록
- 퀴즈 일정
- 과제 일정
- 문제풀이
- 학습정리
- 다운로드 자료

---

# 26. KNOU 계열 처리

U-KNOU / KNOU LMS는 상대적으로 작업량이 적으므로 향후 JINLON으로 분리 가능하다.

초기에는 NODE8 Production 환경에 유지해도 된다.

안정화 후:

```text
NODE8
WDU
SDU

JINLON
U-KNOU
KNOU LMS
```

방식으로 분리 가능하다.

---

# 27. 기존 StudyManager와의 통합 원칙

중요:

Agent를 추가하면서 기존 UI 동작을 변경하지 않는다.

기존 수동 사용:

```text
사용자 → StudyManager UI → 기존 기능
```

원격 사용:

```text
NUC → Agent → 기존 기능
```

두 경로가 같은 Service Layer를 호출하도록 리팩터링한다.

목표:

```text
           ┌─ GUI
Service ←──┤
           └─ Agent
```

GUI가 직접 사이트 Adapter를 호출하는 구조가 있다면 점진적으로 Service 계층으로 이동한다.

---

# 28. 권장 내부 Service API

예:

```text
LectureService
DownloadService
ScrapeService
MediaService
OCRService
AuthService
StatusService
StorageService
```

예:

```python
lecture_service.refresh_list(site, course)
download_service.download_video(...)
media_service.convert_mp3(...)
status_service.collect_course_status(...)
```

GUI와 Agent가 모두 이 API를 사용한다.

---

# 29. 원격 상태 Snapshot

외부 조회 시 브라우저의 raw DOM을 Google Sheets에 보내지 않는다.

StudyManager가 표준 Snapshot을 만든다.

예:

```json
{
  "site": "SDU",
  "course": "과목A",
  "login_state": "LOGIN_OK",
  "lectures": [
    {
      "lecture": "1강",
      "progress": 100,
      "attendance": "DONE",
      "video": "DOWNLOADED",
      "mp3": "CONVERTED",
      "nas": "UPLOADED",
      "stt": "COMPLETED"
    }
  ]
}
```

NUC가 이를 Google Sheets 표시 형식으로 변환한다.

---

# 30. 로깅

로그를 세 종류로 구분한다.

## Application Log

StudyManager 내부 오류

## Job Log

원격 Job 처리 이력

## Audit Log

누가 어떤 명령을 언제 요청했는지

예:

```text
CMD-001
→ JOB-001
→ NODE8
→ RUNNING
→ COMPLETED
```

---

# 31. 장애 처리

## Node Offline

Job을 실행하지 않고 Queue 유지.

## Login Required

WAITING_LOGIN 상태.

## Site Structure Changed

FAILED + SITE_CHANGED 오류.

## Disk 부족

DISK_LOW.

## NAS Offline

로컬 결과 유지 + UPLOAD_PENDING.

## Google Sheets 장애

NUC 내부 SQLite는 계속 운영.

연결 복구 후 상태 동기화.

---

# 32. 안전장치

원격 명령에는 위험도를 둔다.

## 자동 실행 가능

- STATUS_CHECK
- DOWNLOAD
- SCRAPE
- CONVERT_MP3

## 사용자 확인 필요 고려

- DELETE
- 강제 진도 변경
- 대량 재실행
- 계정 설정 변경

초기 원격 API에는 삭제 기능을 넣지 않는 것을 권장한다.

---

# 33. 개발 단계

## Phase 0 — 현재 v9 구조 확인

목표:
- 기존 StudyManager 기능 호출 흐름 파악
- UI → Service → Site Adapter 구조 확인
- 목록 읽기/다운로드/재생/로그인 코드 위치 확정

산출물:
- module-map.md
- remote-integration-gap.md

---

## Phase 1 — Service Layer 정리

목표:
GUI와 Agent가 동일한 기존 기능을 호출할 수 있게 한다.

우선 대상:

1. 상태 조회
2. 목록 읽기
3. 다운로드
4. MP3 변환
5. 로그인 확인

기존 기능 자체를 재작성하지 않는다.

---

## Phase 2 — StudyManager Agent MVP

구현:

- node_id
- capability
- heartbeat
- NUC 등록
- Job Pull
- Job 상태 보고

첫 Job은 `STATUS_CHECK` 하나만 지원한다.

완료 조건:

```text
NUC → STATUS_CHECK
→ NODE8
→ StudyManager 상태 수집
→ NUC 반환
```

---

## Phase 3 — NUC Controller MVP

구현:

- FastAPI
- SQLite
- Nodes
- Jobs
- Heartbeat
- Dispatcher

Google 연동 없이 로컬에서 먼저 검증한다.

완료 조건:

- NODE8 online/offline 표시
- Job 생성
- Agent가 Job 수신
- 완료 상태 저장

---

## Phase 4 — Google Sheets Remote UI

구현:

- COMMANDS 읽기
- Job 변환
- STATUS 기록
- NODES 기록
- ERRORS 기록

완료 조건:

외부에서 Sheets에 STATUS_CHECK 입력
→ NUC
→ NODE8
→ 실제 상태 확인
→ Sheets에 결과 표시

---

## Phase 5 — Persistent Browser Profile

구현:

- 사이트별 프로필 경로 표준화
- 기존 프로필 migration
- 사이트별 세션 재사용
- 브라우저 종료 후 재실행 검증

완료 조건:

StudyManager 재시작 후에도 로그인 세션 유지.

---

## Phase 6 — Login State Manager

구현:

- 사이트별 로그인 판별
- 표준 LoginState
- WAITING_LOGIN
- Google Sheets 오류 표시
- Telegram 알림

완료 조건:

세션 만료 시 원격 작업을 잘못 진행하지 않고 대기.

---

## Phase 7 — 원격 실행 Job 확대

추가:

- LIST_REFRESH
- DOWNLOAD_VIDEO
- DOWNLOAD_MP3
- SCRAPE_NOTE
- CONVERT_MP3
- UPLOAD_RESULT
- RETRY_JOB

각 기능은 기존 StudyManager Service를 호출한다.

---

## Phase 8 — NAS 연동

구현:

- 완료 파일 NAS 업로드
- upload pending
- 재시도
- checksum
- NAS 경로 규칙

---

## Phase 9 — Google Drive Inbox

구현:

- 외부 결과물 감지
- manifest 검증
- checksum
- accepted/error 이동
- NAS 반입

---

## Phase 10 — Mac mini STT 연동

구현:

- STT Queue
- Mac mini Worker
- 처리 상태
- 완료 결과
- NUC 통합 상태

---

## Phase 11 — JINLON Secondary Node

구현:

- JINLON 등록
- capability 기반 배정
- 사이트별 preferred_node
- NODE8 장애 시 fallback

초기에는 자동 failover보다 수동/명시적 배정을 우선한다.

---

## Phase 12 — Telegram / 운영 UI

추가:

- 로그인 필요
- 작업 실패
- STT 완료
- 노드 Offline
- NAS 오류
- 원격 작업 완료

향후 NUC 내부 웹 대시보드 추가 가능.

---

# 34. 구현 순서상 가장 중요한 점

전체 기능을 한 번에 개발하지 않는다.

최초 수직 통합(Vertical Slice)은 다음 하나만 완성한다.

```text
Google Sheets
 ↓
NUC
 ↓
NODE8 StudyManager
 ↓
현재 강의 상태 조회
 ↓
NUC
 ↓
Google Sheets
```

이 경로가 안정화된 뒤 실행 기능을 붙인다.

그 다음:

```text
STATUS_CHECK
→ LOGIN CHECK
→ LIST REFRESH
→ DOWNLOAD
→ CONVERT
→ NAS
→ STT
```

순서로 확장한다.

---

# 35. 첫 번째 개발 Milestone

## Remote Status MVP

목표:

회사나 외부 PC에서 Google Sheets의 명령 한 줄로 집의 NODE8 StudyManager가 실제 사이트를 조회하고 결과를 다시 Google Sheets에 기록한다.

포함:

- NUC FastAPI
- SQLite
- NODE8 Agent
- Heartbeat
- STATUS_CHECK
- 사이트 Login State
- Google Sheets COMMANDS
- Google Sheets STATUS

제외:

- 다운로드 원격 실행
- Drive Inbox
- NAS 자동 전송
- Mac STT
- JINLON 자동 분산
- 자동 로그인

이 Milestone이 성공하면 전체 설계의 핵심 통신 구조가 검증된다.

---

# 36. 두 번째 개발 Milestone

## Remote Action MVP

추가:

- LIST_REFRESH
- DOWNLOAD
- SCRAPE
- CONVERT_MP3
- Progress
- Retry
- WAITING_LOGIN

목표:

상태를 확인한 뒤 사용자가 Google Sheets에서 후속 작업을 지시할 수 있다.

---

# 37. 세 번째 개발 Milestone

## Full Pipeline

추가:

- NAS
- Google Drive Inbox
- Mac mini STT
- JINLON
- Telegram
- 자동 배정

최종 흐름:

```text
외부 사용자
→ 상태 확인
→ 작업 명령
→ NUC
→ StudyManager
→ 로컬 처리
→ NAS
→ STT
→ NAS
→ 상태 완료
→ 외부 사용자 확인
```

---

# 38. 현재 권장 노드 배치

```text
NUC
= Controller

NODE8
= StudyManager Production
= WDU/SDU 우선
= 로그인 주체
= 대량 다운로드
= FFmpeg
= OCR

JINLON
= Secondary/Test
= U-KNOU/KNOU LMS 후보
= 외부 StudyManager 후보

MAC_STT
= Whisper/STT

NAS
= 최종 저장소
```

---

# 39. Codex 작업 시 권장 구현 단위

작업은 다음 순서로 별도 브랜치 또는 작업 단위로 진행한다.

1. `refactor/service-layer`
2. `feature/node-agent`
3. `feature/controller-mvp`
4. `feature/remote-status`
5. `feature/persistent-browser-profile`
6. `feature/login-state-manager`
7. `feature/remote-actions`
8. `feature/nas-handoff`
9. `feature/drive-inbox`
10. `feature/stt-handoff`
11. `feature/multi-node-dispatch`

각 단계마다 기존 StudyManager 수동 실행 회귀 테스트를 수행한다.

---

# 40. 완료 기준

이 개발의 최종 완료 기준은 다음과 같다.

1. 외부에서 Google Sheets로 전체 과목 상태를 요청할 수 있다.
2. NUC가 로그인된 StudyManager 노드에 작업을 배정한다.
3. StudyManager가 실제 사이트에서 상태를 확인한다.
4. 결과가 Google Sheets에 표시된다.
5. 사용자가 후속 작업을 지시할 수 있다.
6. 로그인 만료 시 작업이 안전하게 정지된다.
7. Chrome Remote Desktop으로 로그인 복구 후 재개할 수 있다.
8. 대용량 작업은 로컬 SSD에서 수행된다.
9. 결과가 NAS에 자동 저장된다.
10. STT 필요 파일은 Mac mini로 전달된다.
11. JINLON을 보조 노드로 추가할 수 있다.
12. 기존 StudyManager 수동 기능은 그대로 사용할 수 있다.

---

# 41. 최종 개발 원칙

**StudyManager를 원격 제어 프로그램으로 새로 만드는 것이 아니라, 기존 StudyManager의 기능을 Service Layer로 정리하고 그 위에 Node Agent를 추가한다. NUC는 해당 Agent들을 관제하고 Google Sheets는 사용자의 원격 명령·상태 인터페이스가 된다.**

이 원칙을 유지하면 기존 v9 개발을 계속 진행하면서 원격 관제 기능을 독립적으로 단계별 추가할 수 있다.
