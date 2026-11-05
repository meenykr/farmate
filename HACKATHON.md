# FARMATE — 해커톤 제출 및 심사 가이드

## 한 줄 소개

**FARMATE는 농업 지원사업 공고 PDF를 신청자 정보와 대조해 자격·누락서류를 확인하고, 대화로 정보를 보완해 작성된 HWPX 신청서 초안까지 만드는 AI 행정 에이전트입니다.**

자격 결과는 공식 판정이 아닙니다. AI가 채운 정보와 원문을 사람이 대조하고 최종 제출을 검토해야 합니다.

## 문제와 사용자 가치

농업 지원사업 공고에는 지원 요건과 제출 서류가 긴 문서에 나뉘어 있습니다. 신청자는 공고와 HWP/HWPX 양식 사이를 오가며 자신에게 적용되는 조건을 판단하고 각 항목을 작성해야 합니다. FARMATE는 다음 준비 업무를 하나의 흐름으로 돕습니다.

- PDF 공고의 지원 대상, 자격 조건, 제출 서류를 추출합니다.
- 신청자 정보를 대조하고 근거가 부족한 조건은 질문합니다.
- 질문에 답할 때마다 잠정 자격, 누락 질문, 양식 항목과 신청서 초안을 다시 생성합니다.
- 작성된 초안을 지원서 형태의 HWPX로 내려받고 한글에서 마무리합니다.

현장 사용자 시험, 신청 시간 절감률, 추출 정확도와 30초 내 분석 목표는 아직 검증하지 않았습니다.

## 재현 가능한 데모

### 준비

1. Codespaces에서는 저장소의 `.devcontainer/devcontainer.json`을 사용합니다. Python 3.11 이상이 필요하며 Python 3.12를 권장합니다. 로컬 설치는 다음과 같습니다.

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```

2. 스캔 PDF OCR용 Tesseract와 `kor`/`eng` 언어 데이터가 필요합니다. Codespaces는 Debian Bookworm 이미지를 빌드해 `.devcontainer/Dockerfile`에서 설치합니다. FARMATE와 무관한 Yarn apt 소스만 제거하며 서명 검증은 유지합니다. 현재 터미널이 Alpine이면 **Codespaces: Rebuild Container**를 실행한 뒤 README의 OS/Tesseract 확인 명령을 사용하세요. 로컬 Debian/Ubuntu 및 Windows 설치 방법도 README를 참고하세요.
3. GitHub Copilot CLI/SDK 런타임에 사용할 수 있는 Copilot 구독 인증을 준비합니다. CLI에 로그인하거나 `COPILOT_GITHUB_TOKEN`을 설정하세요.
4. 공고 PDF는 20MB 이하, 최대 50페이지, 추출 텍스트 60,000자 이하여야 합니다. 텍스트가 없는 페이지는 로컬 Tesseract `kor+eng` OCR을 사용합니다. 양식 입력·편집 출력은 HWPX만 지원합니다. 구형 `.hwp`는 한글에서 HWPX로 변환해 업로드하세요.
5. 시연 공고의 접수 마감일을 확인하세요. 제안된 청도군 사업은 전달된 마감일이 2026-11-03이므로, 2026-11-05 기준 진행 중인 사업이라고 소개하지 않습니다.

### 실행 및 시연

```bash
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

로컬은 `http://localhost:8501`, Codespaces는 **Ports** 탭에서 포트 `8501`을 열어 접속합니다.

1. 공고 PDF와 HWPX 신청서 양식을 업로드하고 개인정보를 제외한 신청자 기본 정보를 입력합니다.
2. 공고·신청자 정보·양식 텍스트와 대화 내용이 GitHub Copilot으로 전송됨을 확인하고 동의합니다.
3. **공고 분석 및 대화 시작**을 실행합니다.
4. 자격별 잠정 상태와 PDF 원문 인용, 서류 확인 상태, 첫 질문을 살펴봅니다.
5. 채팅 입력란에 답변합니다. 각 답변 후 Copilot SDK 에이전트가 전체 대화 문맥으로 조건·확인 질문·양식 필드·초안을 갱신합니다.
6. **작성된 HWPX 신청서 다운로드**를 누르고 한글에서 파일을 열어 확인합니다.
7. 자동으로 인식한 항목 및 문서 끝에 덧붙인 전체 초안을 원래 양식과 대조해 사람이 마무리합니다.

단위 테스트:

```bash
python -m unittest discover -s tests -v
```

## 심사 기준별 근거

