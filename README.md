# FARMATE

농업 지원사업 공고를 읽고 신청자의 답변을 대조해 신청서 초안과 서류 확인 목록을 만드는 해커톤 MVP입니다. 분석 결과는 참고용이며, 지원 자격과 제출 전 내용은 사람이 원문 공고와 대조해야 합니다.

## MVP 흐름

1. 로그인 후 말풍선형 채팅 화면에서 **공고 추천** 또는 **신청서 작성** 빠른 선택을 누르거나 메시지를 입력합니다. 선택과 안내는 좌우 구분된 대화 기록에 남습니다.
2. 공고 추천은 농업e지의 익명 공개 목록에서 최신 연도 첫 페이지(최대 36건)를 읽어옵니다. 저장된 작물, 영농 형태, 인증, 지역 키워드로 앱 안에서 순위를 매기며 계좌·식별정보는 매칭에서 제외합니다.
3. 추천 결과에 사업명, 공개된 일정, 온라인 신청 표시, 키워드 일치 근거와 농업e지 원문 검색 링크를 보여줍니다. 마감된 항목은 제외하며 일정 미확인·접수기관 문의 항목은 별도로 표시합니다.
4. 신청서 작성에서는 텍스트 또는 스캔 공고 PDF와 HWPX 신청서 양식을 업로드합니다. 스캔 페이지는 로컬 OCR로 읽습니다.
5. Microsoft Agent Framework의 `GitHubCopilotAgent`(GitHub Copilot SDK 공급자)가 공고, 신청자 정보와 양식 항목을 분석합니다.
6. 확인 질문에 채팅으로 답하면 매 턴 자격 검토·미확인 항목·양식 필드·신청서 초안을 갱신합니다.
7. 확인된 값을 채우고 전체 초안을 문서 끝에 덧붙인 HWPX 파일을 다운로드합니다.

공고 추천은 공개 목록에서 일부 항목만 가져오는 키워드 기반 참고 정보이며 공식 자격 판정이나 접수 가능성 보장이 아닙니다. 사이트 연결 실패 시 임의 공고를 만들지 않고 농업e지 전체 목록으로 안내합니다. 전국 공고 검색, 구형 `.hwp` 편집/출력 및 실제 제출은 지원하지 않습니다. 구형 `.hwp`는 한글에서 `.hwpx`로 변환해 업로드해야 작성본을 다운로드할 수 있습니다. HWPX의 기존 내용과 첨부 파일은 보존하고, 프로필 및 AI 분석에서 확인된 값으로 `{{항목명}}` 자리표시자와 인식된 빈 표 항목 옆 칸을 채웁니다. 인식 가능한 항목이 없으면 기존 양식을 보존하고 전체 초안을 끝에 추가합니다. 자동으로 채워지지 않은 양식 구조는 그대로 남으므로 한글에서 열어 확인하고 마무리해야 합니다. 원문 인용이 PDF 페이지와 일치하지 않으면 결과를 표시하지 않습니다. PDF OCR 텍스트, 신청자가 AI 검토 입력란에 직접 적은 내용, 양식과 대화는 동의 후 GitHub Copilot 서비스로 전송됩니다. 이미 개인정보가 채워진 신청서 양식도 추출 텍스트가 전송될 수 있으므로 비어 있는 양식을 사용하세요. 저장 프로필은 전송하지 않습니다. 업로드 파일을 영구 저장하지 않습니다. 민감한 식별정보를 AI 입력란이나 대화에 직접 입력하지 마세요.

## 로컬 / Codespaces 실행

Python 3.12 권장 (Python 3.11 이상 필요).

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

### 계정, 프로필 및 저장소 암호화

로그인/프로필 저장 기능을 쓸 때만 `FARMATE_PROFILE_ENCRYPTION_KEY`가 필요합니다. 공개 심사자용 게스트 데모에는 로그인, Copilot 자격증명, 프로필 키가 필요하지 않습니다. 게스트는 실시간 공개 공고 조회와 합성 예시 신청서 대화를 체험할 수 있습니다. 새 Fernet 키는 아래 명령으로 생성하세요. 키는 서버 시작 때 임의 생성하지 않으며, 설정한 동일 키를 안전한 비밀 저장소에 보관하세요. 키를 잃으면 암호화된 프로필을 복구할 수 없습니다.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Codespaces에서는 생성한 값을 Repository **Settings → Secrets and variables → Codespaces**의 `FARMATE_PROFILE_ENCRYPTION_KEY` secret으로 추가하세요. Codespaces를 재시작한 후 앱을 실행합니다. 로컬은 `.streamlit/secrets.toml`(gitignore 처리됨)에 다음처럼 저장하거나 환경변수로 설정하세요.

```toml
FARMATE_PROFILE_ENCRYPTION_KEY = "생성한-키"
```

