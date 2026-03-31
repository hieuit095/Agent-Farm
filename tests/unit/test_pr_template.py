"""Tests for PR template auto-checking logic."""

import pytest
from contribai.pr.manager import auto_check_pr_template


def test_auto_check_safe_keywords():
    """Verify that lines with safe keywords are auto-checked."""
    assert auto_check_pr_template("- [ ] Run tests") == "- [x] Run tests"
    assert auto_check_pr_template("- [ ] Check linting") == "- [x] Check linting"
    assert auto_check_pr_template("- [ ] Verify build") == "- [x] Verify build"
    assert auto_check_pr_template("- [ ] Manual review") == "- [x] Manual review"
    assert auto_check_pr_template("- [ ] CI status") == "- [x] CI status"
    assert auto_check_pr_template("- [ ] Code quality") == "- [x] Code quality"


def test_auto_check_dangerous_keywords():
    """Verify that lines with dangerous keywords are NOT auto-checked."""
    assert auto_check_pr_template("- [ ] Breaking change") == "- [ ] Breaking change"
    assert auto_check_pr_template("- [ ] Database migration") == "- [ ] Database migration"
    assert auto_check_pr_template("- [ ] Deploy to production") == "- [ ] Deploy to production"
    assert auto_check_pr_template("- [ ] Visual changes (screenshot)") == "- [ ] Visual changes (screenshot)"

    # Combined safe and dangerous should NOT be checked
    assert auto_check_pr_template("- [ ] Breaking change in tests") == "- [ ] Breaking change in tests"


def test_auto_check_checkbox_formats():
    """Verify support for both '-' and '*' checkbox formats."""
    assert auto_check_pr_template("- [ ] Safe test") == "- [x] Safe test"
    assert auto_check_pr_template("* [ ] Safe lint") == "* [x] Safe lint"


def test_auto_check_no_match():
    """Verify that irrelevant lines or already checked boxes are unchanged."""
    assert auto_check_pr_template("Just a normal line") == "Just a normal line"
    assert auto_check_pr_template("- [x] Already checked test") == "- [x] Already checked test"

    # "No matches here" - careful with 'ci' in 'special' or 'words'
    # 'No matches' - no 'ci', 'pass', etc.
    assert auto_check_pr_template("- [ ] No matches") == "- [ ] No matches"


def test_auto_check_case_insensitivity():
    """Verify that keywords are matched regardless of case."""
    assert auto_check_pr_template("- [ ] RUN TESTS") == "- [x] RUN TESTS"
    assert auto_check_pr_template("- [ ] LINTING check") == "- [x] LINTING check"


def test_auto_check_multiline():
    """Verify that the function correctly processes multi-line strings."""
    body = (
        "## Summary\n"
        "- [ ] Run tests\n"
        "- [ ] Breaking change\n"
        "* [ ] Linting\n"
        "Some other text"
    )
    expected = (
        "## Summary\n"
        "- [x] Run tests\n"
        "- [ ] Breaking change\n"
        "* [x] Linting\n"
        "Some other text"
    )
    assert auto_check_pr_template(body) == expected
