"""
Sentinel UEBA - Training Script

Trains models, evaluates, compares, and saves the best pipeline.
Run: python ml/train.py
"""
import sys
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    average_precision_score, precision_recall_curve, f1_score,
    precision_score, recall_score,
)

from ml.preprocess import (
    build_preprocessor, validate_schema, prepare_features,
    get_feature_names, NUMERIC_FEATURES, CATEGORICAL_FEATURES,
)

ARTIFACTS_DIR = Path("ml/artifacts")
MODEL_VERSION = "sentinel-ueba-v1"
SEED = 42


def load_data():
    """Load training and test data."""
    train_path = ARTIFACTS_DIR / "sentinel_ueba_processed_train.csv"
    test_path = ARTIFACTS_DIR / "sentinel_ueba_processed_test.csv"

    if not train_path.exists() or not test_path.exists():
        print("Dataset not found. Generating...")
        from ml.generate_dataset import generate_dataset
        generate_dataset(str(ARTIFACTS_DIR))

    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    return train, test


def train_and_evaluate(train_df, test_df):
    """Train models and evaluate."""
    # Validate schema
    errors = validate_schema(train_df)
    if errors:
        print("Schema validation errors:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    print("✓ Schema validation passed")

    # Prepare features
    X_train, y_train = prepare_features(train_df)
    X_test, y_test = prepare_features(test_df)

    print(f"  Training samples: {len(X_train)} (threat rate: {y_train.mean():.2%})")
    print(f"  Test samples:     {len(X_test)} (threat rate: {y_test.mean():.2%})")

    # Build preprocessor
    preprocessor = build_preprocessor()

    # Define models
    models = {
        "Logistic Regression": LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=SEED,
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            max_depth=10,
            random_state=SEED,
            n_jobs=-1,
        ),
    }

    results = []

    for name, model in models.items():
        print(f"\nTraining {name}...")

        # Fit preprocessor on train only
        X_train_processed = preprocessor.fit_transform(X_train)
        X_test_processed = preprocessor.transform(X_test)

        # Train model
        model.fit(X_train_processed, y_train)

        # Predict
        y_pred = model.predict(X_test_processed)
        y_proba = model.predict_proba(X_test_processed)[:, 1]

        # Metrics
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        roc_auc = roc_auc_score(y_test, y_proba)
        pr_auc = average_precision_score(y_test, y_proba)
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

        result = {
            "model": name,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "false_positive_rate": round(fpr, 4),
            "confusion_matrix": cm.tolist(),
        }
        results.append(result)

        print(f"  Precision:    {precision:.4f}")
        print(f"  Recall:       {recall:.4f}")
        print(f"  F1:           {f1:.4f}")
        print(f"  ROC-AUC:      {roc_auc:.4f}")
        print(f"  PR-AUC:       {pr_auc:.4f}")
        print(f"  FPR:          {fpr:.4f}")
        print(f"  Confusion:    {cm.tolist()}")

    # Select best model based on F1 (balance of precision/recall for security)
    best = max(results, key=lambda r: r["f1"])
    best_name = best["model"]
    print(f"\n✓ Best model: {best_name} (F1={best['f1']:.4f})")

    # Retrain best model on full train set and save
    best_model = models[best_name]
    X_train_processed = preprocessor.fit_transform(X_train)
    best_model.fit(X_train_processed, y_train)

    # Get feature names and importances
    feature_names = get_feature_names(preprocessor)

    if hasattr(best_model, "feature_importances_"):
        importances = best_model.feature_importances_
    elif hasattr(best_model, "coef_"):
        importances = np.abs(best_model.coef_[0])
    else:
        importances = np.zeros(len(feature_names))

    # Normalize importances
    if importances.max() > 0:
        importances = importances / importances.max()

    feature_importance = sorted(
        zip(feature_names[:len(importances)], importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )[:20]

    # Save pipeline
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    pipeline = {
        "preprocessor": preprocessor,
        "model": best_model,
        "model_name": best_name,
        "model_version": MODEL_VERSION,
        "feature_names": feature_names,
        "feature_importance": feature_importance,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "training_samples": len(X_train),
        "evaluation": best,
        "all_results": results,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
    }

    artifact_path = ARTIFACTS_DIR / "sentinel_ueba_pipeline.joblib"
    joblib.dump(pipeline, artifact_path)

    # Save metrics
    metrics_path = ARTIFACTS_DIR / "model_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump({
            "model_version": MODEL_VERSION,
            "model_name": best_name,
            "training_date": pipeline["training_date"],
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "feature_count": len(feature_names),
            "evaluation": best,
            "all_results": results,
            "feature_importance": feature_importance,
        }, f, indent=2)

    print(f"\n✓ Pipeline saved: {artifact_path}")
    print(f"✓ Metrics saved:  {metrics_path}")

    return pipeline, results


if __name__ == "__main__":
    print("=" * 60)
    print("SENTINEL UEBA - Model Training")
    print("=" * 60)
    print()

    train_df, test_df = load_data()
    pipeline, results = train_and_evaluate(train_df, test_df)

    print("\n" + "=" * 60)
    print("MODEL COMPARISON REPORT")
    print("=" * 60)
    print(f"\n{'Model':<25} {'Precision':>10} {'Recall':>10} {'F1':>10} {'ROC-AUC':>10} {'PR-AUC':>10} {'FPR':>10}")
    print("-" * 85)
    for r in results:
        print(f"{r['model']:<25} {r['precision']:>10.4f} {r['recall']:>10.4f} {r['f1']:>10.4f} {r['roc_auc']:>10.4f} {r['pr_auc']:>10.4f} {r['false_positive_rate']:>10.4f}")

    print(f"\nFinal model: {pipeline['model_name']} v{MODEL_VERSION}")
    print("NOTE: These are validation/test metrics on SYNTHETIC data.")
    print("      They do NOT represent real-world security guarantees.")
