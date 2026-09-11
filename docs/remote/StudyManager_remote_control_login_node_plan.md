# StudyManager 원격 관제·로그인·작업 노드 통합 설계안

## 1. 설계 목적

이 문서는 집 내부의 고정 인프라와 외부 작업 PC를 분리하고, StudyManager를 원격으로 제어하면서도 로그인 문제를 최소화하기 위한 전체 운영 구조를 정의한다.

핵심 목표는 다음과 같다.

- 집 내부 장비는 역할을 고정해 안정적으로 운영한다.
- 외부 PC는 원격 데스크톱으로 집 장비를 조작하지 않고, 작업 결과를 업로드하거나 작업 명령만 전달한다.
- NUC는 중앙 관제만 담당하고 학교 사이트에는 직접 로그인하지 않는다.
- 실제 학교 사이트 로그인은 특정 Windows 작업 노드에 고정한다.
- 로그인 세션은 영구 브라우저 프로필(Persistent Browser Profile)로 유지한다.
- 세션이 만료되면 자동 재로그인을 시도하고, 불가능한 경우 사용자에게 알린다.
- 대용량 파일 처리 중에는 NAS를 작업 디스크처럼 사용하지 않고 각 작업 노드의 로컬 SSD를 사용한다.
- NAS는 최종 저장소와 노드 간 작업 전달 지점으로만 사용한다.

---

## 2. 전체 장비 역할

### 2.1 집 내부 고정 장비

#### NUC
역할: 중앙 관제 서버

예상 사양:
- Intel 5세대 i3
- RAM 8GB
- 유선 LAN

주요 기능:
- 중앙 Job Queue 관리
- SQLite 기반 상태 DB
- 작업 노드 Heartbeat 확인
- 작업 배정
- Google Sheets 원격 명령 수신
- Google Sheets 상태 결과 기록
- Google Drive 외부 반입함 감시
- Telegram 알림
- 작업 실패/재시도 관리
- Wake-on-LAN 기능
- 각 노드 상태 확인

NUC는 학교 사이트에 로그인하지 않는다.

---

#### Mac mini M4

역할: STT 전담 작업 노드

주요 기능:
- Whisper 음성 전사
- 사용자 사전 적용
- 전사 후처리
- 품질 검토
- STT 결과 생성
- 처리 완료 후 NAS 저장

작업 원칙:
- NAS에서 작업 대상 파일을 로컬 SSD로 복사
- 로컬 SSD에서 STT 처리
- 완료 결과만 NAS에 저장

---

#### Synology NAS

역할: 중앙 저장소

주요 기능:
- 원본 강의 자료 보관
- MP3 보관
- 학습노트 보관
- OCR 결과 보관
- STT 결과 보관
- 사용자 사전 중앙본 보관
- 작업 완료 자료 보관
- 백업
- 외부 반입 자료의 최종 저장

NAS는 실시간 작업 디스크로 사용하지 않는다.

---

### 2.2 Windows 작업 노드

#### 8세대 i5 노트북

예상 사양:
- Intel 8세대 i5
- RAM 16GB
- SATA SSD 500GB
- 유선 LAN 가능

역할:
- 주 StudyManager Production Node
- 학교 사이트 로그인 전담 노드
- 대량 자료 수집
- WDU / SDU 우선 처리
- SDU 영상 다운로드
- SDU MP4 → MP3 변환
- PDF-XChange OCR
- FFmpeg
- 대용량 임시 파일 처리

권장 이유:
- 500GB SSD로 대량 강의 임시 저장에 유리
- 유선 LAN으로 NAS 업로드에 유리
- SDU처럼 영상 다운로드 후 MP3 변환이 필요한 작업에 적합

---

#### HP Jinlon

예상 사양:
- Intel 10세대 i7
- RAM 16GB
- NVMe SSD 256GB
- Wi-Fi

역할:
- 보조 Windows 작업 노드
- 외부 작업 PC
- StudyManager 개발/테스트 노드
- 필요 시 KNOU 계열 보조
- 소량 수집 및 스크랩
- 장애 시 8세대 노트북 대체

운영 원칙:
- 내부에서 사용할 경우 Production 노드와 개발/테스트 환경을 분리
- 대용량 파일을 장기간 쌓아두지 않음
- 로컬 NVMe에서 짧고 빠른 작업 수행 후 결과만 업로드

---

## 3. 사이트별 기본 작업 배치

현재 강의량과 처리방식을 고려한 기본 배치는 다음과 같다.

### U-KNOU
기본 노드:
- 8세대 노트북 또는 Jinlon

특징:
- 전체 강의량이 상대적으로 적음
- MP3 다운로드 가능
- 학습노트 수집
- 강의 진행 상태 확인

---

### KNOU LMS
기본 노드:
- 8세대 노트북 또는 Jinlon

