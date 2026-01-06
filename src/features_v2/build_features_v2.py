import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import time
import pandas as pd
from datetime import datetime

from nba_api.stats.static import players as nba_players, teams as nba_teams
from nba_api.stats.endpoints import playergamelog, commonplayerinfo, leaguedashteamstats
from rapidfuzz import process, fuzz

# -----------------------------
# Config
# -----------------------------
SEASON = "2025-26"  # adjust when needed

# -----------------------------
# Caches
# -----------------------------
PLAYER_ID_CACHE: dict[str, int | None] = {}
PLAYER_INFO_CACHE: dict[int, dict] = {}
PLAYER_STATS_CACHE: dict[tuple[int, int], dict] = {}
TEAM_STATS_DF: pd.DataFrame | None = None
TEAM_NAME_CACHE: dict[str, str] = {}  # raw → canonical TEAM_NAME

# -----------------------------
# Helpers
# -----------------------------
def nba_sleep():
    time.sleep(0.5)


def get_all_players():
    return nba_players.get_players()


def get_all_teams():
    return nba_teams.get_teams()


def fuzzy_match_name(name: str, candidates: list[str], min_score: int = 80):
    if not isinstance(name, str):
        return None, 0
    match = process.extractOne(name, candidates, scorer=fuzz.WRatio)
    if match is None:
        return None, 0
    best, score, _ = match
    if score >= min_score:
        return best, score
    return None, score


def get_player_id(player_name: str) -> int | None:
    if player_name in PLAYER_ID_CACHE:
        return PLAYER_ID_CACHE[player_name]

    all_players = get_all_players()

    # exact
    for p in all_players:
        if p["full_name"].lower() == player_name.lower():
            PLAYER_ID_CACHE[player_name] = p["id"]
            return p["id"]

    # fuzzy
    names = [p["full_name"] for p in all_players]
    best, score = fuzzy_match_name(player_name, names, min_score=80)
    if best:
        matched = next(p for p in all_players if p["full_name"] == best)
        print(f"[MATCH] '{player_name}' → '{matched['full_name']}' (score={score})")
        PLAYER_ID_CACHE[player_name] = matched["id"]
        return matched["id"]

    print(f"[WARN] No player match for '{player_name}'")
    PLAYER_ID_CACHE[player_name] = None
    return None


def get_player_info(player_id: int) -> dict:
    if player_id in PLAYER_INFO_CACHE:
        return PLAYER_INFO_CACHE[player_id]

    try:
        info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        nba_sleep()
        df = info.get_data_frames()[0]
        row = df.iloc[0].to_dict()
        PLAYER_INFO_CACHE[player_id] = row
        return row
    except Exception as e:
        print(f"[ERR] commonplayerinfo failed for {player_id}: {e}")
        PLAYER_INFO_CACHE[player_id] = {}
        return {}


def get_team_stats_df() -> pd.DataFrame:
    """
    NBA removed Pace & Defensive Rating from early-season responses.
    This rebuilds them manually using standard basketball formulas.
    """
    global TEAM_STATS_DF
    if TEAM_STATS_DF is not None:
        return TEAM_STATS_DF

    stats = leaguedashteamstats.LeagueDashTeamStats(
        season=SEASON,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Base"
    )
    nba_sleep()

    df = stats.get_data_frames()[0].copy()

    # Sanity check
    required = ["TEAM_NAME", "FGA", "FTA", "OREB", "TOV", "PTS", "PLUS_MINUS"]
    for col in required:
        if col not in df.columns:
            raise RuntimeError(f"Missing expected column {col}. Columns={df.columns.tolist()}")

    # -------------------------------
    # Compute possessions
    # -------------------------------
    df["POSS"] = (
        df["FGA"] +
        0.44 * df["FTA"] +
        df["TOV"] -
        df["OREB"]
    )

    # -------------------------------
    # Compute opponent points
    # -------------------------------
    df["OPP_PTS"] = df["PTS"] - df["PLUS_MINUS"]

    # Avoid divide by zero
    df["POSS"] = df["POSS"].replace(0, df["POSS"].mean())

    # -------------------------------
    # Compute tempo (PACE)
    # -------------------------------
    df["PACE"] = 48 * df["POSS"] / df["MIN"]

    # -------------------------------
    # Compute defensive rating
    # -------------------------------
    df["DEF_RATING"] = 100 * df["OPP_PTS"] / df["POSS"]

    TEAM_STATS_DF = df
    return df



