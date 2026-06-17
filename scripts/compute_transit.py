"""Step 2 — Public-transit travel time to downtown (the accessibility "knob").

Builds a multimodal routable network from the SF street network (OSM) + the
Muni and BART GTFS schedules, then computes the door-to-door public-transit
travel time from the downtown anchor to a fine grid of points covering the city
(typical weekday AM peak, averaged over a one-hour departure window).

The output travel-time *surface* is what lets us (a) draw isochrone heatmaps and
(b) filter candidate parcels at any cutoff (45 / 50 / 60 min …) downstream —
i.e. the transit cutoff is a re-runnable knob, not a hard-coded radius.

Output:
    data/processed/transit_grid.geojson   point grid w/ minutes-to-downtown
    data/processed/transit_grid.csv        same, tabular (lon, lat, minutes)

Usage:
    uv run scripts/compute_transit.py
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import zipfile

# r5py needs Java 21; point JAVA_HOME at it before importing.
for _jh in ("/usr/lib/jvm/java-21-openjdk-amd64", os.environ.get("JAVA_HOME", "")):
    if _jh and os.path.isdir(_jh):
        os.environ["JAVA_HOME"] = _jh
        os.environ["PATH"] = f"{_jh}/bin:" + os.environ.get("PATH", "")
        break

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from shapely.geometry import Point  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import config as C  # noqa: E402


# --------------------------------------------------------------------------- #
# GTFS calendar normalization
# --------------------------------------------------------------------------- #
def normalize_gtfs(src_zip, out_zip) -> None:
    """Rewrite a GTFS feed to a clean 'typical weekday' calendar.

    Feeds of different vintages (archived Muni, current BART) never share a
    service date. We widen every calendar.txt service window to span
    2020-2040 (preserving the weekday flags) and drop calendar_dates.txt
    exceptions, so any ordinary weekday — including DEPARTURE_DATE — has full
    base service in both feeds. This is a deliberate, documented modeling
    choice: we route on representative weekday schedules, not one calendar day.
    """
    with zipfile.ZipFile(src_zip) as zin:
        names = zin.namelist()
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in names:
                base = name.split("/")[-1]
                if base == "calendar_dates.txt":
                    continue  # drop exceptions -> typical weekday
                data = zin.read(name)
                if base == "calendar.txt":
                    text = data.decode("utf-8-sig")
                    lines = text.splitlines()
                    header = lines[0].split(",")
                    si, ei = header.index("start_date"), header.index("end_date")
                    out = [lines[0]]
                    for ln in lines[1:]:
                        if not ln.strip():
                            continue
                        parts = ln.split(",")
                        parts[si], parts[ei] = "20200101", "20401231"
                        out.append(",".join(parts))
                    data = ("\n".join(out) + "\n").encode("utf-8")
                zout.writestr(name, data)


def normalized_feeds() -> list:
    norm_dir = C.GTFS / "normalized"
    if norm_dir.exists():
        shutil.rmtree(norm_dir)
    norm_dir.mkdir(parents=True)
    out = []
    for fname in C.GTFS_FEEDS:
        src = C.GTFS / fname
        dst = norm_dir / fname
        normalize_gtfs(src, dst)
        out.append(dst)
        print(f"  normalized {fname}")
    return out


# --------------------------------------------------------------------------- #
# Grid of destination points over SF land bbox
# --------------------------------------------------------------------------- #
def build_grid() -> gpd.GeoDataFrame:
    b = C.SF_BBOX
    corners = gpd.GeoDataFrame(
        geometry=[Point(b["min_lon"], b["min_lat"]), Point(b["max_lon"], b["max_lat"])],
        crs=C.WGS84,
    ).to_crs(C.SF_CRS_M)
    minx, miny = corners.geometry.iloc[0].x, corners.geometry.iloc[0].y
    maxx, maxy = corners.geometry.iloc[1].x, corners.geometry.iloc[1].y
    xs = np.arange(minx, maxx, C.GRID_SPACING_M)
    ys = np.arange(miny, maxy, C.GRID_SPACING_M)
    pts = [Point(x, y) for y in ys for x in xs]
    grid = gpd.GeoDataFrame(geometry=pts, crs=C.SF_CRS_M).to_crs(C.WGS84)
    grid["id"] = [f"g{i}" for i in range(len(grid))]
    return grid[["id", "geometry"]]


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #
def main() -> None:
    import r5py

    print("Normalizing GTFS calendars …")
    feeds = normalized_feeds()

    print("Building grid …")
    grid = build_grid()
    print(f"  {len(grid):,} destination points")

    origin = gpd.GeoDataFrame(
        {"id": ["downtown"]}, geometry=[Point(*C.DOWNTOWN)], crs=C.WGS84
    )

    print("Building transport network (OSM + Muni + BART) … (first build is slow)")
    network = r5py.TransportNetwork(str(C.OSM_FILE), [str(f) for f in feeds])

    y, m, d = (int(x) for x in C.DEPARTURE_DATE.split("-"))
    hh, mm, ss = (int(x) for x in C.DEPARTURE_TIME.split(":"))
    departure = dt.datetime(y, m, d, hh, mm, ss)

    print(f"Computing travel times from downtown @ {departure} …")
    tt = r5py.TravelTimeMatrix(
        network,
        origins=origin,
        destinations=grid,
        snap_to_network=True,
        departure=departure,
        departure_time_window=dt.timedelta(minutes=C.DEPARTURE_WINDOW_MIN),
        max_time=dt.timedelta(minutes=120),
        max_time_walking=dt.timedelta(minutes=C.MAX_WALK_MIN),
        transport_modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
    )
    tt = pd.DataFrame(tt)
    # columns: from_id, to_id, travel_time (median minutes over the window)
    tt = tt.rename(columns={"to_id": "id", "travel_time": "minutes"})[["id", "minutes"]]

    out = grid.merge(tt, on="id", how="left")
    out["lon"] = out.geometry.x
    out["lat"] = out.geometry.y

    reachable = out["minutes"].notna().sum()
    print(f"  reachable grid points: {reachable:,} / {len(out):,}")
    print(out["minutes"].describe())

    geojson = C.PROCESSED / "transit_grid.geojson"
    csv = C.PROCESSED / "transit_grid.csv"
    # GeoJSON (for the heatmap) keeps only reachable points; CSV keeps all rows
    # but downstream nearest-point assignment already ignores unreachable ones.
    out[out["minutes"].notna()].to_file(geojson, driver="GeoJSON")
    out.drop(columns="geometry").to_csv(csv, index=False)
    print(f"Saved {geojson}\nSaved {csv}")


if __name__ == "__main__":
    main()
