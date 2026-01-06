"""
run_pipeline_v2.py

Runs the NBA Player Prop Model v2 pipeline in order using your current folder structure.

Pipeline order:
1) src/data/fetch_odds.py
2) src/data/clean_odds.py
3) src/features_v2/build_features_v2.py
4) src/simulations_v2/run_simulations_v2.py
5) src/selection_v2/build_portfolio_v2.py
6) src/graphics/build_excel_card_v2.py
"""

from __future__ import annotations

import argparse
import os
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Step:
    name: str
    script: Path


def try_load_dotenv() -> None:
    """load .env if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass


def require_files(steps: Iterable[Step]) -> None:
    missing = [s.script for s in steps if not s.script.exists()]
    if missing:
        msg = "\n".join(f"- {p}" for p in missing)
        raise FileNotFoundError(f"Missing pipeline file(s):\n{msg}")


def run_step(step: Step, *, python: str, cwd: Path) -> None:
    print(f"\n=== {step.name} ===")
    print(f"{step.script}")

    proc = subprocess.run([python, str(step.script)], cwd=str(cwd), check=False)

    if proc.returncode != 0:
        raise RuntimeError(f"Step failed: {step.name} (exit code {proc.returncode})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NBA Player Prop Model v2 pipeline.")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip fetching odds step.")
    args = parser.parse_args()

    try_load_dotenv()

    root = Path(__file__).resolve().parent
    python = sys.executable

    src = root / "src"

    steps = [
        Step("Fetch odds", src / "data" / "fetch_odds.py"),
        Step("Clean odds", src / "data" / "clean_odds.py"),
        Step("Build features (v2)", src / "features_v2" / "build_features_v2.py"),
        Step("Run simulations (v2)", src / "simulations_v2" / "run_simulations_v2.py"),
        Step("Build portfolio (v2)", src / "selection_v2" / "build_portfolio_v2.py"),
        Step("Export Excel cards (v2)", src / "graphics" / "build_excel_card_v2.py"),
    ]

    if args.skip_fetch:
        steps = [s for s in steps if s.script.name != "fetch_odds.py"]

    if os.getenv("ODDS_API_KEY") is None and not args.skip_fetch:
        print("ODDS_API_KEY is not set. If fetch_odds.py needs it, set it in your .env.")

    try:
        require_files(steps)
        print("Starting pipeline...")
        for step in steps:
            run_step(step, python=python, cwd=root)
        print("\n Pipeline complete.")
        return 0
    except Exception as e:
        print(f"\n{e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
