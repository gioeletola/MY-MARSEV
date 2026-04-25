"""Automation Center — process automation and build."""
from sovereign.centers.simple_center import SimpleCenter


class AutomationCenter(SimpleCenter):
    CENTER_ID = "automation_centre"
    DESCRIPTION = "Process Automation & Build"
    PRIMARY_MODE = "business"
    AGENTS = ["codebridge_chief", "app_builder", "automation_builder", "toolsmith_agent", "qa_testing", "deployment_assistant", "bug_triage", "code_review"]
    DOMAIN_MAP = {"app": "app_builder", "automat": "automation_builder", "tool": "toolsmith_agent", "test": "qa_testing", "deploy": "deployment_assistant", "bug": "bug_triage", "code": "code_review"}
    DEFAULT_AGENT = "codebridge_chief"

center = AutomationCenter()
