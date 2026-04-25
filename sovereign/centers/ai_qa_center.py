"""AI QA Center — AI quality assurance and evaluation."""
from sovereign.centers.simple_center import SimpleCenter


class AIQACenter(SimpleCenter):
    CENTER_ID = "ai_qa_centre"
    DESCRIPTION = "AI Quality Assurance & Evals"
    PRIMARY_MODE = "command"
    AGENTS = ["qa_testing", "bias_detector", "trust_scoring_agent"]
    DOMAIN_MAP = {"eval": "eval_agent", "quality": "qa_testing", "bias": "bias_detector", "trust": "trust_scoring_agent", "test": "qa_testing"}
    DEFAULT_AGENT = "qa_testing"

center = AIQACenter()
