"""Data science superpower pack — analysis, ML, statistics, experimentation."""
from __future__ import annotations

PACK = {
    "id": "data_science",
    "title": "Data Science & ML",
    "version": "1.0",
    "sections": {
        "statistics": {
            "distributions": {
                "Normal": "Bell curve; mean=median=mode; 68-95-99.7 rule",
                "Binomial": "n independent trials, P(success)=p; mean=np, var=np(1-p)",
                "Poisson": "Count of rare events; mean=variance=λ",
                "Exponential": "Time between Poisson events; memoryless property",
                "Power law": "Fat tails; Pareto 80/20 is special case",
            },
            "hypothesis_testing": {
                "steps": [
                    "State H0 (null) and H1 (alternative)",
                    "Choose test (t-test, chi-sq, ANOVA, Mann-Whitney…)",
                    "Set α (typically 0.05)",
                    "Calculate p-value or test statistic",
                    "Reject H0 if p < α",
                ],
                "pitfalls": [
                    "p < 0.05 ≠ important (effect size matters)",
                    "Multiple comparisons inflate false positives (Bonferroni correction)",
                    "p-hacking: don't fish for significance",
                    "Underpowered studies miss real effects",
                ],
                "effect_sizes": {
                    "Cohen's d": "Small 0.2, Medium 0.5, Large 0.8",
                    "r": "Small 0.1, Medium 0.3, Large 0.5",
                    "Odds ratio": "OR=1 no effect, OR>1 increased odds",
                },
            },
            "correlation_vs_causation": [
                "Correlation ≠ causation (lurking variables)",
                "RCT (randomised controlled trial) = gold standard for causation",
                "Observational: use DiD, IV, RDD, matching to approximate causal inference",
                "Granger causality: X predicts Y after controlling for Y's own past",
            ],
        },
        "ml_workflow": {
            "steps": [
                "1. Problem framing: regression / classification / clustering / ranking",
                "2. Data collection & labelling",
                "3. EDA (distributions, missing data, correlations, outliers)",
                "4. Feature engineering (encoding, scaling, imputation, interactions)",
                "5. Model selection (start simple: linear/logistic regression)",
                "6. Hyperparameter tuning (CV, grid/random/Bayesian search)",
                "7. Evaluation on hold-out test set",
                "8. Deployment + monitoring (data drift, concept drift)",
            ],
            "bias_variance": {
                "bias": "Systematic error — underfitting",
                "variance": "Sensitivity to training data — overfitting",
                "tradeoff": "Increasing complexity ↑ variance ↓ bias",
                "remedies": {
                    "high_bias": "More features, more complex model, less regularisation",
                    "high_variance": "More data, regularisation, simpler model, ensemble",
                },
            },
            "metrics": {
                "regression": ["MAE", "RMSE", "MAPE", "R²"],
                "classification": ["Accuracy", "Precision", "Recall", "F1", "AUC-ROC", "Log loss"],
                "ranking": ["NDCG", "MAP", "MRR"],
                "clustering": ["Silhouette score", "Davies-Bouldin", "Calinski-Harabasz"],
            },
        },
        "algorithms": {
            "supervised": {
                "Linear/Logistic Regression": "Baseline; interpretable; assumes linearity",
                "Decision Tree": "Interpretable; high variance; CART algorithm",
                "Random Forest": "Ensemble of trees; reduces variance via bagging",
                "Gradient Boosting (XGBoost/LightGBM)": "Boosting sequentially fixes errors; often best on tabular data",
                "SVM": "Max margin; kernel trick for nonlinear; poor on large n",
                "Neural Networks": "Universal approximator; needs lots of data; GPU required for large models",
                "KNN": "Non-parametric; lazy learning; O(n) at inference",
            },
            "unsupervised": {
                "K-Means": "Centroid clustering; fast; need to specify k; sensitive to scale",
                "DBSCAN": "Density-based; detects outliers; arbitrary shapes",
                "PCA": "Linear dim-reduction; maximises variance; interpretable components",
                "t-SNE": "Non-linear 2D/3D visualisation; not for downstream ML",
                "UMAP": "Faster than t-SNE; preserves global structure better",
            },
        },
        "experimentation": {
            "ab_testing": {
                "steps": [
                    "Define metric (primary + guardrails)",
                    "Calculate required sample size (power analysis)",
                    "Randomise units (users, sessions, devices)",
                    "Run until planned n (don't peek early)",
                    "Analyse: t-test, z-test, or bootstrap",
                    "Ship if statistically AND practically significant",
                ],
                "power_formula": "n ≈ 16σ²/δ² for 80% power at α=0.05 (two-sided t-test)",
                "common_mistakes": [
                    "Novelty effect — wait for it to decay",
                    "Segment imbalance — check via SRM test",
                    "Network effects — cluster randomisation",
                    "Long-run vs short-run behaviour differences",
                ],
            },
            "causal_inference": {
                "DiD": "Difference-in-Differences: parallel trends assumption",
                "IV": "Instrumental Variables: exogenous instrument correlated with treatment",
                "RDD": "Regression Discontinuity: exploit arbitrary cutoffs",
                "PSM": "Propensity Score Matching: balance confounders",
            },
        },
        "data_quality": {
            "checks": [
                "Completeness: % missing per column",
                "Uniqueness: duplicate rows / IDs",
                "Validity: values within expected range/domain",
                "Consistency: cross-field rules (end_date > start_date)",
                "Timeliness: data freshness relative to use case",
            ],
            "missing_data": {
                "MCAR": "Missing Completely At Random — safe to drop",
                "MAR": "Missing At Random — impute using other columns",
                "MNAR": "Missing Not At Random — must model missingness",
                "strategies": ["Mean/median/mode imputation", "KNN imputation", "MICE", "Indicator variable"],
            },
        },
        "mental_models": [
            "All models are wrong, some are useful (Box)",
            "Garbage in, garbage out — data quality > algorithm choice",
            "Start with the simplest model that could work",
            "Measure what matters (Goodhart's Law: metric becomes target → stops being good metric)",
            "Correlation in training data may not hold in deployment (distribution shift)",
            "Feature importance ≠ causal importance",
        ],
    },
}