def map_raw_team_to_nba(raw_team_name: str) -> str | None:
    """
    Map Odds API team name to NBA API TEAM_NAME using fuzzy match.
    """
    if raw_team_name in TEAM_NAME_CACHE:
        return TEAM_NAME_CACHE[raw_team_name]

    df = get_team_stats_df()
    team_names = df["TEAM_NAME"].tolist()
    best, score = fuzzy_match_name(raw_team_name, team_names, min_score=80)
    if best:
        TEAM_NAME_CACHE[raw_team_name] = best
        return best

    print(f"[WARN] Could not map team name '{raw_team_name}'")
    TEAM_NAME_CACHE[raw_team_name] = None
    return None


def get_last_n_stats(player_id: int, n: int = 10) -> dict:
    """
    Returns mean & std for last n games for pts, reb, ast, fg3, minutes.
    Cached by (player_id, n).
    """
    key = (player_id, n)
    if key in PLAYER_STATS_CACHE:
        return PLAYER_STATS_CACHE[key]

    try:
        logs = playergamelog.PlayerGameLog(player_id=player_id, season=SEASON)
        nba_sleep()
        df = logs.get_data_frames()[0].head(n)
        stats = {
            "pts_mean": df["PTS"].mean(),
            "pts_std": df["PTS"].std(ddof=1),
            "reb_mean": df["REB"].mean(),
            "reb_std": df["REB"].std(ddof=1),
            "ast_mean": df["AST"].mean(),
            "ast_std": df["AST"].std(ddof=1),
            "fg3_mean": df["FG3M"].mean(),
            "fg3_std": df["FG3M"].std(ddof=1),
            "min_mean": df["MIN"].mean(),
            "min_std": df["MIN"].std(ddof=1),
        }
    except Exception as e:
        print(f"[ERR] Game logs failed for player_id={player_id}: {e}")
        stats = {
            "pts_mean": None, "pts_std": None,
            "reb_mean": None, "reb_std": None,
            "ast_mean": None, "ast_std": None,
            "fg3_mean": None, "fg3_std": None,
            "min_mean": None, "min_std": None,
        }

    PLAYER_STATS_CACHE[key] = stats
    return stats


