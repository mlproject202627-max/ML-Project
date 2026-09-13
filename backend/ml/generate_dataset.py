"""
Sentinel UEBA - Synthetic Dataset Generator

Generates realistic synthetic behavioural data for training the UEBA model.
This is EDUCATIONAL DATA ONLY - not real security events.

Target column: insider_threat (0 = normal, 1 = synthetic threat-like window)
"""
import numpy as np
import pandas as pd
from pathlib import Path

NUM_SAMPLES = 10000
THREAT_RATIO = 0.08  # ~8% positive class (realistic for insider threats)
SEED = 42

DEPARTMENTS = ["Engineering", "Finance", "IT Ops", "Sales", "HR", "Legal", "Product", "Support", "Executive", "Contract"]
ROLES = ["Engineer", "Analyst", "Manager", "Director", "Admin", "Consultant", "Lead", "Specialist"]
ACCOUNT_TYPES = ["standard", "privileged", "service", "contractor"]

COLUMNS = [
    "event_id", "user_id", "department", "role", "account_type",
    "login_count_7d", "failed_login_rate", "off_hours_ratio", "weekend_ratio",
    "sensitive_file_access", "external_transfer_mb", "cloud_upload_mb", "usb_event_count",
    "privileged_access_count", "privilege_change_count_30d",
    "email_external_ratio", "session_duration_mean_min", "access_velocity_per_hour",
    "remote_session_ratio", "unusual_location_score", "new_device_score",
    "peer_deviation_score", "dormant_account_days",
    "after_hours_sensitive_access", "asset_criticality",
    "insider_threat",
]


def generate_normal(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate normal behavioural windows."""
    data = {
        "event_id": [f"EV-{i:06d}" for i in range(n)],
        "user_id": [f"U-{rng.integers(1000, 9999):04d}" for _ in range(n)],
        "department": rng.choice(DEPARTMENTS, n),
        "role": rng.choice(ROLES, n),
        "account_type": rng.choice(ACCOUNT_TYPES, n, p=[0.6, 0.15, 0.15, 0.1]),
        "login_count_7d": rng.poisson(15, n).clip(1, 60),
        "failed_login_rate": rng.beta(2, 20, n).round(4),
        "off_hours_ratio": rng.beta(2, 8, n).round(4),
        "weekend_ratio": rng.beta(2, 10, n).round(4),
        "sensitive_file_access": rng.poisson(2, n).clip(0, 20),
        "external_transfer_mb": rng.exponential(5, n).round(2).clip(0, 100),
        "cloud_upload_mb": rng.exponential(3, n).round(2).clip(0, 50),
        "usb_event_count": rng.poisson(0.5, n).clip(0, 10),
        "privileged_access_count": rng.poisson(3, n).clip(0, 30),
        "privilege_change_count_30d": rng.poisson(0.2, n).clip(0, 5),
        "email_external_ratio": rng.beta(3, 15, n).round(4),
        "session_duration_mean_min": rng.normal(45, 15, n).clip(5, 180).round(1),
        "access_velocity_per_hour": rng.poisson(8, n).clip(1, 40),
        "remote_session_ratio": rng.beta(3, 7, n).round(4),
        "unusual_location_score": rng.beta(2, 15, n).round(4),
        "new_device_score": rng.beta(2, 12, n).round(4),
        "peer_deviation_score": rng.beta(2, 12, n).round(4),
        "dormant_account_days": np.zeros(n, dtype=int),
        "after_hours_sensitive_access": rng.poisson(0.3, n).clip(0, 5),
        "asset_criticality": rng.choice([1, 2, 3, 4, 5], n, p=[0.3, 0.3, 0.2, 0.15, 0.05]),
        "insider_threat": np.zeros(n, dtype=int),
    }
    return pd.DataFrame(data)


def generate_threat(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate threat-like behavioural windows with elevated signals."""
    data = {
        "event_id": [f"EV-{NUM_SAMPLES + i:06d}" for i in range(n)],
        "user_id": [f"U-{rng.integers(1000, 9999):04d}" for _ in range(n)],
        "department": rng.choice(DEPARTMENTS, n),
        "role": rng.choice(ROLES, n),
        "account_type": rng.choice(ACCOUNT_TYPES, n, p=[0.4, 0.3, 0.2, 0.1]),
        "login_count_7d": rng.poisson(30, n).clip(5, 120),
        "failed_login_rate": rng.beta(6, 10, n).round(4),
        "off_hours_ratio": rng.beta(8, 3, n).round(4),
        "weekend_ratio": rng.beta(6, 4, n).round(4),
        "sensitive_file_access": rng.poisson(12, n).clip(2, 60),
        "external_transfer_mb": rng.exponential(80, n).round(2).clip(5, 500),
        "cloud_upload_mb": rng.exponential(40, n).round(2).clip(2, 200),
        "usb_event_count": rng.poisson(4, n).clip(0, 20),
        "privileged_access_count": rng.poisson(15, n).clip(2, 60),
        "privilege_change_count_30d": rng.poisson(3, n).clip(0, 15),
        "email_external_ratio": rng.beta(8, 5, n).round(4),
        "session_duration_mean_min": rng.normal(90, 30, n).clip(10, 300).round(1),
        "access_velocity_per_hour": rng.poisson(25, n).clip(3, 80),
        "remote_session_ratio": rng.beta(7, 3, n).round(4),
        "unusual_location_score": rng.beta(8, 3, n).round(4),
        "new_device_score": rng.beta(7, 3, n).round(4),
        "peer_deviation_score": rng.beta(8, 2, n).round(4),
        "dormant_account_days": rng.choice([0, 0, 0, 30, 60, 90, 120], n),
        "after_hours_sensitive_access": rng.poisson(5, n).clip(1, 20),
        "asset_criticality": rng.choice([1, 2, 3, 4, 5], n, p=[0.1, 0.15, 0.25, 0.3, 0.2]),
        "insider_threat": np.ones(n, dtype=int),
    }
    return pd.DataFrame(data)


def generate_dataset(output_dir: str = "ml/artifacts"):
    """Generate train and test datasets."""
    rng = np.random.default_rng(SEED)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    n_threat = int(NUM_SAMPLES * THREAT_RATIO)
    n_normal = NUM_SAMPLES - n_threat

    normal = generate_normal(n_normal, rng)
    threat = generate_threat(n_threat, rng)

    full = pd.concat([normal, threat], ignore_index=True)
    full = full.sample(frac=1, random_state=SEED).reset_index(drop=True)

    # Split: 80% train, 20% test
    split_idx = int(len(full) * 0.8)
    train = full.iloc[:split_idx].reset_index(drop=True)
    test = full.iloc[split_idx:].reset_index(drop=True)

    train.to_csv(output_path / "sentinel_ueba_processed_train.csv", index=False)
    test.to_csv(output_path / "sentinel_ueba_processed_test.csv", index=False)
    full.to_csv(output_path / "sentinel_ueba_synthetic_raw.csv", index=False)

    print(f"Dataset generated:")
    print(f"  Total:    {len(full)} samples")
    print(f"  Train:    {len(train)} samples ({train['insider_threat'].mean():.1%} threat)")
    print(f"  Test:     {len(test)} samples ({test['insider_threat'].mean():.1%} threat)")
    print(f"  Output:   {output_path}")

    return train, test


if __name__ == "__main__":
    generate_dataset()
