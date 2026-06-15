import os
import shutil
import tempfile
import pytest
from farm_agent.github.guidelines import RepoGuidelines

@pytest.mark.asyncio
async def test_discover_subsystem_docs():
    # Create a temporary directory structure
    temp_dir = tempfile.mkdtemp()
    try:
        # Create root README
        readme_content = "# Root README\nWelcome to Agent-Farm."
        with open(os.path.join(temp_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme_content)

        # Create docs/ subdir with a file
        docs_dir = os.path.join(temp_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        doc1_content = "# User Guide\nThis is the user guide."
        with open(os.path.join(docs_dir, "user_guide.md"), "w", encoding="utf-8") as f:
            f.write(doc1_content)

        # Create architecture/ subdir with a file
        arch_dir = os.path.join(temp_dir, "architecture")
        os.makedirs(arch_dir, exist_ok=True)
        arch_content = "# System Architecture\nHow the system is built."
        with open(os.path.join(arch_dir, "architecture.md"), "w", encoding="utf-8") as f:
            f.write(arch_content)

        # Create wiki/ subdir with a nested file
        wiki_dir = os.path.join(temp_dir, "wiki", "subfolder")
        os.makedirs(wiki_dir, exist_ok=True)
        wiki_content = "# Wiki Page\nNested wiki article."
        with open(os.path.join(wiki_dir, "wiki_page.md"), "w", encoding="utf-8") as f:
            f.write(wiki_content)

        # Instantiate RepoGuidelines and test discovery
        guidelines = RepoGuidelines()
        docs = await guidelines.discover_subsystem_docs(temp_dir)

        # Assertions
        assert "README.md" in docs
        assert docs["README.md"] == readme_content

        assert "docs/user_guide.md" in docs
        assert docs["docs/user_guide.md"] == doc1_content

        assert "architecture/architecture.md" in docs
        assert docs["architecture/architecture.md"] == arch_content

        assert "wiki/subfolder/wiki_page.md" in docs
        assert docs["wiki/subfolder/wiki_page.md"] == wiki_content

        # Verify RepoGuidelines attribute is also set
        assert guidelines.subsystem_docs == docs

    finally:
        shutil.rmtree(temp_dir)
