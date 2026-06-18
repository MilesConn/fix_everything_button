"""Step 3 — Select upzoning candidates (criteria + typology + unit yield).

Replicates the PAU "soft site" logic for San Francisco and goes further by using
(a) real transit travel times (from compute_transit.py) instead of a flat radius
and (b) the *current* Assessor secured roll as the authoritative source of what
is actually built on each parcel — correcting the stale land-use unit counts and
the 2017-vintage LiDAR (which misses every building completed after 2017).

A parcel is a candidate iff ALL hold:
  1. No existing housing to demolish — zero units in BOTH the assessor roll and
     the land-use file, and not a residential property class (PAU: no demolition).
  2. Not protected open space / park.
  3. Not a civic / institutional / medical / government / public parcel
     (libraries, schools, churches, hospitals, fire/police, etc.).
  4. Not an existing office or industrial building.
  5. Genuinely low-rise / underutilized: assessor stories <= MAX_SOFT_SITE_STORIES
     AND LiDAR height <= SINGLE_STORY_MAX_HEIGHT_M AND floor-area-ratio
     <= MAX_SOFT_SITE_FAR (the FAR cap rejects any dense or mis-joined tower).
  6. Not recently built (assessor year_built < RECENT_BUILD_YEAR).
  7. Carries a positive soft-site signal: a surface parking lot, a vacant
     developable lot, or single-story commercial / retail.
  8. Outside the 2100 sea-level-rise inundation zone.
  9. Public-transit travel time to downtown <= the chosen cutoff (default 45).

Each candidate is then assigned a context-matched housing typology (low/mid/
high-rise from surrounding building heights) and a conservative net unit yield.

Output:
    data/processed/candidates.geojson
    data/processed/candidates.csv
    data/processed/candidates_summary.json

Usage:
    uv run scripts/filter_candidates.py [--cutoff 45]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(__file__))
import config as C  # noqa: E402

SQFT_PER_M2 = 10.7639


def _load_polygons(csv, geom_col, cols, name):
    print(f"  reading {name} …")
    df = pd.read_csv(csv, usecols=lambda c: c == geom_col or c in cols, low_memory=False)
    df = df[df[geom_col].notna()].copy()
    geom = gpd.GeoSeries.from_wkt(df[geom_col], crs=C.WGS84)
    gdf = gpd.GeoDataFrame(df.drop(columns=[geom_col]), geometry=geom, crs=C.WGS84)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    print(f"    {len(gdf):,} {name}")
    return gdf


def load_assessor() -> gpd.GeoDataFrame:
    """Current assessor roll as points, with per-record use flags."""
    print("  reading assessor roll …")
    df = pd.read_csv(C.RAW / "assessor_roll.csv", low_memory=False,
                     dtype={"block": str, "lot": str})
    # Parcel key = zero-padded block + lot (matches land-use mapblklot for 99%+).
    df["key"] = df["block"].fillna("").str.zfill(4) + df["lot"].fillna("")
    df = df.reset_index(drop=True)
    df["asr_id"] = df.index
    has_geom = df["the_geom"].notna()
    geom = gpd.GeoSeries.from_wkt(df["the_geom"].where(has_geom, None), crs=C.WGS84)
    g = gpd.GeoDataFrame(df.drop(columns=["the_geom"]), geometry=geom, crs=C.WGS84)
    g["stories"] = pd.to_numeric(g["number_of_stories"], errors="coerce")
    g["units"] = pd.to_numeric(g["number_of_units"], errors="coerce")
    g["year"] = pd.to_numeric(g["year_property_built"], errors="coerce")
    g["barea"] = pd.to_numeric(g["property_area"], errors="coerce").fillna(0)
    cc = g["property_class_code"].astype(str).str.strip().str.upper()
    g["c_inst"] = cc.isin(C.ASSESSOR_INSTITUTIONAL_CLASSES)
    g["c_resid"] = cc.isin(C.ASSESSOR_RESIDENTIAL_CLASSES)
    g["c_offind"] = cc.isin(C.ASSESSOR_OFFICE_INDUSTRIAL_CLASSES)
    g["c_parking"] = cc.isin(C.ASSESSOR_PARKING_CLASSES)
    g["c_vacant"] = cc.isin(C.ASSESSOR_VACANT_CLASSES)
    g["c_comm"] = cc.isin(C.ASSESSOR_COMMERCIAL_CLASSES)
    g["c_excl"] = cc.isin(C.ASSESSOR_EXCLUDE_CLASSES)
    print(f"    {len(g):,} assessor records")
    return g


def assign_transit_minutes(parcels_m: gpd.GeoDataFrame) -> np.ndarray:
    grid = pd.read_csv(C.PROCESSED / "transit_grid.csv")
    grid = grid[grid["minutes"].notna()].copy()
    g = gpd.GeoDataFrame(
        grid, geometry=gpd.points_from_xy(grid.lon, grid.lat), crs=C.WGS84
    ).to_crs(C.SF_CRS_M)
    tree = cKDTree(np.c_[g.geometry.x, g.geometry.y])
    cent = parcels_m.geometry.centroid
    _, idx = tree.query(np.c_[cent.x, cent.y], k=1)
    return g["minutes"].to_numpy()[idx]


def context_height(cand_m: gpd.GeoDataFrame, footprint_pts_m: gpd.GeoDataFrame) -> np.ndarray:
    """Median surrounding building height (m) within 300 m of each candidate."""
    cent = cand_m.copy()
    cent["geometry"] = cent.geometry.centroid
    buf = cent.copy()
    buf["geometry"] = buf.geometry.buffer(300)
    joined = gpd.sjoin(
        footprint_pts_m[["height_m", "geometry"]], buf[["cand_idx", "geometry"]],
        how="inner", predicate="within",
    )
    med = joined.groupby("cand_idx")["height_m"].median()
    return cand_m["cand_idx"].map(med).to_numpy()


def pick_typology(context_h: float) -> str:
    if context_h <= C.TYPOLOGY_CONTEXT_HEIGHT_M["low"]:
        return "low"
    if context_h <= C.TYPOLOGY_CONTEXT_HEIGHT_M["mid"]:
        return "mid"
    return "high"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cutoff", type=int, default=C.DEFAULT_CUTOFF_MIN,
                    help="max transit minutes to downtown")
    args = ap.parse_args()
    cutoff = args.cutoff

    print("Loading datasets …")
    lu = _load_polygons(
        C.RAW / "land_use_current.csv", "the_geom",
        ["mapblklot", "resunits", "total_comm", "retail", "cie", "med",
         "parking_lo", "garage", "open_space"],
        "land-use parcels",
    )
    foot = _load_polygons(
        C.RAW / "building_footprints.csv", "shape",
        ["mblr", "hgt_median_m"], "building footprints",
    )
    slr = _load_polygons(C.RAW / "slr_66in.csv", "the_geom", [], "SLR polygons")
    asr = load_assessor()

    # --- normalize land-use types ---
    for col in ("resunits", "total_comm", "retail", "cie", "med"):
        lu[col] = pd.to_numeric(lu[col], errors="coerce").fillna(0)
    for b in ("parking_lo", "garage", "open_space"):
        lu[b] = lu[b].astype(str).str.lower().isin(["true", "1", "1.0", "t", "yes"])
    foot["height_m"] = pd.to_numeric(foot["hgt_median_m"], errors="coerce").fillna(0)

    # project to meters for all spatial math
    print("Projecting to meters …")
    lu_m = lu.to_crs(C.SF_CRS_M).reset_index(drop=True)
    foot_m = foot.to_crs(C.SF_CRS_M)
    foot_pts = foot_m.copy()
    foot_pts["geometry"] = foot_pts.geometry.centroid
    slr_m = slr.to_crs(C.SF_CRS_M)
    asr_m = asr.to_crs(C.SF_CRS_M)

    lu_m["lot_area_m2"] = lu_m.geometry.area
    lu_m["lot_area_acres"] = lu_m["lot_area_m2"] / 4046.8564224
    lu_m["lot_area_sqft"] = lu_m["lot_area_m2"] * SQFT_PER_M2

    # --- LiDAR building height per parcel (secondary guard) ---
    print("Joining LiDAR building heights to parcels …")
    j = gpd.sjoin(foot_pts[["height_m", "geometry"]], lu_m[["geometry"]],
                  how="inner", predicate="within")
    parcel_h = j.groupby("index_right")["height_m"].max()
    lu_m["building_height_m"] = lu_m.index.map(parcel_h).fillna(0.0)

    # --- Assessor overlay: aggregate the current roll onto each parcel ---
    # Primary join is the exact block+lot key (matches 99%+ of parcels); a
    # spatial point-in-parcel join supplements the rest. Both are unioned so a
    # parcel picks up every assessor record that belongs to it.
    print("Overlaying assessor roll (current stories/units/year/class) …")
    lu_m["pkey"] = lu_m["mapblklot"].astype(str)
    key_pairs = (
        lu_m[["pkey"]].reset_index().rename(columns={"index": "parcel"})
        .merge(asr_m[["key", "asr_id"]], left_on="pkey", right_on="key")
        [["parcel", "asr_id"]]
    )
    asr_pts = asr_m[asr_m.geometry.notna()]
    sp = gpd.sjoin(asr_pts[["asr_id", "geometry"]], lu_m[["geometry"]],
                   how="inner", predicate="within")
    sp_pairs = sp.reset_index().rename(columns={"index_right": "parcel"})[["parcel", "asr_id"]]
    pairs = pd.concat([key_pairs, sp_pairs]).drop_duplicates(["parcel", "asr_id"])
    print(f"  {len(key_pairs):,} key-matched + {len(sp_pairs):,} spatial pairs "
          f"-> {len(pairs):,} unique parcel\u00d7assessor links")

    attrs = asr_m.drop(columns="geometry")[[
        "asr_id", "stories", "units", "year", "barea", "c_inst", "c_resid",
        "c_offind", "c_excl", "c_parking", "c_vacant", "c_comm",
        "property_class_code", "use_definition", "property_location"]]
    aj = pairs.merge(attrs, on="asr_id").rename(columns={"parcel": "index_right"})
    grp = aj.groupby("index_right")
    agg = grp.agg(
        asr_stories=("stories", "max"),
        asr_units=("units", "max"),
        asr_year=("year", "max"),
        asr_barea=("barea", "max"),
        asr_n=("stories", "size"),
        c_inst=("c_inst", "max"),
        c_resid=("c_resid", "max"),
        c_offind=("c_offind", "max"),
        c_excl=("c_excl", "max"),
        c_parking=("c_parking", "max"),
        c_vacant=("c_vacant", "max"),
        c_comm=("c_comm", "max"),
    )
    for col in agg.columns:
        lu_m[col] = lu_m.index.map(agg[col])
    for b in ("c_inst", "c_resid", "c_offind", "c_excl", "c_parking", "c_vacant", "c_comm"):
        lu_m[b] = lu_m[b].fillna(False).astype(bool)
    lu_m["asr_n"] = lu_m["asr_n"].fillna(0)

    # dominant (largest-area) assessor record per parcel — for display fields
    dom = (aj.sort_values("barea", ascending=False)
             .drop_duplicates("index_right")
             .set_index("index_right"))
    lu_m["asr_class"] = lu_m.index.map(dom["property_class_code"])
    lu_m["asr_use"] = lu_m.index.map(dom["use_definition"])
    lu_m["address"] = lu_m.index.map(dom["property_location"])

    # floor-area-ratio (built sqft / lot sqft) from the assessor building area
    lu_m["far"] = (lu_m["asr_barea"].fillna(0) / lu_m["lot_area_sqft"]).replace(
        [np.inf, -np.inf], np.nan).fillna(0)

    # --- criteria ---
    print("Applying refined criteria …")
    has_housing = (lu_m["asr_units"].fillna(0) > C.MAX_EXISTING_RES_UNITS) | \
                  (lu_m["resunits"] > C.MAX_EXISTING_RES_UNITS) | lu_m["c_resid"]
    no_housing = ~has_housing

    not_open = ~lu_m["open_space"]
    not_inst = ~(lu_m["c_inst"] | (lu_m["cie"] > 0) | (lu_m["med"] > 0))
    not_offind = ~lu_m["c_offind"]
    not_excl = ~lu_m["c_excl"]  # garages, hotels, under-water, misc

    stories_ok = lu_m["asr_stories"].isna() | (lu_m["asr_stories"] <= C.MAX_SOFT_SITE_STORIES)
    lidar_ok = lu_m["building_height_m"] <= C.SINGLE_STORY_MAX_HEIGHT_M
    far_ok = lu_m["far"] <= C.MAX_SOFT_SITE_FAR
    not_recent = lu_m["asr_year"].isna() | (lu_m["asr_year"] < C.RECENT_BUILD_YEAR)
    low_rise = stories_ok & lidar_ok & far_ok & not_recent

    # positive soft-site signals
    parking = lu_m["c_parking"] | (lu_m["parking_lo"] & ~lu_m["garage"])
    truly_empty = ((lu_m["asr_n"] == 0) | (lu_m["asr_barea"].fillna(0) == 0)) & \
                  (lu_m["total_comm"] == 0) & (lu_m["building_height_m"] < 2)
    vacant = lu_m["c_vacant"] | truly_empty
    commercial = lu_m["c_comm"] | (lu_m["retail"] > 0)
    signal = parking | vacant | commercial

    mask = no_housing & not_open & not_inst & not_offind & not_excl & low_rise & signal
    cand = lu_m[mask].copy().reset_index(drop=True)
    print(f"  after use/intensity/housing filters: {len(cand):,}")

    # --- SLR exclusion ---
    slr_valid = slr_m.geometry.make_valid()
    slr_union = slr_valid.union_all()
    in_slr = cand.geometry.centroid.within(slr_union)
    cand = cand[~in_slr].reset_index(drop=True)
    print(f"  after SLR (2100 inundation) exclusion: {len(cand):,}")

    # --- transit accessibility ---
    cand["transit_min"] = assign_transit_minutes(cand)
    cand = cand[cand["transit_min"].notna() & (cand["transit_min"] <= cutoff)].reset_index(drop=True)
    print(f"  after transit <= {cutoff} min to downtown: {len(cand):,}")

    if cand.empty:
        raise SystemExit("No candidates — check inputs.")

    # --- use-type label (for display / coloring) ---
    def use_type(r):
        if r["c_parking"] or (r["parking_lo"] and not r["garage"]):
            return "surface_parking"
        if r["c_comm"] or r["retail"] > 0:
            return "single_story_commercial"
        return "vacant"

    # --- typology + unit yield ---
    print("Assigning typology + unit yield …")
    cand["cand_idx"] = np.arange(len(cand))
    cand["use_type"] = cand.apply(use_type, axis=1)
    ctx = context_height(cand, foot_pts)
    cand["context_height_m"] = np.where(np.isnan(ctx), cand["building_height_m"], ctx)
    cand["typology"] = cand["context_height_m"].apply(pick_typology)
    dens = cand["typology"].map(C.TYPOLOGY_DENSITY_DU_PER_ACRE)
    raw_units = dens * cand["lot_area_acres"] * C.BUILDABLE_LOT_FRACTION
    cand["units"] = np.maximum(np.round(raw_units), C.MIN_UNITS_PER_CANDIDATE).astype(int)
    cand["net_new_units"] = cand["units"]

    # --- outputs ---
    out = cand.to_crs(C.WGS84)
    out["geometry"] = out.geometry.simplify(0.00002)  # ~2m, shrink file
    out["asr_stories"] = out["asr_stories"].round(0)
    out["asr_year"] = out["asr_year"].round(0)
    out["far"] = out["far"].round(2)
    out["building_height_m"] = out["building_height_m"].round(1)
    out["context_height_m"] = out["context_height_m"].round(1)
    out["lot_area_acres"] = out["lot_area_acres"].round(3)
    keep = [
        "mapblklot", "address", "use_type", "asr_class", "asr_use", "typology",
        "transit_min", "building_height_m", "asr_stories", "asr_year", "far",
        "context_height_m", "lot_area_acres", "units", "net_new_units",
        "resunits", "total_comm", "geometry",
    ]
    out = out[[c for c in keep if c in out.columns]]
    geojson = C.PROCESSED / "candidates.geojson"
    csv = C.PROCESSED / "candidates.csv"
    out.to_file(geojson, driver="GeoJSON")
    out.drop(columns="geometry").to_csv(csv, index=False)

    summary = {
        "cutoff_min": cutoff,
        "downtown_anchor": C.DOWNTOWN_NAME,
        "assessor_roll_year": C.ASSESSOR_ROLL_YEAR,
        "num_candidates": int(len(out)),
        "total_net_new_units": int(out["net_new_units"].sum()),
        "total_acres": round(float(cand["lot_area_acres"].sum()), 1),
        "by_use_type": out["use_type"].value_counts().to_dict(),
        "by_typology": out.groupby("typology")["net_new_units"].sum().astype(int).to_dict(),
        "units_by_use_type": out.groupby("use_type")["net_new_units"].sum().astype(int).to_dict(),
    }
    with open(C.PROCESSED / "candidates_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== Candidate summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved {geojson}\nSaved {csv}")


if __name__ == "__main__":
    main()
