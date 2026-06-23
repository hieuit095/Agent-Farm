"""Security Disclosure Gate — The Diplomat Protocol.

Checks SECURITY.md and README.md for private/responsible disclosure
requests BEFORE the pipeline generates code or opens PRs. If the
maintainer has requested private disclosure, the pipeline aborts
gracefully and saves vulnerability details locally for manual reporting.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_SECRET_FINDINGS_DIR = Path("/app/secret_findings")

_SECURITY_MD_PATHS = [
    "SECURITY.md",
    ".github/SECURITY.md",
    "docs/SECURITY.md",
    "security.md",
    ".github/security.md",
]

_README_PATHS = [
    "README.md",
    "readme.md",
    "README.MD",
]

_PRIVATE_DISCLOSURE_PHRASES = [
    "do not open a public pr",
    "do not open a public issue",
    "do not file a public issue",
    "do not publicly disclose",
    "do not disclose security",
    "email us at",
    "send an email",
    "report security vulnerabilities to",
    "security@",
    "private disclosure",
    "responsible disclosure",
    "report a vulnerability privately",
    "submit security issues to",
    "security advisory",
    "github security advisory",
    "hackerone",
    "bugcrowd",
    " huntr",
    "intigriti",
    "do not create a public issue",
    "please email",
    "contact us privately",
    "coordinated disclosure",
    "vulnerability should be reported",
]


@dataclass
class SecurityGateResult:
    """Result of the security disclosure gate check."""

    repo_full_name: str
    requires_private_disclosure: bool = False
    security_md_found: bool = False
    security_md_content: str = ""
    readme_section_found: bool = False
    readme_section_content: str = ""
    matched_phrases: list[str] = field(default_factory=list)
    contact_info: str = ""


async def check_security_disclosure_policy(
    github,
    owner: str,
    repo: str,
    readme_content: str | None = None,
) -> SecurityGateResult:
    """Check if a repo requests private/responsible security disclosure.

    Scans SECURITY.md and the security section of README.md for phrases
    that indicate the maintainer wants vulnerabilities reported privately
    rather than through public PRs or issues.

    Args:
        github: GitHubClient instance.
        owner: Repository owner.
        repo: Repository name.
        readme_content: Optional pre-fetched README content.

    Returns:
        SecurityGateResult indicating whether private disclosure is required.
    """
    result = SecurityGateResult(repo_full_name=f"{owner}/{repo}")

    # 1. Check SECURITY.md
    for path in _SECURITY_MD_PATHS:
        try:
            content = await github.get_file_content(owner, repo, path)
            if content:
                result.security_md_found = True
                result.security_md_content = content[:4000]
                break
        except Exception:
            continue

    # 2. Check README.md for security section (if not already provided)
    if not readme_content:
        for path in _README_PATHS:
            try:
                readme_content = await github.get_file_content(owner, repo, path)
                if readme_content:
                    break
            except Exception:
                continue

    if readme_content:
        readme_lower = readme_content.lower()
        security_section_start = -1
        markers = [
            "## security",
            "# security",
            "**security",
            "security policy",
            "## reporting vulnerabilities",
            "## reporting security",
            "### security",
        ]
        for marker in markers:
            idx = readme_lower.find(marker)
            if idx != -1:
                security_section_start = idx
                break

        if security_section_start != -1:
            result.readme_section_found = True
            result.readme_section_content = readme_content[
                security_section_start : security_section_start + 2000
            ]

    # 3. Scan for private disclosure phrases
    combined_content = ""
    if result.security_md_content:
        combined_content += result.security_md_content.lower() + "\n"
    if result.readme_section_content:
        combined_content += result.readme_section_content.lower() + "\n"

    if not combined_content:
        return result

    for phrase in _PRIVATE_DISCLOSURE_PHRASES:
        if phrase in combined_content:
            result.matched_phrases.append(phrase)

    if result.matched_phrases:
        result.requires_private_disclosure = True
        result.contact_info = _extract_contact_info(combined_content)

    return result


def _extract_contact_info(text: str) -> str:
    """Extract email addresses or URLs from security policy text."""
    import re

    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    urls = re.findall(
        r"https?://[^\s<>\")\]]+(?:security|vulnerability|disclosure|hackerone|bugcrowd|huntr|intigriti)[^\s<>\")\]]*",
        text,
        re.IGNORECASE,
    )

    parts = []
    if emails:
        parts.append("Emails: " + ", ".join(emails[:3]))
    if urls:
        parts.append("Reporting URLs: " + ", ".join(urls[:3]))
    return "; ".join(parts) if parts else ""


def save_secret_findings(
    repo_full_name: str,
    findings: list[dict],
    dossier_data: dict | None = None,
) -> Path:
    """Save vulnerability findings to secret_findings/ for manual reporting.

    Creates the directory automatically if it doesn't exist.

    Args:
        repo_full_name: e.g. "owner/repo"
        findings: List of finding dicts with vulnerability details.
        dossier_data: Optional full dossier data for context.

    Returns:
        Path to the saved JSON file.
    """
    _SECRET_FINDINGS_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = repo_full_name.replace("/", "_")
    filename = f"{safe_name}.json"
    filepath = _SECRET_FINDINGS_DIR / filename

    payload = {
        "repo": repo_full_name,
        "saved_at": datetime.now(UTC).isoformat(),
        "findings": findings,
    }
    if dossier_data:
        payload["dossier"] = dossier_data

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

    logger.info("[SECRET FINDINGS] Saved %d findings to %s", len(findings), filepath)
    return filepath


async def run_security_gate(
    github,
    owner: str,
    repo: str,
    dossier=None,
    notifier=None,
    readme_content: str | None = None,
) -> SecurityGateResult | None:
    """Run the full Security Disclosure Gate check.

    If private disclosure is requested:
    1. Logs [COMPLIANCE SKIP]
    2. Saves vulnerability details to secret_findings/
    3. Sends Telegram notification

    Returns the SecurityGateResult if the gate triggers (pipeline should abort),
    or None if the gate does NOT trigger (pipeline should continue).
    """
    result = await check_security_disclosure_policy(
        github, owner, repo, readme_content=readme_content
    )

    if not result.requires_private_disclosure:
        logger.info(
            "[SECURITY GATE] %s: No private disclosure policy detected — proceeding normally.",
            result.repo_full_name,
        )
        return None

    logger.warning(
        "[COMPLIANCE SKIP] Private security disclosure requested by maintainers for %s. "
        "Matched phrases: %s. Contact: %s",
        result.repo_full_name,
        result.matched_phrases,
        result.contact_info or "N/A",
    )

    # Save findings locally
    findings_data = []
    if dossier and hasattr(dossier, "vulnerabilities"):
        for v in dossier.vulnerabilities:
            findings_data.append(
                {
                    "file": v.file,
                    "line": v.line,
                    "snippet": v.snippet,
                    "poc": v.poc,
                    "fix": v.fix,
                    "impact": v.impact,
                    "context_type": v.context_type,
                }
            )
    elif dossier is None:
        findings_data.append(
            {
                "note": "Vulnerabilities detected during analysis — detailed findings available in pipeline logs",  # noqa: E501
            }
        )

    saved_path = save_secret_findings(
        repo_full_name=result.repo_full_name,
        findings=findings_data,
        dossier_data={"repo_url": str(dossier.repo_url)}
        if dossier and hasattr(dossier, "repo_url")
        else None,  # noqa: E501
    )

    # Send Telegram notification (blocking await — guarantees delivery)
    if notifier:
        try:
            await notifier.send_message(
                f"🔒 **SECRET FINDING SAVED**\n"
                f"Target: {result.repo_full_name}\n"
                f"Check secret_findings/ for details to report manually.\n"
                f"Contact: {result.contact_info or 'See SECURITY.md'}"
            )
        except Exception as exc:
            logger.error("Failed to deliver Telegram security gate notification: %s", exc)
    else:
        logger.warning(
            "[SECURITY GATE] No notifier configured — Telegram notification NOT sent. "
            "Findings saved to %s",
            saved_path,
        )

    return result
