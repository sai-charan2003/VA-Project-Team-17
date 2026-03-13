import streamlit as st
import pandas as pd
from sodapy import Socrata
import plotly.express as px
from urllib.request import urlopen
import json

# ==========================================
# Configuration & Setup
# ==========================================
st.set_page_config(
    page_title="HealthLens - Public Health Anti-Smoking AI Strategy",
    layout="wide"
)

# ==========================================
# Styling & Theme
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Google+Sans+Flex:opsz,wght@8..144,100..1000&display=swap');

    /* Apply to main app container and standard text elements */
    .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp li, .stApp label {
        font-family: 'Google Sans Flex', sans-serif !important;
    }

    /* Target Streamlit specific text containers while avoiding icons */
    .stMarkdown, .stDataFrame, .stTable, .stSelectbox label, .stSlider label {
        font-family: 'Google Sans Flex', sans-serif !important;
    }
    
    /* Make headers pop with the variable weight */
    h1, h2, h3 {
        font-variation-settings: "wght" 700, "opsz" 14;
    }
    </style>
    """, unsafe_allow_html=True)

# Load counties geojson for mapping - used in Tab 1 and Tab 3
@st.cache_data
def load_county_geojson():
    with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
        return json.load(response)

# Note: Tract-level mapping for Tab 2 is complex without a specific state geojson. 
# We will use scatter_mapbox or point-based maps if geojson is unavailable, 
# but for this implementation, we will use choropleth for Counties/States and 
# visual indicators for tracts.

# ==========================================
# Data Loading & Transformation
# ==========================================
@st.cache_data(ttl=86400)
def fetch_and_prepare_data():
    """
    Fetches CDC PLACES data, converts it to wide format, and prepares the study dataframe.
    """
    client = Socrata("chronicdata.cdc.gov", None, timeout=120)
    
    # MeasureIds
    # CSMOKING: Current cigarette smoking among adults
    # COPD: COPD among adults
    
    # Optimization: Fetch only needed columns
    select_cols = "locationid, stateabbr, statedesc, countyname, countyfips, year, measureid, data_value, totalpop18plus, geolocation"
    
    # Fetch Smoking Data
    results_smoking = client.get("cwsq-ngmh", measureid="CSMOKING", select=select_cols, limit=100000)
    df_smoking = pd.DataFrame.from_records(results_smoking)
    
    # Fetch COPD Data
    results_copd = client.get("cwsq-ngmh", measureid="COPD", select=select_cols, limit=100000)
    df_copd = pd.DataFrame.from_records(results_copd)
    
    if df_smoking.empty or df_copd.empty:
        return pd.DataFrame()

    # Data Preparation Steps
    # 5. Convert prevalence and population columns into numeric values
    for df in [df_smoking, df_copd]:
        df['data_value'] = pd.to_numeric(df['data_value'], errors='coerce')
        df['totalpop18plus'] = pd.to_numeric(df['totalpop18plus'], errors='coerce')
        # 6. Remove rows with missing values
        df.dropna(subset=['data_value', 'totalpop18plus'], inplace=True)

    # 3. Convert dataset from long format into wide format
    # Join keys: LocationID, StateAbbr, CountyName, Year
    # We also keep statedesc and countyfips for mapping
    df_smoking = df_smoking.rename(columns={'data_value': 'Smoking_Prevalence'})
    df_copd = df_copd.rename(columns={'data_value': 'COPD_Prevalence'})
    
    # Drop measureid as it's now encoded in column name
    df_smoking.drop(columns=['measureid'], inplace=True)
    df_copd.drop(columns=['measureid'], inplace=True)
    
    # 4. Use LocationID, StateAbbr, CountyName, and Year as the join keys
    # Note: totalpop18plus should be the same on both as it's tract-level census data
    wide_df = pd.merge(
        df_smoking, 
        df_copd[['locationid', 'year', 'COPD_Prevalence']], 
        on=['locationid', 'year'], 
        how='inner'
    )
    
    # Rename for clarity
    wider_df = wide_df.rename(columns={'totalpop18plus': 'Population (18+)'})
    
    # Calculate Metrics
    # Estimated Smokers = Population (18+) × Smoking Prevalence (as fraction)
    wider_df['Estimated_Smokers'] = (wider_df['Population (18+)'] * (wider_df['Smoking_Prevalence'] / 100)).astype(int)
    
    # Overlap Score highlights areas where both smoking and COPD are high
    wider_df['Overlap_Score'] = (wider_df['Smoking_Prevalence'] * wider_df['COPD_Prevalence']).round(4)
    
    # Extract Lat/Lon from geolocation for neighborhood mapping
    # CDC Socrata returns: {'type': 'Point', 'coordinates': [longitude, latitude]}
    def extract_lat(loc):
        try:
            if isinstance(loc, dict) and 'coordinates' in loc:
                return float(loc['coordinates'][1])
        except (IndexError, TypeError, ValueError):
            return None
        return None

    def extract_lon(loc):
        try:
            if isinstance(loc, dict) and 'coordinates' in loc:
                return float(loc['coordinates'][0])
        except (IndexError, TypeError, ValueError):
            return None
        return None
    
    wider_df['lat'] = wider_df['geolocation'].apply(extract_lat)
    wider_df['lon'] = wider_df['geolocation'].apply(extract_lon)

    # Ensure year is numeric for filtering and sorting
    wider_df['year'] = pd.to_numeric(wider_df['year'], errors='coerce')
    
    return wider_df

# Load Data
county_geojson = load_county_geojson()
raw_tract_df = fetch_and_prepare_data()

# ==========================================
# Sidebar UI
# ==========================================
st.sidebar.markdown("**Team 17: Billboard Logic**")

if raw_tract_df.empty:
    st.error("Could not fetch data from CDC API. Check your internet connection or API status.")
    st.stop()

# Sidebar Filters
st.sidebar.header("Geography Filters")
all_states = sorted(raw_tract_df['stateabbr'].unique())
selected_state = st.sidebar.selectbox("Select State", options=["All"] + all_states)

# Year Filter (default to latest available year)
available_years = sorted(raw_tract_df['year'].dropna().unique())
default_year = max(available_years) if available_years else None
selected_year = st.sidebar.selectbox(
    "Select Year",
    options=available_years,
    index=available_years.index(default_year) if default_year in available_years else 0
)

st.sidebar.header("Ranking Preference")
rank_metric = st.sidebar.selectbox(
    "Rank By",
    options=["Estimated Smokers (Reach)", "Smoking Prevalence (%)"]
)

if selected_state != "All":
    state_filtered = raw_tract_df[raw_tract_df['stateabbr'] == selected_state]
    all_counties = sorted(state_filtered['countyname'].unique())
    selected_county = st.sidebar.selectbox("Select County", options=["All"] + all_counties)
else:
    state_filtered = raw_tract_df
    selected_county = "All"

# Apply Geography Filters
filtered_df = state_filtered.copy()

# Always apply year filter (used across all tabs)
if selected_year is not None:
    filtered_df = filtered_df[filtered_df['year'] == selected_year]

# Also keep a year-only filtered dataset for state overview (ignores county filter)
year_filtered_df = raw_tract_df.copy()
if selected_year is not None:
    year_filtered_df = year_filtered_df[year_filtered_df['year'] == selected_year]

if selected_county != "All":
    filtered_df = filtered_df[filtered_df['countyname'] == selected_county]



# ==========================================
# Main Layout
# ==========================================
st.title("Public Health Billboard Strategy: Anti-Smoking")

tab1, tab2, tab3, tab4 = st.tabs([
    "Neighborhood Deep Dive (Tracts)", 
    "County Level Targeting", 
    "State Level Overview",
    "Phase 2: Health ROI (COPD)"
])

# ------------------------------------------
# TAB 1: Neighborhood Deep Dive (Census Tract Level)
# ------------------------------------------
with tab1:
    st.header("Neighborhood Deep Dive (Census Tracts)")
    st.write("Precision targeting for community-level billboard placement using census tract data.")
    
    # Use the LocationID column which represents census tracts
    tract_df = filtered_df.copy()
    # Sort by selected ranking metric
    tract_sort_col = 'Estimated_Smokers' if rank_metric.startswith("Estimated") else 'Smoking_Prevalence'
    tract_df = tract_df.sort_values(by=tract_sort_col, ascending=False)
    # Filter tracts with no population or zero smokers to clean up report
    tract_df = tract_df[tract_df['Estimated_Smokers'] > 0]
    tract_df['Rank'] = range(1, len(tract_df) + 1)
    
    st.subheader(f"Ranked Census Tracts — {rank_metric}")
    st.dataframe(
        # Columns: Rank, State, County, LocationID (Census tract), Smoking prevalence percent, Population (18+), Estimated smokers
        tract_df[['Rank', 'stateabbr', 'countyname', 'locationid', 'Smoking_Prevalence', 'Population (18+)', 'Estimated_Smokers']],
        use_container_width=True, hide_index=True
    )
    
    # Top-N tracts bar chart for clear prioritization
    tract_top_n = st.slider("Top N Tracts", min_value=5, max_value=50, value=15, step=5)
    tract_top = tract_df.head(tract_top_n).copy()
    tract_metric = 'Estimated_Smokers' if rank_metric.startswith("Estimated") else 'Smoking_Prevalence'
    tract_title = "Top Tracts by Estimated Smokers (Reach)" if tract_metric == 'Estimated_Smokers' else "Top Tracts by Smoking Prevalence (%)"
    tract_top['tract_label'] = tract_top['countyname'] + " • " + tract_top['locationid'].astype(str)
    fig_tract_bar = px.bar(
        tract_top,
        x=tract_metric,
        y='tract_label',
        color='stateabbr',
        orientation='h',
        title=tract_title,
        labels={tract_metric: rank_metric, 'tract_label': 'Tract (County • ID)'},
        hover_data=['countyname', 'stateabbr', 'Smoking_Prevalence', 'Estimated_Smokers']
    )
    fig_tract_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_tract_bar, use_container_width=True)
    
    st.subheader("Neighborhood Smoking Density (Heat Map)")
    st.info("Showing concentration of smoking prevalence across all neighborhoods.")
    
    # Neighborhood Density Heatmap (High Performance for all tracts)
    heat_metric = 'Estimated_Smokers' if rank_metric.startswith("Estimated") else 'Smoking_Prevalence'
    heat_title = "High-Resolution Reach Hotspots" if heat_metric == 'Estimated_Smokers' else "High-Resolution Smoking Prevalence Hotspots"
    fig_neighborhood_map = px.density_mapbox(
        tract_df, 
        lat="lat", lon="lon",
        z=heat_metric,
        radius=10,
        center=dict(lat=tract_df['lat'].mean(), lon=tract_df['lon'].mean()) if not tract_df.empty else None,
        zoom=4 if selected_state == "All" else 6,
        mapbox_style="carto-positron",
        color_continuous_scale="YlOrRd",
        hover_name="locationid",
        hover_data=["countyname", "Smoking_Prevalence", "Estimated_Smokers"],
        title=heat_title
    )
    fig_neighborhood_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
    st.plotly_chart(fig_neighborhood_map, use_container_width=True)

    st.caption("Tip: Switch the Rank By control in the sidebar to compare prevalence vs reach.")

# ------------------------------------------
# TAB 2: County Level Targeting
# ------------------------------------------
with tab2:
    st.header("County Level Targeting")
    st.write("Identify counties with the largest absolute number of smokers to maximize billboard reach.")
    
    # Aggregate data by State and County
    # Use population-weighted prevalence so percentages reflect total 18+ population
    county_src = filtered_df.copy()
    county_src['Smoking_Weighted'] = county_src['Smoking_Prevalence'] * county_src['Population (18+)']
    county_src['COPD_Weighted'] = county_src['COPD_Prevalence'] * county_src['Population (18+)']
    county_agg = county_src.groupby(['stateabbr', 'countyname', 'countyfips']).agg({
        'Population (18+)': 'sum',
        'Smoking_Weighted': 'sum',
        'COPD_Weighted': 'sum',
        'Estimated_Smokers': 'sum',
        'Overlap_Score': 'mean'
    }).reset_index()
    county_agg['Smoking_Prevalence'] = county_agg['Smoking_Weighted'] / county_agg['Population (18+)']
    county_agg['COPD_Prevalence'] = county_agg['COPD_Weighted'] / county_agg['Population (18+)']
    county_agg.drop(columns=['Smoking_Weighted', 'COPD_Weighted'], inplace=True)
    
    # Sort by selected ranking metric
    county_sort_col = 'Estimated_Smokers' if rank_metric.startswith("Estimated") else 'Smoking_Prevalence'
    county_agg = county_agg.sort_values(by=county_sort_col, ascending=False)
    county_agg['Rank'] = range(1, len(county_agg) + 1)
    
    st.subheader(f"Ranked Recommended Counties — {rank_metric}")
    st.dataframe(
        county_agg[['Rank', 'stateabbr', 'countyname', 'Smoking_Prevalence', 'Population (18+)', 'Estimated_Smokers']],
        use_container_width=True, hide_index=True
    )

    # Top-N bar chart for clear prioritization
    top_n = st.slider("Top N Counties", min_value=5, max_value=50, value=10, step=5)
    county_top = county_agg.head(top_n).copy()
    bar_metric = 'Estimated_Smokers' if rank_metric.startswith("Estimated") else 'Smoking_Prevalence'
    bar_title = "Top Counties by Estimated Smokers (Reach)" if bar_metric == 'Estimated_Smokers' else "Top Counties by Smoking Prevalence (%)"
    fig_bar = px.bar(
        county_top,
        x=bar_metric,
        y='countyname',
        color='stateabbr',
        orientation='h',
        title=bar_title,
        labels={bar_metric: rank_metric, 'countyname': 'County'}
    )
    fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)
    
    st.subheader("Regional Smoker Distribution")
    # Choropleth restricted to selected state or whole US
    map_metric = county_sort_col
    map_title = "Estimated Smokers by County" if map_metric == 'Estimated_Smokers' else "Smoking Prevalence by County"
    fig_map = px.choropleth(
        county_agg,
        geojson=county_geojson,
        locations='countyfips',
        color=map_metric,
        color_continuous_scale="YlOrRd",
        scope="usa",
        hover_name='countyname',
        hover_data=['Smoking_Prevalence', 'Estimated_Smokers'],
        title=map_title
    )
    if selected_state != "All":
        fig_map.update_geos(fitbounds="locations", visible=False)
        
    st.plotly_chart(fig_map, use_container_width=True)
 
    st.caption("Use this map to see where billboard reach is largest by county.")

# ------------------------------------------
# TAB 3: State Level Overview
# ------------------------------------------
with tab3:
    st.header("National State Overview")
    st.write("High-level patterns of tobacco use across the United States.")
    
    # Aggregate data by State
    # Use population-weighted prevalence so percentages reflect total 18+ population
    state_src = year_filtered_df.copy()
    state_src['Smoking_Weighted'] = state_src['Smoking_Prevalence'] * state_src['Population (18+)']
    state_agg = state_src.groupby(['stateabbr']).agg({
        'Population (18+)': 'sum',
        'Smoking_Weighted': 'sum',
        'Estimated_Smokers': 'sum',
        'Overlap_Score': 'mean'
    }).reset_index()
    state_agg['Smoking_Prevalence'] = state_agg['Smoking_Weighted'] / state_agg['Population (18+)']
    state_agg.drop(columns=['Smoking_Weighted'], inplace=True)
    
    
    state_sort_col = 'Estimated_Smokers' if rank_metric.startswith("Estimated") else 'Smoking_Prevalence'
    state_agg = state_agg.sort_values(by=state_sort_col, ascending=False)
    state_agg['Rank'] = range(1, len(state_agg) + 1)
    
    
    st.subheader("State Ranking by Reach")
    st.dataframe(
        state_agg[['Rank', 'stateabbr', 'Smoking_Prevalence', 'Population (18+)', 'Estimated_Smokers']],
        use_container_width=True, hide_index=True
    )

    # Top-N states bar chart for clear prioritization
    state_top_n = st.slider("Top N States", min_value=5, max_value=50, value=15, step=5)
    state_top = state_agg.head(state_top_n).copy()
    state_metric = 'Estimated_Smokers' if rank_metric.startswith("Estimated") else 'Smoking_Prevalence'
    state_title = "Top States by Estimated Smokers (Reach)" if state_metric == 'Estimated_Smokers' else "Top States by Smoking Prevalence (%)"
    fig_state_bar = px.bar(
        state_top,
        x=state_metric,
        y='stateabbr',
        orientation='h',
        title=state_title,
        labels={state_metric: rank_metric, 'stateabbr': 'State'}
    )
    fig_state_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_state_bar, use_container_width=True)
    
    st.subheader("Smoking Prevalence by State")
    state_map_title = "Estimated Smokers by State" if state_sort_col == 'Estimated_Smokers' else "Avg Smoking Prevalence %"
    fig_us_map = px.choropleth(
        state_agg,
        locations='stateabbr',
        locationmode="USA-states",
        color=state_sort_col,
        scope="usa",
        color_continuous_scale="Reds",
        title=state_map_title
    )
    st.plotly_chart(fig_us_map, use_container_width=True)
    

    st.caption("State overview reflects the selected year only.")

# ------------------------------------------
# TAB 4: Phase 2 - Health ROI (COPD)
# ------------------------------------------
with tab4:
    st.header("Phase 2: Health ROI (COPD)")
    st.write("Entrepreneurial expansion: prioritize areas where smoking correlates with high COPD burden.")
    
    st.subheader("Smoking vs COPD Correlation (Neighborhood Level)")
    fig_scatter_t = px.scatter(
        filtered_df.head(2000), x='Smoking_Prevalence', y='COPD_Prevalence',
        size='Population (18+)', color='Estimated_Smokers',
        hover_name='locationid', trendline="ols",
        title="Smoking vs COPD Correlation (Neighborhoods)",
        labels={'Smoking_Prevalence': 'Smoking (%)', 'COPD_Prevalence': 'COPD (%)'}
    )
    st.plotly_chart(fig_scatter_t, use_container_width=True)

    st.subheader("COPD Burden Heat Map (Neighborhood Level)")
    st.info("Heat intensity shows COPD prevalence concentration across neighborhoods.")
    fig_copd_heat = px.density_mapbox(
        filtered_df,
        lat="lat", lon="lon",
        z="COPD_Prevalence",
        radius=10,
        center=dict(lat=filtered_df['lat'].mean(), lon=filtered_df['lon'].mean()) if not filtered_df.empty else None,
        zoom=4 if selected_state == "All" else 6,
        mapbox_style="carto-positron",
        color_continuous_scale="Reds",
        hover_name="locationid",
        hover_data=["countyname", "COPD_Prevalence", "Estimated_Smokers"],
        title="COPD Hotspots"
    )
    fig_copd_heat.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
    st.plotly_chart(fig_copd_heat, use_container_width=True)

    st.subheader("Overlap Heat Map: Smoking + COPD (Co-Occurrence)")
    st.info("Darker regions indicate neighborhoods with both high smoking and high COPD prevalence.")
    overlap_df = filtered_df.copy()
    # Co-occurrence score (higher when both smoking and COPD are high)
    overlap_df['Smoking_COPD_Overlap'] = overlap_df['Smoking_Prevalence'] * overlap_df['COPD_Prevalence']
    fig_overlap_heat = px.density_mapbox(
        overlap_df,
        lat="lat", lon="lon",
        z="Smoking_COPD_Overlap",
        radius=10,
        center=dict(lat=overlap_df['lat'].mean(), lon=overlap_df['lon'].mean()) if not overlap_df.empty else None,
        zoom=4 if selected_state == "All" else 6,
        mapbox_style="carto-positron",
        color_continuous_scale="Magma",
        hover_name="locationid",
        hover_data=["countyname", "Smoking_Prevalence", "COPD_Prevalence", "Estimated_Smokers"],
        title="Co-Occurrence Hotspots (Smoking × COPD)"
    )
    fig_overlap_heat.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
    st.plotly_chart(fig_overlap_heat, use_container_width=True)

    st.subheader("High-Risk County Targeting")
    # County aggregation for COPD risk
    risk_src = filtered_df.copy()
    risk_src['Smoking_Weighted'] = risk_src['Smoking_Prevalence'] * risk_src['Population (18+)']
    risk_src['COPD_Weighted'] = risk_src['COPD_Prevalence'] * risk_src['Population (18+)']
    risk_agg = risk_src.groupby(['stateabbr', 'countyname']).agg({
        'Population (18+)': 'sum',
        'Smoking_Weighted': 'sum',
        'COPD_Weighted': 'sum',
        'Estimated_Smokers': 'sum',
        'Overlap_Score': 'mean'
    }).reset_index()
    risk_agg['Smoking_Prevalence'] = risk_agg['Smoking_Weighted'] / risk_agg['Population (18+)']
    risk_agg['COPD_Prevalence'] = risk_agg['COPD_Weighted'] / risk_agg['Population (18+)']
    risk_agg.drop(columns=['Smoking_Weighted', 'COPD_Weighted'], inplace=True)
    # Recompute Estimated Smokers from county-level prevalence for exact consistency
    risk_agg['Estimated_Smokers'] = (risk_agg['Population (18+)'] * (risk_agg['Smoking_Prevalence'] / 100)).round(2)
    # Risk-Adjusted Reach (RAR) = Estimated Smokers * COPD prevalence factor
    risk_agg['Risk_Adjusted_Reach'] = (risk_agg['Estimated_Smokers'] * (risk_agg['COPD_Prevalence'] / 100)).round(4)
    risk_agg = risk_agg.sort_values(by='Risk_Adjusted_Reach', ascending=False)
    risk_agg['Rank'] = range(1, len(risk_agg) + 1)

    st.dataframe(
        risk_agg[['Rank', 'stateabbr', 'countyname', 'Smoking_Prevalence', 'COPD_Prevalence', 'Population (18+)', 'Estimated_Smokers', 'Risk_Adjusted_Reach']],
        use_container_width=True, hide_index=True
    )

    # Top-N bar chart for high-risk counties
    risk_top_n = st.slider("Top N High-Risk Counties", min_value=5, max_value=50, value=15, step=5)
    risk_top = risk_agg.head(risk_top_n).copy()
    risk_top['county_label'] = risk_top['countyname'] + ", " + risk_top['stateabbr']
    fig_risk_bar = px.bar(
        risk_top,
        x='Risk_Adjusted_Reach',
        y='county_label',
        color='stateabbr',
        orientation='h',
        title="Top High-Risk Counties by Risk-Adjusted Reach",
        labels={'Risk_Adjusted_Reach': 'Risk-Adjusted Reach', 'county_label': 'County'}
    )
    fig_risk_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_risk_bar, use_container_width=True)

# ==========================================
# Footer & Methodology
# ==========================================
st.markdown("---")
with st.expander("Data Methodology & Column Definitions"):
    st.markdown("""
    - **Estimated Smokers:** `18+ Population * (Smoking Prevalence / 100)`
    - **Overlap Score:** `Smoking Prevalence * COPD Prevalence` -> Highlights co-occurrence hotspots.
    - **Risk-Adjusted Reach:** `Estimated Smokers * (COPD Prevalence / 100)` -> Prioritizes high-reach areas with higher COPD burden.
    - **Data Source:** CDC PLACES (2023 release).
    - **Demographic:** Estimates are strictly based on adults aged 18 and older.
    """)
