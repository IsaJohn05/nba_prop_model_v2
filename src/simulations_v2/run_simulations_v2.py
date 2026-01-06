import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import numpy as np
import pandas as pd
from datetime import datetime

from src.utils.math_helpers import american_to_implied_prob, expected_value_per_unit


def adjust_mean(base_mean, pace_factor, defense_factor):
    if base_mean is None or np.isnan(base_mean):
        return np.nan
    return float(base_mean) * float(pace_factor) * float(defense_factor)


def nb_params_from_mean_var(mean, var):
    """
    Given mean and variance, compute Negative Binomial (n, p) parameters.
    If var <= mean, return None to signal Poisson/Normal fallback.
    """
    if mean <= 0 or var <= mean:
        return None, None
    # For NB(n, p):
    # p = mean / var
    # n = mean^2 / (var - mean)
    p = mean / var
    n = mean * mean / (var - mean)
    return n, p


def simulate_points_normal(mean, std, line, n_sims=10000):
    if np.isnan(mean) or np.isnan(line) or mean <= 0 or std <= 0:
        return np.nan, np.nan
    samples = np.random.normal(loc=mean, scale=std, size=n_sims)
    samples = np.clip(samples, 0, None)
    prob_over = float((samples > line).mean())
    prob_under = float((samples < line).mean())
    return prob_over, prob_under


def simulate_poisson(mean, line, n_sims=10000):
    if np.isnan(mean) or np.isnan(line) or mean <= 0:
        return np.nan, np.nan
    samples = np.random.poisson(lam=mean, size=n_sims)
    prob_over = float((samples > line).mean())
    prob_under = float((samples < line).mean())
    return prob_over, prob_under


def simulate_nb_or_poisson(mean, var, line, n_sims=10000):
    if np.isnan(mean) or np.isnan(line) or mean <= 0:
        return np.nan, np.nan

    n, p = nb_params_from_mean_var(mean, var)
    if n is None or p is None or p <= 0 or p >= 1:
        # fallback to Poisson
        return simulate_poisson(mean, line, n_sims=n_sims)

    # numpy negative_binomial uses params (n, p)
    samples = np.random.negative_binomial(n, p, size=n_sims)
    samples = np.clip(samples, 0, None)
    prob_over = float((samples > line).mean())
    prob_under = float((samples < line).mean())
    return prob_over, prob_under


def get_adjusted_mean_and_var(row):
    market = str(row["market"]).lower()
    pace_factor = row.get("pace_factor", 1.0)
    defense_factor = row.get("defense_factor", 1.0)

    if market == "points":
        base_mean = row.get("pts_last10_mean", np.nan)
        base_std = row.get("pts_last10_std", np.nan)
    elif market == "assists":
        base_mean = row.get("ast_last10_mean", np.nan)
        base_std = row.get("ast_last10_std", np.nan)
    elif market == "rebounds":
        base_mean = row.get("reb_last10_mean", np.nan)
        base_std = row.get("reb_last10_std", np.nan)
    elif market in ("threes_made", "three-pointers-made", "threes"):
        base_mean = row.get("fg3_last10_mean", np.nan)
        base_std = row.get("fg3_last10_std", np.nan)
    else:
        base_mean = np.nan
        base_std = np.nan

    adj_mean = adjust_mean(base_mean, pace_factor, defense_factor)
    if np.isnan(base_std):
        adj_var = np.nan
    else:
        # naive: assume var scales similar to mean
        adj_var = (base_std ** 2) * (pace_factor * defense_factor)

    return adj_mean, adj_var


def run_simulations_v2(df_features: pd.DataFrame, n_sims: int = 10000) -> pd.DataFrame:
    rows = []

    for _, row in df_features.iterrows():
        market = row["market"]
        side = row["side"]
        line = row["line"]
        odds = row["odds"]

        mean, var = get_adjusted_mean_and_var(row)

        if np.isnan(mean) or np.isnan(line):
            model_prob = np.nan
        else:
            if market == "points":
                # Normal
                std = np.sqrt(var) if var and not np.isnan(var) and var > 0 else np.sqrt(mean)
                p_over, p_under = simulate_points_normal(mean, std, line, n_sims=n_sims)
            elif market == "assists" or market == "rebounds":
                # NB/Poisson mixture
                # If var is NaN, approximate var ~ mean + 1
                if np.isnan(var) or var <= 0:
                    var_used = mean + 1.0
                else:
                    var_used = var
                p_over, p_under = simulate_nb_or_poisson(mean, var_used, line, n_sims=n_sims)
            else:  # threes
                p_over, p_under = simulate_poisson(mean, line, n_sims=n_sims)

            model_prob = p_over if side == "over" else p_under

        implied_prob = american_to_implied_prob(odds)
        edge = model_prob - implied_prob if (model_prob == model_prob and implied_prob == implied_prob) else np.nan
        ev = expected_value_per_unit(odds, model_prob) if model_prob == model_prob else np.nan

        # Confidence: combine prob, edge magnitude, minutes
        min10 = row.get("min_last10_mean", np.nan)
        prob_component = model_prob if model_prob == model_prob else 0.0
        edge_component = abs(edge) if edge == edge else 0.0
        minutes_component = min(min10 / 36.0, 1.0) if min10 == min10 else 0.0

        confidence = float((prob_component + edge_component + minutes_component) / 3.0)

        out = row.to_dict()
        out.update({
            "adj_mean": mean,
            "adj_var": var,
            "model_prob": model_prob,
            "implied_prob": implied_prob,
            "edge": edge,
            "ev_per_unit": ev,
            "confidence": confidence,
            "n_sims": n_sims,
        })
        rows.append(out)

    return pd.DataFrame(rows)


def save_sim_results_v2(df: pd.DataFrame):
    os.makedirs("data/results/v2", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    path_full = f"data/results/v2/sim_results_v2_{ts}.csv"
    df.to_csv(path_full, index=False)
    print(f"[INFO V2] Saved sim results → {path_full}")

    df.to_csv("data/processed/props_with_sims_today_v2.csv", index=False)
    print("[INFO V2] Saved props_with_sims_today_v2.csv")


if __name__ == "__main__":
    features_path = "data/processed/props_features_today_v2.csv"
    if not os.path.exists(features_path):
        raise RuntimeError("Missing props_features_today_v2.csv – run V2 feature builder first.")

    df_features_v2 = pd.read_csv(features_path)
    print(f"[INFO V2] Loaded {len(df_features_v2)} props with V2 features.")

    df_sims_v2 = run_simulations_v2(df_features_v2, n_sims=10000)
    print(f"[INFO V2] Simulated {len(df_sims_v2)} props.")

    save_sim_results_v2(df_sims_v2)
    print(df_sims_v2.head())