def build_features_v2(df_props: pd.DataFrame) -> pd.DataFrame:
    df_props = df_props.copy()

    team_stats = get_team_stats_df()
    league_avg_pace = team_stats["PACE"].mean()
    league_avg_defrtg = team_stats["DEF_RATING"].mean()

    rows = []

    unique_players = df_props["player_name"].unique()
    print(f"[INFO V2] Unique players: {len(unique_players)}")

    # Pre-resolve player IDs
    for p in unique_players:
        get_player_id(p)

    for _, row in df_props.iterrows():
        player_name = row["player_name"]
        pid = PLAYER_ID_CACHE.get(player_name)
        if pid is None:
            continue

        # Player team info
        info = get_player_info(pid)
        player_team_abbrev = info.get("TEAM_ABBREVIATION")
        player_team_name = info.get("TEAM_NAME")  # NBA API canonical
        if not player_team_name:
            # Fallback: infer from home/away via fuzzy
            player_team_name = None

                # Determine opponent using REAL NBA team, not sportsbook team guess
        home_raw = row["home_team"]
        away_raw = row["away_team"]

        # Map sportsbook team names → official NBA team names
        home_team_name = map_raw_team_to_nba(home_raw)
        away_team_name = map_raw_team_to_nba(away_raw)

        # First: make sure we have a mapped NBA team from API
        # Replace NBA API "TEAM_NAME" (often full) with fuzzy-matched canonical name
        if player_team_name:
            matched_real_team, score = fuzzy_match_name(
                player_team_name,
                [home_team_name, away_team_name],
                min_score=50
            )
            if matched_real_team:
                player_team_name = matched_real_team

        # Now determine correct opponent:
        if player_team_name == home_team_name:
            opp_team_name = away_team_name
        elif player_team_name == away_team_name:
            opp_team_name = home_team_name
        else:
            # If the player's real team is not home or away,
            # pick the opponent as whichever team is NOT closest to the player's real team.
            # This fixes mismatches like "Charlotte Hornets" vs "LA Clippers"
            matched_home, home_score = fuzzy_match_name(player_team_name, [home_team_name], min_score=50)
            matched_away, away_score = fuzzy_match_name(player_team_name, [away_team_name], min_score=50)

            if home_score > away_score:
                player_team_name = home_team_name
                opp_team_name = away_team_name
            else:
                player_team_name = away_team_name
                opp_team_name = home_team_name

        # Get pace & defense for team and opp
        team_row = team_stats[team_stats["TEAM_NAME"] == player_team_name] if player_team_name else pd.DataFrame()
        opp_row = team_stats[team_stats["TEAM_NAME"] == opp_team_name] if opp_team_name else pd.DataFrame()

        if not team_row.empty:
            team_pace = float(team_row.iloc[0]["PACE"])
        else:
            team_pace = league_avg_pace

        if not opp_row.empty:
            opp_pace = float(opp_row.iloc[0]["PACE"])
            opp_defrtg = float(opp_row.iloc[0]["DEF_RATING"])
        else:
            opp_pace = league_avg_pace
            opp_defrtg = league_avg_defrtg

        pace_factor = (team_pace + opp_pace) / (2.0 * league_avg_pace)
        # Lower DEF_RATING = better defense, so <1 means harder matchup
        defense_factor = league_avg_defrtg / opp_defrtg if opp_defrtg else 1.0

        # Rolling stats
        last10 = get_last_n_stats(pid, n=10)
        last5 = get_last_n_stats(pid, n=5)

        # Per-minute rates (last10)
        min_mean10 = last10["min_mean"] or 0
        if min_mean10 > 0:
            pts_per_min = (last10["pts_mean"] or 0) / min_mean10
            reb_per_min = (last10["reb_mean"] or 0) / min_mean10
            ast_per_min = (last10["ast_mean"] or 0) / min_mean10
            fg3_per_min = (last10["fg3_mean"] or 0) / min_mean10
        else:
            pts_per_min = reb_per_min = ast_per_min = fg3_per_min = 0.0

        feature_row = row.to_dict()
        feature_row.update({
            # base rolling stats
            "pts_last10_mean": last10["pts_mean"],
            "pts_last10_std": last10["pts_std"],
            "reb_last10_mean": last10["reb_mean"],
            "reb_last10_std": last10["reb_std"],
            "ast_last10_mean": last10["ast_mean"],
            "ast_last10_std": last10["ast_std"],
            "fg3_last10_mean": last10["fg3_mean"],
            "fg3_last10_std": last10["fg3_std"],
            "min_last10_mean": last10["min_mean"],
            "min_last10_std": last10["min_std"],

            "pts_last5_mean": last5["pts_mean"],
            "reb_last5_mean": last5["reb_mean"],
            "ast_last5_mean": last5["ast_mean"],
            "fg3_last5_mean": last5["fg3_mean"],
            "min_last5_mean": last5["min_mean"],

            # per-minute
            "pts_per_min_last10": pts_per_min,
            "reb_per_min_last10": reb_per_min,
            "ast_per_min_last10": ast_per_min,
            "fg3_per_min_last10": fg3_per_min,

            # pace/defense context
            "player_team_name": player_team_name,
            "opp_team_name": opp_team_name,
            "team_pace": team_pace,
            "opp_pace": opp_pace,
            "league_avg_pace": league_avg_pace,
            "opp_defrtg": opp_defrtg,
            "league_avg_defrtg": league_avg_defrtg,
            "pace_factor": pace_factor,
            "defense_factor": defense_factor,
        })

        rows.append(feature_row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).resolve().parents[2]  # src/features_v2 -> project root
    props_path = PROJECT_ROOT / "src" / "data" / "processed" / "props_today.csv"
    df_props = pd.read_csv(props_path)

    print("[INFO V2] Building V2 features...")
    df_feat_v2 = build_features_v2(df_props)

    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[2]  # src/features_v2 -> project root
    processed_dir = PROJECT_ROOT / "src" / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    out_path = processed_dir / "props_features_v2.csv"
    df_feat_v2.to_csv(out_path, index=False)
    print(f"[INFO V2] Saved V2 features → {out_path}")

    df_feat_v2.to_csv(out_path, index=False)

    print(f"[INFO V2] Features built: {len(df_feat_v2)} props")
    print(f"[INFO V2] Saved → {out_path}")
    print(df_feat_v2.head())
