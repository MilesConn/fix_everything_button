"""Step 1 — Pull all raw inputs (reproducible).

Pulls:
  * DataSF (Socrata) tabular datasets  -> data/raw/*.csv
  * GTFS transit feeds (Muni, BART)    -> data/gtfs/*.zip
  * San Francisco OSM street network   -> data/osm/san_francisco.osm.pbf

Everything is idempotent: existing files are kept unless --force is passed.

Usage:
    uv run scripts/pull_data.py            # pull anything missing
    uv run scripts/pull_data.py --force    # re-pull everything
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
import config as C  # noqa: E402

load_dotenv(C.ROOT / ".env")
load_dotenv(C.ROOT / ".env.secrets")  # optional, per project INSTRUCTIONS
APP_TOKEN = os.getenv("SF_OPENDATA_API_KEY") or None

UA = "make-room-sf/1.0 (housing-capacity research; reproducible pipeline)"
PAGE = 50_000


def _headers() -> dict:
    h = {"User-Agent": UA}
    if APP_TOKEN:
        h["X-App-Token"] = APP_TOKEN
    return h


def _get(url: str, *, stream: bool = False, max_time: int = 120, retries: int = 5):
    last = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=_headers(), stream=stream, timeout=max_time)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        wait = min(2 ** attempt, 30)
        print(f"    [attempt {attempt}] {last}; retrying in {wait}s")
        time.sleep(wait)
    raise RuntimeError(f"Failed to GET {url}: {last}")


def download_socrata(filename: str, resource_id: str, desc: str, force: bool) -> None:
    out = C.RAW / filename
    if out.exists() and not force:
        print(f"[skip] {filename} exists ({out.stat().st_size/1e6:.1f} MB) — {desc}")
        return
    print(f"[pull] {filename}  ({resource_id}) — {desc}")
    offset, first = 0, True
    with open(out, "wb") as f:
        while True:
            url = (
                f"https://{C.SF_DOMAIN}/resource/{resource_id}.csv"
                f"?$limit={PAGE}&$offset={offset}&$order=:id"
            )
            print(f"    offset {offset:,} …")
            lines = _get(url).content.splitlines(keepends=True)
            if not lines or (len(lines) <= 1 and not first):
                break
            f.writelines(lines if first else lines[1:])
            first = False
            if len(lines) - 1 < PAGE:
                break
            offset += PAGE
            time.sleep(0.5)
    print(f"    -> {out} ({out.stat().st_size/1e6:.1f} MB)")


def download_socrata_query(filename: str, resource_id: str, params: dict, desc: str, force: bool) -> None:
    """Pull a Socrata dataset with a custom $select / $where, paginated."""
    import urllib.parse

    out = C.RAW / filename
    if out.exists() and not force:
        print(f"[skip] {filename} exists ({out.stat().st_size/1e6:.1f} MB) — {desc}")
        return
    print(f"[pull] {filename}  ({resource_id}) — {desc}")
    offset, first = 0, True
    base_params = {k: v for k, v in params.items() if k != "$limit"}
    with open(out, "wb") as f:
        while True:
            q = dict(base_params)
            q["$limit"] = PAGE
            q["$offset"] = offset
            q["$order"] = ":id"
            url = (
                f"https://{C.SF_DOMAIN}/resource/{resource_id}.csv?"
                + urllib.parse.urlencode(q, safe="(),=:$")
            )
            print(f"    offset {offset:,} …")
            lines = _get(url).content.splitlines(keepends=True)
            if not lines or (len(lines) <= 1 and not first):
                break
            f.writelines(lines if first else lines[1:])
            first = False
            if len(lines) - 1 < PAGE:
                break
            offset += PAGE
            time.sleep(0.5)
    print(f"    -> {out} ({out.stat().st_size/1e6:.1f} MB)")


def download_file(url: str, out, force: bool, label: str) -> None:
    if out.exists() and not force:
        print(f"[skip] {out.name} exists ({out.stat().st_size/1e6:.1f} MB) — {label}")
        return
    print(f"[pull] {out.name} — {label}\n    {url}")
    r = _get(url, stream=True, max_time=180)
    tmp = out.with_suffix(out.suffix + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    tmp.replace(out)
    print(f"    -> {out} ({out.stat().st_size/1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-pull everything")
    ap.add_argument("--skip-osm", action="store_true", help="skip the large OSM extract")
    args = ap.parse_args()

    print("== DataSF tabular datasets ==")
    for fname, (rid, desc) in C.SOCRATA_DATASETS.items():
        download_socrata(fname, rid, desc, args.force)

    print("\n== DataSF custom queries (assessor roll, boundary) ==")
    for fname, (rid, params, desc) in C.SOCRATA_QUERIES.items():
        download_socrata_query(fname, rid, params, desc, args.force)

    print("\n== GTFS transit feeds ==")
    for fname, url in C.GTFS_FEEDS.items():
        download_file(url, C.GTFS / fname, args.force, "transit schedule")

    if not args.skip_osm:
        print("\n== OSM street network ==")
        download_file(C.OSM_URL, C.OSM_FILE, args.force, "San Francisco street network")

    print("\nData pull complete.")


if __name__ == "__main__":
    main()
