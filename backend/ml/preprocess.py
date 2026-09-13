"""
Sentinel UEBA - Preprocessing Pipeline

Single reproducible pipeline fit ONLY on training data.
Includes: numeric conversion, imputation, log transform, one-hot encoding, standardization.
"""
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.base import BaseEstimator, TransformerMixin
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

# Feature groups
NUMERIC_FEATURES = [
    "login_count_7d", "failed_login_rate", "off_hours_ratio", "weekend_ratio",
    "sensitive_file_access", "external_transfer_mb", "cloud_upload_mb", "usb_event_count",
    "privileged_access_count", "privilege_change_count_30d",
    "email_external_ratio", "session_duration_mean_min", "access_velocity_per_hour",
    "remote_session_ratio", "unusual_location_score", "new_device_score",
    "peer_deviation_score", "dormant_account_days",
    "after_hours_sensitive_access", "asset_criticality",
]

CATEGORICAL_FEATURES = ["department", "role", "account_type"]

LOG_TRANSFORM_FEATURES = [
    "login_count_7d", "sensitive_file_access", "external_transfer_mb",
    "cloud_upload_mb", "usb_event_count", "privileged_access_count",
    "session_duration_mean_min", "access_velocity_per_hour",
]

DROP_COLUMNS = ["event_id", "user_id"]


class LogTransformer(BaseEstimator, TransformerMixin):
    """Apply log1p to strongly skewed nonnegative features."""

    def __init__(self, columns=None):
        self.columns = columns or []
        self._column_indices = []

    def fit(self, X, y=None):
        if hasattr(X, 'columns'):
            self._column_indices = [i for i, c in enumerate(X.columns) if c in self.columns]
        return self

    def transform(self, X):
        if hasattr(X, 'copy'):
            X = X.copy()
        else:
            X = X.copy()
        if hasattr(X, 'columns'):
            for col in self.columns:
                if col in X.columns:
                    X[col] = np.log1p(X[col].clip(lower=0))
        elif isinstance(X, np.ndarray) and self._column_indices:
            for idx in self._column_indices:
                X[:, idx] = np.log1p(np.clip(X[:, idx], 0, None))
        return X


def build_preprocessor() -> ColumnTransformer:
    """Build the preprocessing ColumnTransformer."""
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("log", LogTransformer(columns=LOG_TRANSFORM_FEATURES)),
        ("scaler", StandardScaler()),
    ])

    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )

    return preprocessor


def validate_schema(df: pd.DataFrame) -> list:
    """Validate dataset schema before training."""
    errors = []

    required = NUMERIC_FEATURES + CATEGORICAL_FEATURES + ["insider_threat"]
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    if "event_id" in df.columns and df["event_id"].duplicated().any():
        errors.append("Duplicate event_id found")

    if "insider_threat" in df.columns:
        if not df["insider_threat"].isin([0, 1]).all():
            errors.append("Target column must contain only 0 or 1")

    for col in NUMERIC_FEATURES:
        if col in df.columns:
            non_numeric = pd.to_numeric(df[col], errors="coerce").isna().sum()
            if non_numeric > 0:
                errors.append(f"Column {col} has {non_numeric} non-numeric values")

    return errors


def prepare_features(df: pd.DataFrame, include_target: bool = True):
    """Prepare feature matrix and optionally target vector."""
    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    X = df[feature_cols].copy()

    if include_target and "insider_threat" in df.columns:
        y = df["insider_threat"].values
        return X, y

    return X


def get_feature_names(preprocessor: ColumnTransformer) -> list:
    """Get feature names after preprocessing."""
    feature_names = []

    # Numeric features (log-transformed + scaled, same names)
    feature_names.extend(NUMERIC_FEATURES)

    # Categorical features (one-hot encoded)
    cat_transformer = preprocessor.named_transformers_["cat"]
    encoder = cat_transformer.named_steps["encoder"]
    cat_feature_names = encoder.get_feature_names_out(CATEGORICAL_FEATURES)
    feature_names.extend(cat_feature_names.tolist())

    return feature_names
