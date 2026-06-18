"""Step 5 — Stage processed outputs + model parameters for the website.

Copies the GeoJSON layers into site/static/data and writes a compact model.json
that lets the site recompute the economic impact live as the user moves the
transit-time knob (client-side, from the same elasticities used offline).

Usage:
    uv run scripts/export_site_data.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))
import config as C  # noqa: E402


def main() -> None:
    C.SITE_DATA.mkdir(parents=True, exist_ok=True)

    for name in ("candidates.geojson", "transit_grid.geojson"):
        src = C.PROCESSED / name
        if not src.exists():
            raise SystemExit(f"Missing {src}; run the pipeline first.")
        shutil.copy(src, C.SITE_DATA / name)
        print(f"  copied {name} ({src.stat().st_size/1e6:.1f} MB)")

    summary = json.loads((C.PROCESSED / "candidates_summary.json").read_text())
    impact = json.loads((C.PROCESSED / "economic_impact.json").read_text())

    model = {
        "downtown": {"lon": C.DOWNTOWN[0], "lat": C.DOWNTOWN[1], "name": C.DOWNTOWN_NAME},
        "cutoffs_min": C.TRANSIT_CUTOFFS_MIN,
        "default_cutoff_min": C.DEFAULT_CUTOFF_MIN,
        "sf_housing_units": C.SF_HOUSING_UNITS,
        "sf_average_rent": C.SF_AVERAGE_RENT,
        "sf_renter_households": C.SF_RENTER_HOUSEHOLDS,
        "rent_elasticity": C.RENT_ELASTICITY,
        "buildout_phase_years": C.BUILDOUT_PHASE_YEARS,
        "typology_density_du_per_acre": C.TYPOLOGY_DENSITY_DU_PER_ACRE,
        "elasticity_sources": C.ELASTICITY_SOURCES,
        "caveats": impact["caveats"],
        "method_note": impact["method_note"],
        "summary": summary,
        "impact_default": impact,
    }
    (C.SITE_DATA / "model.json").write_text(json.dumps(model, indent=2))
    print("  wrote model.json")
    print(f"Site data staged in {C.SITE_DATA}")


if __name__ == "__main__":
    main()
