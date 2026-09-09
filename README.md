# StudyManager-Transcribe2

독립 구현한 **0.1.0 개발 미리보기**입니다. 미니·다른 Windows PC의 준비 앱과 맥미니의 AI 허브를 분리합니다. 원본 StudyManager-Transcribe와 코드·Git remote·데이터베이스를 연동하지 않습니다.

## 지금 실행 가능한 기능

- 준비 앱: MP3/WAV/M4A 등록, TXT/MD/검색 가능한 PDF에서 규칙 기반 용어 후보 추출, 사전 편집, 작업별 사전 스냅샷, PC별 전달 폴더, 완료 결과 읽기.
- 허브 앱: 입력 해시 검증·맥 로컬 인수, SQLite 큐, MLX Whisper 어댑터, 원본 TXT/JSON, 대기 취소·실패 재시도·중단 복구, 인수 상태·결과 내보내기.
- 두 개의 Tkinter 창과 CLI. 자동 감시 대신 명시적인 인수·전사 버튼을 사용하는 초기 버전입니다.

**실제 음성 인식·Windows/macOS GUI 실행은 아직 해당 장비에서 검증하지 않았습니다.** 자동 테스트는 대체 전사 함수로 파일 전달·큐·복구를 검증합니다. 완성된 설치 파일은 아직 제공하지 않습니다.

## 미니 / 노트북 / 다른 Windows PC

Python 3.11 이상(Tkinter 포함)이 필요합니다. 저장소를 내려받아 `scripts/Start-Prep.cmd`를 실행하세요. Python이 없으면 설치 안내를 표시합니다. 초기 버전은 Python 자체를 자동 설치하지 않습니다.

터미널에서는 저장소 루트에서:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -e ".[pdf]"
.venv\Scripts\python -m smt2 gui prep
```

1. 교환 폴더를 고릅니다. NAS 설정 전에는 로컬 폴더로 시험합니다.
2. 수집이 완료된 오디오와 강의 제목을 입력합니다.
3. 필요하면 자료에서 용어 후보를 추출하고 검토합니다. 사전을 비워도 됩니다.
4. `전달 준비`를 누릅니다. 이 시점은 **맥 인수 완료가 아닙니다**.
5. 맥이 작업을 인수·상태 내보내기 한 뒤 `맥 인수·처리 상태 확인`으로 확인합니다.

미니의 강의 다운로드·오디오 변환은 별도 수집 앱의 역할입니다. 준비 앱에는 AI 호출·API 키가 없습니다. PDF-XChange OCR은 외부에서 수행한 후 검색 가능한 PDF로 가져옵니다. OCR 자동 실행은 미구현입니다.

## 맥미니 AI 허브

Apple Silicon Mac, Python 3.11 이상(Tkinter 포함), FFmpeg가 필요합니다. Python/FFmpeg 설치 여부를 먼저 확인합니다. 이 문서는 시스템 패키지를 자동 변경하지 않습니다.

```bash
python3 -m tkinter
ffmpeg -version
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mac,pdf]'
.venv/bin/python -m smt2 gui hub
```

환경 준비 후 `bash scripts/Start-Hub.command`로 다시 실행할 수 있습니다.

1. 준비 앱과 같은 내용이 보이는 교환 폴더를 선택합니다.
2. `준비된 작업 인수`를 누릅니다. 허브 로컬 복사·검증·DB 커밋 후 상태를 내보냅니다.
3. `다음 1건 전사`를 누릅니다. 최초 모델 다운로드는 네트워크가 필요할 수 있습니다.
4. 결과는 허브 로컬과 교환 폴더 `results/<device_id>/<request_id>/<attempt>/`에 저장됩니다.
5. `complete.json`이 있고 해시가 일치하는 결과만 완성된 결과로 취급합니다.

기본 모델 ID는 `mlx-community/whisper-turbo`이며 인수 시 작업에 고정됩니다. 실제 속도·메모리·인식 품질은 아직 측정하지 않았습니다. 사전 힌트는 2000자 이내이며 정확한 표기 반영을 보장하지 않습니다. 클라우드 API 호출은 구현하지 않았습니다.

## NAS 없이 시험

맥에서 준비 앱과 허브 앱을 함께 실행하고 동일한 로컬 교환 폴더를 선택하면 됩니다. 준비 앱은 AI 없이도 모든 준비 기능을 실행합니다. 실제 전사까지 확인하려면 위의 맥 환경이 필요합니다.

```bash
python3 -m unittest discover -s tests -v
python3 -m smt2 --help
```

일반 PC 사이 수동 시험은 준비 앱이 만든 요청 UUID 폴더 전체를 맥 교환 폴더 `outbox/<device_id>/`로 복사하고, 복사가 끝난 뒤 인수 버튼을 누릅니다. 이 방식은 NAS 동기화 자동화를 대신하지 않습니다.

## 문서

- [개발 단계·완료 기준](docs/DEVELOPMENT.md)
- [앱 역할·작업 트리·흐름](docs/ARCHITECTURE.md)
- [NAS 추후 공동 설정](docs/NAS_SETUP_LATER.md)
- [전달 계약과 복구 규칙](docs/PROTOCOL.md)
- [검증 기록과 장비별 시험](docs/TESTING.md)

교환 폴더는 신뢰하는 사용자만 접근 가능한 환경을 전제로 합니다. 허브 SQLite는 맥 로컬 디스크에 두세요. 음성·자료·결과·개인 사전·API 키를 Git에 올리지 마세요.
