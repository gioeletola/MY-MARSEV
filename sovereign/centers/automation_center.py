"""Automation Center — process automation and software build."""
from sovereign.centers.simple_center import SimpleCenter


class AutomationCenter(SimpleCenter):
    CENTER_ID = "automation_centre"
    DESCRIPTION = "Process Automation & Software Build"
    PRIMARY_MODE = "business"
    AGENTS = [
        "codebridge_chief", "app_builder", "automation_builder",
        "toolsmith_agent", "qa_testing", "deployment_assistant",
        "bug_triage", "code_review",
    ]
    DOMAIN_MAP = {
        "app": "app_builder",
        "build": "app_builder",
        "automat": "automation_builder",
        "script": "automation_builder",
        "tool": "toolsmith_agent",
        "utility": "toolsmith_agent",
        "test": "qa_testing",
        "qa": "qa_testing",
        "deploy": "deployment_assistant",
        "release": "deployment_assistant",
        "bug": "bug_triage",
        "error": "bug_triage",
        "code": "code_review",
        "review": "code_review",
    }
    DEFAULT_AGENT = "codebridge_chief"
    CAPABILITIES = [
        "End-to-end application design and production-grade code generation",
        "Workflow automation: scripts, integrations, scheduled tasks",
        "Internal tools and productivity utilities on demand",
        "QA: unit, integration, end-to-end test suites and coverage reports",
        "Deployment planning: pre-flight checks, rollout steps, rollback plan",
        "Bug triage: reproduce, root-cause, and fix recommendations",
        "Code review: correctness, security, performance, and maintainability",
    ]


center = AutomationCenter()
