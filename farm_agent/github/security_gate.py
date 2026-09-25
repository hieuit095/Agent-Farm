"""Security Disclosure Gate — The Diplomat Protocol & Bug Bounty Dossier Engine.

Checks SECURITY.md and README.md for private/responsible disclosure
requests, enforces Route C (Private Disclosure) for Critical/High vulnerabilities,
and generates standardized Security Advisory Reports (GHSA & Bug Bounty Dossiers).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from farm_agent.core.models import AdvisoryReport, ContributionType, DisclosureRoute, Finding, Severity
from farm_agent.security.closure import require_confirmed_security_finding

logger = logging.getLogger(__name__)

_DEFAULT_BOUNTY_DIR = Path("bounty_reports")
_SECRET_FINDINGS_DIR = Path("data/secret_findings")

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

# CWE Database for automated categorization and standard CVSS 3.1 estimation
_CWE_DATABASE: list[tuple[str, str, str, float, str]] = [
    (
        r"sql[\s_-]?injection|sqli|blind[\s_-]?sql",
        "CWE-89",
        "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')",
        9.8,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    (
        r"command[\s_-]?injection|rce|remote[\s_-]?code[\s_-]?execution|os[\s_-]?command",
        "CWE-78",
        "Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')",
        9.8,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    (
        r"ssrf|server[\s_-]?side[\s_-]?request[\s_-]?forgery",
        "CWE-918",
        "Server-Side Request Forgery (SSRF)",
        8.6,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N",
    ),
    (
        r"path[\s_-]?traversal|directory[\s_-]?traversal|arbitrary[\s_-]?file[\s_-]?(?:read|write)|lfi",
        "CWE-22",
        "Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')",
        7.5,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
    ),
    (
        r"auth(?:entication)?[\s_-]?bypass|broken[\s_-]?auth|session[\s_-]?fixation|privilege[\s_-]?escalation",
        "CWE-287",
        "Improper Authentication",
        8.8,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
    ),
    (
        r"insecure[\s_-]?deserialization|deserialization|untrusted[\s_-]?data[\s_-]?deserialization|pickle",
        "CWE-502",
        "Deserialization of Untrusted Data",
        9.8,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    (
        r"hardcoded[\s_-]?secret|hardcoded[\s_-]?key|secret[\s_-]?leak|credential[\s_-]?leak",
        "CWE-798",
        "Use of Hard-coded Credentials",
        7.5,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
    ),
    (
        r"cross[\s_-]?site[\s_-]?scripting|xss",
        "CWE-79",
        "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')",
        6.1,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",
    ),
    (
        r"buffer[\s_-]?overflow|memory[\s_-]?corruption|use[\s_-]?after[\s_-]?free",
        "CWE-119",
        "Improper Restriction of Operations within the Bounds of a Memory Buffer",
        9.8,
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
]


def calculate_vulnerability_metrics(
    title: str,
    description: str,
    severity: Severity = Severity.HIGH,
) -> tuple[str, str, float, str]:
    """Derive CWE ID, name, CVSS score, and vector from finding text."""
    combined = f"{title} {description}".lower()

    for pattern, cwe_id, cwe_name, cvss_score, cvss_vector in _CWE_DATABASE:
        if re.search(pattern, combined):
            return cwe_id, cwe_name, cvss_score, cvss_vector

    # Fallback based on severity
    if severity == Severity.CRITICAL:
        return "CWE-699", "Software Development Vulnerability", 9.0, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    elif severity == Severity.HIGH:
        return "CWE-699", "Software Development Vulnerability", 7.5, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"
    elif severity == Severity.MEDIUM:
        return "CWE-699", "Software Development Vulnerability", 5.3, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"
    return "CWE-699", "Software Development Vulnerability", 3.1, "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N"


def generate_bounty_dossier_markdown(report: AdvisoryReport) -> str:
    """Generate a publication-ready Bug Bounty Dossier in Markdown format."""
    ghsa_line = f"| **GHSA Reference** | [{report.ghsa_id}]({report.ghsa_url}) |\n" if report.ghsa_url else ""
    return f"""# Security Advisory: {report.title}

| Field | Details |
| :--- | :--- |
| **Target Repository** | `{report.affected_repo}` |
| **Commit Target** | `{report.target_commit or 'HEAD'}` |
| **Severity** | **{report.severity.upper()}** |
| **CWE ID** | `{report.cwe_id}` - {report.cwe_name} |
| **CVSS v3.1** | **{report.cvss_score}** (`{report.cvss_vector}`) |
| **Disclosure Route** | `{report.route.value}` |
| **Discovered Date** | `{report.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}` |
{ghsa_line}
---

