# Human Behavior Audit & Proposal

## 1. Codebase Audit: Identified Robotic Flaws

After scanning `pipeline.py`, `human.py`, and `patrol.py`, the following "robotic" patterns were identified that could flag the agent to maintainers or anti-abuse ML systems:

1.  **Immediate Notification Reaction (The "Always Online" Flaw):**
    *   **Location:** `contribai/pr/patrol.py` (`_handle_code_fix` and `_handle_question`).
    *   **Issue:** When the bot detects actionable feedback during a patrol cycle, it immediately transitions into the WPM typing delay (`_calculate_typing_delay`). It lacks a "Notification Lag"—the time it naturally takes a human to see a GitHub email, open the laptop, context-switch, and begin typing.

2.  **Perfectly Formatted Micro-Commits:**
    *   **Location:** `contribai/pr/patrol.py` (`GITHUB_REPLIES["COMMIT_FIX"]`).
    *   **Issue:** Commit messages for review fixes rigorously follow conventional commit standards (e.g., `fix: apply reviewer suggestion — ...`). When humans push quick 1-line typographical fixes to their own open PRs, they often use lazy, imperfect messaging like "oops", "typo", or "addressed comments".

3.  **Synchronous Git Timestamps:**
    *   **Location:** `contribai/pr/patrol.py` (`_handle_code_fix`) and PR creation logic in `contribai/orchestrator/pipeline.py`.
    *   **Issue:** Because the files are committed via the GitHub API immediately after the `asyncio.sleep()` delay, the Git `author_date` exactly matches the `committer_date` and the GitHub PR push event timestamp. Real developers usually work locally; there is a natural temporal gap between saving a commit (`author_date`) and pushing it (`committer_date` / push event).

4.  **Always Courteous Surrendering (Zero Ghosting):**
    *   **Location:** `contribai/pr/patrol.py` (Killswitch logic limiting `MAX_DISCUSSION_REPLIES`).
    *   **Issue:** When the bot reaches its max discussion replies, it politely explains the situation and cleanly closes the PR (`GITHUB_REPLIES["SURRENDER"]`). While polite, humans often abandon complex or overly debated PRs without a word (ghosting), leaving the maintainer or stale-bot to close it eventually.

## 2. Proposed "Next-Level" Human Behaviors

To achieve 100% Turing-passable state, we propose implementing the following behavioral upgrades:

### A. The "Notification Lag" & Micro-Distractions
*   **Proposal:** Introduce a randomized `notification_read_delay` (e.g., 10 minutes to 4 hours) before initiating the WPM typing delay in `patrol.py`. If the delay pushes the required action into the "Night Sleep" window, it should explicitly defer the reply until the next morning.
*   **Benefit:** Prevents the bot from acting like a webhook that triggers the second a maintainer submits a review.

### B. Imperfect & Degraded Communication
*   **Proposal:** Introduce a `fatigue_index` based on how many hours the bot has been active that day. As fatigue increases, probabilistically downcase the first letter of comments, remove trailing punctuation, or drop the conventional `fix:` prefix from follow-up commits.
*   **Benefit:** Simulates human burnout and casualization of language over continuous effort.

### C. Git Timestamp Spoofing
*   **Proposal:** When interacting with the GitHub API to construct trees and commits, explicitly supply an `author` object with a `date` timestamp that is backdated by 15–45 minutes relative to the current physical push time.
*   **Benefit:** Makes the commit graph look like the developer committed the code locally piecemeal, ran tests, and then executed a bulk `git push`, effectively defeating ML timing heuristics.

### D. Probabilistic Ghosting
*   **Proposal:** Modify the `SURRENDER` logic. Instead of 100% closure, introduce a 30% chance that the bot will simply "ghost" the PR by silencing notifications for that thread in its SQLite memory, leaving the PR open and abandoning the effort.
*   **Benefit:** Accurately reflects the open-source reality where contributors lose motivation and leave messy PRs unresolved.
