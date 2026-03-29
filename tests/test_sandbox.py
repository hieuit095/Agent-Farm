"""Tests for Polyglot Guillotine sandbox logic."""

import os
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.core.sandbox import (
    LANGUAGE_ENVIRONMENTS,
    DEFAULT_ENV,
    EXTENSION_TO_LANGUAGE,
    detect_language_from_extensions,
    detect_language_from_repo_info,
    get_environment_for_language,
    DockerSandbox,
)


class TestLanguageEnvironments:
    """Verify all language environments are correctly configured."""

    def test_all_languages_have_required_fields(self):
        """Every language must have 'image' and 'test_cmd' keys."""
        required_keys = {"image", "test_cmd", "install_cmd"}
        for lang, env in LANGUAGE_ENVIRONMENTS.items():
            assert required_keys.issubset(env), f"{lang} missing keys: {required_keys - set(env)}"

    def test_python_environment(self):
        env = LANGUAGE_ENVIRONMENTS["python"]
        assert "alpine" in env["image"]
        assert "pytest" in env["test_cmd"]

    def test_rust_environment(self):
        env = LANGUAGE_ENVIRONMENTS["rust"]
        assert "rust:" in env["image"]
        assert "cargo test" in env["test_cmd"]

    def test_javascript_environment(self):
        env = LANGUAGE_ENVIRONMENTS["javascript"]
        assert "node:" in env["image"]
        assert "npm test" in env["test_cmd"]

    def test_go_environment(self):
        env = LANGUAGE_ENVIRONMENTS["go"]
        assert "golang:" in env["image"]
        assert "go test" in env["test_cmd"]

    def test_default_falls_back_to_python(self):
        """Unknown language names must fall back to Python."""
        env = get_environment_for_language("cobol")
        assert env["image"] == LANGUAGE_ENVIRONMENTS["python"]["image"]

    def test_case_insensitive_language_lookup(self):
        """Language lookup must be case-insensitive."""
        assert get_environment_for_language("PYTHON")["image"] == LANGUAGE_ENVIRONMENTS["python"]["image"]
        assert get_environment_for_language("Rust")["image"] == LANGUAGE_ENVIRONMENTS["rust"]["image"]
        assert get_environment_for_language("Go")["image"] == LANGUAGE_ENVIRONMENTS["go"]["image"]


class TestDetectLanguageFromExtensions:
    """Test language detection by scanning file extensions in a directory."""

    def test_detects_python_by_py_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hello')")
            Path(tmpdir, "utils.py").write_text("def foo(): pass")
            lang = detect_language_from_extensions(tmpdir)
            assert lang == "python"

    def test_detects_rust_by_rs_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "lib.rs").write_text("pub fn main() {}")
            Path(tmpdir, "main.rs").write_text("fn main() {}")
            lang = detect_language_from_extensions(tmpdir)
            assert lang == "rust"

    def test_detects_javascript_by_js_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "index.js").write_text("console.log('hello')")
            lang = detect_language_from_extensions(tmpdir)
            assert lang == "javascript"

    def test_detects_typescript_by_ts_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "app.ts").write_text("const x: number = 1;")
            lang = detect_language_from_extensions(tmpdir)
            assert lang == "typescript"

    def test_detects_go_by_go_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "server.go").write_text("package main")
            lang = detect_language_from_extensions(tmpdir)
            assert lang == "go"

    def test_skips_node_modules(self):
        """Files inside node_modules must be ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            modules = Path(tmpdir, "node_modules", "fake.js")
            modules.parent.mkdir(parents=True)
            modules.write_text("require('something')")
            lang = detect_language_from_extensions(tmpdir)
            # node_modules is skipped; with no other files, should fall back to python
            assert lang == "python", f"Expected python (no non-skipped files), got {lang}"

    def test_falls_back_to_python_for_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lang = detect_language_from_extensions(tmpdir)
            assert lang == "python"

    def test_returns_most_common_language(self):
        """When multiple languages exist, return the most frequent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                Path(tmpdir, f"util_{i}.py").write_text("print('py')")
            for i in range(3):
                Path(tmpdir, f"main_{i}.js").write_text("console.log('js')")
            for i in range(2):
                Path(tmpdir, f"lib_{i}.rs").write_text("fn main() {}")
            lang = detect_language_from_extensions(tmpdir)
            assert lang == "python"


class TestDetectLanguageFromRepoInfo:
    """Test language detection from GitHub repo metadata dict."""

    def test_detects_python(self):
        assert detect_language_from_repo_info({"language": "Python"}) == "python"

    def test_detects_javascript(self):
        assert detect_language_from_repo_info({"language": "JavaScript"}) == "javascript"

    def test_detects_typescript(self):
        assert detect_language_from_repo_info({"language": "TypeScript"}) == "typescript"

    def test_detects_rust(self):
        assert detect_language_from_repo_info({"language": "Rust"}) == "rust"

    def test_detects_go(self):
        assert detect_language_from_repo_info({"language": "Go"}) == "go"

    def test_detects_java(self):
        assert detect_language_from_repo_info({"language": "Java"}) == "java"

    def test_returns_none_for_missing_language(self):
        assert detect_language_from_repo_info({"description": "A cool repo"}) is None

    def test_returns_none_for_none_input(self):
        assert detect_language_from_repo_info(None) is None


class TestGetEnvironmentForLanguage:
    """Test environment selection for each language."""

    def test_rust_env_has_correct_image_and_cmd(self):
        env = get_environment_for_language("rust")
        assert "rust:" in env["image"]
        assert "cargo test" in env["test_cmd"]

    def test_go_env(self):
        env = get_environment_for_language("go")
        assert "golang:" in env["image"]
        assert "go test" in env["test_cmd"]

    def test_javascript_env(self):
        env = get_environment_for_language("javascript")
        assert "node:" in env["image"]
        assert "npm test" in env["test_cmd"]

    def test_java_env(self):
        env = get_environment_for_language("java")
        assert "java" in env["image"].lower() or "jdk" in env["image"].lower()

    def test_c_sharp_env(self):
        env = get_environment_for_language("csharp")
        assert "dotnet" in env["image"]