## 1. Vulnerability Summary
{report.summary}

## 2. Root Cause Analysis (RCA)
- **Vulnerable Location:** `{report.vulnerable_file}:{report.vulnerable_line or 'N/A'}`
- **Technical Analysis:**
{report.vulnerability_details or report.summary}

## 3. Step-by-Step Proof-of-Concept (PoC)
### Reproduction Steps:
{report.reproduction_steps or "1. Inspect the vulnerable code path.\\n2. Execute the self-contained verification PoC script."}

### Executable PoC Payload:
```python
{report.poc_script or "# PoC script is available in internal audit log."}
```

## 4. Remediation Patch
The following unified patch eliminates the vulnerability:
```diff
{report.remediation_patch or "# Remediation diff is pending review."}
```

---
*Generated by Farm-Agent Security Research Engine — Adhering to Coordinated Vulnerability Disclosure (CVD).*
"""


def save_bounty_dossier(
    report: AdvisoryReport,
    output_dir: Path | str = _DEFAULT_BOUNTY_DIR,
) -> Path:
    """Save an AdvisoryReport as a professional markdown dossier."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    date_str = report.created_at.strftime("%Y%m%d")
    safe_repo = report.affected_repo.replace("/", "_")
    safe_cwe = report.cwe_id.replace(":", "").replace("-", "_").lower()
    filename = f"{date_str}_{safe_repo}_{safe_cwe}.md"
    file_path = out_path / filename

    content = generate_bounty_dossier_markdown(report)
    file_path.write_text(content, encoding="utf-8")
    report.report_file_path = str(file_path)
    logger.info("[BUG BOUNTY] Dossier written to %s (CVSS %s - %s)", file_path, report.cvss_score, report.cwe_id)
    return file_path


