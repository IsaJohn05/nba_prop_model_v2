import sys
import os
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import json
import pandas as pd
from datetime import datetime

MIN_PROB_V2 = 0.55
MIN_EDGE_V2 = 0.03
MIN_EV_V2   = 0.02
MIN_CONF_V2 = 0.5
MIN_MINUTES_V2 = 15


def filter_props_v2(df: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (df["model_prob"] >= MIN_PROB_V2) &
        (df["edge"] >= MIN_EDGE_V2) &
        (df["ev_per_unit"] >= MIN_EV_V2) &
        (df.get("confidence", 0) >= MIN_CONF_V2) &
        (df.get("min_last10_mean", 0) >= MIN_MINUTES_V2)
    )

    out = df[mask].copy()
    # Deduplicate by (player, market, side)
    out = out.sort_values(["player_name", "market", "side", "ev_per_unit"], ascending=False)
    out = out.drop_duplicates(subset=["player_name", "market", "side"], keep="first")
    return out


def pick_card_v2(df: pd.DataFrame) -> pd.DataFrame:
    overs = df[df["side"] == "over"].sort_values(["confidence", "ev_per_unit"], ascending=False)
    unders = df[df["side"] == "under"].sort_values(["confidence", "ev_per_unit"], ascending=False)

    selected_overs = overs.head(12)
    selected_unders = unders.head(6)

    if len(selected_overs) < 10:
        selected_overs = overs.head(10)
    if len(selected_unders) < 3:
        selected_unders = unders.head(3)

    final = pd.concat([selected_overs, selected_unders])
    final = final.sort_values(["confidence", "ev_per_unit"], ascending=False)
    return final


def save_card_v2(df: pd.DataFrame):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]  # src/selection_v2 -> project root

    results_dir = PROJECT_ROOT / "src" / "data" / "results" / "v2"
    results_dir.mkdir(parents=True, exist_ok=True)

    processed_dir = PROJECT_ROOT / "src" / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    experiments_dir = PROJECT_ROOT / "src" / "experiments" / "v2"
    experiments_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    card_path = results_dir / f"final_card_v2_{ts}.csv"
    df.to_csv(card_path, index=False)
    print(f"[INFO V2] Saved V2 final card → {card_path}")

    final_today_path = processed_dir / "final_card_today_v2.csv"
    df.to_csv(final_today_path, index=False)
    print(f"[INFO V2] Saved final_card_today_v2.csv → {final_today_path}")

    # Save experiment summary
    metrics = {
        "timestamp": ts,
        "num_picks": int(len(df)),
        "num_overs": int((df["side"] == "over").sum()),
        "num_unders": int((df["side"] == "under").sum()),
        "avg_ev": float(df["ev_per_unit"].mean()) if len(df) > 0 else 0.0,
        "avg_confidence": float(df["confidence"].mean()) if "confidence" in df.columns and len(df) > 0 else 0.0,
    }
    metrics_path = experiments_dir / f"metrics_{ts}.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[INFO V2] Saved metrics → {metrics_path}")


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[2]  # src/selection_v2 -> project root
    sims_path = PROJECT_ROOT / "src" / "data" / "processed" / "props_with_sims_today_v2.csv"

    if not sims_path.exists():
        raise RuntimeError(f"Run V2 simulations first (run_simulations_v2.py). Missing: {sims_path}")

    df_sims_v2 = pd.read_csv(sims_path)
    print(f"[INFO V2] Loaded {len(df_sims_v2)} simulated props (V2).")

    filtered = filter_props_v2(df_sims_v2)
    print(f"[INFO V2] Filtered to {len(filtered)} props after V2 rules.")

    final_card_v2 = pick_card_v2(filtered)
    print(f"[INFO V2] Selected {len(final_card_v2)} final V2 picks.")

    save_card_v2(final_card_v2)

    print(
        final_card_v2[
            ["player_name", "market", "side", "line", "odds", "model_prob", "edge", "ev_per_unit", "confidence"]
        ].head(20)
    )
