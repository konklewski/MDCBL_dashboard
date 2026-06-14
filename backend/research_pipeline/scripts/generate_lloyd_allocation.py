"""Generate src/data/lloydAllocation.generated.ts from the internal-allocation CSV.

Reads report/sortedLsoaOfficerAllocation.csv (per-LSOA officer counts produced by
the weighted Lloyd's simulation) and the per-force animations in public/animations/,
then writes the LSOA officer-allocation summary the dashboard reads in the Policy tab.

Per force the summary carries: total officers placed, number of LSOAs covered, and
the top 8 LSOAs by officers placed. A force is listed in `animationForces` only when
its `<slug>_weighted.gif` exists, so the UI can fall back gracefully otherwise.

Run from the repository root:
    python3 backend/research_pipeline/scripts/generate_lloyd_allocation.py
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]

CSV_PATH = PIPELINE / "report" / "sortedLsoaOfficerAllocation.csv"
ANIMATIONS_DIR = ROOT / "public" / "animations"
OUTPUT = ROOT / "src" / "data" / "lloydAllocation.generated.ts"

TOP_N = 8

# The CSV labels the City of London force as "London, City of"; the dashboard uses
# "City of London" everywhere else, so normalise it here.
FORCE_NAME_OVERRIDES = {"London, City of": "City of London"}


def gif_slug(name: str) -> str:
    return name.replace(" & ", "_and_").replace(" ", "_")


# The six LSOAs of the City of London local authority — City of London Police's
# statutory jurisdiction. police.uk geocodes some of its crimes to anonymised map
# points in neighbouring Metropolitan-borough LSOAs (Tower Hamlets, Hackney,
# Islington…), which the filter drops. The weighted Lloyd's sim places 0 officers
# in 001C, so it never appears in the CSV; we pad it back to keep the full set of 6.
CITY_OF_LONDON_LSOAS = [
    ("City of London 001A", "E01000001"),
    ("City of London 001B", "E01000002"),
    ("City of London 001C", "E01000003"),
    ("City of London 001E", "E01000005"),
    ("City of London 001F", "E01032739"),
    ("City of London 001G", "E01032740"),
]


# Keep only City of London Police's own jurisdiction LSOAs, then pad any genuine
# City LSOA the Lloyd's sim placed 0 officers in (absent from the CSV) so the full
# set of 6 shows. Mirrors jurisdictionFilter in src/data/forces.ts.
def jurisdiction_filter(force: str, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if force != "City of London":
        return rows
    kept = [r for r in rows if str(r["name"]).startswith("City of London")]
    seen = {str(r["code"]) for r in kept}
    for name, code in CITY_OF_LONDON_LSOAS:
        if code not in seen:
            kept.append({"name": name, "code": code, "officers": 0})
    return kept


def main() -> None:
    by_force: dict[str, list[dict[str, object]]] = defaultdict(list)
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            force = FORCE_NAME_OVERRIDES.get(row["police_force"], row["police_force"])
            by_force[force].append(
                {
                    "name": row["lsoa_name"],
                    "code": row["lsoa_code"],
                    "officers": int(float(row["officers_assigned"])),
                }
            )

    summary: dict[str, dict[str, object]] = {}
    for force in sorted(by_force):
        lsoas = jurisdiction_filter(force, by_force[force])
        top = sorted(lsoas, key=lambda l: l["officers"], reverse=True)[:TOP_N]
        summary[force] = {
            "totalOfficers": sum(l["officers"] for l in lsoas),
            "lsoaCount": len(lsoas),
            "topLsoas": top,
        }

    animation_forces = sorted(
        force
        for force in summary
        if (ANIMATIONS_DIR / f"{gif_slug(force)}_weighted.gif").exists()
    )

    payload = {"animationForces": animation_forces, "byForce": summary}
    body = json.dumps(payload, indent=2, ensure_ascii=False)

    OUTPUT.write_text(
        "/* Generated from report/sortedLsoaOfficerAllocation.csv + animations/. "
        "Do not edit by hand. */\n"
        f"export const lloydAllocation = {body} as const;\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: {len(summary)} forces, "
          f"{len(animation_forces)} with animations")


if __name__ == "__main__":
    main()
