"""Candidate model training for regression and classification."""
from __future__ import annotations

import logging
from typing import Any
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)


def get_candidate_estimators(problem_type: str, random_state: int = 42) -> dict[str, Any]:
    """Returns candidate estimators according to problem type."""
    p_type = problem_type.lower()
    if p_type == "regression":
        return {
            "LinearRegression": LinearRegression(),
            "RandomForestRegressor": RandomForestRegressor(
                n_estimators=50, random_state=random_state, n_jobs=-1
            ),
            "GradientBoostingRegressor": GradientBoostingRegressor(
                n_estimators=50, random_state=random_state
            ),
        }
    elif p_type == "classification":
        return {
            "LogisticRegression": LogisticRegression(
                max_iter=500, random_state=random_state
            ),
            "RandomForestClassifier": RandomForestClassifier(
                n_estimators=50, random_state=random_state, n_jobs=-1
            ),
            "GradientBoostingClassifier": GradientBoostingClassifier(
                n_estimators=50, random_state=random_state
            ),
        }
    else:
        raise ValueError(f"Unknown problem type: {problem_type}")


def train_candidate_models(
    preprocessor: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    problem_type: str,
    random_state: int = 42,
) -> dict[str, Pipeline]:
    """Trains all candidate estimators bundled into an end-to-end Pipeline with preprocessing."""
    candidates = get_candidate_estimators(problem_type, random_state=random_state)
    trained_pipelines: dict[str, Pipeline] = {}

    for name, estimator in candidates.items():
        try:
            # Build end-to-end pipeline
            pipe = Pipeline([
                ("preprocessor", clone(preprocessor)),
                ("estimator", estimator),
            ])
            pipe.fit(X_train, y_train)
            trained_pipelines[name] = pipe
        except Exception as e:
            logger.warning("Failed to train candidate model %s: %s", name, e)

    if not trained_pipelines:
        raise RuntimeError("Failed to train any candidate machine learning models.")

    return trained_pipelines
