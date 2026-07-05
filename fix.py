import re

with open("farm_agent/analysis/analyzer.py", encoding="utf-8") as f:
    content = f.read()

# 1. Remove _check_sg_available
content = re.sub(
    r"    def _check_sg_available\(self.*?return self\._sg_available\n",
    "",
    content,
    flags=re.DOTALL,
)

# 2. Remove _resolve_rule_files
content = re.sub(
    r"    def _resolve_rule_files\(self.*?return rule_files\n", "", content, flags=re.DOTALL
)

# 3. Remove _run_sg_scan
content = re.sub(r"    async def _run_sg_scan\(self.*?return \[\]\n", "", content, flags=re.DOTALL)

# 4. Remove _run_ast_grep
content = re.sub(
    r"    async def _run_ast_grep\(self.*?return unique\n", "", content, flags=re.DOTALL
)

# 5. Remove LANGUAGE_RULE_PREFIX
content = re.sub(r"    LANGUAGE_RULE_PREFIX.*?\n    \}\n", "", content, flags=re.DOTALL)
content = re.sub(r"    SG_SCAN_TIMEOUT = 120\n", "", content)
content = re.sub(r"        self\._sg_available: bool \| None = None\n", "", content)

# 6. Update run_bloodhound
bloodhound_old = r"""        try:
            # ── Concurrent Radar: ast-grep \+ Semgrep ──
            tasks = \[\]
            task_labels = \[\]

            # ast-grep radar
            sg_available = self\._check_sg_available\(\)
            if sg_available:
                rule_files = self\._resolve_rule_files\(repo\.language\)
                if rule_files:
                    tasks\.append\(self\._run_ast_grep\(rule_files, clone_path\)\)
                    task_labels\.append\(f"ast-grep\(\{len\(rule_files\)\} rules\)"\)

            # Semgrep radar
            use_semgrep = getattr\(self\._config, "use_semgrep", False\)
            if use_semgrep:
                extra_rulesets: list\[str\] = \[\]
                if repo\.language:
                    lang_lower = repo\.language\.lower\(\)
                    if lang_lower == "go":
                        extra_rulesets\.append\("p/golang"\)
                    elif lang_lower == "solidity":
                        extra_rulesets\.extend\(\["p/solidity", "p/smart-contracts", "p/jwt"\]\)
                tasks\.append\(self\._run_semgrep\(clone_path, extra_rulesets=extra_rulesets or None\)\)
                base_rulesets = list\(getattr\(self\._config, "semgrep_rulesets", \[\]\)\)
                total_rulesets = len\(base_rulesets\) \+ len\(extra_rulesets\)
                task_labels\.append\(f"semgrep\(\{total_rulesets\} rulesets\)"\)

            # If neither tool is available, return empty dossier
            if not tasks:
                logger\.warning\(
                    "No radar tools available \(ast-grep=%s, semgrep=%s\) for %s — skipping bloodhound",
                    sg_available, use_semgrep, repo\.full_name,
                \)
                return empty_dossier"""

bloodhound_new = """        try:
            # ── Concurrent Radar: Semgrep ──
            tasks = []
            task_labels = []

            # Semgrep radar
            extra_rulesets: list[str] = []
            if repo.language:
                lang_lower = repo.language.lower()
                if lang_lower == "go":
                    extra_rulesets.append("p/golang")
                elif lang_lower == "solidity":
                    extra_rulesets.extend(["p/solidity", "p/smart-contracts", "p/jwt"])
                elif lang_lower == "rust":
                    extra_rulesets.append("p/rust")
            tasks.append(self._run_semgrep(clone_path, extra_rulesets=extra_rulesets or None))
            base_rulesets = list(getattr(self._config, "semgrep_rulesets", []))
            total_rulesets = len(base_rulesets) + len(extra_rulesets)
            task_labels.append(f"semgrep({total_rulesets} rulesets)")

            # If tool is not available
            if not tasks:
                logger.warning("No radar tools available for %s — skipping bloodhound", repo.full_name)
                return empty_dossier"""

