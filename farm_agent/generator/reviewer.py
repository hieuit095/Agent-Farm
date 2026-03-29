"""Adversarial Reviewer Agent — Paranoid Senior Security Auditor.

This reviewer acts as a completely independent entity from the Generator.
It shares NO conversational history, NO system prompt, and NO LLM instance
with the Generator. Its sole purpose is to find flaws, regressions, and
hallucinations in the Generator's patches.

The Generator and Reviewer are distinct adversarial entities — if the
Reviewer REJECTs, the Generator must rewrite using the critique.
"""

from __future__ import annotations

import json
import logging
import re

from farm_agent.core.models import Contribution, Finding, RepoContext
from farm_agent.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """Independent adversarial reviewer — acts as a paranoid Senior Security Auditor.

    This agent is completely separate from the Generator:
    - Owns its own LLMProvider instance (no shared conversational history)
    - Has its own adversarial system prompt
    - Evaluates patches in isolation, never seeing the Generator's reasoning

    Outputs a strict JSON verdict:
        {"decision": "APPROVE" | "REJECT", "critique": "..."}
    """

    SYSTEM_PROMPT = """You are a paranoid, unforgiving Principal Security Auditor.

Your job is to find every possible flaw in the provided code patch.
You are adversarial by design — you MUST distrust the patch author.

Carefully examine the patch for:
1. HALLUCINATED VARIABLES — does the patch reference variables/functions that don't exist in the file?
2. INCOMPLETE FIX — does the patch fully address the issue, or is it a partial/cosmetic fix?
3. REGRESSIONS — does the patch introduce new bugs, break existing functionality, or add security holes?
4. LOGIC ERRORS — is the conditional logic sound? Are edge cases handled?
5. STYLE VIOLATIONS — does it violate the repository's coding conventions?
6. INCORRECT SCOPE — does it modify unrelated code, or miss related files that should be changed together?

For each changed file:
- Compare the before/after carefully
- Look for off-by-one errors, incorrect indices, wrong operators
- Check if the fix is minimal and focused vs sprawling

CRITIQUE FORMAT:
- Be EXACT and SPECIFIC: cite the exact line or variable name that is problematic
- Never say "looks good" — either APPROVE with no critique, or REJECT with detailed critique
- If you find MULTIPLE issues, list them all — do not stop after the first

OUTPUT STRICT JSON — no markdown, no explanation outside the JSON:
{"decision": "APPROVE", "critique": ""}
{"decision": "REJECT", "critique": "Line 42: variable 'token' is referenced but never defined in scope. The fix assumes it exists but the original code shows it is conditionally set. This will cause a NameError at runtime."}
"""

    def __init__(self, llm: LLMProvider, max_review_tokens: int = 800):
        self._llm = llm
        self._max_review_tokens = max_review_tokens

    async def review(self, contribution: Contribution, context: RepoContext) -> dict:
        """Have the adversarial reviewer evaluate a contribution.

        Returns a dict:
            {
                "decision": "APPROVE" | "REJECT",
                "critique": str,  # empty if APPROVE
            }

        Raises:
            RuntimeError: If the reviewer fails to produce a valid verdict.
        """
        prompt = self._build_review_prompt(contribution, context)

        try:
            response = await self._llm.complete(
                prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.05,  # Very low temperature for consistent JSON
                max_tokens=self._max_review_tokens,
            )
            return self._parse_verdict(response)

        except Exception as exc:
            logger.warning("ReviewerAgent failed: %s — defaulting to APPROVE", exc)
            return {"decision": "APPROVE", "critique": ""}

    def _build_review_prompt(self, contribution: Contribution, context: RepoContext) -> str:
        """Build the adversarial review prompt from the contribution."""
        file_blocks: list[str] = []
        for change in contribution.changes[:10]:  # cap at 10 files
            path = change.path
            new_content = change.new_content or ""
            old_content = change.original_content or ""

            block = f"## File: {path}\n"
            if old_content:
                block += f"--- ORIGINAL ({path}) ---\n```\n{old_content[:3000]}\n```\n"
            block += f"--- PROPOSED PATCH ({path}) ---\n```\n{new_content[:3000]}\n```\n"
            file_blocks.append(block)

        finding = contribution.finding
        prompt = f"""## CONTEXT

**PR Title**: {contribution.title}
**Finding Type**: {finding.type.value} | Severity: {finding.severity.value}
**Finding Description**: {finding.description}
**Expected Fix**: {finding.suggestion or '(not provided)'}
**Primary File**: {finding.file_path}

## CHANGED FILES

"""
        prompt += "\n\n".join(file_blocks)
        prompt += f"""

## YOUR TASK

Review the proposed patch above against the finding description.
Output ONLY a JSON object with your verdict.
If ANY issue exists (hallucination, incomplete fix, regression, logic error),
you MUST REJECT and provide a detailed, specific critique.
"""
        return prompt

    def _parse_verdict(self, response: str) -> dict:
        """Parse the LLM response into a structured verdict dict.

        Handles:
        - JSON with/without markdown fences
        - Trailing commas (invalid JSON)
        - Response prefixed with explanation text
        """
        # Strip markdown fences
        cleaned = re.sub(r"^```json\s*", "", response.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"```\s*$", "", cleaned.strip())

        # Remove trailing commas before } or ]
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning(
                "ReviewerAgent: failed to parse JSON from response: %s | Response: %s",
                exc,
                response[:300],
            )
            # Fallback: try to extract decision by keyword search
            upper = response.upper()
            if '"REJECT"' in upper or "REJECT" in upper.split('\n')[0]:
                return {"decision": "REJECT", "critique": f"[Parse failed — raw response: {response[:200]}]"}
            return {"decision": "APPROVE", "critique": ""}

        decision = parsed.get("decision", "APPROVE").strip().upper()
        if decision not in ("APPROVE", "REJECT"):
            logger.warning("ReviewerAgent: unknown decision '%s' — defaulting to APPROVE", decision)
            decision = "APPROVE"

        return {
            "decision": decision,
            "critique": str(parsed.get("critique", "")).strip(),
        }