기본 SQLite 파일은 `data/farmate_profiles.sqlite3`이며 `FARMATE_PROFILE_DB`로 경로를 바꿀 수 있습니다. `.gitignore`가 DB와 SQLite journal 파일을 제외합니다. 이메일은 계정 식별자로 평문 저장되지만 비밀번호는 사용자별 무작위 salt와 PBKDF2-HMAC-SHA256 해시로만 저장되고, 프로필 전체(계좌번호 및 식별정보 포함)는 Fernet으로 암호화됩니다. 프로필 자동 입력 값은 서버 내부에서 HWPX에 채워지며 Copilot prompt에는 넣지 않습니다. 공고·양식·AI 검토 입력란과 대화는 별도 동의 후 전송됩니다.

이 SQLite 구성은 Codespaces의 소규모 데모용이며, Codespace 삭제 시 데이터가 사라질 수 있고 동시접속·백업·계정 복구·인증 시도 제한을 제공하지 않습니다. Azure Web App 파일시스템도 영구 저장소로 가정하면 안 됩니다. Azure에 공개 배포하기 전에는 영구 데이터베이스/스토리지, 비밀 회전·백업, 접근통제 및 계정 보안 검토가 필요하며 이 앱은 프로덕션 금융정보 저장용으로 인증되지 않았습니다.

공개 게스트 데모는 별도 비밀 설정 없이 실행됩니다. 계정/실제 Copilot 신청서 분석을 사용할 경우 암호화 키와 Copilot 인증 설정이 필요합니다.

```bash
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Codespaces는 `.devcontainer/devcontainer.json`과 Dockerfile을 사용해 Debian Bookworm/Python 3.12 환경을 빌드하고 requirements 설치와 Tesseract `kor`/`eng` 언어 데이터 설치를 자동으로 구성합니다. Dockerfile은 FARMATE에 필요 없는 Yarn 외부 apt 소스만 제거한 뒤 표준 서명 검증을 유지한 채 패키지를 설치합니다. 브랜치 변경 후 현재 터미널이 Alpine이라고 나오면 기존 컨테이너가 설정을 적용하지 않은 상태입니다. Codespaces에서 **Codespaces: Rebuild Container**를 실행한 다음 아래 명령으로 확인하세요.

```bash
cat /etc/os-release
command -v tesseract
tesseract --list-langs
```

Debian, Tesseract 실행 경로, `kor`와 `eng` 언어가 표시되어야 합니다. 컨테이너 재빌드가 끝난 후 아래 Streamlit 명령을 실행하고 **Ports** 탭에서 포트 `8501`을 열어 브라우저에서 확인하세요. 로컬 환경은 `http://localhost:8501`에서 열립니다.

GitHub Copilot CLI/SDK 런타임과 사용할 Copilot 구독 인증도 필요합니다. 로컬에서는 Copilot CLI에 로그인하거나 `COPILOT_GITHUB_TOKEN`을 환경변수로 설정하세요. Codespaces에서는 리포지토리/개발환경 비밀에 토큰을 설정할 수 있습니다. `GITHUB_COPILOT_MODEL`은 선택사항입니다.