content = re.sub(bloodhound_old, bloodhound_new, content, flags=re.DOTALL)

# Fix semgrep
semgrep_old = r"""    async def _run_semgrep\(
        self, repo_path: Path, extra_rulesets: list\[str\] \| None = None
    \) -> list\[dict\]:
        if not self\._check_semgrep_available\(\):
            return \[\]

        rulesets = list\(getattr\(self\._config, "semgrep_rulesets", \[\]\)\)
        if extra_rulesets:
            rulesets\.extend\(extra_rulesets\)
        if not rulesets:
            logger\.info\("No Semgrep rulesets configured — skipping Semgrep radar"\)
            return \[\]

        cmd = \["semgrep", "scan", "--json", "--quiet"\]
        for ruleset in rulesets:
            cmd\.extend\(\["--config", ruleset\]\)
        cmd\.append\(str\(repo_path\)\)

        logger\.info\(
            "Running Semgrep with %d rulesets against %s",
            len\(rulesets\),
            repo_path\.name,
        \)

        try:
            proc = await asyncio\.create_subprocess_exec\(
                \*cmd,
                stdout=asyncio\.subprocess\.PIPE,
                stderr=asyncio\.subprocess\.PIPE,
            \)
            stdout, stderr = await asyncio\.wait_for\(
                proc\.communicate\(\), timeout=self\.SEMGREP_TIMEOUT
            \)

            if proc\.returncode not in \(0, 1\):
                stderr_text = stderr\.decode\("utf-8", errors="replace"\)\[:500\]
                logger\.warning\(
                    "Semgrep returned exit code %d: %s",
                    proc\.returncode,
                    stderr_text,
                \)

            data = json\.loads\(stdout\.decode\("utf-8", errors="replace"\)\)
            results = data\.get\("results", \[\]\)"""

semgrep_new = """    async def _run_semgrep(
        self, repo_path: Path, extra_rulesets: list[str] | None = None
    ) -> list[dict]:
        if not self._check_semgrep_available():
            return []

        rulesets = list(getattr(self._config, "semgrep_rulesets", []))
        if extra_rulesets:
            rulesets.extend(extra_rulesets)
        if not rulesets:
            logger.info("No Semgrep rulesets configured — skipping Semgrep radar")
            return []

        cmd = ["semgrep", "scan", "--json", "--quiet"]
        for ruleset in rulesets:
            cmd.extend(["--config", ruleset])
        cmd.append(str(repo_path))

        logger.info(
            "Running Semgrep with %d rulesets against %s",
            len(rulesets),
            repo_path.name,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024 * 50, # 50MB limit to prevent memory crash
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.SEMGREP_TIMEOUT
            )

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            if proc.returncode not in (0, 1):
                logger.warning(
                    "Semgrep returned exit code %d: %s",
                    proc.returncode,
                    stderr_text[:1000],
                )

            # Robust parsing: Clean JSON extractor
            try:
                data = json.loads(stdout_text)
            except json.JSONDecodeError:
                logger.warning("Semgrep returned invalid JSON. Logging raw output for diagnostics:")
                logger.warning("STDOUT (first 1000 chars): %s", stdout_text[:1000])
                logger.warning("STDERR (first 1000 chars): %s", stderr_text[:1000])

                # Attempt to extract JSON from plain text warnings
                start_idx = stdout_text.find('{')
                end_idx = stdout_text.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    clean_json = stdout_text[start_idx:end_idx+1]
                    try:
                        data = json.loads(clean_json)
                        logger.info("Successfully extracted Clean JSON from Semgrep output")
                    except json.JSONDecodeError:
                        logger.error("Clean JSON extraction failed. Could not parse Semgrep output.")
                        return []
                else:
                    return []

            results = data.get("results", [])"""

content = re.sub(semgrep_old, semgrep_new, content, flags=re.DOTALL)

with open("farm_agent/analysis/analyzer.py", "w", encoding="utf-8") as f:
    f.write(content)
