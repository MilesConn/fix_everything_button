"""Step 3 — Select upzoning candidates (criteria + typology + unit yield).

Replicates the PAU "soft site" logic for San Francisco and goes further by using
real transit travel times (from compute_transit.py) instead of a flat radius.

A parcel is a candidate iff ALL hold:
  1. it is not protected open space / park,
  2. it has no meaningful existing housing to demolish (resunits <= threshold),
  3. it is underutilized — a surface parking lot, OR effectively vacant /
     single-/low-story (tallest building <= SINGLE_STORY_MAX_HEIGHT_M),
  4. it is outside the 2100 sea-level-rise inundation zone,
  5. public-transit travel time to downtown <= the chosen cutoff (default 45).

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


def _load_polygons(csv, geom_col, cols, name):
    print(f"  reading {name} …")
    df = pd.read_csv(csv, usecols=lambda c: c == geom_col or c in cols, low_memory=False)
    df = df[df[geom_col].notna()].copy()
    geom = gpd.GeoSeries.from_wkt(df[geom_col], crs=C.WGS84)
    gdf = gpd.GeoDataFrame(df.drop(columns=[geom_col]), geometry=geom, crs=C.WGS84)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    print(f"    {len(gdf):,} {name}")
    return gdf


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
        ["mapblklot", "resunits", "total_comm", "parking_lo", "garage", "open_space"],
        "land-use parcels",
    )
    foot = _load_polygons(
        C.RAW / "building_footprints.csv", "shape",
        ["mblr", "hgt_median_m"], "building footprints",
    )
    slr = _load_polygons(C.RAW / "slr_66in.csv", "the_geom", [], "SLR polygons")

    # --- normalize types ---
    lu["resunits"] = pd.to_numeric(lu["resunits"], errors="coerce").fillna(0)
    lu["total_comm"] = pd.to_numeric(lu["total_comm"], errors="coerce").fillna(0)
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

    lu_m["lot_area_m2"] = lu_m.geometry.area
    lu_m["lot_area_acres"] = lu_m["lot_area_m2"] / 4046.8564224

    # --- building height per parcel (max footprint height whose centroid is in parcel) ---
    print("Joining building heights to parcels …")
    j = gpd.sjoin(foot_pts[["height_m", "geometry"]], lu_m[["geometry"]],
                  how="inner", predicate="within")
    parcel_h = j.groupby("index_right")["height_m"].max()
    lu_m["building_height_m"] = lu_m.index.map(parcel_h).fillna(0.0)

    # --- criteria ---
    print("Applying criteria …")
    not_open = ~lu_m["open_space"]
    no_housing = lu_m["resunits"] <= C.MAX_EXISTING_RES_UNITS
    surface_parking = lu_m["parking_lo"] & ~lu_m["garage"]
    low_built = lu_m["building_height_m"] <= C.SINGLE_STORY_MAX_HEIGHT_M
    underutilized = surface_parking | (low_built & no_housing)

    def use_type(r):
        if r["parking_lo"] and not r["garage"]:
            return "surface_parking"
        if r["building_height_m"] <= 1.0 and r["total_comm"] == 0:
            return "vacant"
        if r["total_comm"] > 0:
            return "single_story_commercial"
        return "low_intensity"

    mask = not_open & no_housing & underutilized
    cand = lu_m[mask].copy().reset_index(drop=True)
    print(f"  after use/height/housing filters: {len(cand):,}")

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
    # never count below ground we already remove existing housing (resunits<=1)
    cand["net_new_units"] = cand["units"]

    # --- outputs ---
    out = cand.to_crs(C.WGS84)
    out["geometry"] = out.geometry.simplify(0.00002)  # ~2m, shrink file
    keep = [
        "mapblklot", "use_type", "typology", "transit_min",
        "building_height_m", "context_height_m", "lot_area_acres",
        "units", "net_new_units", "resunits", "total_comm", "geometry",
    ]
    out = out[keep]
    geojson = C.PROCESSED / "candidates.geojson"
    csv = C.PROCESSED / "candidates.csv"
    out.to_file(geojson, driver="GeoJSON")
    out.drop(columns="geometry").to_csv(csv, index=False)

    summary = {
        "cutoff_min": cutoff,
        "downtown_anchor": C.DOWNTOWN_NAME,
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
