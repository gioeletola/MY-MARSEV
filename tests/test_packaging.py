"""Tests for packaging, versioning, and project metadata."""
from __future__ import annotations

import importlib
import pathlib

ROOT = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# sovereign package — version
# ---------------------------------------------------------------------------


def test_sovereign_version_string():
    import sovereign
    assert sovereign.__version__ == "0.2.0"


def test_sovereign_all_exports_version():
    import sovereign
    assert "__version__" in sovereign.__all__


def test_sovereign_package_importable():
    mod = importlib.import_module("sovereign")
    assert mod is not None


# ---------------------------------------------------------------------------
# pyproject.toml — metadata
# ---------------------------------------------------------------------------


def test_pyproject_has_correct_name():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'name = "sovereign-ai-os"' in text


def test_pyproject_has_correct_version():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'version = "0.2.0"' in text


def test_pyproject_has_requires_python():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'requires-python = ">=3.11"' in text


def test_pyproject_has_readme():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'readme = "README.md"' in text


def test_pyproject_has_scripts_section():
    text = (ROOT / "pyproject.toml").read_text()
    assert "[project.scripts]" in text


def test_pyproject_has_coverage_section():
    text = (ROOT / "pyproject.toml").read_text()
    assert "[tool.coverage.run]" in text


def test_pyproject_coverage_omits_tests():
    text = (ROOT / "pyproject.toml").read_text()
    assert "tests/*" in text


# ---------------------------------------------------------------------------
# README.md — existence and key sections
# ---------------------------------------------------------------------------


def test_readme_exists():
    assert (ROOT / "README.md").exists()


def test_readme_has_quick_start():
    text = (ROOT / "README.md").read_text()
    assert "Quick Start" in text


def test_readme_has_architecture():
    text = (ROOT / "README.md").read_text()
    assert "Architecture" in text


def test_readme_has_api_reference():
    text = (ROOT / "README.md").read_text()
    assert "API Reference" in text


def test_readme_has_operating_modes():
    text = (ROOT / "README.md").read_text()
    assert "Operating Modes" in text


def test_readme_has_docker_section():
    text = (ROOT / "README.md").read_text()
    assert "Docker" in text


# ---------------------------------------------------------------------------
# CI workflow — coverage flag
# ---------------------------------------------------------------------------


def test_ci_has_cov_fail_under():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "--cov-fail-under" in ci or "--cov" in ci


def test_ci_has_smoke_test():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "smoke" in ci.lower() or "import sovereign" in ci


# ---------------------------------------------------------------------------
# Smoke imports
# ---------------------------------------------------------------------------


def test_import_sovereign_orchestrator():
    mod = importlib.import_module("sovereign.orchestrator")
    assert mod is not None


def test_import_sovereign_entity_registry():
    mod = importlib.import_module("sovereign.entities.entity_registry")
    assert mod is not None


def test_import_sovereign_api_auth():
    mod = importlib.import_module("sovereign.api.auth")
    assert mod is not None