async def handle_responsible_disclosure(
    github,
    owner: str,
    repo: str,
    finding: Finding,
    remediation_patch: str = "",
    poc_script: str = "",
    target_commit: str = "",
    config=None,
    notifier=None,
    memory=None,
) -> AdvisoryReport:
    """Handle responsible private disclosure for critical/high vulnerabilities.

    1. Determines CWE and calculates CVSS 3.1 metrics.
    2. Builds standardized AdvisoryReport.
    3. Checks if GitHub Security Advisories (GHSA) API is enabled for the repo.
    4. Automatically submits via GHSA if configured, or saves local dossier.
    5. Dispatches priority notification to researcher.
    """
    repo_full_name = f"{owner}/{repo}"
    await require_confirmed_security_finding(
        memory, finding, repo_full_name, target_commit=target_commit,
        channel="private_disclosure",
    )
    target_commit = target_commit or finding.metadata["security_target_commit"]
    cwe_id, cwe_name, cvss_score, cvss_vector = calculate_vulnerability_metrics(
        title=finding.title,
        description=finding.description,
        severity=finding.severity,
    )

    report = AdvisoryReport(
        title=f"{cwe_name} in {finding.file_path}",
        summary=finding.description,
        cwe_id=cwe_id,
        cwe_name=cwe_name,
        severity=finding.severity,
        cvss_score=cvss_score,
        cvss_vector=cvss_vector,
        affected_repo=repo_full_name,
        target_commit=target_commit,
        vulnerable_file=finding.file_path,
        vulnerable_line=finding.line_start,
        vulnerability_details=finding.suggestion or finding.description,
        reproduction_steps="Run the attached differential PoC script in the project root.",
        poc_script=poc_script,
        remediation_patch=remediation_patch,
        route=DisclosureRoute.BOUNTY_DOSSIER,
    )

    # Check GHSA capability on target repo
    auto_submit = False
    bounty_dir = _DEFAULT_BOUNTY_DIR
    if config and hasattr(config, "bounty"):
        auto_submit = getattr(config.bounty, "auto_submit_ghsa", False)
        bounty_dir = Path(getattr(config.bounty, "bounty_reports_dir", _DEFAULT_BOUNTY_DIR))

    is_ghsa_enabled = False
    if hasattr(github, "check_private_vulnerability_reporting"):
        is_ghsa_enabled = await github.check_private_vulnerability_reporting(owner, repo)

    if is_ghsa_enabled and auto_submit:
        report.route = DisclosureRoute.PRIVATE_GHSA
        res = await github.submit_security_advisory_report(
            owner=owner,
            repo=repo,
            summary=report.title,
            description=generate_bounty_dossier_markdown(report),
            cwe_ids=[cwe_id],
            severity=report.severity.value,
        )
        if res:
            report.ghsa_url = res.get("html_url")
            report.ghsa_id = res.get("ghsa_id") or res.get("id")

    # Always persist a local markdown dossier
    saved_path = save_bounty_dossier(report, output_dir=bounty_dir)

    # Deliver high-priority Telegram alert
    if notifier:
        msg = (
            f"🛡️ **[RESPONSIBLE DISCLOSURE] Security Advisory Generated**\n"
            f"• Target: `{repo_full_name}`\n"
            f"• Severity: **{report.severity.upper()}** (CVSS: {report.cvss_score})\n"
            f"• CWE: `{report.cwe_id}` ({report.cwe_name})\n"
            f"• File: `{report.vulnerable_file}`\n"
            f"• Dossier: `{saved_path}`\n"
        )
        if report.ghsa_url:
            msg += f"• GHSA Advisory: {report.ghsa_url}\n"
        else:
            msg += f"• Route: Private Dossier (Ready for HackerOne/Bugcrowd/Email)\n"
        try:
            await notifier.send_message(msg)
        except Exception as e:
            logger.error("Failed to deliver bounty Telegram alert: %s", e)

    return report


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
    """Save vulnerability findings to data/secret_findings/ for manual reporting."""
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
    memory=None,
) -> SecurityGateResult | None:
    """Run the full Security Disclosure Gate check.

    If private disclosure is requested:
    1. Logs [COMPLIANCE SKIP]
    2. Saves vulnerability details locally
    3. Sends Telegram notification
    """
    if dossier and hasattr(dossier, "vulnerabilities"):
        for vulnerability in dossier.vulnerabilities:
            if isinstance(vulnerability, Finding) and vulnerability.type == ContributionType.SECURITY_FIX:
                await require_confirmed_security_finding(
                    memory, vulnerability, f"{owner}/{repo}",
                )
    result = await check_security_disclosure_policy(
        github, owner, repo, readme_content=readme_content
    )

    if not result.requires_private_disclosure:
        logger.info(
            "[SECURITY GATE] %s: No private disclosure policy detected — proceeding normally.",
            result.repo_full_name,
        )
        return None

    if dossier and hasattr(dossier, "vulnerabilities"):
        for vulnerability in dossier.vulnerabilities:
            if isinstance(vulnerability, Finding) and vulnerability.type == ContributionType.SECURITY_FIX:
                await require_confirmed_security_finding(
                    memory, vulnerability, f"{owner}/{repo}", channel="private_disclosure",
                )

    logger.warning(
        "[COMPLIANCE SKIP] Private security disclosure requested by maintainers for %s. "
        "Matched phrases: %s. Contact: %s",
        result.repo_full_name,
        result.matched_phrases,
        result.contact_info or "N/A",
    )

    findings_data = []
    if dossier and hasattr(dossier, "vulnerabilities"):
        for v in dossier.vulnerabilities:
            findings_data.append(
                {
                    "file": getattr(v, "file", getattr(v, "file_path", "")),
                    "line": getattr(v, "line", getattr(v, "line_start", None)),
                    "snippet": getattr(v, "snippet", getattr(v, "description", "")),
                    "poc": getattr(v, "poc", ""),
                    "fix": getattr(v, "fix", getattr(v, "suggestion", "")),
                    "impact": getattr(v, "impact", getattr(v, "severity", "")),
                    "context_type": getattr(v, "context_type", ""),
                }
            )
    elif dossier is None:
        findings_data.append(
            {
                "note": "Vulnerabilities detected during analysis — detailed findings available in pipeline logs",
            }
        )

    saved_path = save_secret_findings(
        repo_full_name=result.repo_full_name,
        findings=findings_data,
        dossier_data={"repo_url": str(dossier.repo_url)} if dossier and hasattr(dossier, "repo_url") else None,
    )

    if notifier:
        try:
            await notifier.send_message(
                f"🔒 **SECRET FINDING SAVED**\n"
                f"Target: {result.repo_full_name}\n"
                f"Check {saved_path} for details to report manually.\n"
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
