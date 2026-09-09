# 검증 기록

개발 환경: Linux, Python 3.12.14. `python3 -m unittest discover -s tests -v`로 전달·상태·복구 18개 테스트가 통과했다. 테스트의 fake backend는 실제 음성을 인식하지 않는다.

검증 범위: 인수 후 원본 제거, 요청 재인수의 멱등성, 입력 손상, 경로 탈출 거부, 명시적 재시도, 중단 대기, 완료 체크포인트 복구, 체크포인트 손상, 대기 취소, 로컬 입력 재검증, 여러 device_id, 잘못된 타임스탬프, 결정적 용어 후보, 단일 작성자 잠금.

## 실제 장비에서 남은 시험

- Windows: Python/Tk 설치, 준비 앱 창, 한글·공백 경로, PDF 텍스트 추출, 공유 드라이브.
- Apple Silicon macOS: Python/Tk, FFmpeg, MLX 설치, 모델 다운로드, 한국어 실제 MP3 전사, 처리 시간·메모리·결과 품질.
- 두 앱: 파일 선택과 클릭 동작, 실패 안내, 작업 중 창 닫기 방지.
- NAS: 별도 문서의 연결·권한·중단·복원 시험.

GUI는 디스플레이가 없는 현재 환경에서 실제 창을 띄워 검증하지 않았다. 소스 실행 스크립트의 Windows/macOS 실기 실행도 미검증이다. GitHub Actions에서 수정 커밋 `4d60fd04c517b0c04be30ae53521e01db228b312`의 Windows·macOS·Linux 작업이 모두 성공했다. 각 작업은 18개 계약 테스트와 CLI 도움말 실행을 검증했다. 이는 실제 MLX 전사·GUI 클릭 검증과 구분한다.

[OS별 CI 결과](https://github.com/jcpark-allthings/StudyManager-Transcribe2/actions/runs/34326389439)

최초 Windows 검사에서는 테스트 코드의 기본 인코딩 읽기로 한글 UTF-8 데이터가 실패했다. 테스트의 파일 읽기에 UTF-8을 명시한 뒤 세 OS 모두 통과했다.