특징:
- 전체 강의량이 상대적으로 적음
- 강의별 MP3 수집
- 학습노트 수집
- 강의 진행 상태 확인

---

### WDU
기본 노드:
- 8세대 노트북

특징:
- 강의량이 상대적으로 많음
- 자료 수집량이 많음
- 강의 목록/출석 인정기간/퀴즈/과제 일정 수집
- 문제풀이 및 학습정리 스크랩

---

### SDU
기본 노드:
- 8세대 노트북

특징:
- 강의량이 상대적으로 많음
- 영상 다운로드 필요
- 영상이 HLS 방식이 아니므로 curl 등으로 직접 다운로드 가능
- MP3가 별도 제공되지 않으므로 영상 다운로드 후 FFmpeg 변환 필요
- 대용량 임시 저장 공간 필요

---

## 4. 전체 통신 구조

기본 구조:

사용자  
→ Google Sheets  
→ NUC 관제 서버  
→ Windows StudyManager 작업 노드  
→ NAS  
→ Mac mini STT  
→ NAS

대용량 파일은 Google Sheets로 전달하지 않는다.

구분:

- 명령/상태: Google Sheets
- 외부 결과물: Google Drive Inbox
- 내부 상태 DB: NUC SQLite
- 내부 작업 명령: NUC FastAPI
- 대용량 최종 파일: NAS
- STT 작업: Mac mini 로컬 SSD

---

## 5. 원격 사용 시나리오 A  
## 외부에서 StudyManager를 직접 사용하는 경우

외부에서 Jinlon 또는 다른 Windows PC로 StudyManager를 직접 실행한다.

흐름:

1. 외부 PC에서 StudyManager 실행
2. 사용자가 해당 사이트에 정상 로그인
3. 강의 자료 수집
4. 학습노트/MP3/영상/메타데이터 생성
5. 로컬 SSD에서 필요한 후처리
6. 작업 완료 패키지 생성
7. Google Drive Inbox에 업로드
8. NUC가 새 패키지 감지
9. 파일 무결성 및 manifest 확인
10. NAS의 적절한 위치로 이동
11. STT 필요 작업은 STT Queue 생성
12. Mac mini가 STT 작업 처리
13. 결과를 NAS에 저장
14. NUC가 Google Sheets에 완료 상태 기록

이 경우 외부 PC에서 집 내부 장비를 원격 조작하지 않는다.

---

## 6. 원격 사용 시나리오 B  
## 외부에서 작업 결과물만 업로드하는 경우

StudyManager가 아닌 다른 프로그램이나 수동 작업으로 생성한 결과물도 동일하게 처리한다.

흐름:

1. 외부 PC에서 파일 생성
2. 지정된 작업 패키지 형식으로 정리
3. Google Drive Inbox 업로드
4. NUC가 감지
5. 파일 검증
6. NAS 반입
7. 필요 시 OCR/STT Queue 등록
8. 결과 처리
9. Google Sheets에 상태 기록

---

## 7. 원격 사용 시나리오 C  
## Google Sheets를 통한 StudyManager 상태 조회

사용자가 외부에서 현재 강의 상태를 보고 싶을 때 사용한다.

예시 명령:

- STATUS ALL
- STATUS U-KNOU
- STATUS WDU
- CHECK_PROGRESS
- CHECK_UPLOAD
- CHECK_DOWNLOAD

처리 흐름:

1. 사용자가 Google Sheets COMMANDS 시트에 상태조회 명령 입력
2. NUC가 명령 감지
3. NUC가 담당 StudyManager Agent에 조회 요청
4. 해당 Windows 노드가 기존 로그인 세션을 사용해 사이트 확인
5. StudyManager가 강의별 상태 수집
6. 결과를 NUC에 반환
7. NUC가 Google Sheets STATUS 시트에 기록
8. 사용자가 결과 확인
9. 필요한 후속 명령 결정

조회 가능한 상태 예시:

- 과목
- 강의명
- 현재 진도율
- 수강 완료 여부
- 출석 인정 여부
- 자료 다운로드 여부
- MP3 다운로드 여부
- MP3 변환 여부
- 학습노트 저장 여부
- NAS 업로드 여부
- STT 대기 여부
- STT 완료 여부
- 오류 여부

---

## 8. 원격 사용 시나리오 D  
## 상태 확인 후 후속 명령 전달

상태 확인 후 사용자가 다시 Google Sheets에 명령을 입력한다.

예:

- START
- DOWNLOAD
- SCRAPE
- CONVERT_MP3
- UPLOAD
- RETRY
- STOP

흐름:

사용자  
→ Google Sheets COMMANDS  
→ NUC  
→ 대상 노드 선택  
→ StudyManager Agent  
→ 작업 실행  
→ 진행률 NUC 보고  
→ Google Sheets 상태 갱신

