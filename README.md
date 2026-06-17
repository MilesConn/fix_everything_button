# Make Room for San Francisco

A reproducible, San Francisco replication of the New York Times / PAU study
[**“How to Make Room for One Million New Yorkers.”**](https://www.nytimes.com/interactive/2023/12/30/opinion/new-york-housing-solution.html)

It answers, with open data: **how much housing can SF add without demolishing a
single home — and what would that do to rents?**

The pipeline finds underused, transit-accessible parcels (parking lots, vacant
land, single-/low-story buildings with no housing), scales each to a
context-matched housing typology, and estimates the rent impact with a
range-based economic model grounded in the causal literature. A SvelteKit site
presents the map, the transit-time "knob", and the live economic estimate.

See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) for the full write-up and citations.

---

## Headline result (45-minute transit cutoff)

| | |
|---|---|
| Candidate sites | **~7,500** |
| Net-new homes (no demolition) | **~99,600** |
| Underused land | **~1,800 acres** |
| Increase in SF housing stock | **~24%** |
| Projected rent change (full buildout) | **−6% to −24%** (central **−12%**) |
| Defensible marginal effect | each **10,000** homes ⇒ **~−1.2%** rent (central) |

All numbers regenerate from raw public data and update live on the site as the
transit cutoff changes.

---

## How it works

Five reproducible steps (each script is standalone; `main.py` runs them in order):

| Step | Script | What it does |
|------|--------|--------------|
| 1 | `scripts/pull_data.py` | Pulls DataSF parcels, land use, zoning, building footprints (LiDAR heights), the 2100 sea-level-rise zone; Muni + BART GTFS; the SF OSM street network. Idempotent. |
| 2 | `scripts/compute_transit.py` | Builds a multimodal network (OSM + GTFS) with **r5py** and computes door-to-door public-transit travel time from downtown to a 200 m grid (typical weekday AM, averaged over an hour). This travel-time surface is the adjustable accessibility knob. |
| 3 | `scripts/filter_candidates.py` | Applies the candidate criteria, excludes the SLR zone, joins transit times, and assigns each site a context-matched typology + conservative unit yield. |
| 4 | `scripts/economic_model.py` | Translates net-new units into a rent change using a metro **stock elasticity of rent** (central −0.5; band −0.25 to −1.0), with marginal, phased and full-buildout framings + caveats. |
| 5 | `scripts/export_site_data.py` | Stages GeoJSON layers + a compact `model.json` into `site/static/data` for the website. |

All knobs (transit cutoff, height thresholds, densities, elasticities, sources)
live in [`scripts/config.py`](scripts/config.py).

### Candidate criteria (all must hold)

1. **No home demolished** — zero existing residential units.
2. **Underused** — surface parking (not a garage), vacant, or tallest building ≤ ~9 m (single-/low-story), from LiDAR.
3. **Not a park** — protected open space excluded.
4. **Outside the 2100 SLR + 100-yr-storm inundation zone.**
5. **Transit-served** — public-transit travel time to downtown ≤ the chosen cutoff (default 45 min).

---

## Reproduce it

### Data + model (Python via [uv](https://docs.astral.sh/uv/))

Requires **Java 21** (for r5py transit routing) and Python 3.12.

```bash
uv sync
uv run main.py            # pull (if missing) -> transit -> filter -> model -> export
# or run a single step, e.g. a different transit cutoff:
uv run scripts/filter_candidates.py --cutoff 60 && uv run scripts/economic_model.py
```

Large reproducible inputs (`building_footprints.csv`, GTFS, OSM) are gitignored
and re-fetched by `pull_data.py`. An optional DataSF app token can be set as
`SF_OPENDATA_API_KEY` in `.env` for faster pulls (the pipeline works without one).

### Website (SvelteKit)

```bash
cd site
npm install
npm run dev        # local dev
npm run build      # static build -> site/build (deployable to any static host)
```

For a GitHub Pages project site, build with a base path:
`BASE_PATH=/<repo-name> npm run build`.

---

## Repo layout

```
scripts/        pipeline (config, pull, transit, filter, model, export)
main.py         end-to-end orchestrator
docs/           METHODOLOGY.md (method + citations)
data/raw/       open inputs (large ones regenerated on demand)
data/processed/ candidates + transit grid + economic_impact.json
site/           SvelteKit website (map, transit knob, live economics)
```

## Notes on rigor

- Rent-impact numbers are **ranges with citations**, not a single headline. The
  full-buildout figure is explicitly flagged as a linear extrapolation of a large
  (~24%) stock shock; the per-10k-units and phased figures are the defensible
  headline.
- Muni's live GTFS endpoint is license-gated; the last freely-archived full feed
  is used (via the Wayback Machine) and normalized to a typical weekday so it can
  be combined deterministically with BART. Supply a current regional feed if you
  have 511.org access.
