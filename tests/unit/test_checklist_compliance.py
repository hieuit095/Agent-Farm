"""Unit test for auto_check_pr_template."""

from contribai.pr.manager import auto_check_pr_template


def test_auto_check_safe_boxes_only():
    """Verify that only safe compliance boxes are checked."""
    template = (
        "## Pre-submission Checklist\n"
        "\n"
        "- [ ] Existing tests pass\n"
        "- [ ] Linting is clean\n"
        "- [ ] Code formatting looks good\n"
        "- [ ] Build succeeds without errors\n"
        "- [ ] Manual review completed\n"
        "- [ ] Type checking passes\n"
        "- [ ] CI checks pass\n"
        "- [ ] Code quality standards met\n"
        "- [ ] This introduces a breaking change\n"
        "- [ ] Requires database migration\n"
        "- [ ] Screenshots attached for visual changes\n"
        "- [ ] Backward compatibility verified\n"
        "- [ ] Release notes updated\n"
        "- [ ] This has been deployed to staging\n"
        "- [ ] No new warnings or errors introduced\n"
        "* [ ] Style guidelines followed\n"
    )

    result = auto_check_pr_template(template)

    # Should be CHECKED (safe compliance keywords)
    assert "- [x] Existing tests pass" in result
    assert "- [x] Linting is clean" in result
    assert "- [x] Code formatting looks good" in result
    assert "- [x] Build succeeds without errors" in result
    assert "- [x] Manual review completed" in result
    assert "- [x] Type checking passes" in result
    assert "- [x] CI checks pass" in result
    assert "- [x] Code quality standards met" in result
    assert "- [x] No new warnings or errors introduced" in result
    assert "* [x] Style guidelines followed" in result

    # Should remain UNCHECKED (dangerous keywords)
    assert "- [ ] This introduces a breaking change" in result
    assert "- [ ] Requires database migration" in result
    assert "- [ ] Screenshots attached for visual changes" in result
    assert "- [ ] Backward compatibility verified" in result

    # Should remain UNCHECKED (no safe keyword match)
    assert "- [ ] Release notes updated" in result
    assert "- [ ] This has been deployed to staging" in result


def test_no_checkboxes_unchanged():
    """Body with no checkboxes passes through unchanged."""
    body = "## Description\n\nThis is a plain PR body.\n"
    assert auto_check_pr_template(body) == body


def test_already_checked_unchanged():
    """Already checked boxes are not modified."""
    body = "- [x] Tests pass\n- [ ] Breaking change\n"
    result = auto_check_pr_template(body)
    assert "- [x] Tests pass" in result
    assert "- [ ] Breaking change" in result


if __name__ == "__main__":
    test_auto_check_safe_boxes_only()
    test_no_checkboxes_unchanged()
    test_already_checked_unchanged()

    print("=== ALL TESTS PASSED ===")

    # Show a visual demo
    template = (
        "- [ ] Existing tests pass\n"
        "- [ ] Linting is clean\n"
        "- [ ] Build succeeds\n"
        "- [ ] Manual review completed\n"
        "- [ ] This introduces a breaking change\n"
        "- [ ] Requires database migration\n"
        "- [ ] Screenshots attached\n"
        "- [ ] No new warnings introduced\n"
        "* [ ] Style guidelines followed\n"
    )
    result = auto_check_pr_template(template)
    print("\n=== DEMO OUTPUT ===")
    for line in result.split("\n"):
        if "[x]" in line or "[ ]" in line:
            status = "CHECKED  " if "[x]" in line else "UNCHECKED"
            print(f"  {status}: {line.strip()}")
