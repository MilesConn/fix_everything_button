import os
import pandas as pd
from pathlib import Path

PROCESSED_DIR = Path("../data/processed")

# Economic Assumptions (based on research for Austin, Minneapolis, and general urban economics)
# Elasticity: A 1% increase in housing stock leads to an ELASTICITY% change in rent.
# Studies show varying numbers: Austin (~ -0.63%), Minneapolis (~ -1.1%). We use -0.8% as a baseline.
RENT_ELASTICITY = -0.8 

# Current SF Context
SF_CURRENT_HOUSING_STOCK = 410000  # Approx SF housing units
SF_CURRENT_AVERAGE_RENT = 3000     # Approx average rent in USD

# Development Assumptions
# If we upzone a candidate parcel, how many units on average can be built?
# This could be a function of lot size. For now, let's assume an average of 10 units per candidate lot.
UNITS_PER_LOT = 10

def run_economic_model():
    candidates_path = PROCESSED_DIR / "candidates.csv"
    
    df = pd.read_csv(candidates_path)
    num_candidates = len(df)
    print(f"Loaded {num_candidates} candidate parcels.")
    
    # Calculate total new units
    total_new_units = num_candidates * UNITS_PER_LOT
    
    # Calculate percentage increase in housing stock
    stock_increase_pct = (total_new_units / SF_CURRENT_HOUSING_STOCK) * 100
    
    # Calculate percentage drop in rent
    rent_drop_pct = stock_increase_pct * abs(RENT_ELASTICITY)
    
    # Calculate new average rent
    new_average_rent = SF_CURRENT_AVERAGE_RENT * (1 - (rent_drop_pct / 100))
    monthly_savings = SF_CURRENT_AVERAGE_RENT - new_average_rent
    
    print("\n--- Economic Model Results ---")
    print(f"Current SF Housing Stock: {SF_CURRENT_HOUSING_STOCK:,} units")
    print(f"Current Average Rent: ${SF_CURRENT_AVERAGE_RENT:,.2f}/month")
    print(f"\nCandidates for upzoning: {num_candidates:,} parcels")
    print(f"Assumed new units per lot: {UNITS_PER_LOT}")
    print(f"Total new units projected: {total_new_units:,} units")
    
    print(f"\nIncrease in Housing Stock: {stock_increase_pct:.2f}%")
    print(f"Rent Elasticity (Rent drop per 1% supply increase): {abs(RENT_ELASTICITY):.2f}%")
    
    print(f"\nProjected Rent Drop: {rent_drop_pct:.2f}%")
    print(f"Projected New Average Rent: ${new_average_rent:,.2f}/month")
    print(f"Monthly Savings per renter: ${monthly_savings:,.2f}")
    print("------------------------------\n")
    
    # Save output summary
    results = {
        "num_candidates": num_candidates,
        "new_units_projected": total_new_units,
        "stock_increase_pct": stock_increase_pct,
        "projected_rent_drop_pct": rent_drop_pct,
        "new_average_rent": new_average_rent,
        "monthly_savings": monthly_savings
    }
    
    import json
    with open(PROCESSED_DIR / "economic_impact.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("Saved economic impact summary to data/processed/economic_impact.json")

if __name__ == "__main__":
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    run_economic_model()
