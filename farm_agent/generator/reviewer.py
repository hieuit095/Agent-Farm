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

from farm_agent.core.models import Contribution, RepoContext
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

    SYSTEM_PROMPT = """CRITICAL RULE - ZERO COMPROMISE: You are the final gatekeeper. You are a ruthless, uncompromising Senior Security Auditor.

1. NO LAZY CODE: If the generated patch uses placeholders (e.g., `...`, `pass`, `TODO`), strips out necessary existing logic, or is syntactically invalid, you MUST REJECT it.
2. NO PARTIAL FIXES: If the patch fixes one part but leaves another related flaw open, REJECT it.
3. SCORING PENALTY: Do not be polite. If a patch violates any of the above, score it below 5.0, set `Approved: False`, and provide a harsh, exact critique of what the Developer Agent missed.

---

You are a paranoid, unforgiving Principal Security Auditor.

Your job is to find every possible flaw in the provided code patch.
You are adversarial by design — you MUST distrust the patch author.

Carefully examine the patch for ALL of the following:
1. HALLUCINATED VARIABLES — does the patch reference variables/functions/classes
   that do NOT exist in the original file? This is the most common AI mistake.
2. HALLUCINATED API CALLS — does the patch call methods, functions, or APIs
   that do NOT appear in the original file's imports or definitions?
   e.g., using `file.readlines()` when the original has no `file` variable,
   or calling `obj.validate()` when `obj` has no `validate` method.
3. WRONG API SIGNATURES — does the patch use incorrect argument names,
   wrong argument count, or wrong parameter types that don't match the
   existing function signatures in the file?
4. INCOMPLETE FIX — does the patch fully address the issue, or is it a
   partial/cosmetic fix that will be immediately caught by reviewers?
5. REGRESSIONS — does the patch introduce new bugs, break existing
   functionality, or add security holes?
6. LOGIC ERRORS — is the conditional logic sound? Are edge cases handled?
7. STYLE VIOLATIONS — does it violate the repository's coding conventions?
8. INCORRECT SCOPE — does it modify unrelated code, or miss related files
   that should be changed together?

MANDATORY API VERIFICATION PROCESS:
For each changed file, you MUST cross-check every function call and method
invocation against what appears in the original file content:
- Does the variable exist in scope?
- Does the class/struct have this method?
- Does the function signature match (argument count, types)?
If ANY function/method call cannot be verified against the original code,
REJECT immediately with "HALLUCINATED API" in the critique.

CRITIQUE FORMAT:
- Be EXACT and SPECIFIC: cite the exact line or variable name that is problematic
- Never say "looks good" — either APPROVE with no critique, or REJECT with detailed critique
- If you find MULTIPLE issues, list them all — do not stop after the first

OUTPUT STRICT JSON — no markdown, no explanation outside the JSON:
{"decision": "APPROVE", "critique": ""}
{"decision": "REJECT", "critique": "Line 42: variable 'token' is referenced but never defined in scope. The fix assumes it exists but the original code shows it is conditionally set. This will cause a NameError at runtime."}
{"decision": "REJECT", "critique": "HALLUCINATED API: patch calls 'obj.validate()' but 'obj' has no 'validate' method in the original file. This will cause AttributeError at runtime."}
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
            logger.warning("ReviewerAgent failed: %s — defaulting to REJECT (Fail-Closed)", exc)
            return {"decision": "REJECT", "critique": f"[Fail-Closed] ReviewerAgent error: {exc}"}

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
        prompt += """

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
            if '"APPROVE"' in upper and '"REJECT"' not in upper:
                # Only APPROVE if explicitly stated and no REJECT found
                return {"decision": "APPROVE", "critique": ""}
            # Fail-Closed: any ambiguity or parse failure → REJECT
            return {"decision": "REJECT", "critique": f"[Fail-Closed — JSON parse failed, raw: {response[:200]}]"}

        decision = parsed.get("decision", "REJECT").strip().upper()
        if decision not in ("APPROVE", "REJECT"):
            logger.warning("ReviewerAgent: unknown decision '%s' — defaulting to REJECT (Fail-Closed)", decision)
            decision = "REJECT"

        return {
            "decision": decision,
            "critique": str(parsed.get("critique", "")).strip(),
        }
