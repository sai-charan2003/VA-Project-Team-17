# HealthLens – Public Health Anti-Smoking AI Strategy

A Streamlit app for exploring CDC PLACES data on cigarette smoking and COPD, with maps and visualizations.

## Prerequisites

- **Python 3.8+**
- **pip** (Python package manager)

## Running the app

### 1. Clone the repository (if needed)

```bash
git clone <repository-url>
cd Project1
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
```

Activate it:

- **macOS / Linux:** `source venv/bin/activate`
- **Windows:** `venv\Scripts\activate`

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the app

```bash
streamlit run app.py
```

The app will open in your browser at **http://localhost:8501**. If it doesn’t, open that URL manually.

## Quick run (if dependencies are already installed)

```bash
streamlit run app.py
```

## Project structure

| File / folder      | Description                          |
|--------------------|--------------------------------------|
| `app.py`           | Main Streamlit application           |
| `requirements.txt` | Python dependencies                  |
| `.streamlit/`      | Streamlit config (e.g. theme)        |
| `venv/`            | Virtual environment (do not commit)  |

## Dependencies

- **streamlit** – Web app framework  
- **pandas** – Data handling  
- **sodapy** – CDC Socrata API client  
- **plotly** – Interactive charts and maps  
- **statsmodels** – Statistical analysis  
- **numpy** – Numerical operations  