---

## 9. 로그인 설계

### 핵심 원칙

같은 사이트의 로그인 세션을 여러 장비에 복사하지 않는다.

대신:

**로그인된 노드로 작업을 보낸다.**

---

## 10. 로그인 담당 노드

초기 권장 구성:

### NUC
- 로그인 없음

### Mac mini
- 로그인 없음

### NAS
- 로그인 없음

### 8세대 노트북
- U-KNOU
- KNOU LMS
- WDU
- SDU
- Production 로그인 세션 보유

### Jinlon
- 기본적으로 로그인 없음
- 외부 직접 사용 시 해당 세션을 별도로 사용
- 내부 보조 노드로 정식 편입할 경우 사이트별로 로그인 담당을 고정

향후 작업량이 많아질 경우:

- 8세대 노트북: WDU / SDU
- Jinlon: U-KNOU / KNOU LMS

처럼 사이트별 로그인 책임을 분리할 수 있다.

---

## 11. Persistent Browser Profile

StudyManager는 사이트별 영구 브라우저 프로필을 사용한다.

예:

StudyManager/
- browser_profiles/
  - uknou/
  - knou_lms/
  - wdu/
  - sdu/

처음 한 번 사용자가 직접 로그인한다.

이후 StudyManager는 항상 같은 브라우저 프로필을 사용한다.

유지 대상:

- 로그인 쿠키
- 세션 정보
- 사이트 설정
- 브라우저 Local Storage
- 로그인 상태

---

## 12. Login State Manager

StudyManager에 Login State Manager를 추가한다.

상태 예:

- LOGIN_OK
- SESSION_EXPIRED
- LOGIN_REQUIRED
- MFA_REQUIRED
- ACCOUNT_LOCKED
- LOGIN_FAILED

처리 우선순위:

1. 기존 Persistent Browser Profile 세션 사용
2. 세션 만료 여부 확인
3. 가능한 경우 저장된 자격정보로 자동 로그인
4. 추가 인증 또는 사용자 개입 필요 여부 확인
5. 자동 로그인이 불가능하면 LOGIN_REQUIRED
6. NUC로 상태 전달
7. Google Sheets 및 Telegram 알림
8. 해당 작업 QUEUED 또는 PAUSED 유지

---

## 13. 자격정보 저장 원칙

금지:
- Google Sheets 평문 비밀번호
- SQLite 평문 비밀번호
- NAS 일반 텍스트 파일에 비밀번호 저장

권장:
- Windows Credential Manager
- OS 보안 저장소
- 암호화된 Secret Storage

Google Sheets에는 비밀번호가 아닌 상태만 기록한다.

---

## 14. NUC 내부 관제 스택

권장 구성:

- Python
- FastAPI
- SQLite
- APScheduler
- Google Sheets 연동
- Google Drive 연동
- Telegram Bot

기능 모듈 예:

controller/
- api/
- dispatcher/
- scheduler/
- db/
- google_sheets/
- google_drive/
- telegram/
- node_registry/
- heartbeat/
- job_queue/
- retry_manager/

---

## 15. StudyManager Agent

각 Windows 작업 노드의 StudyManager에 Agent 기능을 넣는다.

StudyManager/
- UI
- Site Adapters
- Downloader
- Scraper
- FFmpeg Worker
- OCR Worker
- Login State Manager
- Browser Profile Manager
- Node Agent
  - Heartbeat
  - Job Pull
  - Status Report
  - Progress Report
  - Result Report

---

## 16. Push가 아닌 Pull 방식 권장

NUC가 Windows 노드에 직접 작업을 밀어넣기보다 작업 노드가 NUC에 작업을 요청한다.

예:

GET /api/jobs/next?node=NODE8

장점:

- 작업 노드 IP 변경 영향 감소
- 노드 재부팅 후 자동 복귀 가능
- 방화벽 관리 단순화
- 노드가 꺼져 있어도 Queue 유지
- 여러 작업 노드 추가가 쉬움

---

## 17. Node Capability 기반 작업 배정

예:

### NODE8
- U_KNOU
- KNOU_LMS
- WDU
- SDU
- DOWNLOAD
- FFMPEG
- OCR
- SCRAPE

### JINLON
- U_KNOU
- KNOU_LMS
- DOWNLOAD
- SCRAPE
- FFMPEG_LIGHT
- TEST

NUC는 다음 기준으로 작업을 배정한다.

1. 사이트 담당 노드
2. 로그인 가능 여부
3. Node Online 여부
4. Capability
5. 현재 작업량
6. 저장공간
7. 우선순위

---

## 18. Google Sheets 구조

권장 시트:

### COMMANDS
사용자가 입력하는 명령

