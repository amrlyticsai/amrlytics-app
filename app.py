"""
AMRlytics — Global Antimicrobial Resistance Intelligence Platform

Pages and gating:
  1. Home — FREE
  2. Surveillance — FREE (with Pro 'Custom Reports' request CTA)
  3. Trend-based AI Forecasting — FREE DEMO (Italy MRSA only) + PRO (everything else)
  4. Alerts & Insights — Tab 1 FREE, Tabs 2-4 PRO (accordion layout)
  5. Benchmarking — Tab 1 FREE, Tabs 2-3 PRO (accordion layout)
  6. Methodology — FREE

Pro password: AMRlytics-Pilot-2026 (rotate per cohort)
Built by Ahmad Junaid · amrlytics.ai
"""

import streamlit as st
import csv
import os
import altair as alt
import pandas as pd
from collections import defaultdict

st.set_page_config(
    page_title="AMRlytics",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🧬",
)

# ============================================================
# PRO ACCESS — PASSWORD GATE
# ============================================================

PRO_PASSWORD = "AMRlytics-Pilot-2026"
FREE_DEMO_COUNTRY = "Italy"
FREE_DEMO_PATHOGEN = "Staphylococcus aureus"
FREE_DEMO_ANTIBIOTIC = "Meticillin (MRSA)"  # ECDC naming

# Initialize session state
if "pro_unlocked" not in st.session_state:
    st.session_state.pro_unlocked = False


