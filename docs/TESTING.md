# 검증 기록

이번 변경의 개발 환경: Windows, Python 3.12.10. `python -m unittest discover -s tests -v`로 전달·상태·복구·자동 처리 21개 테스트가 통과했다. 테스트의 fake backend는 실제 음성을 인식하지 않는다.

검증 범위: 인수 후 원본 제거, 요청 재인수의 멱등성, 입력 손상, 경로 탈출 거부, 명시적 재시도, 중단 대기, 완료 체크포인트 복구, 체크포인트 손상, 대기 취소, 로컬 입력 재검증, 여러 device_id, 잘못된 타임스탬프, 결정적 용어 후보, 단일 작성자 잠금, 손상 요청과 정상 요청의 동시 처리, 교환 폴더 중단 중 로컬 전사와 복구 후 결과 발행, 변경 없는 공유 결과의 중복 쓰기 방지.

## 실제 장비에서 남은 시험

- Windows: Python/Tk 설치, 준비 앱 창, 한글·공백 경로, PDF 텍스트 추출, 공유 드라이브.
- Apple Silicon macOS: Python/Tk, FFmpeg 포함 패키지·MLX 설치, 모델 다운로드, 한국어 실제 MP3 전사, 자동 처리 창, 처리 시간·메모리·결과 품질.
- 두 앱: 파일 선택과 클릭 동작, 실패 안내, 작업 중 창 닫기 방지.
- NAS: 별도 문서의 연결·권한·중단·복원 시험.

GUI 자동 처리 클릭과 실제 MLX 전사는 이번 Windows 개발 환경에서 검증하지 않았다. 아래의 기존 GitHub Actions 결과는 커밋 `4d60fd04c517b0c04be30ae53521e01db228b312`의 Windows·macOS·Linux 작업 성공이며, 그 시점의 18개 계약 테스트와 CLI 도움말만 검증했다. 이번 0.2.0 변경의 CI 결과는 아직 없다.

`python -m smt2 serve --help`가 성공했다. `python -m pip wheel --no-deps . -w dist`로 `studymanager_transcribe2-0.2.0-py3-none-any.whl`을 만들고, 휠에 `smt2/service.py`가 포함되며 메타데이터 버전이 0.2.0임을 확인했다. 이 휠은 Mac 통합 설치본이 아니다.

[OS별 CI 결과](https://github.com/jcpark-allthings/StudyManager-Transcribe2/actions/runs/34326389439)

최초 Windows 검사에서는 테스트 코드의 기본 인코딩 읽기로 한글 UTF-8 데이터가 실패했다. 테스트의 파일 읽기에 UTF-8을 명시한 뒤 세 OS 모두 통과했다.
