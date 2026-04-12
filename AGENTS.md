# Agent Instructions

This document defines the technical, design, and analytical standards for the Streamlit application developed for the Anti-Smoking Campaign project.

---

# 1. Project Context

## 1.1 Mission
This project is part of a consulting simulation where the team acts as a Public Health Marketing Agency.

The objective is to use real health data to identify geographic areas with high tobacco use prevalence and recommend optimal billboard placements to reduce smoking rates.

## 1.2 Role and Mindset
- You are expected to operate as data consultants, not just developers.
- The goal is not only visualization, but decision support for real-world resource allocation.
- Every output must be tied to actionable business or public health value.

---

# 4. Data Source

## 4.1 Dataset
- CDC PLACES: Local Data for Better Health (Census Tract Level)

## 4.2 Access Method
- API Provider: Socrata Open Data Platform
- Python Client: `sodapy`

## 4.3 Reference Link
https://chronicdata.cdc.gov/500-Cities-Places/PLACES-Local-Data-for-Better-Health-Census-Tract-D/cwsq-ngmh

---

# 5. Development Environment

- Use **uv** as the package manager.
- All dependencies must be installed and managed using uv.
- No direct pip usage unless explicitly required for debugging or recovery.

---

# 6. Required Dependencies

The following packages must be installed before running the application:

- streamlit: Main application framework  
- pandas: Data processing and preparation  
- sodapy: Integration with CDC PLACES (Socrata) API  
- plotly: Primary engine for interactive maps and charts  
- statsmodels: Required for OLS trendlines in Plotly scatter plots  
- numpy: Numerical operations  
- matplotlib: Static analysis and export reports  
- seaborn: Enhanced statistical visuals for deep analysis  

---

# 7. UI and UX Standards

## 7.1 Typography
- Use Google Sans Flex as the primary font across the application.
- Ensure consistent typography across dashboards, charts, and UI components.

## 7.2 Theme
- Default theme must be Dark Mode.
- theme
    primaryColor="#e4e4e7"
    backgroundColor="#09090b"
    secondaryBackgroundColor="#18181b"
    textColor="#f4f4f5"
- Place the theme in the in the .streamlit/config.toml if it is not already there.


## 7.3 Interactive Elements
- Every interactive element must include a tooltip.
- Tooltips must clearly describe the function and expected effect of the control.
- No interactive element should be ambiguous or unexplained.

## 7.4 Visual Outputs
- No images generated during analysis may be stored in the project.
- Visual outputs are for display only and must remain in-memory.
- Exported reports may contain derived charts, but not raw generated image artifacts from analysis steps.
- No emojis in UI, logs, documentation, or outputs.

---

# 8. Data Methodology Governance

- Any change in calculation logic, transformation rules, or metrics definition must immediately update the Data Methodology section in the UI.
- The Data Methodology section is the single source of truth for analytical transparency.
- No silent updates to metrics are allowed.
- All changes must be documented clearly and consistently.

---

# 9. Engineering Standards
- Avoid hardcoding values wherever possible.

---