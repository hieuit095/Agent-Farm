"""Tests for data models."""

import pytest

from contribai.core.models import (
    AnalysisResult,
    ContributionType,
    Finding,
    ImpactLevel,
    Repository,
    Severity,
)


class TestRepository:
    def test_url_property(self, sample_repo):
        assert sample_repo.url == "https://github.com/testowner/testrepo"

    def test_create_minimal(self):
        repo = Repository(owner="x", name="y", full_name="x/y")
        assert repo.stars == 0
        assert repo.default_branch == "main"


class TestFinding:
    def test_priority_score(self, sample_finding):
        # HIGH severity (3.0) * 0.9 confidence * 1.2 HIGH impact = 3.24
        assert sample_finding.priority_score == pytest.approx(3.24)

    def test_impact_level_default(self):
        f = Finding(
            type=ContributionType.CODE_QUALITY,
            severity=Severity.MEDIUM,
            title="Test",
            description="",
            file_path="a.py",
        )
        assert f.impact_level == ImpactLevel.TRIVIAL

    def test_impact_level_trivial_crushes_score(self):
        f = Finding(
            type=ContributionType.README_FIX,
            severity=Severity.MEDIUM,
            title="Add docstring",
            description="",
            file_path="a.py",
            confidence=1.0,
            impact_level=ImpactLevel.TRIVIAL,
        )
        # MEDIUM(2.0) * 1.0 * TRIVIAL(0.1) = 0.2
        assert f.priority_score == pytest.approx(0.2)

    def test_impact_level_critical_boosts_score(self):
        f = Finding(
            type=ContributionType.SECURITY_FIX,
            severity=Severity.CRITICAL,
            title="SQL injection",
            description="",
            file_path="a.py",
            confidence=1.0,
            impact_level=ImpactLevel.CRITICAL,
        )
        # CRITICAL(4.0) * 1.0 * CRITICAL(1.5) = 6.0
        assert f.priority_score == pytest.approx(6.0)

    def test_critical_priority(self):
        f = Finding(
            type=ContributionType.SECURITY_FIX,
            severity=Severity.CRITICAL,
            title="Test",
            description="Test",
            file_path="test.py",
            confidence=1.0,
            impact_level=ImpactLevel.MEDIUM,
        )
        assert f.priority_score == 4.0

    def test_low_priority(self):
        f = Finding(
            type=ContributionType.README_FIX,
            severity=Severity.LOW,
            title="Test",
            description="Test",
            file_path="test.py",
            confidence=0.5,
            impact_level=ImpactLevel.MEDIUM,
        )
        assert f.priority_score == 0.5


class TestAnalysisResult:
    def test_top_findings_sorted(self, sample_repo):
        findings = [
            Finding(
                type=ContributionType.README_FIX,
                severity=Severity.LOW,
                title="Low",
                description="",
                file_path="a.py",
            ),
            Finding(
                type=ContributionType.SECURITY_FIX,
                severity=Severity.CRITICAL,
                title="Critical",
                description="",
                file_path="b.py",
            ),
            Finding(
                type=ContributionType.CODE_QUALITY,
                severity=Severity.MEDIUM,
                title="Medium",
                description="",
                file_path="c.py",
            ),
        ]
        result = AnalysisResult(repo=sample_repo, findings=findings)
        top = result.top_findings
        assert top[0].title == "Critical"
        assert top[-1].title == "Low"

    def test_filter_by_type(self, sample_repo):
        findings = [
            Finding(
                type=ContributionType.SECURITY_FIX,
                severity=Severity.HIGH,
                title="Sec",
                description="",
                file_path="a.py",
            ),
            Finding(
                type=ContributionType.README_FIX,
                severity=Severity.LOW,
                title="Doc",
                description="",
                file_path="b.py",
            ),
        ]
        result = AnalysisResult(repo=sample_repo, findings=findings)
        sec = result.filter_by_type(ContributionType.SECURITY_FIX)
        assert len(sec) == 1
        assert sec[0].title == "Sec"

    def test_filter_by_severity(self, sample_repo):
        findings = [
            Finding(
                type=ContributionType.SECURITY_FIX,
                severity=Severity.LOW,
                title="Low",
                description="",
                file_path="a.py",
            ),
            Finding(
                type=ContributionType.SECURITY_FIX,
                severity=Severity.HIGH,
                title="High",
                description="",
                file_path="b.py",
            ),
            Finding(
                type=ContributionType.SECURITY_FIX,
                severity=Severity.CRITICAL,
                title="Crit",
                description="",
                file_path="c.py",
            ),
        ]
        result = AnalysisResult(repo=sample_repo, findings=findings)
        high_plus = result.filter_by_severity(Severity.HIGH)
        assert len(high_plus) == 2
