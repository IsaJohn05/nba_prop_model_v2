"""
run_pipeline_v2.py

Runs the NBA player prop model v2 pipeline in the correct order:
1) fetch_odds.py
2) clean_odds.py
3) build_features_v2.py
4) run_simulations_v2.py
5) build_portfolio_v2.py
6) build_excel-card_v2.py
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path


def try_load_dotenv() -> None:
    """
    loads environment variables from a local .env file if python-dotenv is installed.
    This keeps secrets out of code and out of git.
    """
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        # No dotenv installed (or no .env). That's fine.
        pass


def run_script(script_path: Path) -> None:
    """
    Runs a python script as a subprocess using the same Python interpreter.
    Fails fast if any script errors.
    """
    print(f"\n Running: {script_path}")
    result = subprocess.run([sys.executable, str(script_path)], check=False)

    if result.returncode != 0:
        print(f"\n Failed: {script_path} (exit code {result.returncode})")
        sys.exit(result.returncode)

    print(f"✅ Done: {script_path}")


def main() -> None:
    try_load_dotenv()

    # (Remove this if you don't use ODDS_API_KEY)
    if os.getenv("ODDS_API_KEY") is None:
        print("ℹ️  Note: ODDS_API_KEY is not set. If fetch_odds.py requires it, set it in your .env.")

    root = Path(__file__).resolve().parent

    pipeline = [
        root / "fetch_odds.py",
        root / "clean_odds.py",
        root / "build_features_v2.py",
        root / "run_simulations_v2.py",
        root / "build_portfolio_v2.py",
        root / "build_excel-card_v2.py",
    ]

    # Validate all files exist before running anything
    missing = [p for p in pipeline if not p.exists()]
    if missing:
        print("\nThese pipeline files were not found:")
        for p in missing:
            print(f"   - {p}")
        print("\nFix the file names/paths in run_pipeline_v2.py and try again.")
        sys.exit(1)

    print(" Starting Player Prop Model v2 pipeline...")
    for script in pipeline:
        run_script(script)

    print("\n Pipeline complete!")


if __name__ == "__main__":
    main()
