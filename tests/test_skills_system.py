"""Tests for sovereign/skills/ system."""
from __future__ import annotations

import pathlib


from sovereign.skills.types import (
    SkillDefinition, SkillInput, SkillOutput, SkillPermission, SkillStatus,
)
from sovereign.skills.index import SkillIndex
from sovereign.skills.security import validate_skill, check_execution_allowed


# ---------------------------------------------------------------------------
# SkillDefinition helpers
# ---------------------------------------------------------------------------

def _make_skill(
    skill_id: str = "test-skill",
    status: SkillStatus = SkillStatus.ACTIVE,
    permissions: list[SkillPermission] | None = None,
    requires_approval: bool = False,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        name=f"Test Skill {skill_id}",
        description="A test skill.",
        version="1.0.0",
        status=status,
        permissions=permissions or [SkillPermission.READ],
        requires_approval=requires_approval,
        inputs=[SkillInput(name="topic", type="string", required=True, description="Topic")],
        outputs=[SkillOutput(name="result", type="string", description="Result")],
    )


# ---------------------------------------------------------------------------
# SkillDefinition
# ---------------------------------------------------------------------------

def test_skill_definition_basic():
    skill = _make_skill()
    assert skill.skill_id == "test-skill"
    assert skill.status == SkillStatus.ACTIVE


def test_skill_definition_defaults():
    skill = _make_skill()
    assert skill.tags == []
    assert skill.dependencies == []
    assert skill.requires_approval is False


# ---------------------------------------------------------------------------
# SkillIndex
# ---------------------------------------------------------------------------

def test_skill_index_register_and_get():
    index = SkillIndex()
    skill = _make_skill("email-draft")
    index.register(skill)
    retrieved = index.get("email-draft")
    assert retrieved is not None
    assert retrieved.skill_id == "email-draft"


def test_skill_index_get_missing():
    index = SkillIndex()
    assert index.get("nonexistent") is None


def test_skill_index_all():
    index = SkillIndex()
    index.register(_make_skill("s1"))
    index.register(_make_skill("s2"))
    all_skills = index.all()
    assert len(all_skills) == 2


def test_skill_index_enable_disable():
    index = SkillIndex()
    skill = _make_skill("toggle-me")
    index.register(skill)

    index.disable("toggle-me")
    assert index.get("toggle-me").status == SkillStatus.DISABLED

    index.enable("toggle-me")
    assert index.get("toggle-me").status == SkillStatus.ACTIVE


def test_skill_index_by_tag():
    index = SkillIndex()
    s1 = _make_skill("s1")
    s1.tags = ["email", "draft"]
    s2 = _make_skill("s2")
    s2.tags = ["calendar"]
    index.register(s1)
    index.register(s2)

    email_skills = index.by_tag("email")
    assert len(email_skills) == 1
    assert email_skills[0].skill_id == "s1"


def test_skill_index_to_dict_list():
    index = SkillIndex()
    index.register(_make_skill("d1"))
    dicts = index.to_dict_list()
    assert len(dicts) == 1
    assert dicts[0]["skill_id"] == "d1"
    assert "status" in dicts[0]


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def test_validate_skill_ok():
    skill = _make_skill(permissions=[SkillPermission.READ])
    validate_skill(skill)  # Should not raise


def test_validate_skill_high_risk_forces_approval():
    # Security module auto-corrects requires_approval to True (logs warning, no raise)
    skill = _make_skill(
        permissions=[SkillPermission.EXECUTE],
        requires_approval=False,
    )
    validate_skill(skill)
    # After validation, requires_approval must be True
    assert skill.requires_approval is True


def test_validate_skill_code_forces_approval():
    skill = _make_skill(
        permissions=[SkillPermission.CODE],
        requires_approval=False,
    )
    validate_skill(skill)
    assert skill.requires_approval is True


def test_validate_skill_high_risk_with_approval_ok():
    skill = _make_skill(
        permissions=[SkillPermission.EXECUTE],
        requires_approval=True,
    )
    validate_skill(skill)  # Should not raise, approval already set


def test_check_execution_allowed_active():
    skill = _make_skill(status=SkillStatus.ACTIVE)
    skill.enabled = True
    ok = check_execution_allowed(skill, set())
    assert ok is True


def test_check_execution_allowed_disabled():
    skill = _make_skill(status=SkillStatus.DISABLED)
    skill.enabled = False
    ok = check_execution_allowed(skill, set())
    assert ok is False


# ---------------------------------------------------------------------------
# Parser — basic TOML parsing via built-in TOML packs
# ---------------------------------------------------------------------------

def test_parser_loads_real_skill_pack():
    from sovereign.skills.parser import parse_skill_file
    skills_dir = pathlib.Path("sovereign/skills/data")
    toml_files = list(skills_dir.glob("*.toml"))
    assert len(toml_files) > 0, "No TOML skill packs found"

    # Parse the first one
    skill = parse_skill_file(toml_files[0])
    assert skill is not None
    assert skill.skill_id != ""
    assert skill.name != ""


def test_loader_loads_all_packs():
    from sovereign.skills.loader import load_all_skills
    skills = load_all_skills(pathlib.Path("sovereign/skills/data"))
    assert len(skills) >= 5  # We created at least 9 packs
    ids = {s.skill_id for s in skills}
    assert "email-draft" in ids
    assert "daily-digest" in ids
    assert "meeting-notes" in ids
