# FARMATE Product Requirements

## Product

FARMATE helps Korean farmers prepare for agricultural support programs by connecting public notice discovery with an application-writing workflow.

## Users and access

- **Public judge/guest:** no account, invitation, encryption key, or Copilot credential required to try the chatbot, read live public notice recommendations, and complete the clearly labeled synthetic application demo.
- **Account user:** can save an encrypted applicant profile and use it to autofill supported HWPX application forms.

Guest mode never reads or writes account profiles. The synthetic demo is not presented as a real support program or an AI result.

## Core workflows

1. Start in a Korean-language messenger-style chat with quick replies for **공고 추천** and **신청서 작성**.
2. Notice discovery fetches a bounded page from 농업e지's anonymous public listing, ranks it locally against non-sensitive profile keywords when available, and shows dates, source links, and eligibility caveats.
3. Guest applicants can interact with a synthetic Q&A/result/draft walkthrough without external AI calls or personal data.
4. Account users can upload a support-program PDF and HWPX template, explicitly consent to Copilot processing, answer follow-up questions, review citations/checklists/draft, and download an HWPX draft.

## Trust and privacy requirements

- Never invent a live notice when the public source is unavailable.
- Identify synthetic demo content and uncertain eligibility/date information.
- Do not require judges to provide credentials for the public guest walkthrough.
- Do not send saved profile fields to the notice source or Copilot automatically.
- Account profile fields are encrypted at rest; credentials and secrets are not committed.
- Uploaded application files and user-entered application data are sent to Copilot only after explicit consent.
- Human review is required before relying on eligibility or submitting an application.

## Out of scope

Official eligibility decisions, automatic application submission, broad crawling, editing legacy binary `.hwp`, and production-grade account recovery or financial-data security certification.

## Acceptance evidence

- A fresh visitor can access the guest path without login or secrets.
- The guest can browse the live public notice flow and complete the visibly synthetic application demo.
- Tests cover guest access, chat choices/navigation, notice parsing and outage behavior.
- Account workflow retains profile encryption, consent, citation validation, and HWPX output.