class TestSandboxPolyglotDispatch:
    """Test that DockerSandbox dispatches to the correct image based on language."""

    @pytest.fixture
    def sandbox(self):
        return DockerSandbox()

    @pytest.mark.asyncio
    async def test_run_in_sandbox_auto_selects_rust_image_for_rust_language(self):
        """When language='rust', resolved image must be rust:1.75-alpine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "lib.rs").write_text("fn main() {}")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "abc123"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            result = await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                language="rust",
                timeout=30,
            )

            # Verify rust image was used
            call_image = mock_client.containers.run.call_args[0][0]
            assert "rust:" in call_image, f"Expected rust image, got {call_image}"

            # Verify cargo test was in the command
            call_args = mock_client.containers.run.call_args
            cmd_list = call_args[0][1]
            assert any("cargo test" in str(c) for c in cmd_list), f"Expected cargo test, got {cmd_list}"

            assert result["exit_code"] == 0
            assert result["timed_out"] is False

    @pytest.mark.asyncio
    async def test_run_in_sandbox_auto_selects_go_image_for_go_language(self):
        """When language='go', resolved image must be golang:1.21-alpine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.go").write_text("package main")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "abc456"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            result = await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                language="go",
                timeout=30,
            )

            call_image = mock_client.containers.run.call_args[0][0]
            assert "golang:" in call_image, f"Expected golang image, got {call_image}"
            assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_run_in_sandbox_auto_selects_nodejs_for_typescript(self):
        """When language='typescript', resolved image must be node:20-alpine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "app.ts").write_text("const x: number = 1;")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "abc789"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            result = await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                language="typescript",
                timeout=30,
            )

            call_image = mock_client.containers.run.call_args[0][0]
            assert "node:" in call_image, f"Expected node image, got {call_image}"
            assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_run_in_sandbox_auto_selects_java_image(self):
        """When language='java', resolved image must include JDK."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "Main.java").write_text("public class Main { public static void main(String[] args) {} }")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "java123"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            result = await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                language="java",
                timeout=30,
            )

            call_image = mock_client.containers.run.call_args[0][0]
            assert "java" in call_image.lower() or "jdk" in call_image.lower()

    @pytest.mark.asyncio
    async def test_run_in_sandbox_auto_detects_language_from_file_extensions(self):
        """When no language is given, sandbox must auto-detect from repo files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.rs").write_text("fn main() {}")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "rs456"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            # No language parameter — must auto-detect
            result = await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                timeout=30,
            )

            call_image = mock_client.containers.run.call_args[0][0]
            assert "rust:" in call_image, f"Expected rust (auto-detected), got {call_image}"

    @pytest.mark.asyncio
    async def test_run_in_sandbox_auto_detects_from_repo_info(self):
        """When repo_info has language metadata, use it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.go").write_text("package main")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "go789"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            result = await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                repo_info={"language": "Go"},
                timeout=30,
            )

            call_image = mock_client.containers.run.call_args[0][0]
            assert "golang:" in call_image, f"Expected golang (from repo_info), got {call_image}"

    @pytest.mark.asyncio
    async def test_run_in_sandbox_pulls_image_only_if_not_present(self):
        """client.images.pull must ONLY be called when ImageNotFound is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hi')")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "pulltest"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}
            # images.pull should NOT be called for a pre-existing image
            mock_client.images.pull = MagicMock()

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                language="python",
                timeout=30,
            )

            # images.pull must not be called when container run succeeds
            mock_client.images.pull.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_in_sandbox_pulls_image_on_imagenotfound(self):
        """If image is missing, pull it before running."""
        from docker.errors import ImageNotFound

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hi')")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "pull2"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}

            # First call raises ImageNotFound → triggers pull
            # Second call succeeds
            mock_client.containers.run.side_effect = [ImageNotFound("not found"), mock_container]
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}
            mock_pull = MagicMock()
            mock_client.images.pull = mock_pull

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                language="python",
                timeout=30,
            )

            # images.pull MUST be called once after ImageNotFound
            mock_pull.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_in_sandbox_returns_correct_result_dict(self):
        """Verify the result dict contains polyglot metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hi')")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "resulttest"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 42}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = iter([(b"hello", b"")])
            mock_client.api.wait.return_value = {"StatusCode": 42}

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            result = await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                language="python",
                timeout=30,
            )

            assert result["exit_code"] == 42
            assert result["timed_out"] is False
            assert "python" in result["image"]  # resolved image returned
            assert result["stdout"] == "hello"
            assert result["stderr"] == ""

    @pytest.mark.asyncio
    async def test_run_in_sandbox_falls_back_to_python_for_unknown_language(self):
        """Unknown language → Python image must be used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hi')")
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.id = "fallback"
            mock_container.status = "exited"
            mock_container.attrs = {"State": {"ExitCode": 0}}
            mock_client.containers.run.return_value = mock_container
            mock_client.containers.list.return_value = []
            mock_client.api.attach.return_value = (b"", b"")
            mock_client.api.wait.return_value = {"StatusCode": 0}

            sandbox = DockerSandbox()
            sandbox.client = mock_client

            result = await sandbox.run_in_sandbox(
                repo_path=tmpdir,
                language="cobol",  # unknown
                timeout=30,
            )

            call_image = mock_client.containers.run.call_args[0][0]
            assert "python:" in call_image, f"Expected python fallback, got {call_image}"
