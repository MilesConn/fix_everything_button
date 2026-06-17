# Make Room for San Francisco — Methodology

A San Francisco replication of the New York Times / PAU (Vishaan Chakrabarti)
study *"How to Make Room for One Million New Yorkers"* (Dec 2023).

This document is the authoritative description of how every number on the site
is produced. Every step is reproducible from raw open data via the scripts in
`scripts/`.

---

## 1. What the original (NYT/PAU) study did

PAU answered: *how much housing can be added without demolishing any existing
home?* Their published methodology (NYT op-ed; PAU studio; CTBUH paper 4676):

- **Soft sites** = privately-owned **vacant lots**, **surface parking lots**
  (excluding structured parking garages), and **"taxpayer" parcels** —
  single-story commercial buildings with unused development rights.
- **Transit constraint**: only sites within a **half-mile (800 m)** of a transit
  station (subway, commuter rail, ferry).
- **Climate constraint**: exclude sites inside the **predicted 2100 floodplain**.
- **Context constraint**: assign each site a low / mid / high-rise typology
  matched to the **height of the surrounding neighborhood** (no demolition, no
  out-of-character towers).
- **Result**: ~520,245 net-new homes on ~1,700 acres, housing ~1.3M people.

## 2. How we adapt it for San Francisco (and where we go further)

Same conservative spirit (no demolition of housing, transit-oriented, climate
aware, context-scaled), with three deliberate upgrades the user asked for:

1. **Real transit travel time, not just a radius.** Instead of an 800 m buffer,
   we compute door-to-door **public-transit travel time to downtown** for every
   candidate using GTFS schedules (Muni + BART) and the street network. The
   accessibility threshold (e.g. 45 / 50 / 60 minutes) is an **adjustable knob**,
   so we can render isochrone heatmaps and re-filter candidates at any cutoff.
2. **Building-height–based "underutilization."** We use LiDAR-derived building
   heights to identify genuinely under-built parcels (single-story / very low
   FAR relative to what zoning allows), not just a land-use label.
3. **An explicitly bounded economic model** grounded in peer-reviewed causal
   estimates, reported as a range with sensitivity analysis rather than a single
   headline number.

## 3. Data sources (all open, all re-pullable)

All pulled by `scripts/pull_data.py` from DataSF (Socrata) and public GTFS.

| Dataset | Source | Used for |
|---|---|---|
| Parcels (`acdm-wktn`) | DataSF | parcel geometry, zoning code per lot |
| Land Use (`fdfd-xptc` / current) | DataSF | use flags: parking lot vs garage, commercial sqft, residential units, open space |
| Zoning Districts (`xzez-p3nc`) | DataSF | base zoning + height/bulk districts |
| Building Footprints (`ynuv-fyni`) | DataSF (LiDAR 2010) | building height → stories → underutilization |
| Sea Level Rise vulnerability zone | DataSF | exclude 2100 inundation (SLR + 100-yr storm) |
| Muni GTFS | SFMTA / 511 | transit schedule for travel-time routing |
| BART GTFS | BART | regional rail for travel-time routing |
| OSM street network (Bay Area) | Geofabrik | walking access/egress legs for routing |

## 4. Upzoning criteria (candidate selection)

A parcel is a **candidate** if **all** of the following hold:

1. **Not housing we'd demolish**: existing residential units ≤ a small threshold
   (we never count parcels with meaningful existing housing).
2. **Underutilized**, i.e. at least one of:
   - surface **parking lot** (excluding structured garages),
   - **vacant** (no commercial sqft, no residential units, not open space),
   - **single-story / very-low commercial** building (LiDAR height ≤ ~1–2
     stories, or built FAR far below zoned capacity).
3. **Not protected open space / parks.**
4. **Transit-accessible**: public-transit travel time to downtown ≤ the chosen
   cutoff (default 45 min; adjustable).
5. **Outside the 2100 sea-level-rise vulnerability zone.**

Each surviving parcel is assigned a **height typology** from the local
neighborhood context (median building height of nearby parcels) and a
conservative **units-per-acre** yield for that typology, giving net-new units per
site. This mirrors PAU's low/mid/high-rise context matching.

## 5. Economic model (rent impact)

Goal: a defensible statement of the form *"building N homes lowers SF rents by
~X%."* Built to be conservative and fully sourced.

**Core relationship.** We use a **metro-level supply elasticity of rent**: the %
change in market rent per 1% change in the housing stock. We do **not** invent a
number; we anchor to causal/quasi-experimental literature and report a range:

- **Pew (2025)** across 1,654 Zillow ZIPs: a 10% rise in a *metro's* stock ⇒ rent
  grew ~5% less ⇒ stock elasticity ≈ **−0.5**. (Region-wide supply has ~4× the
  effect of purely local supply.)
- **Mense (2025, JPE-Macro)**: 1% increase in *new* (flow) supply ⇒ −0.19% rents;
  short-run demand elasticity ≈ −0.025 (moving-chain / filtering channel).
- **Pennington (2021, SF)**: new construction cuts rents ~2% within 100 m and
  cuts displacement risk 17% (local, causal, fire-instrument).
- **Asquith–Mast–Reed (2023, REStat)**: new buildings cut nearby rents 5–7%.
- **Austin natural experiment (2022–24)**: ~+13% stock over ~2 yrs ⇒ rents fell
  ~ -15% in the metro — a real-world upper-bound cross-check.

We adopt a **central elasticity of −0.5** with a **sensitivity band of −0.25
(conservative) to −1.0 (optimistic)**.

**Key honesty upgrades over a naive model:**
- Report impact **per 10,000 units** and for a **phased buildout**, because a
  ~25% stock shock is far outside the range where a constant elasticity is
  validated — we flag linear extrapolation explicitly and prefer marginal
  framing.
- Distinguish **partial vs general equilibrium**, **short vs long run**, and the
  **induced-demand** caveat (new supply can raise neighborhood desirability).
- Convert % effects to **$/month savings** vs current SF average rent, with the
  full range shown, never a single false-precision figure.

## 6. Outputs

- `data/processed/candidates.geojson` / `.csv` — selected sites + attributes.
- `data/processed/isochrones.geojson` — transit travel-time surface to downtown.
- `data/processed/economic_impact.json` — units, stock change, rent-impact range,
  $ savings, with all assumptions and citations embedded.
- A Svelte site that presents the narrative, the site-selection map (with the
  adjustable transit knob), and the economic results.

## 7. Reproducibility

```
uv sync
uv run scripts/pull_data.py        # raw open data + GTFS + OSM
uv run scripts/compute_transit.py  # travel-time surface (knob = minutes)
uv run scripts/filter_candidates.py
uv run scripts/economic_model.py
```
Outputs are deterministic given the same input snapshots.
