import streamlit as st
import pandas as pd
from sodapy import Socrata
import plotly.express as px
import numpy as np
from urllib.request import urlopen
import json
import plotly.io as pio

# Set default Plotly template to match dark theme
pio.templates.default = "plotly_dark"
pio.templates["plotly_dark"].layout.font.family = "Google Sans Flex, sans-serif"
pio.templates["plotly_dark"].layout.paper_bgcolor = "#09090b"
pio.templates["plotly_dark"].layout.plot_bgcolor = "#09090b"

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

    /* Custom hover effects for interactive elements */
    .stSelectbox:hover, .stSlider:hover, .stNumberInput:hover, .stRadio:hover {
        border-color: #e4e4e7 !important;
        transition: all 0.3s ease;
    }

    /* Premium card-like feel for sidebar */
    [data-testid="stSidebar"] {
        background-color: #09090b !important;
        border-right: 1px solid #1e1e2e;
    }

    /* Button hover state */
    .stButton>button:hover {
        border-color: #f4f4f5 !important;
        color: #f4f4f5 !important;
        background-color: rgba(255, 255, 255, 0.05) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
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
    
    # Increase limit to 1M to capture all US Census Tracts (~72,000 records)
    # Note: Use a Socrata App Token for reliable fetching of large datasets
    results_smoking = client.get("cwsq-ngmh", measureid="CSMOKING", select=select_cols, limit=1000000)
    df_smoking = pd.DataFrame.from_records(results_smoking)
    
    # Fetch COPD Data
    results_copd = client.get("cwsq-ngmh", measureid="COPD", select=select_cols, limit=1000000)
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
    # Estimated Smokers = Population (18+) * Smoking Prevalence (as fraction)
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
    
    # Region Mapping
    region_map = {
        'CT': 'Northeast', 'ME': 'Northeast', 'MA': 'Northeast', 'NH': 'Northeast', 'RI': 'Northeast', 'VT': 'Northeast',
        'NJ': 'Northeast', 'NY': 'Northeast', 'PA': 'Northeast',
        'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'KS': 'Midwest', 'MI': 'Midwest', 'MN': 'Midwest',
        'MO': 'Midwest', 'NE': 'Midwest', 'ND': 'Midwest', 'OH': 'Midwest', 'SD': 'Midwest', 'WI': 'Midwest',
        'AL': 'South', 'AR': 'South', 'DE': 'South', 'FL': 'South', 'GA': 'South', 'KY': 'South', 'LA': 'South',
        'MD': 'South', 'MS': 'South', 'NC': 'South', 'OK': 'South', 'SC': 'South', 'TN': 'South', 'TX': 'South',
        'VA': 'South', 'WV': 'South', 'DC': 'South',
        'AK': 'West', 'AZ': 'West', 'CA': 'West', 'CO': 'West', 'HI': 'West', 'ID': 'West', 'MT': 'West',
        'NV': 'West', 'NM': 'West', 'OR': 'West', 'UT': 'West', 'WA': 'West', 'WY': 'West'
    }
    wider_df['Region'] = wider_df['stateabbr'].map(region_map).fillna('Other')
    
    # Priority Score for Strategy (Reach * Risk Factor)
    wider_df['priority_score'] = (wider_df['Estimated_Smokers'] * (wider_df['COPD_Prevalence'] / 100)).round(2)
    
    return wider_df

# ==========================================
# Strategy Helper Functions
# ==========================================
def run_billboard_allocation(base_df, total_billboards, priority_metric="priority_score"):
    """
    Allocates billboards based on a given metric across regions and then identifies top tracts.
    """
    if base_df.empty:
        return pd.DataFrame(), pd.DataFrame(), 0
        
    # Step 1: Regional Allocation
    regional_data = base_df.groupby('Region')[priority_metric].sum().reset_index()
    total_metric_sum = regional_data[priority_metric].sum()
    
    if total_metric_sum > 0:
        regional_data['share'] = regional_data[priority_metric] / total_metric_sum
        regional_data['billboards'] = (regional_data['share'] * total_billboards).round().astype(int)
        
        # Rounding adjustment to match total_billboards
        diff = total_billboards - regional_data['billboards'].sum()
        if diff != 0:
            idx = regional_data[priority_metric].idxmax()
            regional_data.at[idx, 'billboards'] += diff
    else:
        regional_data['billboards'] = 0

    # Step 2: Within Each Region - Select Top Tracts
    selected_locations_list = []
    active_regions = regional_data[regional_data['billboards'] > 0]['Region'].tolist()
    
    for reg in active_regions:
        n_billboards = regional_data[regional_data['Region'] == reg]['billboards'].values[0]
        reg_df = base_df[base_df['Region'] == reg].sort_values(by=priority_metric, ascending=False).head(n_billboards)
        selected_locations_list.append(reg_df)
    
    final_df = pd.concat(selected_locations_list) if selected_locations_list else pd.DataFrame()
    
    return regional_data, final_df, total_metric_sum

def display_strategy_ui(regional_data, final_selected_df, total_billboards, filtered_df, strategy_name, selected_state, show_copd=True):
    """
    Renders the consistent UI for billboard strategies.
    """
    col_summary, col_map = st.columns([1, 2])
    
    with col_summary:
        st.subheader("Regional Allocation")
        st.dataframe(regional_data[regional_data['billboards'] > 0][['Region', 'billboards']], hide_index=True, use_container_width=True)
        
        if not final_selected_df.empty:
            st.subheader("Strategic Impact Summary")
            total_smokers_view = filtered_df['Estimated_Smokers'].sum()
            reached_smokers = final_selected_df['Estimated_Smokers'].sum()
            p_smokers = (reached_smokers / total_smokers_view * 100) if total_smokers_view > 0 else 0
            
            st.metric("Total Smokers Targeted", f"{reached_smokers:,}", help="The estimated number of smokers reached by the proposed billboard allocation.")
            st.caption(f"{p_smokers:.2f}% of current selection reach")
            
            if show_copd:
                total_copd_raw = (filtered_df['Population (18+)'] * (filtered_df['COPD_Prevalence'] / 100)).sum()
                reached_copd = (final_selected_df['Population (18+)'] * (final_selected_df['COPD_Prevalence'] / 100)).sum()
                p_copd = (reached_copd / total_copd_raw * 100) if total_copd_raw > 0 else 0
                
                st.metric("COPD Patients Reached", f"{int(reached_copd):,}", help="The estimated number of COPD patients reached by the proposed billboard allocation.")
                st.caption(f"{p_copd:.2f}% of current selection risk burden")

    with col_map:
        st.subheader("Billboard Locations Map")
        if not final_selected_df.empty:
            hover_items = ["countyname", "stateabbr", "Estimated_Smokers"]
            if show_copd:
                hover_items.append("COPD_Prevalence")
                
            fig_map = px.scatter_mapbox(
                final_selected_df, lat="lat", lon="lon",
                size="Estimated_Smokers" if not show_copd else "priority_score", 
                color="Region",
                hover_name="locationid", 
                hover_data=hover_items,
                zoom=3 if selected_state == "All" else 7,
                mapbox_style="carto-positron",
                title=f"Targeted Zones: {strategy_name}",
                size_max=18
            )
            fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("No locations selected. Adjust filters or billboard count.")

    st.subheader("Recommended Locations (Detailed Table)")
    if not final_selected_df.empty:
        display_cols = ['locationid', 'countyname', 'stateabbr', 'Region', 'Estimated_Smokers']
        if show_copd:
            display_cols.extend(['COPD_Prevalence', 'priority_score'])
            
        st.dataframe(
            final_selected_df[display_cols].sort_values(by=display_cols[-1], ascending=False),
            use_container_width=True, hide_index=True
        )

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
selected_state = st.sidebar.selectbox("Select State", options=["All"] + all_states, help="Filter data by a specific U.S. State.")

# Year Filter (default to latest available year)
available_years = sorted(raw_tract_df['year'].dropna().unique())
default_year = max(available_years) if available_years else None
selected_year = st.sidebar.selectbox(
    "Select Year",
    options=available_years,
    index=available_years.index(default_year) if default_year in available_years else 0,
    help="Filter results by the available CDC data reporting year."
)



if selected_state != "All":
    state_filtered = raw_tract_df[raw_tract_df['stateabbr'] == selected_state]
    all_counties = sorted(state_filtered['countyname'].unique())
    selected_county = st.sidebar.selectbox("Select County", options=["All"] + all_counties, help="Filter results by a specific county within the selected state.")
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
st.title("HealthLens: Anti-Smoking Billboard Strategy")

tab1, tab2, tab3, tab4 = st.tabs([
    "Smoking and Population", 
    "Smoking-Only Strategy", 
    "COPD vs Smoking Relation", 
    "Strategy: Tobacco and COPD"
])

# ------------------------------------------
# ------------------------------------------
# TAB 1: Smoking & Population (18+)
# ------------------------------------------
with tab1:
    st.header("Smoking Concentration Map")
    st.write("Drill down from national state-level trends to specific neighborhood hotspots.")
    
    # Unified Granularity Selector
    map_res_1 = st.radio("Resolution Level", ["State", "County", "Census Tract"], horizontal=True, key="map_res_1", help="Toggle between State, County, or Census Tract (Neighborhood) map views.")
    
    # Map Logic
    if map_res_1 == "State":
        s_src = year_filtered_df.copy()
        s_src['Smoking_Weighted'] = s_src['Smoking_Prevalence'] * s_src['Population (18+)']
        s_agg = s_src.groupby(['stateabbr']).agg({
            'Population (18+)': 'sum', 'Smoking_Weighted': 'sum', 'Estimated_Smokers': 'sum'
        }).reset_index()
        s_agg['Smoking_Prevalence'] = (s_agg['Smoking_Weighted'] / s_agg['Population (18+)']).round(2)
        
        f_map = px.choropleth(
            s_agg, locations='stateabbr', locationmode="USA-states",
            color='Smoking_Prevalence', scope="usa", color_continuous_scale="YlOrRd",
            title="USA State Overview: Avg Smoking Prevalence (%)",
            hover_data=['Estimated_Smokers', 'Population (18+)']
        )
        d_df = s_agg
        d_lbl = "State"
        s_col = 'Smoking_Prevalence'

    elif map_res_1 == "County":
        c_src = filtered_df.copy()
        c_src['Smoking_Weighted'] = c_src['Smoking_Prevalence'] * c_src['Population (18+)']
        c_agg = c_src.groupby(['stateabbr', 'countyname', 'countyfips']).agg({
            'Population (18+)': 'sum', 'Smoking_Weighted': 'sum', 'Estimated_Smokers': 'sum'
        }).reset_index()
        c_agg['Smoking_Prevalence'] = (c_agg['Smoking_Weighted'] / c_agg['Population (18+)']).round(2)
        
        f_map = px.choropleth(
            c_agg, geojson=county_geojson, locations='countyfips',
            color='Smoking_Prevalence', color_continuous_scale="YlOrRd",
            scope="usa", title=f"County View: {selected_state if selected_state != 'All' else 'National'} Breakdown",
            hover_name='countyname', hover_data=['stateabbr', 'Estimated_Smokers']
        )
        if selected_state != "All":
            f_map.update_geos(fitbounds="locations", visible=False)
        d_df = c_agg
        d_lbl = "County"
        s_col = 'Smoking_Prevalence'

    else:  # Census Tract
        t_df = filtered_df.copy()
        f_map = px.density_mapbox(
            t_df, lat="lat", lon="lon", z="Smoking_Prevalence", radius=10,
            center=dict(lat=t_df['lat'].mean(), lon=t_df['lon'].mean()) if not t_df.empty else None,
            zoom=4 if selected_state == "All" else 7, mapbox_style="carto-positron",
            color_continuous_scale="YlOrRd", title="Neighborhood Precision Heatmap (Tract Level)",
            hover_name="locationid", hover_data=["countyname", "Smoking_Prevalence", "Estimated_Smokers"]
        )
        f_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
        d_df = t_df
        d_lbl = "Tract"
        s_col = 'Smoking_Prevalence'

    st.plotly_chart(f_map, use_container_width=True)

    # Coordinated Ranking and Data
    st.divider()
    t_n = st.slider(f"Top {d_lbl}s Ranking", 10, 50, 15, key="t_n_1", help="Adjust the number of top-ranked locations to display in the chart below.")
    top_d = d_df.sort_values(by=s_col, ascending=False).head(t_n)
    
    if map_res_1 == "Census Tract":
        top_d['label'] = top_d['countyname'] + " (" + top_d['locationid'].astype(str) + ")"
    elif map_res_1 == "County":
        top_d['label'] = top_d['countyname'] + ", " + top_d['stateabbr']
    else:
        top_d['label'] = top_d['stateabbr']

    f_bar = px.bar(
        top_d, x=s_col, y='label', orientation='h',
        title=f"High Risk {d_lbl}s: Top {t_n} by Prevalence",
        labels={s_col: "Smoking (%)", "label": d_lbl},
        color=s_col, color_continuous_scale="Reds"
    )
    f_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(f_bar, use_container_width=True)

    st.subheader(f"{d_lbl} Level Intelligence")
    st.dataframe(d_df.sort_values(by=s_col, ascending=False), use_container_width=True, hide_index=True)


# ------------------------------------------
# TAB 2: Smoking-Only Strategy
# ------------------------------------------
with tab2:
    st.header("Smoking-Only Placement Strategy")
    st.write("Allocation based purely on the volume of current smokers, ignoring other health complications.")

    smk_billboards = st.number_input("Total Number of Billboards", min_value=1, max_value=100000, value=1000, step=100, key="smk_bill_input", help="Enter the total number of billboards to be allocated based on smoker volume.")

    # Calculate using Estimated_Smokers only
    reg_data_smk, final_df_smk, _ = run_billboard_allocation(filtered_df, smk_billboards, priority_metric="Estimated_Smokers")

    # Display UI - Explicitly hide COPD
    display_strategy_ui(reg_data_smk, final_df_smk, smk_billboards, filtered_df, "Smoker Volume Priority", selected_state, show_copd=False)

    if not final_df_smk.empty:
        st.info("**Strategy Recommendation (Smoking-Only):**")
        top_reg_smk = reg_data_smk.loc[reg_data_smk['billboards'].idxmax(), 'Region'] if not reg_data_smk.empty else "N/A"
        reached_smokers_smk = final_df_smk['Estimated_Smokers'].sum()
        st.markdown(f"""
        This strategy focuses exclusively on high-volume environments. It distributes **{smk_billboards} billboards** primarily based on population density and smoking prevalence.
        
        - **Primary Focus:** High-density smoking areas in the **{top_reg_smk}**.
        - **Projected Impact:** Directly visible to an estimated **{reached_smokers_smk:,}** smokers.
        - **Allocation Logic:** Billboards are proportional to regional smoker volume (e.g., a region with 24.4% of total smokers receives 244 out of 1,000 billboards).
        - **Advantage:** Simplest implementation for general awareness campaigns.
        """)


# ------------------------------------------
# TAB 3: COPD vs Smoking Relation
# ------------------------------------------
with tab3:
    st.header("Phase 2: Health ROI (COPD)")
    st.write("Entrepreneurial expansion: prioritize areas where smoking correlates with high COPD burden.")
    
    st.subheader("Smoking vs COPD Correlation (Neighborhood Level)")
    scatter_df = filtered_df.copy()
    scatter_df = scatter_df.dropna(subset=['Smoking_Prevalence', 'COPD_Prevalence', 'Population (18+)'])
    # Use all rows for full representation
    fig_scatter = px.scatter(
        scatter_df,
        x='Smoking_Prevalence',
        y='COPD_Prevalence',
        size='Population (18+)',
        color='Smoking_Prevalence',
        color_continuous_scale="Oranges",
        trendline="ols",
        labels={
            'Smoking_Prevalence': 'Smoking (%)',
            'COPD_Prevalence': 'COPD (%)',
            'Population (18+)': 'Population (18+)'
        },
        title="Higher Smoking Prevalence -> Higher COPD Prevalence"
    )
    fig_scatter.update_coloraxes(colorbar_title="Smoking (%)")
    fig_scatter.update_layout(legend_title_text="")
    st.plotly_chart(fig_scatter, use_container_width=True)
    st.caption("Each circle is a neighborhood tract. Circle size = population; color = smoking prevalence. The trendline shows the overall relationship.")

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
        title="Co-Occurrence Hotspots (Smoking x COPD)"
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
    risk_top_n = st.slider("Top N High-Risk Counties", min_value=5, max_value=50, value=15, step=5, help="Select the number of high-risk counties to display in the ranking below.")
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


# ------------------------------------------
# TAB 4: Smoking + COPD Strategy
# ------------------------------------------
with tab4:
    st.header("Integrated Strategy (Smoking + COPD)")
    st.write("Optimized allocation prioritizing high smoking rates where COPD burden is also significant.")

    total_billboards = st.number_input("Total Number of Billboards", min_value=1, max_value=100000, value=1000, step=100, key="total_bill_input", help="Enter the total number of billboards for the integrated risk-based strategy.")

    # Calculate using priority_score (Smokers * COPD Factor)
    reg_data_int, final_df_int, _ = run_billboard_allocation(filtered_df, total_billboards, priority_metric="priority_score")

    # Display UI
    display_strategy_ui(reg_data_int, final_df_int, total_billboards, filtered_df, "Health ROI Priority", selected_state)

    if not final_df_int.empty:
        st.info("**Strategy Recommendation (Integrated):**")
        top_reg_int = reg_data_int.loc[reg_data_int['billboards'].idxmax(), 'Region'] if not reg_data_int.empty else "N/A"
        reached_smokers_int = final_df_int['Estimated_Smokers'].sum()
        reached_copd_int = (final_df_int['Population (18+)'] * (final_df_int['COPD_Prevalence'] / 100)).sum()
        
        st.markdown(f"""
        This strategy distributes **{total_billboards} billboards** using an ROI model that mitigates clinical risk.
        
        - **Primary Focus:** High disease-burden areas in the **{top_reg_int}**.
        - **Reach Optimization:** Targets tracts with the highest concentration of smokers (estimated {reached_smokers_int:,} individuals).
        - **Risk Mitigation:** Prioritizes areas with significant COPD burden (targeting {int(reached_copd_int):,} high-risk individuals).
        - **Allocation Logic:** Proportional distribution based on regional "Priority Score" (e.g., 24.4% of national risk results in 244 out of 1,000 billboards).
        """)

# ==========================================
# Footer & Methodology
# ==========================================
st.markdown("---")
with st.expander("Data Methodology & Calculation Definitions"):
    m_tabs = st.tabs(["Tab 1: Overview", "Tab 2: Smoker Strategy", "Tab 3: COPD ROI", "Tab 4: Integrated Strategy"])
    
    with m_tabs[0]:
        st.markdown("""
        **Core Definitions:**
        - **Estimated Smokers:** `18+ Population * (Smoking Prevalence / 100)`. This represents the absolute count of smokers in a given area (Tract, County, or State).
        """)

    with m_tabs[1]:
        st.markdown("""
        **Smoker-Only Allocation:**
        - **Metric:** `Estimated Smokers`.
        - **Logic:** Rank-based selection targets the highest volume of tobacco users regardless of clinical history.
        - **Regional Share:** Determined by the total number of smokers in a region vs. the national total.
        - **Regional Mapping:** States are categorized into four US Census Regions (Northeast, Midwest, South, West).
        
        **Proportional Allocation Steps:**
        1. **Sum Regional Scores:** The total priority score (or smoker count) is summed for each of the 4 US Census regions.
        2. **Calculate Share:** `Regional Sum / National Total Sum`.
        3. **Distribute Billboards:** `Share * Total Input Billboards`.
        4. **Rounding Adjustment:** If rounding causes the total to miss the user's input, the remainder is assigned to the region with the single highest Priority Score to ensure exact totals.

        **Step-by-Step Example (Allocation for 1,000 Billboards):**
        1. **Regional Totals:** Sum estimated smokers for each region (e.g., Midwest = 6.1M; National Total = 25M).
        2. **Compute Share:** Divide regional total by national total (e.g., 6.1M / 25M = 0.244).
        3. **Final Count:** Multiply share by billboard budget (e.g., 0.244 * 1,000 = **244 billboards**).
        """)

    with m_tabs[2]:
        st.markdown("""
        **Risk Metrics:**
        - **Risk-Adjusted Reach (RAR):** `Estimated Smokers * (COPD Prevalence / 100)`.
        - **Co-Occurrence Index:** `Smoking Prevalence * COPD Prevalence`. Identifies "Dual-Burden" hotspots.
        - **Trendline (OLS):** Uses Ordinary Least Squares to map the relationship between behavioral risk and health outcomes.
        """)
    
    with m_tabs[3]:
        st.markdown("""
        **Integrated Allocation Logic:**
        - **Priority Score:** `Estimated Smokers * (COPD Prevalence / 100)`.
        - **Proportional Allocation Steps:**
            1. **Sum Regional Scores:** The total priority score (or smoker count) is summed for each of the 4 US Census regions.
            2. **Calculate Share:** `Regional Sum / National Total Sum`.
            3. **Distribute Billboards:** `Share * Total Input Billboards`.
            4. **Rounding Adjustment:** If rounding causes the total to miss the user's input, the remainder is assigned to the region with the single highest Priority Score to ensure exact totals.
        
        **Step-by-Step Example (Allocation for 1,000 Billboards):**
        1. **Regional Totals:** Sum the Priority Score for each region (e.g., Midwest = 6,100; National Total = 25,000).
        2. **Compute Share:** Divide regional total by national total (e.g., 6,100 / 25,000 = 0.244).
        3. **Final Count:** Multiply share by billboard budget (e.g., 0.244 * 1,000 = **244 billboards**).
        """)
    
    st.caption("**Data Source:** CDC PLACES (2023 release). All demographic estimates are based on adults aged 18 and older.")