스캔 PDF OCR에는 시스템 Tesseract와 `kor`/`eng` 언어 데이터가 필요합니다. Codespaces 컨테이너는 `.devcontainer/Dockerfile`에서 설치합니다. HWPX XML을 안전하게 읽는 패키지는 requirements에 포함됩니다. Dockerfile 변경 후 컨테이너를 재빌드하세요. Ubuntu/Debian 로컬 환경은 아래 패키지를 설치한 뒤 Python 의존성을 설치합니다.

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng
```

Windows에서는 Tesseract OCR을 별도로 설치하고 `tesseract.exe`를 `PATH`에서 실행할 수 있도록 설정해야 합니다. 언어 데이터나 실행 파일을 찾을 수 없거나 페이지를 판독하지 못하면 오류를 표시합니다. OCR 출력은 PDF 품질과 언어 설정에 따라 틀릴 수 있으므로 원문을 확인하세요.

HWPX 표의 라벨과 모델이 반환한 항목명이 일치하고 오른쪽 칸이 비어 있으면 내용을 입력합니다. `{{성명}}`과 같은 자리표시자도 지원합니다. 생성 결과는 전체 신청서 초안을 문서 끝에 추가하므로 한글에서 열어 원본 항목과 대조하고 빠진 칸을 보완하세요. 구형 HWP를 HWPX로 변환하는 작업은 앱에서 하지 않습니다.

단위 테스트:

```bash
python -m unittest discover -s tests -v
```

### Copilot 분석 오류

화면의 `TypeError`만으로는 인증 문제라고 판단할 수 없습니다. FARMATE는 화면에 분류 가능한 SDK 인자 오류만 간단히 보여주며, 원인 확인은 `streamlit run ...`을 실행한 Codespaces 터미널의 `Traceback`에서 해야 합니다. 해당 요청의 `Traceback` 시작부터 마지막 예외 줄까지 복사하되, 토큰·인증정보와 신청자 이름/연락처/주소 등은 삭제한 뒤 공유하세요.

### 농업e지 공고 추천 출처 및 제한

`farmate/notices.py`는 먼저 공개 전체사업 페이지에 접속해 익명 세션 쿠키를 받은 뒤, 해당 페이지가 사용하는 읽기 전용 JSON 검색 경로를 호출합니다. 각 요청은 12초로 제한합니다. 현재 연도의 첫 페이지에서 최대 36개만 가져오고 결과를 15분 캐시합니다. 목록 전체를 크롤링하지 않으며, 로그인 전용 사업 상세/개인화 경로를 호출하지 않습니다. 프로필 키워드 비교는 로컬에서 수행하고 계좌번호·생년월일·등록번호·이름·연락처를 공고 사이트나 Copilot으로 보내지 않습니다.

추천은 제목·설명·담당기관 문자열과 제한된 프로필 키워드의 단순 일치 점수입니다. 마감일이 지난 항목은 제외하지만, 사이트 표시 일정이 실제 접수기간인지 또는 신청자 자격이 있는지는 검증하지 않습니다. 목록에 일정이 없거나 기관 문의로 표시되면 확인 필요로 안내합니다. 연결에 실패하면 화면에 HTTP 상태 또는 DNS/TLS/시간초과 등 가능한 원인을 보여주고 공식 목록 링크를 제공합니다. Codespaces에서 계속 실패한다면 공개 사이트 연결을 확인하세요.

```bash
python -c "import urllib.request; print(urllib.request.urlopen('https://www.nongupez.go.kr/nsm/bizAply/wholeBiz/wholeBizMain', timeout=15).status)"
```

명령도 실패하면 Codespace 네트워크/DNS 정책에서 사이트 접속이 차단되었을 수 있습니다. 앱은 오류 상황에서 임의 공고를 표시하지 않습니다. 원문/접수기관에서 대상, 신청기간, 제출 조건을 확인하세요.

## 배포

`.github/workflows/azure-webapp.yml`은 이미 만들어진 Azure Linux Web App에 수동 배포하는 GitHub Actions 워크플로입니다. 저장소에 `AZURE_WEBAPP_NAME`, `AZURE_RESOURCE_GROUP` 변수를 설정하고, OIDC용 `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` 비밀 및 Azure 앱 등록의 federated credential/RBAC를 준비해야 합니다. 워크플로는 Azure 리소스를 만들지 않습니다. 현재 저장소에 설정된 Azure 대상 앱/인증정보는 확인할 수 없어 실제 배포는 완료되지 않았습니다. 심사 제출 전 기존 앱과 OIDC 권한을 연결하고 워크플로를 실행한 다음 `*.azurewebsites.net` 기본 도메인에서 게스트 경로를 확인해야 합니다.

게스트 경로에는 Copilot 또는 계정 암호화 비밀이 필요하지 않습니다. 실제 AI 계정 기능을 공개할 때만 Azure 앱 설정에 `COPILOT_GITHUB_TOKEN`과 `FARMATE_PROFILE_ENCRYPTION_KEY`를 안전하게 설정하고, SQLite 경로를 재시작 후에도 유지되는 영구 스토리지로 지정하세요. Python 3.12 런타임 및 외부 런타임 다운로드가 가능한 네트워크도 필요합니다. 워크플로는 `startup.sh`를 시작 명령으로 설정하고 배포 중 requirements를 설치합니다.

공개 데모: 로그인 없이 **로그인 없이 공개 데모 사용** → **공고 추천**으로 농업e지 실시간 공고를 확인하거나 **신청서 작성**으로 명시적으로 가상 표기된 합성 Q&A/결과/초안을 볼 수 있습니다. 데모 입력은 로컬 세션 내에서만 처리되고 Copilot으로 전송되지 않습니다.

## 데모 및 한계

초기 기획에서 제시된 청도군 사업 공고의 마감일은 2026-11-03으로 전달됐습니다. 현재 데모 날짜(2026-11-05) 기준 신청 가능한 공고라고 가정하지 말고, 유효한 공고인지 확인하거나 만료된 사례임을 분명히 표시하세요. 30초 데모 목표와 추출 정확도는 실제 PDF 및 인증된 모델 호출로 아직 검증되지 않았습니다.

AI가 해석한 지원 자격은 공식 판정이 아닙니다. 인용, 체크리스트, 초안을 담당자가 원문과 대조하고 최종 신청을 직접 검토해야 합니다.

해커톤 발표·평가용 구현 근거, 데모 순서 및 미검증 항목은 [HACKATHON.md](HACKATHON.md)를 참고하세요.
