"""Central configuration for the "Make Room for San Francisco" pipeline.

Every tunable knob, data source, and economic assumption lives here so the
analysis is transparent and reproducible. See docs/METHODOLOGY.md for the
narrative and citations.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
GTFS = DATA / "gtfs"
OSM = DATA / "osm"
PROCESSED = DATA / "processed"
SITE_DATA = ROOT / "site" / "static" / "data"

for _d in (RAW, GTFS, OSM, PROCESSED):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# DataSF (Socrata) resources
# --------------------------------------------------------------------------- #
SF_DOMAIN = "data.sfgov.org"

SOCRATA_DATASETS = {
    # filename: (resource_id, human description)
    "parcels.csv": ("acdm-wktn", "Parcels – Active and Retired (geometry, zoning code)"),
    "land_use_current.csv": ("c5ge-t6pj", "Land Use (use flags: parking, commercial sqft, residential units)"),
    "zoning_districts.csv": ("xzez-p3nc", "Zoning Districts (base zoning + height/bulk)"),
    "building_footprints.csv": ("ynuv-fyni", "Building Footprints w/ LiDAR heights (2017 survey)"),
    "slr_66in.csv": ("6ann-usi8", "100-yr storm + 66in Sea Level Rise (2100 inundation zone)"),
}

# Datasets that need a custom Socrata query ($select / $where) rather than a full
# table dump. Pulled by pull_data.download_socrata_query().
#   filename: (resource_id, params, description)
ASSESSOR_ROLL_YEAR = 2024  # latest closed secured-roll year (authoritative, current)
SOCRATA_QUERIES = {
    # The Assessor secured roll is the authoritative, *current* source of what is
    # actually built on each parcel: stories, units, year built, building area,
    # and a clean property-class code. It corrects the stale land-use unit counts
    # and the 2017-vintage LiDAR (which misses every post-2017 building).
    "assessor_roll.csv": (
        "wv5m-vpq2",
        {
            "$select": (
                "block,lot,property_location,property_class_code,"
                "property_class_code_definition,use_definition,year_property_built,"
                "number_of_stories,number_of_units,property_area,lot_area,the_geom"
            ),
            "$where": f"closed_roll_year={ASSESSOR_ROLL_YEAR}",
        },
        f"Assessor secured property roll {ASSESSOR_ROLL_YEAR} (stories/units/year/class)",
    ),
    # SF land boundary (SF Find Neighborhoods) — used to clip the travel-time
    # heatmap and candidates to the city, dropping Daly City / Oakland / open bay.
    "sf_neighborhoods.csv": (
        "gfpk-269f",
        {"$select": "name,the_geom", "$limit": "5000"},
        "SF Find Neighborhoods (city land boundary for clipping)",
    ),
}

# --------------------------------------------------------------------------- #
# Transit feeds (GTFS) + street network (OSM)
# --------------------------------------------------------------------------- #
# Muni's live endpoint (gtfs.sfmta.com) is license-gated and not reachable from
# CI; we use the last freely-archived full feed via the Wayback Machine. Supply
# a 511.org API key in .env (FIVEONEONE_API_KEY) to fetch a current regional
# feed instead (see pull_data.py).
GTFS_FEEDS = {
    "muni.zip": "https://web.archive.org/web/20221226083451id_/http://gtfs.sfmta.com/transitdata/google_transit.zip",
    "bart.zip": "https://www.bart.gov/dev/schedules/google_transit.zip",
}

# San Francisco OSM extract (BBBike), used by r5py for walking access/egress.
OSM_URL = "https://download.bbbike.org/osm/bbbike/SanFrancisco/SanFrancisco.osm.pbf"
OSM_FILE = OSM / "san_francisco.osm.pbf"

# --------------------------------------------------------------------------- #
# Geography
# --------------------------------------------------------------------------- #
WGS84 = "EPSG:4326"
# NAD83 / California zone 3 (US feet) – accurate planar distances in SF.
SF_CRS_FT = "EPSG:2227"
# Web-mercator-ish meters for area math when needed.
SF_CRS_M = "EPSG:26910"  # UTM 10N (meters)

# Downtown anchor = Salesforce Transit Center / Montgomery core (lon, lat).
DOWNTOWN = (-122.39681, 37.78962)
DOWNTOWN_NAME = "Salesforce Transit Center (downtown core)"

# Bounding box for the SF land grid used to render isochrones (lon/lat).
# Excludes the Farallon Islands and most open bay.
SF_BBOX = {"min_lon": -122.515, "max_lon": -122.355, "min_lat": 37.706, "max_lat": 37.833}
GRID_SPACING_M = 200  # isochrone grid resolution

# --------------------------------------------------------------------------- #
# Transit routing parameters
# --------------------------------------------------------------------------- #
# A canonical "typical weekday" departure. Both feeds are normalized so this
# date is an ordinary weekday with full service (see compute_transit.py).
DEPARTURE_DATE = "2026-11-18"          # a Wednesday
DEPARTURE_TIME = "08:00:00"            # AM peak
DEPARTURE_WINDOW_MIN = 60              # average over an hour (frequency smoothing)
MAX_WALK_MIN = 20                      # max access/egress walk leg
TRANSIT_MODES = ("WALK", "TRANSIT")

# --------------------------------------------------------------------------- #
# Upzoning / candidate-selection criteria (the "knobs")
# --------------------------------------------------------------------------- #
# Default transit-accessibility cutoff (minutes to downtown). The pipeline also
# emits the full travel-time surface so any cutoff can be applied downstream.
TRANSIT_CUTOFFS_MIN = [30, 45, 60]
DEFAULT_CUTOFF_MIN = 45

# "Underutilized" building height: a parcel whose tallest building is at or
# below this height (meters) is treated as effectively single-/low-story and a
# candidate for additional stories. ~1 story ≈ 3.5–4.5 m; we use 9 m (≈ up to 2
# low stories) to capture single-story commercial "taxpayer" buildings. This is
# a *secondary* guard now — a parcel with a LiDAR building taller than this is
# rejected even if the (current) assessor roll calls it low-rise.
SINGLE_STORY_MAX_HEIGHT_M = 9.0

# Authoritative story cap from the assessor roll. PAU targets single-story
# "taxpayer" commercial; we require at most this many stories on any existing
# building (vacant / parking lots have 0). Set to 1 to be deliberately strict.
MAX_SOFT_SITE_STORIES = 1

# Floor-area-ratio (built sqft / lot sqft) ceiling. A genuinely underutilized
# soft site has lots of unused development rights, i.e. a low FAR. This is the
# backstop that rejects any dense or mis-joined parcel (e.g. a tower whose roll
# record lost its story count) regardless of the height/story signals.
MAX_SOFT_SITE_FAR = 1.2

# A parcel counts as having no existing housing to demolish if it has at most
# this many residential units (per BOTH the land-use file and the current
# assessor roll). PAU's rule is "no demolition of any home", so we require zero.
MAX_EXISTING_RES_UNITS = 0

# Don't treat a recently-completed building as a soft site even if other signals
# lag: any parcel whose assessor year-built is at or after this is excluded.
RECENT_BUILD_YEAR = 2015

# --------------------------------------------------------------------------- #
# Assessor property-class-code taxonomy (drives use-based eligibility)
# --------------------------------------------------------------------------- #
# Civic / institutional / medical / government / public land — NEVER upzoned
# (libraries, schools, churches, hospitals, fire/police, consulates, clubs,
# golf courses, theatres, and all government / public-owned + public-vacant).
ASSESSOR_INSTITUTIONAL_CLASSES = {
    "E", "EG", "LIBG", "W", "N1", "N1G", "N2", "N2G", "FIRG", "POLG", "CONG",
    "SP", "U", "UG", "GC", "T", "PI", "VG", "VPUB", "VSP",
}
# Existing housing (any of these means the parcel already holds homes).
ASSESSOR_RESIDENTIAL_CLASSES = {
    "D", "DA", "DA5", "DA15", "DBM", "DCON", "DD", "DD5", "DD15", "DF", "F",
    "F2", "F5", "F15", "FA", "FA5", "FS", "FS5", "FS15", "A", "A5", "A5G",
    "A15", "AC", "ACG", "AG", "Z", "ZBM", "ZEU", "LZ", "LZBM", "CO", "COS",
    "TH", "THBM", "TIC", "TIA", "TI15", "PD", "RH", "RH1", "RHG", "XV",
    "OA", "OA5", "OA15",
}
# Office / industrial buildings (PAU does not target these for conversion).
ASSESSOR_OFFICE_INDUSTRIAL_CLASSES = {
    "O", "O35", "OAH", "OAL", "OBH", "OBM", "OC", "OCH", "OCL", "OCM", "OG",
    "OMD", "OZ", "OZEU", "B", "BZ", "I", "IDC", "IG", "IW", "IX", "IXG", "IZ",
}
# Other structures that are NOT soft sites: parking *garages* (vs. surface
# lots), hotels/motels (occupied buildings), under-water lots, and misc.
ASSESSOR_EXCLUDE_CLASSES = {
    "G", "GG", "GZ", "PLG", "PZ",              # parking garages / stall condos
    "H", "H1", "H2", "HC", "HG", "M", "MG",    # hotels / motels
    "UWL",                                     # under-water lots
    "X",                                       # misc / unclassified
}
# Positive soft-site signals -------------------------------------------------
ASSESSOR_PARKING_CLASSES = {"PL"}                       # surface parking lot only
ASSESSOR_VACANT_CLASSES = {"V", "VR", "VRX", "VCI", "VA15", "TDR"}
ASSESSOR_COMMERCIAL_CLASSES = {"C", "CZ", "CM", "C1", "CD", "CG", "C1G", "S"}

# --------------------------------------------------------------------------- #
# Housing-typology yields (units the upzoned parcel could hold)
# --------------------------------------------------------------------------- #
# Conservative net density (homes per acre) by context typology, matched to the
# median building height of the surrounding neighborhood (à la PAU's low/mid/
# high-rise context matching). Calibrated to realistic SF multifamily projects.
#   low-rise  : 3-4 stories     ~ 75 du/acre
#   mid-rise  : 5-8 stories     ~ 135 du/acre
#   high-rise : 9+ stories      ~ 250 du/acre
TYPOLOGY_DENSITY_DU_PER_ACRE = {"low": 75, "mid": 135, "high": 250}
# Neighborhood-context height (m) thresholds that pick the typology.
TYPOLOGY_CONTEXT_HEIGHT_M = {"low": 12.0, "mid": 25.0}  # else "high"
# Share of lot realistically buildable after setbacks/streets/feasibility.
BUILDABLE_LOT_FRACTION = 0.70
# Floor for tiny lots (a parcel that clears all criteria yields >= this).
MIN_UNITS_PER_CANDIDATE = 2

# --------------------------------------------------------------------------- #
# Economic model (rent impact) – see docs/METHODOLOGY.md §5 for citations.
# --------------------------------------------------------------------------- #
# Current SF context (documented constants, with sources).
SF_HOUSING_UNITS = 407_000          # ACS 2022 5-yr housing units, City & County of SF
SF_AVERAGE_RENT = 3_200             # Zillow Observed Rent Index, SF (2024), all bedrooms
SF_RENTER_HOUSEHOLDS = 230_000      # ACS: ~57% of ~362k SF households are renters

# Metro stock elasticity of rent: % change in rent per 1% change in housing
# stock. Central = -0.5 (Pew 2025: +10% metro stock ⇒ rents grew ~5% less).
# Band spans the credible causal range.
RENT_ELASTICITY = {"conservative": -0.25, "central": -0.50, "optimistic": -1.00}

ELASTICITY_SOURCES = [
    "Pew Charitable Trusts (2025): +10% metro housing stock ⇒ rents grew ~5% "
    "less over 2017–2024 across 1,654 Zillow ZIPs ⇒ stock elasticity ≈ -0.5; "
    "regional supply ~4x more effective than purely local supply.",
    "Mense (2025, J. Pol. Econ. Macro): 1% increase in new (flow) supply lowers "
    "rents ~0.19% via moving chains; short-run demand elasticity ≈ -0.025.",
    "Pennington (2021, UC Berkeley): in SF, new construction cuts rents ~2% "
    "within 100m and lowers displacement risk ~17% (fire-instrument, causal).",
    "Asquith, Mast & Reed (2023, Rev. Econ. Stat.): large new buildings in "
    "low-income areas cut nearby rents 5–7% vs. counterfactual.",
    "Austin natural experiment (2022–24): ~+13% multifamily stock over ~2 yrs "
    "coincided with ~-15% asking rents — a real-world upper-bound cross-check.",
]

# Buildout phasing (years) for translating a large stock shock into annual,
# defensible marginal steps rather than one implausible linear jump.
BUILDOUT_PHASE_YEARS = 15


# --------------------------------------------------------------------------- #
# San Francisco land boundary (for clipping the heatmap / candidates to the city)
# --------------------------------------------------------------------------- #
def sf_boundary_union(buffer_m: float = 150.0):
    """Return the SF land boundary as one (slightly buffered) WGS84 polygon.

    Built by unioning the SF Find Neighborhoods polygons. The small buffer keeps
    grid points that fall in streets / on the shoreline edge. Cached on disk-read.
    """
    import geopandas as gpd
    import pandas as pd

    df = pd.read_csv(RAW / "sf_neighborhoods.csv")
    df = df[df["the_geom"].notna()]
    g = gpd.GeoSeries.from_wkt(df["the_geom"], crs=WGS84).make_valid()
    union_m = g.to_crs(SF_CRS_M).union_all().buffer(buffer_m)
    return gpd.GeoSeries([union_m], crs=SF_CRS_M).to_crs(WGS84).iloc[0]
