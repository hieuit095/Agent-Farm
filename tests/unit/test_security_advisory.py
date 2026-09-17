"""Unit tests for Bug Bounty Dossier, CVSS calculation, and Responsible Disclosure (Route C)."""

import pytest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from farm_agent.core.models import AdvisoryReport, ContributionType, DisclosureRoute, Finding, Severity
from farm_agent.github.security_gate import (
    calculate_vulnerability_metrics,
    generate_bounty_dossier_markdown,
    handle_responsible_disclosure,
    save_bounty_dossier,
)


def test_calculate_vulnerability_metrics_sqli():
    cwe_id, cwe_name, cvss_score, cvss_vector = calculate_vulnerability_metrics(
        title="SQL Injection in auth handler",
        description="User input is directly concatenated into SQL query",
        severity=Severity.CRITICAL,
    )
    assert cwe_id == "CWE-89"
    assert "SQL" in cwe_name
    assert cvss_score == 9.8
    assert "CVSS:3.1" in cvss_vector


def test_calculate_vulnerability_metrics_rce():
    cwe_id, cwe_name, cvss_score, cvss_vector = calculate_vulnerability_metrics(
        title="Remote Code Execution via eval",
        description="Arbitrary command execution via untrusted parameter",
        severity=Severity.CRITICAL,
    )
    assert cwe_id == "CWE-78"
    assert "OS Command" in cwe_name
    assert cvss_score == 9.8


def test_calculate_vulnerability_metrics_fallback():
    cwe_id, cwe_name, cvss_score, cvss_vector = calculate_vulnerability_metrics(
        title="Custom logic vulnerability",
        description="Unexpected state transition",
        severity=Severity.MEDIUM,
    )
    assert cwe_id == "CWE-699"
    assert cvss_score == 5.3


def test_generate_bounty_dossier_markdown():
    report = AdvisoryReport(
        title="SQL Injection in login endpoint",
        summary="Attacker can bypass authentication via ' OR '1'='1",
        cwe_id="CWE-89",
        cwe_name="SQL Injection",
        severity=Severity.CRITICAL,
        cvss_score=9.8,
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        affected_repo="target-org/target-repo",
        target_commit="a1b2c3d4",
        vulnerable_file="src/auth.py",
        vulnerable_line=42,
        vulnerability_details="Raw query concatenation in execute()",
        reproduction_steps="curl -X POST http://localhost:8080/login -d \"user=' OR 1=1--\"",
        poc_script="import requests\nres = requests.post('http://localhost:8080/login')\nassert res.status_code == 200",
        remediation_patch="--- a/src/auth.py\n+++ b/src/auth.py\n@@ -42 +42 @@\n-db.execute(f'SELECT * FROM users WHERE user={u}')\n+db.execute('SELECT * FROM users WHERE user=?', (u,))",
        route=DisclosureRoute.BOUNTY_DOSSIER,
    )

    md = generate_bounty_dossier_markdown(report)
    assert "# Security Advisory: SQL Injection in login endpoint" in md
    assert "target-org/target-repo" in md
    assert "CVSS v3.1" in md
    assert "9.8" in md
    assert "CWE-89" in md
    assert "src/auth.py:42" in md
    assert "Remediation Patch" in md
    assert "Coordinated Vulnerability Disclosure" in md


def test_save_bounty_dossier(tmp_path):
    report = AdvisoryReport(
        title="SSRF in image fetcher",
        summary="Server-Side Request Forgery allows accessing metadata",
        cwe_id="CWE-918",
        cwe_name="SSRF",
        severity=Severity.HIGH,
        cvss_score=8.6,
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N",
        affected_repo="test-org/web-app",
        vulnerable_file="fetcher.py",
        route=DisclosureRoute.BOUNTY_DOSSIER,
    )

    saved_file = save_bounty_dossier(report, output_dir=tmp_path)
    assert saved_file.exists()
    assert "test-org_web-app" in saved_file.name
    assert "cwe_918" in saved_file.name
    assert report.report_file_path == str(saved_file)

    content = saved_file.read_text(encoding="utf-8")
    assert "SSRF in image fetcher" in content


@pytest.mark.asyncio
async def test_handle_responsible_disclosure_local(tmp_path):
    github = MagicMock()
    github.check_private_vulnerability_reporting = AsyncMock(return_value=False)
    notifier = MagicMock()
    notifier.send_message = AsyncMock()

    finding = Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="Path traversal vulnerability",
        description="Allows arbitrary file read via ../ in filename",
        file_path="server/files.py",
        line_start=15,
    )

    config = MagicMock()
    config.bounty.auto_submit_ghsa = False
    config.bounty.bounty_reports_dir = str(tmp_path)

    advisory = await handle_responsible_disclosure(
        github=github,
        owner="sec-org",
        repo="storage-service",
        finding=finding,
        remediation_patch="diff ...",
        poc_script="import os ...",
        target_commit="deadbeef",
        config=config,
        notifier=notifier,
    )

    assert advisory.cwe_id == "CWE-22"
    assert advisory.severity == Severity.HIGH
    assert advisory.route == DisclosureRoute.BOUNTY_DOSSIER
    assert advisory.report_file_path is not None
    assert Path(advisory.report_file_path).exists()
    notifier.send_message.assert_called_once()
    assert "RESPONSIBLE DISCLOSURE" in notifier.send_message.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_responsible_disclosure_ghsa_api(tmp_path):
    github = MagicMock()
    github.check_private_vulnerability_reporting = AsyncMock(return_value=True)
    github.submit_security_advisory_report = AsyncMock(return_value={
        "html_url": "https://github.com/sec-org/repo/security/advisories/GHSA-1234",
        "ghsa_id": "GHSA-1234",
    })
    notifier = MagicMock()
    notifier.send_message = AsyncMock()

    finding = Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.CRITICAL,
        title="Remote code execution in worker",
        description="Command injection via worker queue",
        file_path="worker.py",
    )

    config = MagicMock()
    config.bounty.auto_submit_ghsa = True
    config.bounty.bounty_reports_dir = str(tmp_path)

    advisory = await handle_responsible_disclosure(
        github=github,
        owner="sec-org",
        repo="repo",
        finding=finding,
        config=config,
        notifier=notifier,
    )

    assert advisory.route == DisclosureRoute.PRIVATE_GHSA
    assert advisory.ghsa_id == "GHSA-1234"
    assert advisory.ghsa_url == "https://github.com/sec-org/repo/security/advisories/GHSA-1234"
    github.submit_security_advisory_report.assert_called_once()
