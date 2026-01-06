import numpy as np

def american_to_implied_prob(odds: float) -> float:
    """
    Convert American odds to implied probability (no vig removed).
    Returns a float between 0 and 1.
    """
    if odds is None or np.isnan(odds):
        return np.nan

    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return (-odds) / (-odds + 100.0)


def american_to_decimal(odds: float) -> float:
    """
    Convert American odds to decimal odds.
    """
    if odds is None or np.isnan(odds):
        return np.nan

    if odds > 0:
        return 1.0 + odds / 100.0
    else:
        return 1.0 + 100.0 / -odds


def expected_value_per_unit(odds: float, win_prob: float, stake: float = 1.0) -> float:
    """
    Expected profit per unit staked given American odds and win probability.
    """
    if odds is None or np.isnan(odds) or win_prob is None or np.isnan(win_prob):
        return np.nan

    # Payout per 1 unit if it wins
    if odds > 0:
        payout = stake * (odds / 100.0)
    else:
        payout = stake * (100.0 / -odds)

    lose_prob = 1.0 - win_prob
    ev = win_prob * payout - lose_prob * stake
    return ev
