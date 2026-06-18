"""Step 4 — Economic model: how much would the new homes lower SF rents?

Design goal: a defensible, transparent statement of the form
"building N homes lowers SF rents by ~X% (± a stated range)."

Method (see docs/METHODOLOGY.md §5):
  * Anchor on a metro-level STOCK elasticity of rent — the % change in rent per
    1% change in the housing stock — taken from the causal/quasi-experimental
    literature, not invented. Central = -0.5 (Pew 2025), band -0.25 to -1.0.
  * Report the MARGINAL effect (per 10k units) as the headline, because that is
    inside the range the literature validates.
  * Report the full-buildout effect too, but explicitly flag it as a linear
    extrapolation of a one-time stock shock larger than the variation the
    elasticities were directly measured on.
  * Convert to $/month per renter and an aggregate citywide annual figure.
  * Carry cross-checks (Austin, Pennington) and caveats in the output so the
    numbers are never presented without their context.

Output:
    data/processed/economic_impact.json

Usage:
    uv run scripts/economic_model.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import config as C  # noqa: E402


def scenario(units: int, elasticity: float) -> dict:
    stock_pct = units / C.SF_HOUSING_UNITS * 100.0
    rent_pct = stock_pct * elasticity  # negative
    new_rent = C.SF_AVERAGE_RENT * (1 + rent_pct / 100.0)
    monthly_savings = C.SF_AVERAGE_RENT - new_rent
    return {
        "elasticity": elasticity,
        "rent_change_pct": round(rent_pct, 2),
        "new_average_rent": round(new_rent, 2),
        "monthly_savings_per_renter": round(monthly_savings, 2),
        "annual_savings_per_renter": round(monthly_savings * 12, 2),
        "citywide_annual_savings": round(monthly_savings * 12 * C.SF_RENTER_HOUSEHOLDS, 0),
    }


def main() -> None:
    summary_path = C.PROCESSED / "candidates_summary.json"
    if not summary_path.exists():
        raise SystemExit("Run filter_candidates.py first (candidates_summary.json missing).")
    summary = json.loads(summary_path.read_text())
    units = int(summary["total_net_new_units"])

    stock_pct = units / C.SF_HOUSING_UNITS * 100.0

    scenarios = {name: scenario(units, e) for name, e in C.RENT_ELASTICITY.items()}
    marginal = {
        name: round((10_000 / C.SF_HOUSING_UNITS * 100.0) * e, 3)
        for name, e in C.RENT_ELASTICITY.items()
    }

    units_per_year = round(units / C.BUILDOUT_PHASE_YEARS)
    phased = {
        "years": C.BUILDOUT_PHASE_YEARS,
        "units_per_year": units_per_year,
        "annual_stock_pct": round(units_per_year / C.SF_HOUSING_UNITS * 100.0, 3),
        "annual_rent_change_pct_central": round(
            (units_per_year / C.SF_HOUSING_UNITS * 100.0) * C.RENT_ELASTICITY["central"], 3
        ),
    }

    result = {
        "headline": (
            f"Building ~{units:,} net-new homes (a {stock_pct:.1f}% increase in SF's "
            f"housing stock) is projected to lower average market rents by "
            f"{abs(scenarios['conservative']['rent_change_pct']):.0f}–"
            f"{abs(scenarios['optimistic']['rent_change_pct']):.0f}% "
            f"(central estimate {abs(scenarios['central']['rent_change_pct']):.0f}%), "
            f"≈ ${abs(scenarios['central']['monthly_savings_per_renter']):,.0f}/month "
            f"off the typical rent."
        ),
        "inputs": {
            "net_new_units": units,
            "transit_cutoff_min": summary["cutoff_min"],
            "sf_housing_units": C.SF_HOUSING_UNITS,
            "sf_average_rent": C.SF_AVERAGE_RENT,
            "sf_renter_households": C.SF_RENTER_HOUSEHOLDS,
        },
        "stock_increase_pct": round(stock_pct, 2),
        "marginal_rent_pct_per_10k_units": marginal,
        "scenarios_full_buildout": scenarios,
        "phased_buildout": phased,
        "cross_checks": C.ELASTICITY_SOURCES,
        "caveats": [
            f"Elasticities are estimated for marginal supply changes; this "
            f"~{stock_pct:.0f}% one-time stock increase is still larger than the "
            f"year-to-year variation the elasticities were measured on, so the "
            f"full-buildout figures are a linear extrapolation and should be read "
            f"as an order-of-magnitude estimate, not a point forecast. The "
            f"per-10k-units and phased figures are the most defensible headline.",
            "Estimates are partial-equilibrium for the rental market and hold "
            "incomes/amenities fixed; new supply can modestly raise local demand "
            "(amenity/induced-demand effect documented by Pennington 2021), which "
            "the elasticity band already partly reflects.",
            "Benefits are largest for older, mid- and lower-cost units via filtering "
            "and moving chains (Mense 2025; Pew 2025); the citywide average understates "
            "relief at the bottom of the market.",
            "Unit yields are conservative (context-matched typologies, 70% buildable "
            "lot fraction); actual capacity could be higher with deeper upzoning.",
        ],
        "method_note": (
            "Rent change = (net-new units / current stock) x 100 x elasticity. "
            "Elasticity is the metro stock elasticity of rent; central -0.5 from "
            "Pew (2025), band -0.25..-1.0 spanning the causal literature."
        ),
    }

    out = C.PROCESSED / "economic_impact.json"
    out.write_text(json.dumps(result, indent=2))

    print("=== Economic impact ===")
    print(result["headline"])
    print(f"\nStock increase: {stock_pct:.1f}%")
    print("Full-buildout rent change:")
    for name, s in scenarios.items():
        print(f"  {name:>12}: {s['rent_change_pct']:+.1f}%  "
              f"(${-s['monthly_savings_per_renter']:,.0f}/mo, "
              f"new avg ${s['new_average_rent']:,.0f})")
    print(f"\nMarginal (per 10k units): {marginal}")
    print(f"Phased ({phased['years']} yrs): {phased['units_per_year']:,} units/yr "
          f"-> {phased['annual_rent_change_pct_central']:+.2f}%/yr (central)")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
