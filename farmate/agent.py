from __future__ import annotations

from agent_framework.github import GitHubCopilotAgent


def create_agent() -> GitHubCopilotAgent:
    """Create the Microsoft Agent Framework provider backed by GitHub Copilot SDK."""
    return GitHubCopilotAgent(
        name="FARMATE",
        instructions=(
            "농업 지원사업 공고와 신청자 정보를 바탕으로 신청 준비를 돕습니다. "
            "확정적인 자격 판정을 하지 않고, 공고 원문 인용과 미확인 사항을 분명히 합니다."
        ),
    )
