# FARMATE

농업 지원사업 공고를 읽고 신청자의 답변을 대조해 신청서 초안과 서류 확인 목록을 만드는 해커톤 MVP입니다. 분석 결과는 참고용이며, 지원 자격과 제출 전 내용은 사람이 원문 공고와 대조해야 합니다.

## MVP 흐름

1. 텍스트 PDF 또는 스캔 이미지 PDF를 업로드합니다. 텍스트가 없는 페이지는 로컬 OCR로 인식합니다.
2. 농가 정보를 입력하고, 원문 및 신청자 정보가 GitHub Copilot으로 처리된다는 점에 동의합니다.
3. PDF 페이지 텍스트와 입력 정보를 Microsoft Agent Framework의 `GitHubCopilotAgent`에 전달합니다. 이 공급자는 GitHub Copilot SDK를 사용합니다.
4. 지원 대상, 자격 조건별 잠정 판정과 원문 인용, 미확인 질문, 제출서류 확인 목록, 신청서 초안을 확인합니다.

전국 공고 검색, HWP/HWPX 자동 입력 및 실제 제출은 포함하지 않습니다. 원문 인용이 페이지 내용과 일치하지 않으면 결과를 표시하지 않습니다. OCR은 로컬 Tesseract 및 한국어/영어 언어 데이터를 사용하며, OCR된 텍스트도 분석 동의 후 GitHub Copilot 서비스로 전송됩니다. 파일은 앱에 저장하지 않습니다. 민감한 식별정보는 입력하지 마세요.

## 로컬 / Codespaces 실행

Python 3.12 권장 (Python 3.11 이상 필요).

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Codespaces는 `.devcontainer/devcontainer.json`과 Dockerfile을 사용해 Debian Bookworm/Python 3.12 환경을 빌드하고 requirements 설치와 Tesseract `kor`/`eng` 언어 데이터 설치를 자동으로 구성합니다. 브랜치 변경 후 현재 터미널이 Alpine이라고 나오면 기존 컨테이너가 설정을 적용하지 않은 상태입니다. Codespaces에서 **Codespaces: Rebuild Container**를 실행한 다음 아래 명령으로 확인하세요.

```bash
cat /etc/os-release
command -v tesseract
tesseract --list-langs
```

Debian, Tesseract 실행 경로, `kor`와 `eng` 언어가 표시되어야 합니다. 컨테이너 재빌드가 끝난 후 아래 Streamlit 명령을 실행하고 **Ports** 탭에서 포트 `8501`을 열어 브라우저에서 확인하세요. 로컬 환경은 `http://localhost:8501`에서 열립니다.

GitHub Copilot CLI/SDK 런타임과 사용할 Copilot 구독 인증도 필요합니다. 로컬에서는 Copilot CLI에 로그인하거나 `COPILOT_GITHUB_TOKEN`을 환경변수로 설정하세요. Codespaces에서는 리포지토리/개발환경 비밀에 토큰을 설정할 수 있습니다. `GITHUB_COPILOT_MODEL`은 선택사항입니다.

스캔 PDF OCR에는 시스템 Tesseract와 `kor`/`eng` 언어 데이터가 필요합니다. Codespaces 컨테이너는 `.devcontainer/Dockerfile`에서 설치합니다. Dockerfile 변경 후 컨테이너를 재빌드하세요. Ubuntu/Debian 로컬 환경은 아래 패키지를 설치한 뒤 Python 의존성을 설치합니다.

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng
```

Windows에서는 Tesseract OCR을 별도로 설치하고 `tesseract.exe`를 `PATH`에서 실행할 수 있도록 설정해야 합니다. 언어 데이터나 실행 파일을 찾을 수 없거나 페이지를 판독하지 못하면 오류를 표시합니다. OCR 출력은 PDF 품질과 언어 설정에 따라 틀릴 수 있으므로 원문을 확인하세요.

단위 테스트:

```bash
python -m unittest discover -s tests -v
```

## 배포

`.github/workflows/azure-webapp.yml`은 이미 만들어진 Azure Linux Web App에 수동 배포하는 GitHub Actions 워크플로입니다. 저장소에 `AZURE_WEBAPP_NAME`, `AZURE_RESOURCE_GROUP` 변수를 설정하고, OIDC용 `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` 비밀 및 Azure 앱 등록의 federated credential/RBAC를 준비해야 합니다. 워크플로는 Azure 리소스를 만들지 않습니다.

Azure 앱 설정에서 `COPILOT_GITHUB_TOKEN`을 비밀로 설정하고, Python 3.12 런타임 및 외부 런타임 다운로드가 가능한 네트워크를 확인하세요. 워크플로는 `startup.sh`를 시작 명령으로 설정하고 배포 중 requirements를 설치합니다. Copilot 인증 및 서비스 이용 권한이 배포 환경에서 유효한지 먼저 확인해야 합니다. 이 저장소에는 연결된 Azure 앱/권한이 없어 실제 Azure 배포는 수행하지 않았습니다.

## 데모 및 한계

초기 기획에서 제시된 청도군 사업 공고의 마감일은 2026-11-03으로 전달됐습니다. 현재 데모 날짜(2026-11-05) 기준 신청 가능한 공고라고 가정하지 말고, 유효한 공고인지 확인하거나 만료된 사례임을 분명히 표시하세요. 30초 데모 목표와 추출 정확도는 실제 PDF 및 인증된 모델 호출로 아직 검증되지 않았습니다.

AI가 해석한 지원 자격은 공식 판정이 아닙니다. 인용, 체크리스트, 초안을 담당자가 원문과 대조하고 최종 신청을 직접 검토해야 합니다.

해커톤 발표·평가용 구현 근거, 데모 순서 및 미검증 항목은 [HACKATHON.md](HACKATHON.md)를 참고하세요.
