# Experimental Labs — SOVEREIGN AI OS v0.3.0

SOVEREIGN includes **21 experimental labs** — sandboxed research environments for hypothesis-driven improvements. Each lab is a subclass of `LabsFramework` with domain-specific experiment templates, agent assignments, and benchmark metrics.

Labs are stored under `sovereign/labs/` and experiments persist to `data/labs/experiments.json`.

---

## Experiment Lifecycle

```
DRAFT → RUNNING → COMPLETED → GRADUATED
                    ↓
                  FAILED
```

| Status | Meaning |
|---|---|
| `draft` | Experiment created but not started |
| `running` | Actively collecting observations and metrics |
| `paused` | Suspended — can be resumed |
| `completed` | Hypothesis evaluated; outcome recorded |
| `graduated` | Promoted to production — treatment config applied |
| `failed` | Hypothesis not supported by measured results |

---

## The 21 Labs

| Lab ID | Class | Description |
|---|---|---|
| `finance` | `FinanceLab` | Financial modeling, predictive market research, portfolio optimization, and quantitative strategy experiments |
| `simulation` | `SimulationLab` | Monte Carlo simulations, probabilistic scenario modeling, portfolio stress tests |
| `cyber` | `CyberLab` | Adversarial security testing, vulnerability scanning, breach response simulation |
| `red_team` | `RedTeamLab` | Adversarial testing, security red-teaming, and controlled attack simulation (all exercises authorized) |
| `strategy` | `StrategyLab` | Strategic planning experiments, competitive analysis, and long-term scenario planning |
| `behavioral` | `BehavioralLab` | Behavioral pattern analysis, habit science, cognitive bias detection, and decision heuristics |
| `bio` | `BioLab` | Health, biometrics, sleep, fitness, and nutrition protocol design (informational only) |
| `black_swan` | `BlackSwanLab` | Extreme tail risk, catastrophic scenario modeling, and anti-fragility stress testing |
| `automation` | `AutomationLab` | Workflow automation experiments, SOP replacement testing, parallelism benchmarks |
| `ai_experiment` | `AIExperimentLab` | Prompt engineering experiments, agent behavior testing, and model comparison studies |
| `decision_science` | `DecisionScienceLab` | Decision quality research: cognitive bias detection, option generation, regret minimization |
| `design` | `DesignLab` | Aesthetic design, visual systems, brand identity, and signature style experimentation |
| `future_systems` | `FutureSystemsLab` | Emerging technologies, future trends, long-range forecasting, and megatrend analysis |
| `georisk` | `GeoRiskLab` | Geopolitical risk modeling, sanctions screening, jurisdiction analysis, and macro scenario planning |
| `media` | `MediaLab` | Content production experiments, video strategy optimization, thumbnail testing, and distribution channel comparison |
| `memory` | `MemoryLab` | Experiments on memory architecture, knowledge graph analysis, and retention patterns |
| `offline_survival` | `OfflineSurvivalLab` | Offline capability testing, survival protocol validation, and resilience assessment |
| `product` | `ProductLab` | Product ideation, feature design experiments, user research synthesis, and QA testing |
| `research` | `ResearchLab` | Systematic deep research, literature review, knowledge synthesis, and citation management |
| `social_dynamics` | `SocialDynamicsLab` | Social network analysis, influence modeling, relationship dynamics, and status signals |
| `3d` | `ThreeDLab` | 3D design concepts, spatial modeling, virtual environment planning, and spatial aesthetics |

---

## CLI Commands

```bash
# List all 21 labs with IDs and descriptions
python main.py lab list

# Show status and experiment summary for a lab
python main.py lab status finance
python main.py lab status ai_experiment

# List all experiments in a lab
python main.py lab experiments finance

# Start an experiment from a built-in template
python main.py lab run finance --template 0
python main.py lab run behavioral --template 1
```

---

## Python API

Import any lab directly from `sovereign.labs`:

```python
from sovereign.labs import FinanceLab, BehavioralLab, LabsFramework
from sovereign.labs.labs_framework import Hypothesis
```

### Creating and running an experiment

```python
from sovereign.labs import FinanceLab
from sovereign.labs.labs_framework import Hypothesis

lab = FinanceLab()

# Option A: use a built-in template (creates and starts automatically)
exp = lab.quick_experiment(template_index=0)

# Option B: create a custom experiment
hyp = Hypothesis(
    statement="If we apply momentum filters then Sharpe improves because noise is reduced",
    metric="sharpe_ratio",
    success_threshold=0.15,
    baseline=0.0,
)
exp = lab.create_experiment(
    name="Momentum Filter Test",
    description="Compare baseline vs momentum-filtered portfolio construction.",
    hypothesis=hyp,
    control_config={"filter": False},
    treatment_config={"filter": True, "lookback_days": 20},
    tags=["portfolio", "momentum"],
)
lab.start(exp.experiment_id)
```

### Recording observations and results

```python
lab.record_observation(exp.experiment_id, "Treatment shows 22% improvement in Sharpe at week 2")
lab.record_result(exp.experiment_id, "sharpe_ratio", 0.23)
lab.record_result(exp.experiment_id, "max_drawdown", -0.08, extra={"period": "Q1"})
```

### Completing and graduating

```python
# Evaluate hypothesis — marks COMPLETED or FAILED
evaluation = lab.complete(exp.experiment_id)
print(evaluation)
# {"success": True, "measured": 0.23, "threshold": 0.15}

# Promote a successful experiment to production
lab.graduate(exp.experiment_id)
```

### Leaderboard and comparison

```python
# Rank all completed/graduated experiments by their hypothesis metric
rows = lab.leaderboard()
for row in rows:
    print(row["name"], row["value"], row["passed"])

# Rank by a specific metric across experiments
rows = lab.leaderboard(metric="sharpe_ratio")

# Side-by-side comparison of two experiments
result = lab.compare(exp_a_id, exp_b_id)
print(result["winner"], result["delta"])
```

### Dashboard summary

```python
info = lab.dashboard()
print(info)
# {"total": 5, "by_status": {"completed": 3, "graduated": 1, "failed": 1}, "graduated": ["Momentum Filter Test"]}
```

---

## Data Storage

All experiments are persisted to `data/labs/experiments.json`. This file is created automatically on first use. Back it up before destructive operations.

```json
{
  "ab12cd34": {
    "experiment_id": "ab12cd34",
    "name": "Momentum Filter Test",
    "status": "graduated",
    "hypothesis": { ... },
    "results": { ... },
    "observations": [ ... ]
  }
}
```