| 심사 기준 | 배점 | 구현 근거 및 시연할 내용 | 미검증/범위 한계 |
|---|---:|---|---|
| GitHub Copilot SDK + Microsoft Agent Framework | 25% | `farmate/agent.py`의 Microsoft Agent Framework `GitHubCopilotAgent`가 GitHub Copilot SDK로 구동됩니다. 초기 분석 및 매 답변 뒤에 공고 텍스트, 양식, 신청자 문맥과 대화를 전달하고 구조화 결과를 검증합니다. | SDK 설치 및 에이전트 초기화는 확인했으나 인증된 실시간 Copilot 모델 호출은 아직 하지 않았습니다. |
| 생산성 및 문제 적합성 | 18% | PDF와 HWPX 양식 업로드에서 질문 답변, 자격 검토, 누락서류, 초안 작성, HWPX 다운로드까지 농업 행정 신청 흐름을 연결합니다. | 현장 사용자 테스트와 신청 소요시간 비교를 하지 않았습니다. 절감률은 주장하지 않습니다. |
| Azure 클라우드 통합 | 18% | `.github/workflows/azure-webapp.yml`은 GitHub Actions OIDC로 기존 Azure Linux Web App을 설정하고 배포하는 수동 워크플로입니다. | 대상 Azure 앱 및 OIDC 권한이 없어 클라우드 배포는 검증하지 않았습니다. 워크플로는 Azure 리소스를 생성하지 않습니다. |
| 완성도 및 기술 구현 | 16% | `farmate/pdf.py` 페이지 한도/OCR/인용 검증, `farmate/templates.py` HWPX 패키지 보존·자리표시자 및 빈 표 칸 입력·초안 추가, 턴별 분석을 제공합니다. 테스트가 PDF/인용과 HWPX 다운로드의 주요 경로를 확인합니다. | 구형 `.hwp` 편집/출력 및 실제 Hancom 앱 호환성은 검증되지 않았고 지원하지 않습니다. 실공고 회귀 데이터셋이 없습니다. |
| UX 및 업무 흐름 | 12% | 동의가 포함된 업로드, 챗 형태의 질의·응답, 매 턴 상태 갱신, 다운로드 가능한 HWPX, 최종 검토 지침을 제공합니다. | Streamlit 해커톤 MVP이며 농업인 사용성 및 접근성을 시험하지 않았습니다. |
| 책임 있는 AI, 보안, 신뢰 | 6% | 전송 동의를 받고, 없는 정보는 만들지 않도록 지시합니다. 자격은 잠정 상태이며 원문 인용 검증 실패 시 결과를 거부합니다. 입력 파일은 서버에 저장하지 않으며 OCR은 로컬에서 수행합니다. | 사용자가 동의하면 추출한 PDF/양식 텍스트와 대화는 GitHub Copilot 서비스로 전송됩니다. 서비스 데이터 처리·보존 정책 검토를 대신하지 않습니다. |
| 혁신성과 차별성 | 5% | 일반적인 문서 요약에서 끝나지 않고 농업 지원 요건 비교와 신청 양식 작성을 연결합니다. 미확인 조건은 대화로 보완하며 출처와 인간 검토를 유지합니다. | 경쟁 제품 비교와 시장 독창성 검증은 수행하지 않았습니다. |

## 실제 데이터 흐름

```text
Streamlit 업로드/동의
  ├─ 공고 PDF ─ pypdf 텍스트 추출 또는 로컬 Tesseract OCR
  ├─ HWPX 양식 ─ 안전한 XML 본문 추출
  └─ 신청자 정보 + 대화 이력
                 │
                 v
 Microsoft Agent Framework GitHubCopilotAgent
           (GitHub Copilot SDK)
                 │
                 v
 구조화된 자격/서류/질문/양식 필드/신청서 초안
                 │
         PDF 페이지 원문 인용 검증
                 │
                 v
 HWPX 자리표시자/빈 칸 입력 + 전체 초안 추가 + 다운로드
```

HWPX의 zip 항목과 비수정 파일은 결과에도 보존합니다. 채울 수 있는 위치는 `{{항목명}}` 자리표시자 및 모델이 반환한 양식 라벨과 일치하는 행에서 바로 오른쪽의 빈 표 칸입니다. 전체 초안은 양식 문서 끝에도 추가해, 인식되지 않는 양식 구조도 검토할 수 있도록 합니다. 따라서 표/필드를 임의로 완전 자동 매핑했다고 주장하지 않습니다. 구형 `.hwp` 파일은 바이너리 양식 수정/출력을 지원하지 않으므로 한글에서 `.hwpx`로 변환해야 합니다. HWPX 출력도 한글에서 열어 실제 출력 모양과 값들을 최종 확인해야 합니다.

에이전트 결과와 업로드 텍스트는 신뢰할 수 없는 입력으로 취급합니다. 형식 또는 공고 인용 검증에 실패하면 정상 결과처럼 표시하지 않습니다. 질문 답변은 전체 신청자 문맥과 함께 각 턴 요청에 포함됩니다.

## Azure 배포 상태

`.github/workflows/azure-webapp.yml`은 **이미 준비된** Azure Linux Web App을 대상으로 수동 실행됩니다. 저장소 변수 `AZURE_WEBAPP_NAME`, `AZURE_RESOURCE_GROUP`, OIDC 비밀 `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, federated credential/RBAC 및 안전한 `COPILOT_GITHUB_TOKEN` 설정이 필요합니다. 이 환경에서는 Azure 자격과 대상이 없어 배포하지 않았습니다.

## 범위와 아직 검증되지 않은 주장

- 포함: 텍스트/스캔 공고 PDF, 자격 조건 대조, 출처 인용, 문답형 정보 보완, HWPX 양식 필드 일부 입력, HWPX 다운로드.
- 제외: 구형 HWP 편집/출력, 전국 공고 검색, OCR 이미지 전용 신청서 양식, 실제 신청 제출 및 공식 자격 판정.
- 데모 30초 내 처리 및 추출 정확도는 목표/미측정 항목입니다.
- GitHub Copilot 인증 실시간 요청과 Azure 배포를 완료했다고 주장하지 않습니다.
- 마감된 공고는 접수 가능 사업인 것처럼 소개하지 않습니다.
