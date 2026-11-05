# FARMATE Technical Requirements

## Architecture

- **UI/runtime:** Python 3.12 and Streamlit, packaged for Codespaces and Azure Linux Web App.
- **Notice source:** `farmate/notices.py` first requests the public 농업e지 listing page to establish an anonymous session, then calls the same public read-only JSON search used by that page. It requests one page of at most 36 rows with a 12-second timeout; successful data is cached for 15 minutes.
- **Recommendation:** title/summary/office text is ranked locally using only crop, farm type, certification, and location profile fields. Account identifiers, bank data, birth dates, names, and phone numbers are excluded.
- **AI application flow:** Microsoft Agent Framework `GitHubCopilotAgent` uses the GitHub Copilot SDK. Personal PDF/form/chat content is sent only following explicit user consent. Guest demo makes no AI calls.
- **Profile storage:** account profiles use Fernet-encrypted JSON in SQLite; passwords use salted PBKDF2-HMAC-SHA256. Guest mode does not access the profile store.
- **Documents:** `pypdf` plus local Tesseract OCR for scanned PDFs; `defusedxml` and ZIP processing for HWPX read/fill/export. Binary `.hwp` output is unsupported.

## Public judge path

The public guest workflow requires no authentication, Copilot token, or encryption secret. It exposes:

1. Chat quick replies and free text navigation.
2. Live public notice lookup with official source links and explicit errors if unavailable.
3. A synthetic, non-PII application Q&A/result/draft walkthrough clearly labeled as fictional and not AI-generated.

The separate account flow remains available when a profile encryption key is configured. Guest mode cannot save profile information or start an authenticated Copilot application analysis.

## Deployment

The repository includes `.github/workflows/azure-webapp.yml` for manual OIDC deployment to an **existing** Azure Linux Web App. It does not create Azure resources. It needs repository variables `AZURE_WEBAPP_NAME`, `AZURE_RESOURCE_GROUP` and GitHub OIDC secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, plus a configured federated credential and RBAC role. Streamlit binds to `PORT` (default 8000) via `startup.sh`.

No Azure CLI login, authorized app target, or deployment credentials were available in the implementation environment; no Azure deployment or Azure hostname is claimed. Before judges can use a hosted URL, the repository owner must configure the existing target and OIDC settings, run the workflow, and verify its `*.azurewebsites.net` default hostname and guest path.

## Verification

Run `python -m unittest discover -s tests -v`. The suite covers profile isolation/encryption, guest access, chat navigation, PDF/OCR/citation validation, public notice parsing/ranking/error cases, and HWPX handling.

## Operational limits

Public source availability depends on the Codespace/Azure outbound network and the public site schema. Failures are shown with HTTP/network diagnostics; FARMATE does not fabricate current notices. The SQLite configuration is a hackathon MVP, not a production persistent multi-user store. Azure storage, Copilot auth, and real deployment must be configured and verified separately.
