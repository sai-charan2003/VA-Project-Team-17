import pandas as pd
from sodapy import Socrata
import matplotlib.pyplot as plt
import seaborn as sns
import sys

# --- CONFIGURATION ---
DATASET_ID = "cwsq-ngmh"  # CDC PLACES 2023 - Census Tract Data
APP_TOKEN = None  # Add Socrata App Token here if you have one for higher limits
CLIENT_URL = "chronicdata.cdc.gov"
MEASURE_ID = "CSMOKING"  # Current Smoking

def fetch_data():
    """
    Fetches Current Smoking data for all US Census Tracts.
    """
    print("Connecting to CDC Socrata API...")
    client = Socrata(CLIENT_URL, APP_TOKEN)
    
    # Query: Filter for Smoking measure, Crude Prevalence
    # Limit set to 100,000 to ensure we get all ~72k tracts
    print("Fetching data (this may take a moment)...")
    results = client.get(
        DATASET_ID, 
        measureid=MEASURE_ID,
        datavaluetypeid="CrdPrv", # Crude Prevalence
        limit=100000
    )
    
    df = pd.DataFrame.from_records(results)
    
    # Convert data_value to numeric
    df['data_value'] = pd.to_numeric(df['data_value'], errors='coerce')
    
    print(f"Data loaded: {len(df)} records found.")
    return df

def analyze_and_plot(df):
    """
    Performs the hierarchical drill-down analysis and plots graphs.
    """
    sns.set_theme(style="whitegrid")
    
    # 1. STATE WISE ANALYSIS
    # Group by State and calculate average smoking prevalence
    state_avg = df.groupby('stateabbr')['data_value'].mean().sort_values(ascending=False).head(10)
    
    plt.figure(figsize=(10, 6))
    sns.barplot(x=state_avg.index, y=state_avg.values, palette="Reds_r")
    plt.title("Top 10 States with Highest Avg Smoking Prevalence")
    plt.ylabel("Avg Smoking Prevalence (%)")
    plt.xlabel("State")
    plt.tight_layout()
    plt.savefig("1_state_level_analysis.png")
    plt.close()
    print("Generated: 1_state_level_analysis.png")

    # 2. COUNTY WISE ANALYSIS (Drill down into the #1 State)
    top_state = state_avg.index[0]
    print(f"\nDrilling down into Top State: {top_state}")
    
    state_df = df[df['stateabbr'] == top_state]
    county_avg = state_df.groupby('countyname')['data_value'].mean().sort_values(ascending=False).head(10)
    
    plt.figure(figsize=(12, 6))
    sns.barplot(x=county_avg.values, y=county_avg.index, palette="Reds_r")
    plt.title(f"Top 10 Counties in {top_state} by Smoking Prevalence")
    plt.xlabel("Avg Smoking Prevalence (%)")
    plt.ylabel("County")
    plt.tight_layout()
    plt.savefig("2_county_level_analysis.png")
    plt.close()
    print("Generated: 2_county_level_analysis.png")

    # 3. LOCAL (CENSUS TRACT) ANALYSIS (Drill down into the #1 County)
    top_county = county_avg.index[0]
    print(f"Drilling down into Top County: {top_county}")
    
    # Filter for the specific county in that state
    county_df = state_df[state_df['countyname'] == top_county].copy()
    
    # Sort by prevalence to find the worst neighborhoods
    top_tracts = county_df.sort_values(by='data_value', ascending=False).head(15)
    
    # Create a descriptive label for the tract (LocationName is usually FIPS, try to use it)
    # Note: PLACES data often has 'locationname' as the FIPS code.
    
    plt.figure(figsize=(10, 8))
    sns.barplot(x='data_value', y='locationname', data=top_tracts, palette="dark:red")
    
    # Add vertical line for State Average for context
    plt.axvline(state_df['data_value'].mean(), color='blue', linestyle='--', label=f'{top_state} Avg')
    plt.axvline(county_df['data_value'].mean(), color='orange', linestyle='--', label=f'{top_county} Avg')
    
    plt.title(f"Top 15 High-Risk Neighborhoods (Census Tracts)\nIn {top_county}, {top_state}")
    plt.xlabel("Smoking Prevalence (%)")
    plt.ylabel("Census Tract FIPS Code")
    plt.legend()
    plt.tight_layout()
    plt.savefig("3_census_tract_level_analysis.png")
    plt.close()
    print("Generated: 3_census_tract_level_analysis.png")
    
    # Output the actionable data
    print("\n--- ACTIONABLE INSIGHTS FOR BILLBOARDS ---")
    print(f"Target these specific neighborhoods in {top_county}, {top_state}:")
    print(top_tracts[['locationname', 'data_value', 'totalpopulation']].to_string(index=False))

if __name__ == "__main__":
    try:
        df = fetch_data()
        analyze_and_plot(df)
        print("\nAnalysis Complete. Check the generated PNG files.")
    except Exception as e:
        print(f"An error occurred: {e}")
