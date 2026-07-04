from __future__ import annotations

import argparse
import shutil
from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parent / "template"
SCRIPT_FILES = [
    "config.py",
    "fetch_ga4.py",
    "fetch_gsc.py",
    "fetch_google_ads.py",
    "fetch_shopify.py",
    "transform_data.py",
    "generate_report.py",
    "generate_weekly_comparison_template.py",
    "build_owner_dashboard.py",
]


def copy_file(src: Path, dst: Path, overwrite: bool) -> None:
    if dst.exists() and not overwrite:
        print(f"SKIP existing {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"COPY {src.name} -> {dst}")


def install(target: Path, overwrite: bool) -> None:
    if not TEMPLATE_DIR.exists():
        raise RuntimeError(f"Template directory not found: {TEMPLATE_DIR}")

    for directory in ("scripts", "data/raw", "data/processed", "reports", "outputs", "work"):
        (target / directory).mkdir(parents=True, exist_ok=True)

    for filename in SCRIPT_FILES:
        copy_file(TEMPLATE_DIR / filename, target / "scripts" / filename, overwrite)

    copy_file(TEMPLATE_DIR / "requirements.txt", target / "requirements.txt", overwrite)
    env_target = target / ".env.example"
    copy_file(TEMPLATE_DIR / ".env.example", env_target, overwrite)

    if not (target / ".env").exists():
        print("NEXT create .env from .env.example and fill local credentials.")
    print("DONE growth reporting pipeline installed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the DTC growth data reporting pipeline into a project.")
    parser.add_argument("--target", default=".", help="Target project directory.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing pipeline files.")
    args = parser.parse_args()

    install(Path(args.target).expanduser().resolve(), args.overwrite)


if __name__ == "__main__":
    main()