def render_pro_lock_screen(feature_name, feature_description):
    """Render the upgrade screen when a Free user hits a Pro feature."""
    st.markdown(f"""
    <style>
    .pro-lock-card {{
        background: linear-gradient(180deg, rgba(216,90,48,0.08) 0%, rgba(255,255,255,0.02) 100%);
        border: 1px solid rgba(216,90,48,0.3);
        border-radius: 6px;
        padding: 2.5rem;
        margin: 2rem 0;
        text-align: center;
    }}
    .pro-lock-icon {{
        font-size: 2.5rem;
        margin-bottom: 1rem;
        color: #d85a30;
    }}
    .pro-lock-title {{
        font-family: 'Instrument Serif', serif;
        font-size: 1.8rem;
        margin-bottom: 0.5rem;
    }}
    .pro-lock-tag {{
        display: inline-block;
        background: rgba(216,90,48,0.15);
        color: #d85a30;
        padding: 0.3rem 0.8rem;
        border-radius: 2px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        margin-bottom: 1.25rem;
    }}
    .pro-lock-desc {{
        color: #aaa;
        line-height: 1.7;
        max-width: 540px;
        margin: 0 auto 1.5rem;
    }}
    </style>
    <div class='pro-lock-card'>
        <div class='pro-lock-icon'>🔒</div>
        <div class='pro-lock-tag'>Pro feature · Pilot access required</div>
        <div class='pro-lock-title'>{feature_name}</div>
        <div class='pro-lock-desc'>{feature_description}</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "**Pilot access is currently free** for microbiologists, public health "
            "researchers, clinicians, and pharma R&D professionals. "
            "Submit a brief request and you'll receive your access password by email."
        )
        st.link_button("Request Pro Access →", "https://amrlytics.ai/#contact",
                       type="primary", use_container_width=True)

        with st.expander("Already have a pilot password?"):
            entered = st.text_input("Enter pilot password",
                type="password", key=f"pwd_{feature_name}")
            if st.button("Unlock", key=f"unlock_{feature_name}"):
                if entered == PRO_PASSWORD:
                    st.session_state.pro_unlocked = True
                    st.success("✓ Pro access unlocked. Refreshing…")
                    st.rerun()
                else:
                    st.error("Incorrect password. Contact hello@amrlytics.ai for access.")


# ============================================================
# CONSTANTS — risk tiers, last-line drugs
# ============================================================

RISK_TIERS = [
    ("Low",       0,  10, "#3b6d11", "Generally suitable for empiric monotherapy"),
    ("Moderate",  10, 20, "#7a8b00", "Local context and combination therapy considered"),
    ("High",      20, 50, "#ba7517", "Empiric monotherapy generally discouraged"),
    ("Critical",  50, 70, "#d85a30", "Empiric monotherapy strongly discouraged"),
    ("Extreme",   70, 101, "#a32d2d", "Antibiotic effectively non-functional in this context"),
]


def get_tier(resistance_pct):
    for name, low, high, color, desc in RISK_TIERS:
        if low <= resistance_pct < high:
            return name, color, desc
    return "Unknown", "#666", "No tier assigned"


LAST_LINE_DRUGS = {
    "Carbapenems": "Last-line for Gram-negative infections (WHO AWaRe Reserve)",
    "Meropenem": "Last-line for Gram-negative infections (WHO AWaRe Watch)",
    "Imipenem": "Last-line for Gram-negative infections (WHO AWaRe Watch)",
    "Ertapenem": "Last-line for Gram-negative infections (WHO AWaRe Watch)",
    "Colistin": "Last-resort for MDR Gram-negatives (WHO AWaRe Reserve)",
    "Polymyxin B": "Last-resort for MDR Gram-negatives (WHO AWaRe Reserve)",
    "Vancomycin": "Last-line for MRSA and Enterococci (WHO AWaRe Watch)",
    "Teicoplanin": "Last-line for Gram-positive resistant infections",
    "Daptomycin": "Last-line for VRE and complicated Gram-positive infections (WHO AWaRe Reserve)",
    "Linezolid": "Last-line for VRE and MRSA (WHO AWaRe Reserve)",
    "Ceftaroline": "Last-line for MRSA (WHO AWaRe Reserve)",
    "Ceftazidime-avibactam": "Last-line for CRE/DTR Pseudomonas (WHO AWaRe Reserve)",
    "Cefiderocol": "Last-line for CRE/CRAB/DTR Pseudomonas (WHO AWaRe Reserve)",
    "Tigecycline": "Reserve agent for MDR Gram-negative infections",
}


def is_last_line(antibiotic_name):
    if not antibiotic_name:
        return False, ""
    name_lower = antibiotic_name.lower()
    for drug, desc in LAST_LINE_DRUGS.items():
        if drug.lower() in name_lower or name_lower in drug.lower():
            return True, desc
    return False, ""


# ============================================================
# DATA LOADING
# ============================================================

data_folder = os.path.dirname(__file__)


@st.cache_data
def load_who_glass(filepath, filename):
    rows = []
    file = open(filepath, encoding="utf-8-sig")
    header_line = None
    for i, line in enumerate(file):
        if "CountryTerritoryArea" in line:
            header_line = i
            break
    if header_line is None:
        file.close()
        return rows
    file.close()
    file = open(filepath, encoding="utf-8-sig")
    for i in range(header_line):
        next(file)
    reader = csv.DictReader(file)
    for row in reader:
        if not row.get("CountryTerritoryArea"):
            continue
        rows.append({
            "country": row.get("CountryTerritoryArea", ""),
            "iso3": row.get("Iso3", ""),
            "region": row.get("WHORegionName", ""),
            "year": row.get("Year", ""),
            "pathogen": row.get("PathogenName", ""),
            "antibiotic": row.get("AbTargets", ""),
            "resistance": row.get("PercentResistant", ""),
            "specimen": row.get("Specimen", "BLOOD"),
            "source": "WHO GLASS",
        })
    file.close()
    return rows


@st.cache_data
def load_ecdc(filepath, filename):
    rows = []
    skipped = 0
    file = open(filepath, encoding="utf-8-sig")
    reader = csv.DictReader(file)
    for row in reader:
        indicator = row.get("Indicator", "").strip().lower()
        unit = row.get("Unit", "").strip()
        if "percentage" not in indicator and unit != "%":
            skipped += 1
            continue
        num_value = row.get("NumValue", "-")
        if num_value == "-" or num_value == "" or num_value is None:
            continue
        region_name = row.get("RegionName", "")
        if region_name in ("EU/EEA", "EU"):
            continue
        population = row.get("Population", "")
        if "|" in population:
            pathogen, antibiotic = population.split("|", 1)
        else:
            pathogen = population
            antibiotic = ""
        rows.append({
            "country": region_name,
            "iso3": row.get("RegionCode", ""),
            "region": "European Region",
            "year": row.get("Time", ""),
            "pathogen": pathogen.strip(),
            "antibiotic": antibiotic.strip(),
            "resistance": num_value,
            "specimen": "BLOOD",
            "source": "ECDC EARS-Net",
        })
    file.close()
    return rows, skipped


@st.cache_data
def load_all_data():
    all_rows = []
    skipped_files = []
    for filename in sorted(os.listdir(data_folder)):
        if not filename.endswith(".csv"):
            continue
        filepath = os.path.join(data_folder, filename)
        f = open(filepath, encoding="utf-8-sig")
        first_line = f.readline()
        f.close()
        if "HealthTopic" in first_line:
            rows, skipped = load_ecdc(filepath, filename)
            if skipped > 0 and len(rows) == 0:
                skipped_files.append(f"{filename} (count data)")
        else:
            rows = load_who_glass(filepath, filename)
        if rows:
            all_rows.extend(rows)
    return all_rows, skipped_files


all_data, skipped_files = load_all_data()
specimen_labels = {"BLOOD": "Bloodstream", "URINE": "Urinary tract", "STOOL": "Gastrointestinal"}
sources_loaded = sorted(set(row["source"] for row in all_data))
source_text = " + ".join(sources_loaded)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_resistance_for_combo(pathogen, antibiotic, country, specimen="BLOOD", year=None):
    matches = [r for r in all_data
               if r["pathogen"] == pathogen
               and r["antibiotic"] == antibiotic
               and r["country"] == country
               and r.get("specimen", "BLOOD") == specimen]
    if year:
        matches = [r for r in matches if r["year"] == str(year)]
    if not matches:
        return None
    try:
        latest = max(matches, key=lambda r: r["year"])
        return float(latest["resistance"]), latest["year"]
    except (ValueError, TypeError):
        return None


def get_3yr_change(pathogen, antibiotic, country, specimen="BLOOD"):
    matches = [r for r in all_data
               if r["pathogen"] == pathogen
               and r["antibiotic"] == antibiotic
               and r["country"] == country
               and r.get("specimen", "BLOOD") == specimen]
    if len(matches) < 2:
        return None
    try:
        sorted_by_year = sorted(matches, key=lambda r: int(r["year"]))
        latest = sorted_by_year[-1]
        latest_year = int(latest["year"])
        baseline_year = latest_year - 3
        baseline_candidates = [r for r in sorted_by_year if int(r["year"]) <= baseline_year]
        if not baseline_candidates:
            baseline_candidates = [sorted_by_year[0]]
        baseline = baseline_candidates[-1]
        latest_pct = float(latest["resistance"])
        baseline_pct = float(baseline["resistance"])
        return {
            "change": round(latest_pct - baseline_pct, 1),
            "baseline_year": baseline["year"],
            "baseline_pct": round(baseline_pct, 1),
            "latest_year": latest["year"],
            "latest_pct": round(latest_pct, 1),
        }
    except (ValueError, TypeError, IndexError):
        return None


def run_prophet_forecast(historical, forecast_years):
    """Run Prophet on a list of {year, pct} dicts and return chart-ready data."""
    from prophet import Prophet
    import logging
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

    hist_df = pd.DataFrame(historical)
    prophet_df = pd.DataFrame({
        "ds": pd.to_datetime(hist_df["year"].astype(str) + "-01-01"),
        "y": hist_df["pct"].clip(0, 100)
    })
    m = Prophet(yearly_seasonality=False, weekly_seasonality=False,
        daily_seasonality=False, changepoint_prior_scale=0.05, interval_width=0.80)
    m.fit(prophet_df)
    future = m.make_future_dataframe(periods=forecast_years, freq="YS")
    pred = m.predict(future)
    for col in ["yhat", "yhat_lower", "yhat_upper"]:
        pred[col] = pred[col].clip(0, 100)
    return pred, hist_df


def render_forecast_chart(pred, historical, forecast_years, title):
    """Render the historical + forecast chart with confidence band."""
    chart_rows = []
    for _, r in pred.iterrows():
        year = r["ds"].year
        is_forecast = year > historical[-1]["year"]
        chart_rows.append({"Year": year, "Resistance (%)": round(float(r["yhat"]), 1),
            "Lower": round(float(r["yhat_lower"]), 1), "Upper": round(float(r["yhat_upper"]), 1),
            "Type": "Forecast" if is_forecast else "Historical"})
    chart_df = pd.DataFrame(chart_rows)
    actual_rows = pd.DataFrame([{"Year": h["year"], "Resistance (%)": round(h["pct"], 1)}
                                for h in historical])

    band = alt.Chart(chart_df[chart_df["Type"] == "Forecast"]).mark_area(
        opacity=0.2, color="#d85a30").encode(x="Year:O",
        y=alt.Y("Lower:Q", scale=alt.Scale(domain=[0, 100]), title="Resistance (%)"),
        y2="Upper:Q")
    forecast_line = alt.Chart(chart_df[chart_df["Type"] == "Forecast"]).mark_line(
        color="#d85a30", strokeDash=[6, 4], strokeWidth=2.5).encode(x="Year:O",
        y=alt.Y("Resistance (%):Q", scale=alt.Scale(domain=[0, 100])))
    obs_line = alt.Chart(actual_rows).mark_line(color="#3b6d11", strokeWidth=2.5).encode(
        x="Year:O", y="Resistance (%):Q")
    obs_points = alt.Chart(actual_rows).mark_circle(color="#3b6d11", size=80).encode(
        x="Year:O", y="Resistance (%):Q", tooltip=["Year", "Resistance (%)"])

    return (band + forecast_line + obs_line + obs_points).properties(
        height=480, title=title)


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.markdown(
    "<div style='font-family:\"Instrument Serif\",serif; font-size:1.6rem; padding:0.5rem 0;'>"
    "AMR<span style='color:#d85a30; font-style:italic'>lytics</span></div>",
    unsafe_allow_html=True,
)
st.sidebar.caption("Predicting the future of antimicrobial resistance using data and AI")

# Pro status badge
if st.session_state.pro_unlocked:
    st.sidebar.markdown(
        "<div style='background:rgba(59,109,17,0.12); border:1px solid rgba(59,109,17,0.4); "
        "padding:0.4rem 0.7rem; border-radius:2px; margin:0.5rem 0; "
        "font-family:JetBrains Mono,monospace; font-size:0.7rem; color:#5dcaa5; "
        "letter-spacing:0.12em;'>"
        "✓ PRO ACCESS · ACTIVE</div>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Lock Pro features", use_container_width=True):
        st.session_state.pro_unlocked = False
        st.rerun()
else:
    st.sidebar.markdown(
        "<div style='background:rgba(216,90,48,0.08); border:1px solid rgba(216,90,48,0.3); "
        "padding:0.4rem 0.7rem; border-radius:2px; margin:0.5rem 0; "
        "font-family:JetBrains Mono,monospace; font-size:0.7rem; color:#d85a30; "
        "letter-spacing:0.12em;'>"
        "FREE TIER</div>",
        unsafe_allow_html=True,
    )

st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Home",
        "📊 Surveillance",
        "📈 Trend-based AI Forecasting",
        "⚠ Alerts & Insights",
        "🌐 Benchmarking",
        "📋 Methodology",
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")

if not st.session_state.pro_unlocked:
    if st.sidebar.button("🔓 Enter Pro password", use_container_width=True):
        st.session_state.show_pwd_input = True
    if st.session_state.get("show_pwd_input"):
        pwd = st.sidebar.text_input("Pilot password", type="password", key="sidebar_pwd")
        if st.sidebar.button("Unlock"):
            if pwd == PRO_PASSWORD:
                st.session_state.pro_unlocked = True
                st.session_state.show_pwd_input = False
                st.rerun()
            else:
                st.sidebar.error("Incorrect password")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<div style='font-family:JetBrains Mono,monospace; font-size:0.65rem; color:#666; "
    "letter-spacing:0.08em; text-align:center;'>"
    "POWERED BY AMRLYTICS<br>amrlytics.ai</div>",
    unsafe_allow_html=True,
)

if skipped_files:
    with st.sidebar.expander("⚠ Data validation"):
        st.warning(f"Skipped {len(skipped_files)} count file(s).")
        for f in skipped_files:
            st.caption(f"• {f}")


# ============================================================
# PAGE 1: HOME
# ============================================================

if page == "🏠 Home":
    st.markdown("""
    <style>
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(24px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(0.9); }
    }
    .home-hero { animation: fadeUp 0.8s ease forwards; padding: 1rem 0 2rem; }
    .home-stat {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 4px; padding: 1.5rem;
        animation: fadeUp 0.8s ease forwards; opacity: 0;
        transition: border-color 0.3s, transform 0.3s;
    }
    .home-stat:hover {
        border-color: rgba(216, 90, 48, 0.3); transform: translateY(-3px);
    }
    .home-stat:nth-child(1) { animation-delay: 0.15s; }
    .home-stat:nth-child(2) { animation-delay: 0.25s; }
    .home-stat:nth-child(3) { animation-delay: 0.35s; }
    .home-stat:nth-child(4) { animation-delay: 0.45s; }
    .stat-num {
        font-family: 'Instrument Serif', serif;
        font-size: 2.5rem; line-height: 1;
        color: #d85a30; margin-bottom: 0.3rem;
    }
    .stat-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem; text-transform: uppercase;
        letter-spacing: 0.12em; color: #888;
    }
    .stat-sub { font-size: 0.78rem; color: #aaa; margin-top: 0.4rem; }
    .nav-card {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 4px; padding: 1.5rem;
        animation: fadeUp 0.8s ease forwards; opacity: 0;
        transition: all 0.3s; height: 100%;
    }
    .nav-card:hover {
        border-color: rgba(216, 90, 48, 0.4);
        background: rgba(216, 90, 48, 0.04);
        transform: translateY(-3px);
    }
    .nav-card-title {
        font-family: 'Instrument Serif', serif;
        font-size: 1.3rem; margin-bottom: 0.4rem;
    }
    .nav-card-desc { font-size: 0.85rem; color: #aaa; line-height: 1.5; }
    .nav-card-num {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem; color: #d85a30;
        letter-spacing: 0.18em; margin-bottom: 0.6rem;
    }
    .nav-card-tag {
        display: inline-block;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.6rem; letter-spacing: 0.12em;
        padding: 0.2rem 0.5rem; border-radius: 2px;
        margin-top: 0.6rem;
    }
    .tag-free {
        background: rgba(59,109,17,0.15); color: #5dcaa5;
        border: 1px solid rgba(59,109,17,0.3);
    }
    .tag-pro {
        background: rgba(216,90,48,0.15); color: #d85a30;
        border: 1px solid rgba(216,90,48,0.3);
    }
    .live-indicator {
        display: inline-flex; align-items: center; gap: 0.5rem;
        background: rgba(59, 109, 17, 0.1);
        border: 1px solid rgba(59, 109, 17, 0.3);
        padding: 0.3rem 0.7rem; border-radius: 2px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem; color: #5dcaa5; letter-spacing: 0.12em;
    }
    .live-indicator::before {
        content: ''; width: 6px; height: 6px;
        border-radius: 50%; background: #5dcaa5;
        animation: pulse 2s infinite;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='home-hero'>", unsafe_allow_html=True)
    st.markdown("<span class='live-indicator'>AMRLYTICS · BETA · IN DEVELOPMENT</span>",
                unsafe_allow_html=True)
    st.title("Welcome to AMRlytics")
    st.markdown(
        "<p style='font-size:1.05rem; color:#aaa; max-width:720px; line-height:1.7; margin-top:1rem;'>"
        "Global antimicrobial resistance intelligence platform powered by WHO GLASS and ECDC EARS-Net data. "
        "Track surveillance trends freely. Unlock forecasting, alerts, and advanced benchmarking through pilot access."
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    total_countries = len(set(r["country"] for r in all_data))
    total_pathogens = len(set(r["pathogen"] for r in all_data))
    total_antibiotics = len(set(r["antibiotic"] for r in all_data))
    years_in_data = sorted(set(r["year"] for r in all_data if r["year"]))
    year_range = f"{years_in_data[0]}–{years_in_data[-1]}" if years_in_data else "—"

    col1, col2, col3, col4 = st.columns(4)
    stats = [
        (col1, len(all_data), "Surveillance rows", source_text),
        (col2, total_countries, "Countries", "From 2 surveillance networks"),
        (col3, f"{total_pathogens} / {total_antibiotics}", "Pathogens / Antibiotics", "And growing"),
        (col4, year_range, "Years of data", "Live time-series"),
    ]
    for col, num, label, sub in stats:
        col.markdown(
            f"<div class='home-stat'>"
            f"<div class='stat-num'>{num}</div>"
            f"<div class='stat-label'>{label}</div>"
            f"<div class='stat-sub'>{sub}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("### Explore the platform")
    st.caption("Free tier: full surveillance dashboard. Pro tier: forecasting, alerts, advanced benchmarking.")

    pages_info = [
        ("01 — Surveillance", "📊 Interactive Dashboard",
         "Filter resistance trends by pathogen, antibiotic, and country across 60+ countries.",
         "FREE"),
        ("02 — Forecasting", "📈 Trend-based AI Forecasting",
         "Prophet time-series projections with 80% confidence intervals. Free demo available — Italy MRSA.",
         "PRO · 1 free demo"),
        ("03 — Alerts", "⚠ Risk Classification",
         "Critical resistance, last-line drug warnings, 3-year acceleration alerts, actionable insights.",
         "FREE + PRO"),
        ("04 — Benchmarking", "🌐 Country Comparison",
         "Compare against WHO regional averages, WHO BPPL classification, and historical trajectory peers.",
         "FREE + PRO"),
    ]

    cols = st.columns(2)
    for i, (num, title, desc, tier) in enumerate(pages_info):
        tier_class = "tag-free" if tier == "FREE" else "tag-pro"
        with cols[i % 2]:
            st.markdown(
                f"<div class='nav-card' style='animation-delay: {0.5 + i*0.1}s;'>"
                f"<div class='nav-card-num'>{num}</div>"
                f"<div class='nav-card-title'>{title}</div>"
                f"<div class='nav-card-desc'>{desc}</div>"
                f"<div class='nav-card-tag {tier_class}'>{tier}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info(
        "**Important:** AMRlytics is a surveillance and forecasting tool. It is not clinical decision support. "
        "Forecasts are experimental and should not replace consultation with qualified clinicians and microbiologists. "
        "See the Methodology page for full limitations."
    )


# ============================================================
# PAGE 2: SURVEILLANCE (FREE — full access)
# ============================================================

elif page == "📊 Surveillance":
    st.title("Surveillance Dashboard")
    st.caption(f"Real-time AMR surveillance powered by {source_text}")

    if not all_data:
        st.error("No data loaded.")
        st.stop()

    st.sidebar.markdown("### Filters")

    specimens = sorted(set(row.get("specimen", "BLOOD") for row in all_data))
    if len(specimens) > 1:
        selected_specimen = st.sidebar.selectbox(
            "Infection type", specimens,
            format_func=lambda x: specimen_labels.get(x, x))
    else:
        selected_specimen = specimens[0] if specimens else "BLOOD"

    pathogens = sorted(set(r["pathogen"] for r in all_data
                           if r.get("specimen", "BLOOD") == selected_specimen))
    selected_pathogen = st.sidebar.selectbox("Pathogen", pathogens)

    matching_antibiotics = sorted(set(r["antibiotic"] for r in all_data
        if r["pathogen"] == selected_pathogen
        and r.get("specimen", "BLOOD") == selected_specimen))
    selected_antibiotic = st.sidebar.selectbox("Antibiotic", matching_antibiotics)

    matching_countries = sorted(set(r["country"] for r in all_data
        if r["pathogen"] == selected_pathogen
        and r["antibiotic"] == selected_antibiotic
        and r.get("specimen", "BLOOD") == selected_specimen))

    filtered = [r for r in all_data
        if r["pathogen"] == selected_pathogen
        and r["antibiotic"] == selected_antibiotic
        and r.get("specimen", "BLOOD") == selected_specimen]

    is_ll, ll_desc = is_last_line(selected_antibiotic)
    if is_ll:
        st.warning(f"⚠ **{selected_antibiotic} is a last-line/reserve antibiotic.** {ll_desc}.")

    all_years_in_filtered = sorted(set(r["year"] for r in filtered))
    latest_year = all_years_in_filtered[-1] if all_years_in_filtered else None
    latest_year_data = [r for r in filtered if r["year"] == latest_year] if latest_year else []

    if latest_year_data:
        resistances = []
        for r in latest_year_data:
            try:
                resistances.append(float(r["resistance"]))
            except (ValueError, TypeError):
                continue
        if resistances:
            avg_resistance = sum(resistances) / len(resistances)
            max_val = max(resistances)
            min_val = min(resistances)
            max_row = next(r for r in latest_year_data if float(r["resistance"]) == max_val)
            min_row = next(r for r in latest_year_data if float(r["resistance"]) == min_val)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Avg resistance", f"{avg_resistance:.1f}%", f"in {latest_year}")
            col2.metric("Highest", f"{max_val:.1f}%", max_row["country"])
            col3.metric("Lowest", f"{min_val:.1f}%", min_row["country"])
            col4.metric("Countries reporting", len(latest_year_data), source_text)

    st.markdown("---")

    tab1, tab2 = st.tabs(["📈 Trends over time", "📊 Country comparison"])

    with tab1:
        selected_countries = st.multiselect("Select countries", matching_countries,
            default=matching_countries[:3] if len(matching_countries) >= 3 else matching_countries)
        trend_data = [r for r in filtered if r["country"] in selected_countries]
        chart_data = []
        for r in trend_data:
            try:
                chart_data.append({"Country": r["country"], "Year": int(r["year"]),
                    "Resistance (%)": round(float(r["resistance"]), 1), "Source": r["source"]})
            except (ValueError, TypeError):
                continue
        df = pd.DataFrame(chart_data)
        if not df.empty:
            chart = alt.Chart(df).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("Year:O"),
                y=alt.Y("Resistance (%):Q", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("Country:N"),
                tooltip=["Country", "Year", "Resistance (%)", "Source"]
            ).properties(
                title=f"{selected_pathogen} — {selected_antibiotic}",
                height=450)
            st.altair_chart(chart, use_container_width=True)

    with tab2:
        available_years = sorted(set(r["year"] for r in filtered))
        if available_years:
            selected_year = st.select_slider("Year", options=available_years, value=available_years[-1])
            comp_rows = []
            for r in [r for r in filtered if r["year"] == selected_year]:
                try:
                    pct = round(float(r["resistance"]), 1)
                    tier_name, _, _ = get_tier(pct)
                    comp_rows.append({"Country": r["country"], "Resistance (%)": pct,
                                      "Tier": tier_name, "Source": r["source"]})
                except (ValueError, TypeError):
                    continue
            comp_df = pd.DataFrame(comp_rows)
            if not comp_df.empty:
                comp_df = comp_df.sort_values("Resistance (%)", ascending=True)
                bar = alt.Chart(comp_df).mark_bar().encode(
                    x=alt.X("Resistance (%):Q", scale=alt.Scale(domain=[0, 100])),
                    y=alt.Y("Country:N", sort="-x", title=""),
                    color=alt.Color("Tier:N", scale=alt.Scale(
                        domain=["Low", "Moderate", "High", "Critical", "Extreme"],
                        range=["#3b6d11", "#7a8b00", "#ba7517", "#d85a30", "#a32d2d"])),
                    tooltip=["Country", "Resistance (%)", "Tier", "Source"]
                ).properties(height=max(len(comp_df) * 25, 300))
                st.altair_chart(bar, use_container_width=True)

    # ---- REQUEST CUSTOM REPORT CTA (below charts) ----
    st.markdown("---")
    st.markdown("""
    <style>
    .custom-report-card {
        background: linear-gradient(180deg, rgba(216,90,48,0.06) 0%, rgba(255,255,255,0.02) 100%);
        border: 1px solid rgba(216,90,48,0.3);
        border-radius: 6px;
        padding: 2rem;
        margin: 1rem 0;
    }
    </style>
    <div class='custom-report-card'>
        <div style='font-family:JetBrains Mono,monospace; font-size:0.65rem; color:#d85a30; letter-spacing:0.18em; margin-bottom:0.5rem;'>
            PRO FEATURE
        </div>
        <h3 style='font-family:Instrument Serif,serif; font-size:1.5rem; margin:0 0 0.75rem; color:#e8e8e8;'>
            Need a custom intelligence report?
        </h3>
        <p style='color:#aaa; line-height:1.7; max-width:640px; margin-bottom:1.25rem;'>
            Request a tailored analysis for your country, pathogen, or surveillance question.
            Our team will prepare a downloadable PDF report with charts, interpretation, and citations,
            delivered to your inbox within 5 working days.
        </p>
    </div>
    """, unsafe_allow_html=True)
    # NOTE: Replace placeholder URL with your actual Custom Report formspree form URL
st.markdown(
        """
        <a href="https://formspree.io/f/mwvyeypw" target="_blank" rel="noopener noreferrer"
        style="display:inline-block; background:#d85a30; color:#fff; padding:0.6rem 1.4rem;
        border-radius:2px; text-decoration:none; font-size:0.9rem; font-weight:500;
        font-family:Inter,sans-serif; transition:background 0.2s;">
        Request Custom Report →
        </a>
        """,
        unsafe_allow_html=True
    )
   st.caption("Custom reports are a Pro feature delivered manually by the AMRlytics team. "
               "Replies arrive at the email you provide in the form.")


# ============================================================
# PAGE 3: TREND-BASED AI FORECASTING (Pro w/ free demo)
# ============================================================

elif page == "📈 Trend-based AI Forecasting":
    st.title("Trend-based AI Forecasting")
    st.caption("Prophet time-series model · projections with 80% confidence intervals")

    if st.session_state.pro_unlocked:
        # ---- FULL PRO ACCESS ----
        st.sidebar.markdown("### Forecast parameters")

        specimens = sorted(set(r.get("specimen", "BLOOD") for r in all_data))
        selected_specimen = st.sidebar.selectbox("Infection type", specimens,
            format_func=lambda x: specimen_labels.get(x, x)) if len(specimens) > 1 else specimens[0]

        available_pathogens = sorted(set(r["pathogen"] for r in all_data
            if r.get("specimen", "BLOOD") == selected_specimen))
        selected_pathogen = st.sidebar.selectbox("Pathogen", available_pathogens)

        available_antibiotics = sorted(set(r["antibiotic"] for r in all_data
            if r["pathogen"] == selected_pathogen
            and r.get("specimen", "BLOOD") == selected_specimen))
        selected_antibiotic = st.sidebar.selectbox("Antibiotic", available_antibiotics)

        country_years = defaultdict(set)
        for r in all_data:
            if (r["pathogen"] == selected_pathogen
                and r["antibiotic"] == selected_antibiotic
                and r.get("specimen", "BLOOD") == selected_specimen):
                country_years[r["country"]].add(r["year"])
        eligible = sorted([c for c, yrs in country_years.items() if len(yrs) >= 5])

        if not eligible:
            st.warning(f"No countries with ≥5 years of data for {selected_pathogen} + {selected_antibiotic}.")
            st.stop()

        selected_country = st.sidebar.selectbox(f"Country ({len(eligible)} eligible)", eligible)
        forecast_years = st.sidebar.slider("Years to forecast", 3, 10, 5)

        historical = []
        for r in all_data:
            if (r["pathogen"] == selected_pathogen
                and r["antibiotic"] == selected_antibiotic
                and r["country"] == selected_country
                and r.get("specimen", "BLOOD") == selected_specimen):
                try:
                    historical.append({"year": int(r["year"]), "pct": float(r["resistance"])})
                except (ValueError, TypeError):
                    continue
        historical = sorted(historical, key=lambda x: x["year"])

        is_ll, ll_desc = is_last_line(selected_antibiotic)
        if is_ll:
            st.warning(f"⚠ **{selected_antibiotic}** — {ll_desc}")

        st.markdown(f"### {selected_pathogen} — {selected_antibiotic}")
        st.caption(f"**{selected_country}** · {len(historical)} years ({historical[0]['year']}–{historical[-1]['year']})")

        with st.spinner("Training Prophet model..."):
            try:
                pred, hist_df = run_prophet_forecast(historical, forecast_years)
                title = f"{forecast_years}-year forecast · 80% CI"
                chart = render_forecast_chart(pred, historical, forecast_years, title)
                st.altair_chart(chart, use_container_width=True)

                # Forecast table
                chart_rows = []
                for _, r in pred.iterrows():
                    year = r["ds"].year
                    is_forecast = year > historical[-1]["year"]
                    chart_rows.append({"Year": year, "Resistance (%)": round(float(r["yhat"]), 1),
                        "Lower": round(float(r["yhat_lower"]), 1),
                        "Upper": round(float(r["yhat_upper"]), 1),
                        "Type": "Forecast" if is_forecast else "Historical"})
                chart_df = pd.DataFrame(chart_rows)
                forecast_only = chart_df[chart_df["Type"] == "Forecast"][
                    ["Year", "Resistance (%)", "Lower", "Upper"]].copy()
                forecast_only.columns = ["Year", "Predicted (%)", "Lower (80% CI)", "Upper (80% CI)"]
                st.dataframe(forecast_only, use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Forecasting error: {e}")

    else:
        # ---- FREE TIER: show the locked screen + ONE free demo ----
        render_pro_lock_screen(
            "Trend-based AI Forecasting",
            "Project resistance trends 3–10 years forward using Prophet time-series models, "
            "with 80% confidence intervals. Pro pilots can forecast any country–pathogen–antibiotic "
            "combination with sufficient historical data."
        )

        st.markdown("---")
        st.markdown("### 🎁 Free demo — try it now")
        st.caption(f"Below is a live forecast for **{FREE_DEMO_PATHOGEN}** ({FREE_DEMO_ANTIBIOTIC}) "
                   f"in **{FREE_DEMO_COUNTRY}**, using 25 years of ECDC EARS-Net data. "
                   f"Pro pilots can run this for any combination.")

        # Try to run the demo forecast
        demo_records = [r for r in all_data
                        if r["country"] == FREE_DEMO_COUNTRY
                        and r["pathogen"] == FREE_DEMO_PATHOGEN
                        and FREE_DEMO_ANTIBIOTIC.lower() in r["antibiotic"].lower()]

        if not demo_records:
            # Try alternative MRSA naming
            demo_records = [r for r in all_data
                            if r["country"] == FREE_DEMO_COUNTRY
                            and r["pathogen"] == FREE_DEMO_PATHOGEN
                            and ("methicillin" in r["antibiotic"].lower()
                                 or "meticillin" in r["antibiotic"].lower())]

        if demo_records:
            historical = []
            for r in demo_records:
                try:
                    historical.append({"year": int(r["year"]), "pct": float(r["resistance"])})
                except (ValueError, TypeError):
                    continue
            historical = sorted(historical, key=lambda x: x["year"])

            if len(historical) >= 5:
                with st.spinner("Running demo forecast…"):
                    try:
                        pred, _ = run_prophet_forecast(historical, 5)
                        title = f"DEMO · {FREE_DEMO_COUNTRY} MRSA · 5-year forecast · 80% CI"
                        chart = render_forecast_chart(pred, historical, 5, title)
                        st.altair_chart(chart, use_container_width=True)
                        st.success(
                            f"📈 The model projects MRSA resistance in {FREE_DEMO_COUNTRY} "
                            f"based on {len(historical)} years of ECDC data. "
                            f"Want to forecast for your country or pathogen of interest? "
                            f"[Request Pro access →](https://amrlytics.ai/#contact)"
                        )
                    except Exception as e:
                        st.warning(f"Demo unavailable: {e}")
            else:
                st.info("Demo data not available locally. Pro pilots can run forecasts on the full dataset.")
        else:
            st.info(
                f"Free demo unavailable in current data. Pro pilots can run forecasts for any "
                f"country–pathogen–antibiotic combination with ≥5 years of historical data."
            )


# ============================================================
# PAGE 4: ALERTS & INSIGHTS (Tab 1 free, others Pro — accordion)
# ============================================================

elif page == "⚠ Alerts & Insights":
    st.title("Alerts & Actionable Insights")
    st.caption("Risk classification · Last-line drug monitoring · Acceleration alerts · Actionable interpretation")

    st.markdown("""
    AMRlytics scans the surveillance dataset and surfaces concerning patterns. Click any section below to explore.
    """)

    # Build alerts (cached, runs once)
    @st.cache_data
    def build_alerts():
        critical_alerts = []
        last_line_alerts = []
        acceleration_alerts = []
        groups = defaultdict(list)
        for r in all_data:
            try:
                pct = float(r["resistance"])
                key = (r["pathogen"], r["antibiotic"], r["country"], r.get("specimen", "BLOOD"))
                groups[key].append({"year": int(r["year"]), "pct": pct, "source": r["source"]})
            except (ValueError, TypeError):
                continue
        for (pathogen, antibiotic, country, specimen), records in groups.items():
            records = sorted(records, key=lambda x: x["year"])
            if not records:
                continue
            latest = records[-1]
            tier_name, color, desc = get_tier(latest["pct"])
            if tier_name in ("Critical", "Extreme"):
                critical_alerts.append({
                    "Pathogen": pathogen, "Antibiotic": antibiotic, "Country": country,
                    "Specimen": specimen_labels.get(specimen, specimen),
                    "Year": latest["year"], "Resistance (%)": latest["pct"],
                    "Tier": tier_name, "Source": latest["source"],
                })
            is_ll, ll_desc = is_last_line(antibiotic)
            if is_ll and latest["pct"] >= 10:
                last_line_alerts.append({
                    "Pathogen": pathogen, "Antibiotic": antibiotic, "Country": country,
                    "Specimen": specimen_labels.get(specimen, specimen),
                    "Year": latest["year"], "Resistance (%)": latest["pct"],
                    "Tier": tier_name, "Note": ll_desc,
                })
            if len(records) >= 2:
                latest_year = records[-1]["year"]
                target_baseline_year = latest_year - 3
                baseline_candidates = [r for r in records if r["year"] <= target_baseline_year]
                if not baseline_candidates:
                    baseline_candidates = [records[0]]
                baseline = baseline_candidates[-1]
                change = latest["pct"] - baseline["pct"]
                if change >= 10:
                    acceleration_alerts.append({
                        "Pathogen": pathogen, "Antibiotic": antibiotic, "Country": country,
                        "Specimen": specimen_labels.get(specimen, specimen),
                        "Baseline year": baseline["year"], "Baseline (%)": baseline["pct"],
                        "Latest year": latest_year, "Latest (%)": latest["pct"],
                        "Change (pts)": round(change, 1),
                    })
        return critical_alerts, last_line_alerts, acceleration_alerts

    critical_alerts, last_line_alerts, acceleration_alerts = build_alerts()

    col1, col2, col3 = st.columns(3)
    col1.metric("Critical/Extreme alerts", len(critical_alerts), "Resistance >50%")
    col2.metric("Last-line drug alerts", len(last_line_alerts), "Reserve agents")
    col3.metric("3-year acceleration", len(acceleration_alerts), "Change >10 pts")

    st.markdown("---")

    # ---- Tab 1: Critical & Extreme (FREE, accordion) ----
    with st.expander("🔴 Critical & Extreme alerts (Free)", expanded=False):
        st.caption("Combinations where resistance has reached >50% — empiric therapy strongly discouraged at this level.")
        if critical_alerts:
            df = pd.DataFrame(critical_alerts).sort_values("Resistance (%)", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True, height=500)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download as CSV", csv, "amrlytics_critical_alerts.csv", "text/csv")
        else:
            st.info("No critical alerts in current data.")

    # ---- Tab 2: Last-line drugs (PRO) ----
    with st.expander("💊 Last-line drug alerts (Pro)", expanded=False):
        if st.session_state.pro_unlocked:
            st.caption("WHO AWaRe Reserve and key last-line agents where resistance ≥10%.")
            if last_line_alerts:
                df = pd.DataFrame(last_line_alerts).sort_values("Resistance (%)", ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True, height=500)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("Download as CSV", csv, "amrlytics_last_line_alerts.csv", "text/csv")
            else:
                st.info("No last-line alerts at current data thresholds.")
        else:
            render_pro_lock_screen(
                "Last-line drug alerts",
                "Track resistance to WHO AWaRe Reserve antibiotics — Carbapenems, Colistin, Vancomycin, "
                "Daptomycin, Linezolid, Ceftaroline, Ceftazidime-avibactam, Cefiderocol — across all countries. "
                "When these drugs fail, treatment options become limited."
            )

    # ---- Tab 3: 3-year acceleration (PRO) ----
    with st.expander("📈 3-year acceleration alerts (Pro)", expanded=False):
        if st.session_state.pro_unlocked:
            st.caption("Combinations where resistance increased by ≥10 percentage points over 3 years.")
            if acceleration_alerts:
                df = pd.DataFrame(acceleration_alerts).sort_values("Change (pts)", ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True, height=500)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("Download as CSV", csv, "amrlytics_acceleration_alerts.csv", "text/csv")
            else:
                st.info("No acceleration alerts at current data thresholds.")
        else:
            render_pro_lock_screen(
                "3-year acceleration alerts",
                "Identify countries where resistance has accelerated rapidly over a 3-year window. "
                "These rapid changes often signal emerging epidemics, outbreak clusters, or stewardship failures "
                "that warrant immediate investigation."
            )

    # ---- Tab 4: Actionable Insights (PRO) ----
    with st.expander("🎯 Actionable insights — query a specific combination (Pro)", expanded=False):
        if st.session_state.pro_unlocked:
            st.caption("Get a structured interpretation for any pathogen/antibiotic/country combination.")
            col1, col2, col3 = st.columns(3)
            with col1:
                ai_pathogen = st.selectbox("Pathogen",
                    sorted(set(r["pathogen"] for r in all_data)), key="ai_p")
            with col2:
                ai_antibiotic = st.selectbox("Antibiotic",
                    sorted(set(r["antibiotic"] for r in all_data
                              if r["pathogen"] == ai_pathogen)), key="ai_a")
            with col3:
                ai_country = st.selectbox("Country",
                    sorted(set(r["country"] for r in all_data
                              if r["pathogen"] == ai_pathogen
                              and r["antibiotic"] == ai_antibiotic)), key="ai_c")

            result = get_resistance_for_combo(ai_pathogen, ai_antibiotic, ai_country)
            if result:
                pct, year = result
                tier_name, color, desc = get_tier(pct)
                is_ll, ll_desc = is_last_line(ai_antibiotic)
                change = get_3yr_change(ai_pathogen, ai_antibiotic, ai_country)

                st.markdown("---")
                st.markdown(f"### {ai_pathogen} — {ai_antibiotic} in {ai_country}")

                col1, col2, col3 = st.columns(3)
                col1.metric("Latest resistance", f"{pct:.1f}%", f"in {year}")
                col2.metric("Risk tier", tier_name)
                if change:
                    col3.metric("3-year change", f"{change['change']:+.1f} pts",
                               f"{change['baseline_year']} → {change['latest_year']}")

                st.markdown("### Interpretation")
                interpretation = []
                if tier_name == "Low":
                    interpretation.append(f"✅ **Resistance level: {pct:.1f}% (Low tier)** — {desc}.")
                elif tier_name == "Moderate":
                    interpretation.append(f"🟡 **Resistance level: {pct:.1f}% (Moderate tier)** — {desc}.")
                elif tier_name == "High":
                    interpretation.append(f"🟠 **Resistance level: {pct:.1f}% (High tier)** — {desc}.")
                elif tier_name == "Critical":
                    interpretation.append(f"🔴 **Resistance level: {pct:.1f}% (Critical tier)** — {desc}.")
                elif tier_name == "Extreme":
                    interpretation.append(f"⛔ **Resistance level: {pct:.1f}% (Extreme tier)** — {desc}.")

                if is_ll:
                    interpretation.append(f"⚠ **{ai_antibiotic} is a reserve/last-line antibiotic** ({ll_desc}).")

                if change and change['change'] >= 10:
                    interpretation.append(f"📈 **Rapid increase:** {change['change']:.1f} percentage points in 3 years.")
                elif change and change['change'] <= -10:
                    interpretation.append(f"📉 **Encouraging decline:** {abs(change['change']):.1f} percentage points in 3 years.")

                for line in interpretation:
                    st.markdown(line)

                st.markdown("### Surveillance-supported alternatives")
                st.caption("Other antibiotics tested in this country, sorted by lowest resistance. **NOT a prescribing recommendation.**")

                other_drugs = [r for r in all_data
                              if r["pathogen"] == ai_pathogen
                              and r["country"] == ai_country
                              and r["antibiotic"] != ai_antibiotic]
                drug_latest = {}
                for r in other_drugs:
                    try:
                        pct_r = float(r["resistance"])
                        year_r = int(r["year"])
                        if r["antibiotic"] not in drug_latest or year_r > drug_latest[r["antibiotic"]]["year"]:
                            drug_latest[r["antibiotic"]] = {"pct": pct_r, "year": year_r,
                                                            "source": r["source"]}
                    except (ValueError, TypeError):
                        continue

                if drug_latest:
                    alt_rows = []
                    for ab, info in drug_latest.items():
                        tier, _, _ = get_tier(info["pct"])
                        is_ll_alt, _ = is_last_line(ab)
                        alt_rows.append({
                            "Antibiotic": ab,
                            "Resistance (%)": round(info["pct"], 1),
                            "Tier": tier,
                            "Last-line": "Yes" if is_ll_alt else "—",
                            "Year": info["year"],
                            "Source": info["source"],
                        })
                    alt_df = pd.DataFrame(alt_rows).sort_values("Resistance (%)")
                    st.dataframe(alt_df, use_container_width=True, hide_index=True)
                    st.warning("⚠ Population-level surveillance data, NOT prescribing guidance. Treatment decisions require local antibiograms, susceptibility testing, and clinical judgement.")
                else:
                    st.info("No alternative antibiotics with surveillance data for this combination.")
            else:
                st.warning("No data for this combination.")
        else:
            render_pro_lock_screen(
                "Actionable insights",
                "Query any pathogen/antibiotic/country combination and receive a structured interpretation: "
                "risk tier classification, last-line drug warnings, 3-year change analysis, and a sorted list "
                "of surveillance-supported alternative antibiotics with WHO AWaRe classification."
            )


# ============================================================
# PAGE 5: BENCHMARKING (Tab 1 free, Tabs 2-3 Pro — accordion)
# ============================================================

elif page == "🌐 Benchmarking":
    st.title("Benchmarking")
    st.caption("Compare countries against regional averages, WHO BPPL classification, and trajectory peers")

    if not all_data:
        st.error("No data loaded.")
        st.stop()

    st.sidebar.markdown("### Benchmark parameters")
    pathogens = sorted(set(r["pathogen"] for r in all_data))
    bench_pathogen = st.sidebar.selectbox("Pathogen", pathogens, key="b_p")
    antibiotics = sorted(set(r["antibiotic"] for r in all_data if r["pathogen"] == bench_pathogen))
    bench_antibiotic = st.sidebar.selectbox("Antibiotic", antibiotics, key="b_a")
    countries = sorted(set(r["country"] for r in all_data
        if r["pathogen"] == bench_pathogen and r["antibiotic"] == bench_antibiotic))
    bench_country = st.sidebar.selectbox("Country", countries, key="b_c")

    # ---- Tab 1: vs WHO Region (FREE) ----
    with st.expander("🌍 Country vs WHO Region (Free)", expanded=False):
        st.markdown(f"### {bench_country} vs its WHO region")
        st.caption("Compare a country's resistance trajectory against its WHO regional median.")

        country_records = [r for r in all_data if r["country"] == bench_country]
        if country_records:
            country_region = country_records[0].get("region", "Unknown")
            st.markdown(f"**Region:** {country_region}")

            relevant = [r for r in all_data
                       if r["pathogen"] == bench_pathogen
                       and r["antibiotic"] == bench_antibiotic]

            country_data = []
            for r in relevant:
                if r["country"] == bench_country:
                    try:
                        country_data.append({"Year": int(r["year"]),
                            "Resistance (%)": round(float(r["resistance"]), 1),
                            "Series": bench_country})
                    except (ValueError, TypeError):
                        continue

            regional = [r for r in relevant if r.get("region") == country_region]
            regional_by_year = defaultdict(list)
            for r in regional:
                try:
                    regional_by_year[int(r["year"])].append(float(r["resistance"]))
                except (ValueError, TypeError):
                    continue
            regional_data = []
            for year, vals in sorted(regional_by_year.items()):
                if vals:
                    regional_data.append({"Year": year,
                        "Resistance (%)": round(sum(vals)/len(vals), 1),
                        "Series": f"{country_region} (avg)"})

            global_by_year = defaultdict(list)
            for r in relevant:
                try:
                    global_by_year[int(r["year"])].append(float(r["resistance"]))
                except (ValueError, TypeError):
                    continue
            global_data = []
            for year, vals in sorted(global_by_year.items()):
                if vals:
                    global_data.append({"Year": year,
                        "Resistance (%)": round(sum(vals)/len(vals), 1),
                        "Series": "Global avg"})

            combined = pd.DataFrame(country_data + regional_data + global_data)
            if not combined.empty:
                chart = alt.Chart(combined).mark_line(point=True, strokeWidth=2.5).encode(
                    x=alt.X("Year:O"),
                    y=alt.Y("Resistance (%):Q", scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color("Series:N", scale=alt.Scale(
                        range=["#d85a30", "#3b6d11", "#888"])),
                    tooltip=["Series", "Year", "Resistance (%)"]
                ).properties(height=400, title=f"{bench_pathogen} — {bench_antibiotic}")
                st.altair_chart(chart, use_container_width=True)

                if country_data and regional_data:
                    latest_country = country_data[-1]["Resistance (%)"]
                    latest_regional = regional_data[-1]["Resistance (%)"]
                    diff = latest_country - latest_regional
                    if abs(diff) < 2:
                        msg = f"**{bench_country} is in line with the {country_region} average** ({latest_country:.1f}% vs {latest_regional:.1f}%)."
                    elif diff > 0:
                        msg = f"**{bench_country} is {abs(diff):.1f} pts higher than {country_region} average.**"
                    else:
                        msg = f"**{bench_country} is {abs(diff):.1f} pts lower than {country_region} average.**"
                    st.info(msg)

    # ---- Tab 2: vs WHO BPPL (PRO) ----
    with st.expander("🏛 vs WHO Priority Pathogens List 2024 (Pro)", expanded=False):
        if st.session_state.pro_unlocked:
            st.markdown("### WHO Bacterial Priority Pathogens List 2024")
            st.caption("Classification per WHO BPPL 2024 (Sati et al., Lancet Infect Dis 2025).")

            bppl = {
                "Critical": [
                    ("Mycobacterium tuberculosis", "Rifampicin-resistant"),
                    ("Acinetobacter baumannii", "Carbapenem-resistant"),
                    ("Acinetobacter spp.", "Carbapenem-resistant"),
                    ("Klebsiella pneumoniae", "Carbapenem-resistant / 3GC-resistant"),
                    ("Escherichia coli", "Carbapenem-resistant / 3GC-resistant"),
                ],
                "High": [
                    ("Salmonella spp. (typhoid)", "Fluoroquinolone-resistant"),
                    ("Salmonella spp.", "Fluoroquinolone-resistant"),
                    ("Shigella spp.", "Fluoroquinolone-resistant"),
                    ("Enterococcus faecium", "Vancomycin-resistant"),
                    ("Pseudomonas aeruginosa", "Carbapenem-resistant"),
                    ("Neisseria gonorrhoeae", "3GC- / fluoroquinolone-resistant"),
                    ("Staphylococcus aureus", "Methicillin-resistant"),
                ],
                "Medium": [
                    ("Group A Streptococcus", "Macrolide-resistant"),
                    ("Streptococcus pneumoniae", "Macrolide- / penicillin-resistant"),
                    ("Haemophilus influenzae", "Ampicillin-resistant"),
                    ("Group B Streptococcus", "Penicillin-resistant"),
                ],
            }
            found_tier = None
            for tier, pathogens_list in bppl.items():
                for p_name, _ in pathogens_list:
                    if p_name.lower() in bench_pathogen.lower() or bench_pathogen.lower() in p_name.lower():
                        found_tier = tier
                        break
                if found_tier:
                    break
            if found_tier:
                tier_colors = {"Critical": "#a32d2d", "High": "#d85a30", "Medium": "#ba7517"}
                st.markdown(
                    f"<div style='background:{tier_colors[found_tier]}22; border-left:4px solid {tier_colors[found_tier]}; padding:1rem 1.5rem; border-radius:3px;'>"
                    f"<div style='font-family:JetBrains Mono,monospace; font-size:0.7rem; letter-spacing:0.15em; color:{tier_colors[found_tier]}; text-transform:uppercase;'>WHO BPPL 2024 · {found_tier} Priority</div>"
                    f"<div style='font-family:Instrument Serif,serif; font-size:1.5rem; margin-top:0.5rem;'>{bench_pathogen}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info(f"{bench_pathogen} is not in the WHO BPPL 2024 list.")
            st.markdown("---")
            st.markdown("#### Full WHO BPPL 2024 reference")
            for tier in ["Critical", "High", "Medium"]:
                with st.expander(f"{tier} priority pathogens"):
                    for p, res in bppl[tier]:
                        st.markdown(f"- **{p}** — {res}")
            st.caption("Source: Sati H et al. WHO Bacterial Priority Pathogens List 2024. Lancet Infect Dis 2025.")
        else:
            render_pro_lock_screen(
                "vs WHO Priority Pathogens List 2024",
                "See exactly where the selected pathogen sits on WHO's official Bacterial Priority Pathogens "
                "List (Critical / High / Medium tier), with full WHO BPPL 2024 reference and citations. "
                "Built on Sati et al., Lancet Infectious Diseases 2025."
            )

    # ---- Tab 3: vs Trajectory Peers (PRO) ----
    with st.expander("📊 vs Trajectory Peers (Pro)", expanded=False):
        if st.session_state.pro_unlocked:
            st.markdown(f"### {bench_country} vs trajectory peers")
            st.caption("Find countries that previously had similar resistance levels to track what happened next.")

            country_relevant = [r for r in all_data
                              if r["pathogen"] == bench_pathogen
                              and r["antibiotic"] == bench_antibiotic
                              and r["country"] == bench_country]
            if not country_relevant:
                st.warning("No data for this combination in selected country.")
            else:
                try:
                    latest = max(country_relevant, key=lambda r: int(r["year"]))
                    latest_pct = float(latest["resistance"])
                    latest_year = int(latest["year"])

                    st.markdown(f"**{bench_country} latest:** {latest_pct:.1f}% ({latest_year})")
                    st.markdown(f"Searching for countries that had {latest_pct-5:.1f}–{latest_pct+5:.1f}% in earlier years…")

                    analogs = []
                    for r in all_data:
                        if (r["pathogen"] == bench_pathogen
                            and r["antibiotic"] == bench_antibiotic
                            and r["country"] != bench_country):
                            try:
                                pct = float(r["resistance"])
                                year = int(r["year"])
                                if abs(pct - latest_pct) < 5 and year < latest_year:
                                    analogs.append({"country": r["country"],
                                        "match_year": year, "match_pct": pct})
                            except (ValueError, TypeError):
                                continue

                    trajectory_data = []
                    for r in country_relevant:
                        try:
                            trajectory_data.append({
                                "Country": bench_country,
                                "Years from peer match": int(r["year"]) - latest_year,
                                "Year": int(r["year"]),
                                "Resistance (%)": round(float(r["resistance"]), 1),
                                "Type": "Focal country",
                            })
                        except (ValueError, TypeError):
                            continue

                    seen_countries = set()
                    analog_count = 0
                    for analog in sorted(analogs, key=lambda x: -x["match_year"]):
                        if analog["country"] in seen_countries:
                            continue
                        seen_countries.add(analog["country"])
                        if analog_count >= 5:
                            break
                        for r in all_data:
                            if (r["country"] == analog["country"]
                                and r["pathogen"] == bench_pathogen
                                and r["antibiotic"] == bench_antibiotic):
                                try:
                                    year = int(r["year"])
                                    if year >= analog["match_year"]:
                                        trajectory_data.append({
                                            "Country": analog["country"],
                                            "Years from peer match": year - analog["match_year"],
                                            "Year": year,
                                            "Resistance (%)": round(float(r["resistance"]), 1),
                                            "Type": "Trajectory peer",
                                        })
                                except (ValueError, TypeError):
                                    continue
                        analog_count += 1

                    if len(trajectory_data) > 5:
                        traj_df = pd.DataFrame(trajectory_data)
                        chart = alt.Chart(traj_df).mark_line(point=True, strokeWidth=2).encode(
                            x=alt.X("Years from peer match:Q",
                                title="Years since reaching this resistance level"),
                            y=alt.Y("Resistance (%):Q", scale=alt.Scale(domain=[0, 100])),
                            color=alt.Color("Country:N"),
                            strokeDash=alt.condition(alt.datum.Type == "Focal country",
                                alt.value([0]), alt.value([4, 4])),
                            tooltip=["Country", "Year", "Resistance (%)", "Type"],
                        ).properties(
                            height=400,
                            title=f"Trajectory comparison · countries that previously had ~{latest_pct:.0f}%",
                        )
                        st.altair_chart(chart, use_container_width=True)
                        st.info(f"💡 **{bench_country}** (solid) at year 0. Peers (dashed) reached this level earlier — their trajectory shows possible futures.")
                    else:
                        st.warning("Not enough trajectory peers for meaningful comparison.")
                except (ValueError, TypeError) as e:
                    st.error(f"Trajectory analysis error: {e}")
        else:
            render_pro_lock_screen(
                "vs Trajectory Peers",
                "Find countries that previously had your selected country's current resistance level. See "
                "what happened to those peers next — did resistance rise further, plateau, or decline? An "
                "original methodology unique to AMRlytics."
            )


# ============================================================
# PAGE 6: METHODOLOGY (FREE)
# ============================================================

elif page == "📋 Methodology":
    st.title("Methodology")
    st.caption("Transparent. Scientifically defensible. Limitations explicit.")

    st.markdown("""
AMRlytics integrates surveillance data from multiple international networks. Each network uses
different methodologies, breakpoints, and reporting standards. This page documents how AMRlytics
handles those differences, the basis for its risk classifications, and what users should be
aware of when interpreting the data.
    """)

    st.markdown("---")
    st.markdown("## Data sources")
    st.dataframe(pd.DataFrame([
        {"Source": "WHO GLASS", "Coverage": "90+ countries globally", "Time range": "2018–2023",
         "Specimens": "Bloodstream, urinary, gastrointestinal", "Breakpoints": "Country-determined (CLSI or EUCAST)"},
        {"Source": "ECDC EARS-Net", "Coverage": "30 EU/EEA countries", "Time range": "2000–2024",
         "Specimens": "Invasive (blood, CSF) only", "Breakpoints": "EUCAST exclusively"},
    ]), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("## Risk tier classification")
    st.markdown("""
AMRlytics classifies resistance percentages into five tiers, derived from the **empiric therapy success principle**
(≥80% predicted success rate target), widely cited in clinical microbiology. They are **not WHO-published numerical thresholds**.
    """)

    tier_df = pd.DataFrame([
        {"Tier": name, "Resistance range": f"{low}–{high if high < 101 else '100+'}%",
         "Surveillance interpretation": desc}
        for name, low, high, color, desc in RISK_TIERS
    ])
    st.dataframe(tier_df, use_container_width=True, hide_index=True)

    st.markdown("**References:** IDSA 2024, EUCAST 2024 v14, CLSI M100 34th Ed., WHO AWaRe 2023, WHO BPPL 2024 (Sati et al. Lancet ID 2025).")

    st.markdown("---")
    st.markdown("## Last-line / Reserve antibiotics")
    ll_df = pd.DataFrame([
        {"Antibiotic / Class": k, "Classification": v}
        for k, v in LAST_LINE_DRUGS.items()
    ])
    st.dataframe(ll_df, use_container_width=True, hide_index=True)
    st.markdown("**Reference:** WHO AWaRe Classification of Antibiotics 2023.")

    st.markdown("---")
    st.markdown("## Forecasting methodology")
    st.markdown("""
**Model:** Prophet (Meta open-source time-series library)

- `yearly_seasonality=False`, `weekly_seasonality=False`, `daily_seasonality=False`
- `changepoint_prior_scale=0.05` (low — AMR trends evolve slowly)
- `interval_width=0.80` (80% confidence interval)
- All output clamped to [0, 100]

**Eligibility:** ≥5 historical years of data per (country, pathogen, antibiotic) combination.

**Limitations:** Model assumes future patterns resemble past patterns. Cannot predict policy changes,
new antibiotic approvals, surveillance disruptions, or epidemiological shocks.
    """)

    st.markdown("---")
    st.markdown("## Limitations and disclaimers")

    st.warning("""
**AMRlytics is a surveillance and forecasting intelligence tool. It is not clinical decision support.**

- No medical advice. Risk tiers and forecasts are not treatment recommendations.
- Surveillance ≠ clinical antibiogram. Local antibiograms remain the basis for empiric therapy guidelines.
- Reporting bias possible. Absence of data is not absence of resistance.
- Specimen and breakpoint differences exist between WHO GLASS and ECDC EARS-Net.
    """)

    st.markdown("---")
    st.markdown("## Citing AMRlytics")
    st.code("""
AMRlytics: Global antimicrobial resistance intelligence platform.
amrlytics.ai. Data: WHO GLASS (2018–2023) and ECDC EARS-Net (2000–2024).
Risk tier classification adapted from empiric therapy success principle.
Accessed [date].
""", language="text")


# ============================================================
# FOOTER (all pages)
# ============================================================

st.markdown("---")
total_countries = len(set(r["country"] for r in all_data))
total_pathogens = len(set(r["pathogen"] for r in all_data))
total_antibiotics = len(set(r["antibiotic"] for r in all_data))

st.markdown(
    f"<div style='text-align:center; color:#666; font-size:0.78rem; padding:1rem 0; "
    f"font-family: JetBrains Mono, monospace; letter-spacing: 0.08em;'>"
    f"<b>POWERED BY AMRLYTICS</b> · amrlytics.ai · "
    f"{source_text} · "
    f"{len(all_data):,} rows · "
    f"{total_countries} countries · "
    f"{total_pathogens} pathogens · "
    f"{total_antibiotics} antibiotics<br>"
    f"© 2026 AMRLYTICS · ALL RIGHTS RESERVED"
    f"</div>",
    unsafe_allow_html=True,
)