예:
- command_id
- command
- site
- course
- action
- target
- requested_at
- status

### STATUS
사람이 읽는 현재 상태

### JOBS
실제 작업 Queue 상태

### NODES
각 노드 상태

예:
- NODE8
- JINLON
- MACMINI
- ONLINE/OFFLINE
- LAST_HEARTBEAT
- CURRENT_JOB

### ERRORS
오류 및 로그인 요구 상태

---

## 19. Google Drive 외부 반입함

권장 구조:

StudyManager-Inbox/
- incoming/
- accepted/
- error/

업로드 중 파일은 완료 파일과 구분한다.

예:

lecture_package.zip.uploading

업로드 완료 후:

lecture_package.zip

NUC는 .uploading 파일을 무시한다.

---

## 20. 외부 작업 패키지 형식

예:

job_20260911_001/
- manifest.json
- source/
  - lecture.mp4
  - lecture.mp3
  - note.pdf
- metadata/
  - course.json
  - lecture.json
- dictionary/
  - user_terms.json

manifest 필드 권장:

- job_id
- site
- course
- lecture
- source_node
- created_at
- files
- file_size
- checksum
- requires_stt
- requires_ocr
- requires_ffmpeg

---

## 21. 로컬 처리 원칙

대용량 작업은 모두 로컬 SSD에서 처리한다.

### 8세대 노트북

인터넷  
→ SATA SSD 500GB  
→ 다운로드  
→ OCR / FFmpeg / 정리  
→ 작업 완료  
→ NAS

### Mac mini

NAS  
→ Mac mini 로컬 SSD  
→ Whisper/STT  
→ 후처리  
→ NAS

### Jinlon

인터넷  
→ NVMe 256GB  
→ 짧은 작업/스크랩/테스트  
→ 완료  
→ NAS 또는 Google Drive

---

## 22. 전체 최종 구조

### 집 내부

NUC
= 중앙 관제

Mac mini M4
= STT

Synology NAS
= 중앙 저장소

8세대 i5 노트북
= Production StudyManager / 로그인 / 대량 작업

### 외부 또는 보조

Jinlon
= 외부 StudyManager / 개발 테스트 / 보조 작업

기타 외부 PC
= 결과물 업로드 또는 원격 명령 입력

---

## 23. 최종 운영 원칙

1. NUC는 관제만 한다.
2. 학교 사이트 로그인은 Windows 작업 노드에 고정한다.
3. 로그인 세션은 Persistent Browser Profile로 유지한다.
4. 세션이 만료되면 Login State Manager가 감지한다.
5. 사용자 개입이 필요한 경우 Google Sheets/Telegram으로 알린다.
6. 외부 명령은 Google Sheets를 사용한다.
7. 외부 대용량 결과물은 Google Drive Inbox로 받는다.
8. 내부 대용량 파일은 NAS에 최종 저장한다.
9. 작업 중간 파일은 각 노드의 로컬 SSD에서 처리한다.
10. Mac mini는 STT만 담당한다.
11. NUC는 SQLite를 기준 DB로 사용한다.
12. Google Sheets는 관제 DB가 아니라 외부 명령/상태 인터페이스로 사용한다.
13. 같은 사이트 세션을 여러 PC에 복사하지 않는다.
14. 필요 시 사이트별 로그인 담당 노드를 분리한다.
15. 작업 노드는 NUC에서 작업을 Pull하는 방식으로 동작한다.

---

## 24. 개발 우선순위

### Phase 1
- NUC Controller 기본 구조
- SQLite Job Queue
- FastAPI
- Node Heartbeat
- StudyManager Agent 기본 통신

### Phase 2
- Google Sheets COMMANDS/STATUS 연동
- 원격 상태조회
- 작업 실행 명령
- 결과 기록

### Phase 3
- Persistent Browser Profile
- Login State Manager
- 세션 만료 감지
- LOGIN_REQUIRED 알림

### Phase 4
- Node Capability
- 자동 작업 배정
- Retry Manager
- Node Offline 처리

### Phase 5
- Google Drive Inbox
- 외부 작업 패키지
- checksum 검증
- NAS 자동 반입

### Phase 6
- Mac mini STT Queue 연계
- STT 완료 결과 회수
- 전체 상태 통합

### Phase 7
- Telegram 명령/알림
- 대시보드
- 운영 로그
- 장애 복구 자동화

---

## 25. 최종 핵심 문장

**사용자는 Google Sheets에서 상태를 확인하고 명령을 내리며, NUC는 이를 해석·배정하고, 로그인 세션을 가진 StudyManager 작업 노드가 실제 사이트 작업을 수행한다. 대용량 파일은 각 노드의 로컬 SSD에서 처리한 뒤 NAS에 최종 저장하고, STT는 Mac mini가 전담한다.**
