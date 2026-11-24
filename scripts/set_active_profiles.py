"""Update deployments/local/active-profiles.env without cmd.exe delayed-expansion bugs."""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "deployments" / "local" / "active-profiles.env"


def read() -> dict[str, str]:
    vals = {"EIMS_EXPECT_OBSERVABILITY": "0", "EIMS_EXPECT_POOLER": "0"}
    if not PATH.is_file():
        return vals
    for line in PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        key = key.strip()
        if key in vals:
            vals[key] = "1" if raw.strip() in {"1", "true", "yes", "on"} else "0"
    return vals


def write(obs: str | None = None, pool: str | None = None) -> None:
    vals = read()
    if obs is not None:
        vals["EIMS_EXPECT_OBSERVABILITY"] = "1" if obs in {"1", "true", "yes", "on"} else "0"
    if pool is not None:
        vals["EIMS_EXPECT_POOLER"] = "1" if pool in {"1", "true", "yes", "on"} else "0"
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(
        "# Written by scripts/set_active_profiles.py - Portal infra-status reads this file.\n"
        f"EIMS_EXPECT_OBSERVABILITY={vals['EIMS_EXPECT_OBSERVABILITY']}\n"
        f"EIMS_EXPECT_POOLER={vals['EIMS_EXPECT_POOLER']}\n",
        encoding="utf-8",
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--observability", choices=["0", "1"])
    p.add_argument("--pooler", choices=["0", "1"])
    args = p.parse_args()
    if args.observability is None and args.pooler is None:
        raise SystemExit("pass --observability and/or --pooler")
    write(obs=args.observability, pool=args.pooler)


if __name__ == "__main__":
    main()
