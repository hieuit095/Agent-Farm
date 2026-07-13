"""LLM-powered PoC generator and verification evaluator."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from farm_agent.core.models import Finding
from farm_agent.generator.engine import _extract_core_payload

if TYPE_CHECKING:
    from farm_agent.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class PoCGenerator:
    """Generate PoC scripts to verify findings and evaluate sandbox execution results."""

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def generate_poc(
        self,
        finding: Finding,
        target_file_content: str,
    ) -> tuple[str | None, str | None, str | None]:
        """Generate an executable script to dynamically trigger the finding's vulnerability."""
        system_prompt = (
            "You are a Senior Security Engineer and QA Automation Specialist.\n"
            "Your task is to write a Proof-of-Concept (PoC) validation script to dynamically trigger\n"  # noqa: E501
            "the bug or vulnerability described in the finding.\n\n"
            "Requirements:\n"
            "1. The script must be written to run locally inside the repository workspace (e.g. Python, Bash, or Go/Rust test).\n"  # noqa: E501
            "2. It should specifically trigger the bug/vulnerability, causing an assertion failure, exception, crash, or non-zero exit code.\n"  # noqa: E501
            "3. If the bug has been fixed, the script must exit successfully with code 0.\n"
            "4. Keep it self-contained and avoid external HTTP requests or complex system configurations. Do not require network access.\n"  # noqa: E501
            "5. Return the result strictly in JSON format inside markdown code fences:\n"
            "```json\n"
            "{\n"
            '    "filename": "test_poc.py",\n'
            '    "content": "import os\\n...",\n'
            '    "command": "python test_poc.py"\n'
            "}\n"
            "```"
        )

        deps = finding.metadata.get("module_dependencies", {})
        prompt = (
            f"Finding: {finding.title}\n"
            f"Description: {finding.description}\n"
            f"File Path: {finding.file_path}\n"
            f"Severity: {finding.severity}\n"
            f"Impact Level: {finding.impact_level}\n\n"
            f"Module Dependencies Context:\n"
            f"Imports: {deps.get('imports', [])}\n"
            f"Calls: {deps.get('calls', [])}\n"
            f"Dependents: {deps.get('dependents', [])}\n\n"
            f"Target Source File Content:\n"
            f"```\n{target_file_content}\n```\n\n"
            f"Construct the PoC script. Output the JSON payload containing 'filename', 'content', and 'command'."  # noqa: E501
        )

        try:
            raw_response = await self._llm.complete(
                prompt=prompt,
                system=system_prompt,
                temperature=0.2,
            )
            payload_str = _extract_core_payload(raw_response)
            if not payload_str:
                logger.warning("PoC Generator returned unparseable response: %s", raw_response)
                return None, None, None

            data = json.loads(payload_str)
            filename = data.get("filename")
            content = data.get("content")
            command = data.get("command")

            if not filename or not content or not command:
                logger.warning("PoC JSON missing required fields: %s", data)
                return None, None, None

            return filename, content, command
        except Exception as e:
            logger.warning("PoC generation failed: %s", e)
            return None, None, None

    async def evaluate_poc_result(
        self,
        finding: Finding,
        poc_content: str,
        sandbox_output: dict,
    ) -> tuple[bool, str]:
        """Evaluate sandbox output to determine if the vulnerability was successfully triggered (True Positive) or if it is a False Positive."""  # noqa: E501
        system_prompt = (
            "You are a Vulnerability Verification Auditor.\n"
            "Your task is to analyze the execution output of a PoC verification script inside a sandbox container.\n"  # noqa: E501
            "Determine if the crash or output was caused by the target vulnerability (True Positive) or if it is a False Positive\n"  # noqa: E501
            "(e.g., syntax errors, compilation failures, missing module dependencies, command not found, or successful exit without hitting the bug).\n\n"  # noqa: E501
            "Analyze exit_code, stdout, stderr, and timed_out:\n"
            "- True Positive: Exit code != 0 due to an AssertionError, panic, crash, or unexpected exception related to the vulnerability described. Or stdout/stderr contains printed proof of leak.\n"  # noqa: E501
            "- False Positive: Exit code != 0 due to SyntaxError, ModuleNotFoundError, compile errors, command not found. Or exit code is 0 meaning it failed to trigger the issue.\n\n"  # noqa: E501
            "Return the result strictly in JSON format inside markdown code fences:\n"
            "```json\n"
            "{\n"
            '    "is_triggered": true,\n'
            '    "reason": "AssertionError: expected X but got Y"\n'
            "}\n"
            "```"
        )

        prompt = (
            f"Finding: {finding.title}\n"
            f"Description: {finding.description}\n"
            f"File Path: {finding.file_path}\n\n"
            f"PoC Script Content:\n"
            f"```\n{poc_content}\n```\n\n"
            f"Sandbox Execution Result:\n"
            f"Exit Code: {sandbox_output.get('exit_code')}\n"
            f"Timed Out: {sandbox_output.get('timed_out')}\n"
            f"Stdout:\n{sandbox_output.get('stdout')}\n\n"
            f"Stderr:\n{sandbox_output.get('stderr')}\n\n"
            f"Determine if the vulnerability is triggered. Output the JSON payload containing 'is_triggered' (boolean) and 'reason'."  # noqa: E501
        )

        try:
            raw_response = await self._llm.complete(
                prompt=prompt,
                system=system_prompt,
                temperature=0.1,
            )
            payload_str = _extract_core_payload(raw_response)
            if not payload_str:
                logger.warning("PoC Evaluator returned unparseable response: %s", raw_response)
                return False, "Failed to parse evaluation response"

            data = json.loads(payload_str)
            is_triggered = data.get("is_triggered", False)
            reason = data.get("reason", "No reason provided by evaluator")
            return bool(is_triggered), str(reason)
        except Exception as e:
            logger.warning("PoC evaluation failed: %s", e)
            return False, f"PoC evaluation error: {e}"
