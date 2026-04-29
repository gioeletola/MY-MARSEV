"""Engineering superpower pack — system design, code quality, architecture patterns."""
from __future__ import annotations

ENGINEERING_PACK = {
    "id": "engineering",
    "name": "Senior Engineer Brain",
    "version": "1.0",
    "description": "System design principles, architectural patterns, code quality, debugging frameworks.",
    "system_design": {
        "scalability_ladder": [
            "Single server → Vertical scaling (more RAM/CPU)",
            "Read replicas → Horizontal read scaling",
            "Caching layer (Redis/Memcached) → Reduce DB load",
            "CDN → Static asset offload",
            "Load balancer → Horizontal app scaling",
            "Sharding/partitioning → Write scaling",
            "Microservices → Independent scaling per domain",
            "Event-driven → Async decoupling",
            "Multi-region → Geo distribution + HA",
        ],
        "cap_theorem": {
            "consistency": "All nodes see same data at same time",
            "availability": "Every request gets a response",
            "partition_tolerance": "System works despite network splits",
            "rule": "Pick 2 of 3. In practice, partition tolerance is required → choose CP or AP.",
        },
        "estimation_rules": [
            "1M req/day = ~12 req/sec",
            "1B req/day = ~12K req/sec",
            "1KB × 1M users = 1GB storage",
            "Read-heavy: cache aggressively (>80% of reads often cacheable)",
            "P99 latency target for user-facing: <200ms",
        ],
    },
    "architecture_patterns": {
        "CQRS": "Command Query Responsibility Segregation — separate read and write models",
        "event_sourcing": "Store events, not state — enables time travel, audit, replay",
        "saga": "Distributed transaction pattern using compensating transactions",
        "circuit_breaker": "Fail fast when downstream is unhealthy; recover gradually",
        "bulkhead": "Isolate failures — thread pools per integration, not shared",
        "strangler_fig": "Incrementally replace legacy by routing new traffic to new system",
        "hexagonal": "Ports & Adapters — keep domain logic independent of infrastructure",
    },
    "code_quality": {
        "SOLID": {
            "S": "Single Responsibility — one reason to change",
            "O": "Open/Closed — open for extension, closed for modification",
            "L": "Liskov Substitution — subtypes must be substitutable",
            "I": "Interface Segregation — no forced dependency on unused interfaces",
            "D": "Dependency Inversion — depend on abstractions, not concretions",
        },
        "four_rules_simple_design": [
            "Passes all tests",
            "Reveals intention (names explain)",
            "No duplication (DRY)",
            "Fewest elements (YAGNI)",
        ],
        "refactoring_smells": [
            "Long method (>20 lines)",
            "God class (knows too much)",
            "Feature envy (method uses another class more than its own)",
            "Primitive obsession (int/string for domain concepts)",
            "Shotgun surgery (one change forces many small edits elsewhere)",
        ],
    },
    "debugging_framework": {
        "OODA": "Observe → Orient → Decide → Act (military decision loop applied to bugs)",
        "steps": [
            "1. Reproduce: Isolate minimal reproducible case",
            "2. Hypothesise: List all plausible causes",
            "3. Eliminate: Binary search through the system",
            "4. Instrument: Add logging/metrics at decision points",
            "5. Verify: Confirm fix doesn't break related paths",
            "6. Prevent: Add test that would have caught this",
        ],
        "golden_rule": "Never fix a bug you don't understand. Fix the understanding first.",
    },
    "performance_rules": [
        "Measure before optimising — intuition is usually wrong",
        "Bottleneck first: CPU? Memory? I/O? Network?",
        "N+1 queries kill most backends — always check query counts",
        "Index the WHERE and JOIN columns, not everything",
        "Async I/O > thread pools > process pools for I/O-bound work",
        "Profile in production-like conditions, not dev",
    ],
    "security_checklist": [
        "Input validation at every boundary",
        "Parameterised queries — never string-concatenate SQL",
        "Secrets in env vars or vault — never in code",
        "Least privilege: service accounts, IAM roles, DB users",
        "Rate limiting on all public endpoints",
        "Log enough to detect, not so much you expose PII",
        "Dependency audit on every release (pip-audit, npm audit)",
        "Pin dependencies in production",
    ],
}


def get_pack() -> dict:
    return ENGINEERING_PACK


def pattern_info(name: str) -> str | None:
    return ENGINEERING_PACK["architecture_patterns"].get(name)


def debug_checklist() -> list[str]:
    return ENGINEERING_PACK["debugging_framework"]["steps"]
