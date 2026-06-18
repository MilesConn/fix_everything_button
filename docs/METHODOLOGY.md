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
aware, context-scaled), with four deliberate upgrades:

1. **Real transit travel time, not just a radius.** Instead of an 800 m buffer,
   we compute door-to-door **public-transit travel time to downtown** for every
   candidate using GTFS schedules (Muni + BART) and the street network. The
   accessibility threshold is an **adjustable knob** with 1-minute granularity
   (15–75 min), so we can render isochrone heatmaps and re-filter candidates at
   any cutoff. The heatmap is **clipped to the SF land boundary** (SF Find
   Neighborhoods) so it never spills into Daly City, Oakland or the open bay.
2. **The current Assessor secured roll as the authoritative “what’s built”
   layer.** Two earlier data layers proved unreliable on their own: the LiDAR
   building footprints are a **2017 survey**, so every building completed after
   2017 has *no footprint → zero height → looks vacant* (this is why Salesforce
   Tower and 188 Octavia slipped in); and the land-use `total_comm` field lumps
   **civic/institutional** floor area (libraries, schools, churches) together
   with retail (this is why a branch library slipped in). The Assessor roll
   (`wv5m-vpq2`, 2024, 212k parcels) provides current **stories, units, year
   built, building area, and a clean property-class code**, joined to parcels by
   exact block+lot key (99%+) plus a spatial fallback.
3. **Use-aware, density-aware soft-site rules.** We exclude parcels by property
   class (institutional, residential, office/industrial, hotels, parking
   garages, public/under-water land), require genuinely low intensity (≤ 1 story
   *and* LiDAR ≤ 9 m *and* floor-area ratio ≤ 1.2 — the FAR cap rejects any dense
   or mis-mapped tower), drop anything built since 2015, and require a positive
   soft-site signal (surface parking, vacant lot, or single-story commercial).
4. **An explicitly bounded economic model** grounded in peer-reviewed causal
   estimates, reported as a range with sensitivity analysis rather than a single
   headline number.

> **Why the candidate count fell from the first draft.** The first pass (~7,500
> sites) counted ~39% of parcels that had *zero* LiDAR height — mostly
> post-2017 towers and mis-joins — as “vacant,” and counted institutional floor
> area as commercial. After the Assessor-roll refinement, ~2,200 sites survive.
> This is the correct, precise number: the removed sites were predominantly
> false positives, exactly the failure mode flagged during review.

## 3. Data sources (all open, all re-pullable)

All pulled by `scripts/pull_data.py` from DataSF (Socrata) and public GTFS.

| Dataset | Source | Used for |
|---|---|---|
| Parcels (`acdm-wktn`) | DataSF | parcel geometry, zoning code per lot |
| Land Use (`fdfd-xptc` / current) | DataSF | use flags: parking lot vs garage, commercial sqft, residential units, open space |
| Zoning Districts (`xzez-p3nc`) | DataSF | base zoning + height/bulk districts |
| Building Footprints (`ynuv-fyni`) | DataSF (LiDAR **2017** survey) | secondary height guard; stale for post-2017 buildings |
| **Assessor secured roll (`wv5m-vpq2`, 2024)** | DataSF | **authoritative current** stories, units, year built, building area, property-class code |
| **SF Find Neighborhoods (`gfpk-269f`)** | DataSF | SF land boundary for clipping the heatmap / candidates |
| Sea Level Rise vulnerability zone | DataSF | exclude 2100 inundation (SLR + 100-yr storm) |
| Muni GTFS | SFMTA / 511 | transit schedule for travel-time routing |
| BART GTFS | BART | regional rail for travel-time routing |
| OSM street network (Bay Area) | Geofabrik | walking access/egress legs for routing |

## 4. Upzoning criteria (candidate selection)

A parcel is a **candidate** if **all** of the following hold (knobs in
`scripts/config.py`):

1. **No housing we'd demolish**: zero existing residential units in **both** the
   land-use file and the Assessor roll, and not a residential property class.
2. **Not civic / institutional / medical / government / public**: excluded by
   Assessor property class (libraries `LIBG`, schools `E/EG`, churches `W`,
   hospitals `N1/N2`, fire/police, consulates, clubs, golf courses, theatres,
   and all government / public-owned + public-vacant land), and not flagged as
   civic (`cie`) or medical (`med`) in the land-use file.
3. **Not an office / industrial building, hotel/motel, or parking garage**
   (vs. a surface parking *lot*, which is eligible).
4. **Genuinely low-rise and underbuilt** — all three must hold:
   - Assessor **stories ≤ 1** (`MAX_SOFT_SITE_STORIES`),
   - LiDAR roof height **≤ 9 m** (`SINGLE_STORY_MAX_HEIGHT_M`),
   - **floor-area ratio ≤ 1.2** (`MAX_SOFT_SITE_FAR`, built sqft ÷ lot sqft) —
     the backstop that rejects any dense or mis-joined tower regardless of the
     story/height signals.
5. **Not recently built**: Assessor year built **< 2015** (`RECENT_BUILD_YEAR`),
   so new buildings the older layers miss don't appear as “vacant.”
6. **A positive soft-site signal** — at least one of: a surface **parking lot**
   (`PL`, or land-use parking flag and not a garage), a **vacant** developable
   lot (`V/VR/VCI/…` or truly empty in land-use + LiDAR), or **single-story
   commercial / retail** (`C/CZ/CM/…` or land-use retail sqft).
7. **Not protected open space / parks.**
8. **Outside the 2100 sea-level-rise vulnerability zone.**
9. **Transit-accessible**: public-transit travel time to downtown ≤ the chosen
   cutoff (default 45 min; adjustable 15–75 at 1-min granularity).

Each surviving parcel is assigned a **height typology** from the local
neighborhood context (median LiDAR building height within 300 m) and a
conservative **units-per-acre** yield for that typology, giving net-new units per
site. This mirrors PAU's low/mid/high-rise context matching.

### Verification against the reviewed false positives

| Site | Earlier draft | Now | Why |
|---|---|---|---|
| Salesforce Tower | candidate (“vacant”) | **excluded** | Assessor stories/FAR + office class |
| 188 Octavia (2020, 29 units) | candidate (“vacant”) | **excluded** | Assessor units > 0 + year ≥ 2015 |
| Jose Sarria Ct / Harvey Milk Library | candidate (“single-story commercial”) | **excluded** | institutional class / `cie` |

A companion **annotation tool** (`/review` on the site) renders every candidate
with a satellite photo + Street View link and lets a reviewer mark each
feasible / infeasible / unsure with a reason, exported to CSV to feed back into
these rules.

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
