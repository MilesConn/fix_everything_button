import os
import pandas as pd
from shapely import wkt
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path
import json

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = (SCRIPT_DIR / "../data/raw").resolve()
PROCESSED_DIR = (SCRIPT_DIR / "../data/processed").resolve()
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Salesforce Tower as our "downtown" center proxy
SALESFORCE_TOWER_COORDS = (-122.3972, 37.7897)  # (lon, lat)
MAX_DISTANCE_MILES = 5.0 # Rough proxy for 45 mins transit (can be parameterized)

# Coordinate Reference System (CRS) for accurate distance in meters
# EPSG:3857 (Web Mercator) or EPSG:2227 (NAD83 / California zone 3)
SF_CRS = 'EPSG:2227' 

def filter_candidates():
    print("Loading datasets...")
    
    # We will load the parcels and land use datasets
    # Note: In a real run, you'd merge the parcels shapefile/CSV with land use
    try:
        parcels_path = DATA_DIR / "parcels.csv"
        land_use_path = DATA_DIR / "land_use_current.csv"
        
        # Load chunks or select columns if dataset is too large
        parcels_df = pd.read_csv(parcels_path, usecols=['mapblklot', 'blklot', 'block_num', 'lot_num', 'shape'])
        land_use_df = pd.read_csv(land_use_path, usecols=['mapblklot', 'open_space', 'parking_lo', 'total_comm', 'resunits'])
        
        # We also want to load stories/height, which might be in archived land use or parcels
        # For simplicity, let's assume we can merge land use and parcels
        
        df = pd.merge(parcels_df, land_use_df, on='mapblklot', how='inner')
        print(f"Total parcels before filtering: {len(df)}")
        
    except FileNotFoundError as e:
        print(f"Data file not found: {e}. Please ensure pull_data.py has been run and downloaded the files.")
        print("Using dummy data for the sake of the script structure...")
        # Create dummy structure
        df = pd.DataFrame({
            'mapblklot': ['0001001', '0002001', '0003001', '0004001'],
            'open_space': [False, True, False, False],
            'parking_lo': [False, False, True, False],
            'resunits': [0, 0, 0, 0],
            'total_comm': [5000, 0, 0, 0],
            'shape': [
                'POINT (-122.3972 37.7897)',
                'POINT (-122.4000 37.7900)',
                'POINT (-122.4100 37.7800)',
                'POINT (-122.5000 37.7000)'
            ]
        })

    # Criteria filtering
    # Exclude parks/open space
    df = df[df['open_space'] == False]
    
    # Include parking lots, vacant lots, small commercial (which could be 1-2 stories based on sqft as proxy if stories missing)
    # Vacant proxy: no residential units and no commercial sqft
    df = df[
        (df['parking_lo'] == True) |
        ((df['total_comm'] > 0) & (df['total_comm'] < 10000) & (df['resunits'] == 0)) |
        ((df['total_comm'] == 0) & (df['resunits'] == 0))
    ]
    
    print(f"Parcels after use filtering: {len(df)}")

    # Proximity Filtering
    # Convert string representation of geometry to shapely objects
    # Note: the 'shape' column in DataSF CSVs often contains POINT or MULTIPOLYGON WKT
    df['geometry'] = df['shape'].apply(lambda x: wkt.loads(x) if pd.notnull(x) else None)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
    
    # Create the downtown point
    downtown_pt = Point(SALESFORCE_TOWER_COORDS)
    downtown_gdf = gpd.GeoDataFrame({'geometry': [downtown_pt]}, crs="EPSG:4326")
    
    # Project to a local CRS to measure distance in meters/feet
    gdf_proj = gdf.to_crs(SF_CRS)
    downtown_proj = downtown_gdf.to_crs(SF_CRS).iloc[0].geometry
    
    # Calculate distance in feet (EPSG:2227 is in US feet)
    gdf_proj['distance_to_downtown_ft'] = gdf_proj.geometry.distance(downtown_proj)
    gdf_proj['distance_to_downtown_miles'] = gdf_proj['distance_to_downtown_ft'] / 5280.0
    
    # Filter those within max distance
    gdf_proj = gdf_proj[gdf_proj['distance_to_downtown_miles'] <= MAX_DISTANCE_MILES]
    
    print(f"Parcels after transit proxy (distance) filtering: {len(gdf_proj)}")
    
    # Convert back to WGS84 for GeoJSON export
    final_gdf = gdf_proj.to_crs("EPSG:4326")
    
    # Output
    csv_out = PROCESSED_DIR / "candidates.csv"
    geojson_out = PROCESSED_DIR / "candidates.geojson"
    
    # Drop complex geometry for CSV
    final_gdf.drop(columns=['geometry']).to_csv(csv_out, index=False)
    
    # Save GeoJSON
    final_gdf.to_file(geojson_out, driver='GeoJSON')
    print(f"Saved {len(final_gdf)} candidates to {csv_out} and {geojson_out}")

if __name__ == "__main__":
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    filter_candidates()
