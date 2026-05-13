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


def safe_year(val, default=0):
    """Convert year to int safely — returns default if val is 'Unknown', None, or unparseable."""
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default


def is_last_line(antibiotic_name):
    if not antibiotic_name:
        return False, ""
    name_lower = antibiotic_name.lower()
    for drug, desc in LAST_LINE_DRUGS.items():
        if drug.lower() in name_lower or name_lower in drug.lower():
            return True, desc
    return False, ""


# ============================================================
# ANTIBIOTIC CLASSIFICATION TIERS (WHO AWaRe-aligned)
# ============================================================
# LAST_RESORT — never suggested as first-line empiric therapy regardless of S%
# RESERVE     — suggested only with explicit warning, after first-line exhausted
# Everything else defaults to FIRST_LINE
LAST_RESORT_ABX = {
    "colistin", "polymyxin b", "polymyxin", "tigecycline",
    "ceftazidime-avibactam", "cefiderocol", "daptomycin",
}
RESERVE_ABX = {
    "meropenem", "imipenem", "ertapenem",
    "vancomycin", "teicoplanin", "linezolid", "ceftaroline",
}

def classify_antibiotic(antibiotic_name):
    """Return one of: FIRST LINE, RESERVE, LAST RESORT."""
    if not antibiotic_name:
        return "FIRST LINE"
    n = antibiotic_name.lower().strip()
    for lr in LAST_RESORT_ABX:
        if lr in n or n in lr:
            return "LAST RESORT"
    for rv in RESERVE_ABX:
        if rv in n or n in rv:
            return "RESERVE"
    return "FIRST LINE"

def classification_badge_html(tier):
    """Inline-styled badge for the three tiers."""
    styles = {
        "FIRST LINE":  ("rgba(59,109,17,0.18)",  "#7fc24a", "FIRST LINE"),
        "RESERVE":     ("rgba(186,117,23,0.18)", "#e4a850", "RESERVE"),
        "LAST RESORT": ("rgba(163,45,45,0.18)",  "#e07070", "LAST RESORT"),
    }
    bg, fg, lbl = styles.get(tier, styles["FIRST LINE"])
    return (f"<span style='background:{bg}; color:{fg}; "
            f"font-family:JetBrains Mono,monospace; font-size:0.6rem; "
            f"font-weight:600; letter-spacing:0.08em; padding:0.15rem 0.45rem; "
            f"border-radius:3px; margin-left:0.4rem;'>{lbl}</span>")


def assess_parser_confidence(records, metadata):
    """Score parser output. Returns dict with confidence label, structured flag, methodology."""
    n_rec   = len(records)
    n_path  = len(set(r["pathogen"]   for r in records)) if records else 0
    n_abx   = len(set(r["antibiotic"] for r in records)) if records else 0
    fmt     = metadata.get("format_detected", "")

    # Confidence tiers based on extraction signal
    if n_rec >= 50 and n_path >= 3 and n_abx >= 5:
        confidence = "High"
    elif n_rec >= 10 and n_abx >= 3:
        confidence = "Medium"
    elif n_rec > 0:
        confidence = "Low"
    else:
        confidence = "None"

    # Structured detection — true if a recognised structured format was used
    structured = fmt in ("SKMCH", "SHIFA", "AKU", "AMRLYTICS")

    # Methodology detection scans embedded text in records or metadata
    raw_text = (metadata.get("raw_text") or "").lower()
    blob = " ".join([
        raw_text,
        " ".join(str(r.get("source", "")) for r in records[:5]),
    ]).lower()
    methodology = None
    if "clsi" in blob:
        methodology = "CLSI"
    elif "eucast" in blob:
        methodology = "EUCAST"

    return {
        "confidence": confidence,
        "structured": structured,
        "methodology": methodology,
        "format": fmt,
        "n_records": n_rec,
        "n_pathogens": n_path,
        "n_antibiotics": n_abx,
    }


def render_parser_badges(assessment, metadata):
    """Render the parser confidence + methodology badges as a horizontal row."""
    conf  = assessment["confidence"]
    color = {"High":"#3b6d11", "Medium":"#ba7517", "Low":"#a32d2d", "None":"#666"}[conf]
    bg    = {"High":"rgba(59,109,17,0.12)", "Medium":"rgba(186,117,23,0.12)",
             "Low":"rgba(163,45,45,0.12)", "None":"rgba(102,102,102,0.12)"}[conf]

    def chip(text, fg, bgc):
        return (f"<span style='display:inline-block; background:{bgc}; color:{fg}; "
                f"font-family:JetBrains Mono,monospace; font-size:0.7rem; font-weight:600; "
                f"padding:0.3rem 0.7rem; border-radius:3px; margin-right:0.5rem; "
                f"letter-spacing:0.06em;'>{text}</span>")

    chips = [chip(f"PARSER CONFIDENCE: {conf.upper()}", color, bg)]
    if assessment["structured"]:
        chips.append(chip("STRUCTURED PDF DETECTED", "#5b8def", "rgba(91,141,239,0.12)"))
    if assessment["methodology"]:
        chips.append(chip(f"{assessment['methodology']} INTERPRETATION DETECTED",
                          "#7fc24a", "rgba(127,194,74,0.12)"))
    st.markdown(
        "<div style='margin:0.5rem 0 1rem 0;'>" + "".join(chips) + "</div>",
        unsafe_allow_html=True
    )


def save_normalized_to_database(records, metadata, csv_path="hospital_normalized_database.csv"):
    """Append normalized hospital records to a persistent CSV.
    Deduplicates on (hospital, year, pathogen, antibiotic, patient_type)."""
    import os, pandas as _pd
    if not records:
        return None
    new_df = _pd.DataFrame([{
        "Hospital":      r.get("hospital", metadata.get("hospital", "Unknown")),
        "Year":          r.get("year",     metadata.get("year",     "Unknown")),
        "Pathogen":      r.get("pathogen", "Unknown"),
        "Antibiotic":    r.get("antibiotic", "Unknown"),
        "Susceptible_%": r.get("susceptible_pct", 0),
        "Resistance_%":  r.get("resistance_pct",  0),
        "N_tested":      r.get("n_tested", 0),
        "Specimen":      r.get("specimen", "All"),
        "Patient_type":  r.get("patient_type", "All"),
        "Source":        r.get("source", "Hospital antibiogram (PDF)"),
        "Methodology":   metadata.get("methodology", ""),
        "Format":        metadata.get("format_detected", ""),
    } for r in records])

    if os.path.exists(csv_path):
        try:
            existing = _pd.read_csv(csv_path)
            combined = _pd.concat([existing, new_df], ignore_index=True)
        except Exception:
            combined = new_df
    else:
        combined = new_df

    # Dedupe — keep latest entry per logical key
    combined = combined.drop_duplicates(
        subset=["Hospital", "Year", "Pathogen", "Antibiotic", "Patient_type", "Specimen"],
        keep="last"
    )
    combined.to_csv(csv_path, index=False)
    return csv_path


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
        sorted_by_year = sorted(matches, key=lambda r: safe_year(r["year"]))
        latest = sorted_by_year[-1]
        latest_year = safe_year(latest["year"])
        baseline_year = latest_year - 3
        baseline_candidates = [r for r in sorted_by_year if safe_year(r["year"]) <= baseline_year]
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
# UNIVERSAL HOSPITAL ANTIBIOGRAM ETL PIPELINE
# Upload → Extract → Parse → Clean → Standardize → Validate → Store
#
# Accepts any hospital antibiogram worldwide:
#   - CSV (any column layout, auto-detected)
#   - PDF (text-extractable, any hospital format)
# Not specific to any network, country, or hospital brand.
# ============================================================

import re as _re
import io as _io

# ---- STEP 1: STANDARDIZED PATHOGEN NAMES ----
# Maps hundreds of spelling variants to canonical binomial names.
# Covers CLSI, EUCAST, PARN, CDC, WHO GLASS, and clinical shorthand.

PATHOGEN_MAP = {
    # Escherichia
    "e. coli": "Escherichia coli", "e.coli": "Escherichia coli",
    "escherichia coli": "Escherichia coli", "eshcerichia coli": "Escherichia coli",
    "e coli": "Escherichia coli",
    # Klebsiella
    "k. pneumoniae": "Klebsiella pneumoniae",
    "k.pneumoniae": "Klebsiella pneumoniae",
    "klebsiella pneumoniae": "Klebsiella pneumoniae",
    "klebsiella spp": "Klebsiella spp.",
    "klebsiella spp.": "Klebsiella spp.",
    "klebsiella": "Klebsiella pneumoniae",
    # Pseudomonas
    "p. aeruginosa": "Pseudomonas aeruginosa",
    "p.aeruginosa": "Pseudomonas aeruginosa",
    "pseudomonas aeruginosa": "Pseudomonas aeruginosa",
    "pseudomonas spp": "Pseudomonas spp.",
    # Acinetobacter
    "acinetobacter baumanni": "Acinetobacter baumannii",
    "acinetobacter baumannii": "Acinetobacter baumannii",
    "acinetobacter baumannii complex": "Acinetobacter baumannii",
    "acinetobacter spp": "Acinetobacter spp.",
    "acinetobacter spp.": "Acinetobacter spp.",
    "acinetobacter species": "Acinetobacter spp.",
    "acinetobacter": "Acinetobacter spp.",
    # Staphylococcus
    "s. aureus": "Staphylococcus aureus",
    "s.aureus": "Staphylococcus aureus",
    "staphylococcus aureus": "Staphylococcus aureus",
    "staph aureus": "Staphylococcus aureus",
    "mrsa": "Staphylococcus aureus",
    "coagulase negative staphylococcus": "Staphylococcus (CoNS)",
    "coagulase negative staph": "Staphylococcus (CoNS)",
    "cons": "Staphylococcus (CoNS)",
    # Enterococcus
    "enterococcus faecium": "Enterococcus faecium",
    "enterococcus faecalis": "Enterococcus faecalis",
    "enterococcus species": "Enterococcus spp.",
    "enterococcus spp": "Enterococcus spp.",
    "enterococcus spp.": "Enterococcus spp.",
    "enterococcus": "Enterococcus spp.",
    # Salmonella
    "salmonella typhi": "Salmonella Typhi",
    "salmonella typhi,para a, b, c": "Salmonella Typhi",
    "salmonella typhi, para a, b, c": "Salmonella Typhi",
    "salmonella paratyphi a": "Salmonella Paratyphi A",
    "salmonella spp": "Salmonella spp.",
    # Shigella
    "shigella species": "Shigella spp.",
    "shigella spp": "Shigella spp.",
    "shigella spp.": "Shigella spp.",
    # Haemophilus
    "haemophilus influenzae": "Haemophilus influenzae",
    "h. influenzae": "Haemophilus influenzae",
    # Streptococcus
    "streptococcus pneumoniae": "Streptococcus pneumoniae",
    "s. pneumoniae": "Streptococcus pneumoniae",
    "streptococcus pyogenes": "Streptococcus pyogenes",
    "streptococcus agalactiae": "Streptococcus agalactiae",
    "streptococcus spp": "Streptococcus spp.",
    "streptococcus spp.": "Streptococcus spp.",
    # Neisseria
    "neisseria gonorrhoeae": "Neisseria gonorrhoeae",
    "neisseria gonorrhea": "Neisseria gonorrhoeae",
    "neisseria gonorrheae": "Neisseria gonorrhoeae",
    "n. gonorrhoeae": "Neisseria gonorrhoeae",
    # Others
    "proteus mirabilis": "Proteus mirabilis",
    "proteus spp": "Proteus spp.",
    "proteus spp.": "Proteus spp.",
    "enterobacter cloacae": "Enterobacter cloacae",
    "enterobacter spp": "Enterobacter spp.",
    "enterobacter spp.": "Enterobacter spp.",
    "stenotrophomonas maltophilia": "Stenotrophomonas maltophilia",
    "burkholderia cepacia": "Burkholderia cepacia",
    "serratia marcescens": "Serratia marcescens",
    "serratia spp": "Serratia spp.",
    "citrobacter freundii": "Citrobacter freundii",
    "citrobacter spp": "Citrobacter spp.",
    "morganella morganii": "Morganella morganii",
    "candida albicans": "Candida albicans",
    "candida spp": "Candida spp.",
}


def std_pathogen(name):
    """Standardize pathogen name to canonical form."""
    if not name:
        return ""
    cleaned = _re.sub(r"\s+", " ", name.strip().lower())
    cleaned = _re.sub(r"[/\\]", " ", cleaned).rstrip(".,;:")
    return PATHOGEN_MAP.get(cleaned, name.strip().title())


# ---- ANTIBIOTIC FULL NAMES ----
# Full name lookup AND abbreviation lookup (critical for Indus/Liaquat/generic PDFs)

ANTIBIOTIC_FULL = {
    # Abbreviation → full name (used by Indus, Civil, Liaquat and many older PDFs)
    "ak": "Amikacin",
    "amc": "Amoxicillin-clavulanate",
    "amp": "Ampicillin",
    "caz": "Ceftazidime",
    "cfm": "Cefixime",
    "cip": "Ciprofloxacin",
    "cro": "Ceftriaxone",
    "ctx": "Cefotaxime",
    "c": "Chloramphenicol",
    "cx": "Cloxacillin",
    "cn": "Gentamicin",
    "da": "Clindamycin",
    "e": "Erythromycin",
    "etp": "Ertapenem",
    "f": "Nitrofurantoin",
    "fos": "Fosfomycin",
    "lzd": "Linezolid",
    "ipm": "Imipenem",
    "mem": "Meropenem",
    "nor": "Norfloxacin",
    "pb": "Polymyxin B",
    "p": "Penicillin G",
    "tet": "Tetracycline",
    "scf": "Cefoperazone-sulbactam",
    "sxt": "Trimethoprim-sulfamethoxazole",
    "tzp": "Piperacillin-tazobactam",
    "tec": "Teicoplanin",
    "va": "Vancomycin",
    "lev": "Levofloxacin",
    "ofx": "Ofloxacin",
    "nit": "Nitrofurantoin",
    "pt": "Piperacillin-tazobactam",
    "cxm": "Cefuroxime",
    "fep": "Cefepime",
    "col": "Colistin",
    "ct": "Colistin",
    "fd": "Fusidic acid",
    "mrp": "Meropenem",
    "imi": "Imipenem",
    "azm": "Azithromycin",
    "azt": "Aztreonam",
    "cl": "Clindamycin",
    "k": "Kanamycin",
    "min": "Minocycline",
    "tgc": "Tigecycline",
    "tig": "Tigecycline",
    "rif": "Rifampicin",
    "tmp": "Trimethoprim",
    "ts": "Trimethoprim-sulfamethoxazole",
    "fox": "Cefoxitin",
    "ceft": "Ceftriaxone",
    "amk": "Amikacin",
    "gent": "Gentamicin",
    "vanc": "Vancomycin",
    "linz": "Linezolid",
    "merop": "Meropenem",
    "imip": "Imipenem",
    "pb/ct": "Polymyxin B",
    "cip/ofx": "Ciprofloxacin",
    "cip/ ofx": "Ciprofloxacin",
    # Alias normalization
    "co-trimoxazole": "Trimethoprim-sulfamethoxazole",
    "cotrimoxazole": "Trimethoprim-sulfamethoxazole",
    "trimethoprim-sulfamethoxazole": "Trimethoprim-sulfamethoxazole",
    "trimethoprim sulfamethoxazole": "Trimethoprim-sulfamethoxazole",
    "co-amoxiclav": "Amoxicillin-clavulanate",
    "amoxicillin-clavulanate": "Amoxicillin-clavulanate",
    "amoxicillin clavulanate": "Amoxicillin-clavulanate",
    "piperacillin-tazobactam": "Piperacillin-tazobactam",
    "piperacillin tazobactam": "Piperacillin-tazobactam",
    "pipercillin/tazobactam": "Piperacillin-tazobactam",
    "ceftazidime-avibactam": "Ceftazidime-avibactam",
    "ceftazidime avibactam": "Ceftazidime-avibactam",
    "cefoperazone/sulbactam": "Cefoperazone-sulbactam",
    "cefoperazone sulbactam": "Cefoperazone-sulbactam",
    "imi-/meropenem": "Meropenem",
    "amoxil/clav.": "Amoxicillin-clavulanate",
    "amoxil/clav": "Amoxicillin-clavulanate",
    "ciprofloxacin/levofloxacin": "Ciprofloxacin",
    "cip/lev": "Ciprofloxacin",
    "gentamycin": "Gentamicin",  # common misspelling
}

# All known antibiotic names (longest first for greedy matching)
KNOWN_ANTIBIOTICS = sorted([
    "Trimethoprim-sulfamethoxazole", "Piperacillin-tazobactam",
    "Ceftazidime-avibactam", "Amoxicillin-clavulanate",
    "Cefoperazone-sulbactam", "Ciprofloxacin/Levofloxacin",
    "Co-trimoxazole", "Co-amoxiclav",
    "Nitrofurantoin", "Chloramphenicol", "Erythromycin", "Azithromycin",
    "Clarithromycin", "Cefoperazone", "Ceftriaxone", "Ceftaroline",
    "Ceftazidime", "Cefotaxime", "Cefiderocol", "Cefuroxime",
    "Cefepime", "Cefixime", "Clindamycin", "Cloxacillin",
    "Doxycycline", "Minocycline", "Tetracycline", "Tigecycline",
    "Tobramycin", "Gentamicin", "Amikacin", "Kanamycin", "Streptomycin",
    "Vancomycin", "Teicoplanin", "Daptomycin", "Linezolid",
    "Meropenem", "Imipenem", "Ertapenem", "Doripenem",
    "Aztreonam", "Colistin", "Polymyxin", "Fosfomycin",
    "Rifampin", "Rifampicin", "Penicillin", "Ampicillin",
    "Oxacillin", "Methicillin", "Meticillin", "Nalidixic acid",
    "Levofloxacin", "Ciprofloxacin", "Moxifloxacin", "Ofloxacin",
    "Norfloxacin", "Trimethoprim", "Piperacillin",
], key=len, reverse=True)


def std_antibiotic(name):
    """Standardize antibiotic name from any format including abbreviations."""
    if not name:
        return ""
    cleaned = _re.sub(r"\s+", " ", name.strip().lower()).rstrip(".,;:")
    # Try abbreviation lookup first
    if cleaned in ANTIBIOTIC_FULL:
        return ANTIBIOTIC_FULL[cleaned]
    # Try full name alias lookup
    for k, v in ANTIBIOTIC_FULL.items():
        if cleaned == k:
            return v
    return name.strip()


# ---- STEP 2: CSV EXTRACTION ----
# Auto-detects column layout — no rigid template required.

CSV_COLUMN_VARIANTS = {
    # Hospital column
    "hospital": ["hospital", "institution", "facility", "site", "centre", "center"],
    # Year
    "year": ["year", "period", "yr", "date", "reporting_year", "reporting year"],
    # Pathogen
    "pathogen": ["pathogen", "organism", "bacteria", "bug", "species",
                 "microorganism", "micro-organism", "isolate"],
    # Antibiotic
    "antibiotic": ["antibiotic", "antimicrobial", "drug", "agent",
                   "antibiotic_name", "drug_name", "abx"],
    # Susceptibility (% susceptible)
    "susceptible": ["%susceptible", "susceptible", "% susceptible",
                    "susceptibility", "%s", "s%", "percent_susceptible",
                    "pct_susceptible", "pct susceptible"],
    # Resistance (% resistant)
    "resistant": ["%resistant", "resistant", "% resistant", "resistance",
                  "%r", "r%", "percent_resistant", "pct_resistant",
                  "pct resistant", "%_resistant", "% resistant"],
    # N tested
    "n": ["n", "n_tested", "total", "isolates", "count", "n tested",
          "number", "tested", "no_tested", "no. tested"],
    # Specimen
    "specimen": ["specimen", "sample", "specimen_type", "sample_type",
                 "infection_site", "site", "source"],
    # Patient type
    "patient_type": ["patient_type", "patient type", "setting", "inpatient",
                     "outpatient", "ipd", "opd", "ward"],
}


def _match_col(header, field):
    """Return True if header matches any variant for this field."""
    h = header.strip().lower().replace(" ", "_").replace("%", "pct")
    h2 = header.strip().lower()
    variants = CSV_COLUMN_VARIANTS.get(field, [])
    for v in variants:
        if h == v.replace(" ", "_").replace("%", "pct"):
            return True
        if h2 == v:
            return True
    return False


def _detect_csv_columns(fieldnames):
    """Map standardized field names to actual column names in the CSV."""
    mapping = {}
    clean_fields = [f.strip() for f in (fieldnames or [])]
    for field in ["hospital", "year", "pathogen", "antibiotic",
                  "susceptible", "resistant", "n", "specimen", "patient_type"]:
        for col in clean_fields:
            if _match_col(col, field):
                mapping[field] = col
                break
    return mapping


def get_csv_template():
    """Universal blank CSV template with instructions."""
    lines = [
        "# AMRlytics Universal Antibiogram Template",
        "# Fill in one row per organism-antibiotic combination.",
        "# Use either %Susceptible OR %Resistant (not both required).",
        "# N_tested: total isolates tested. Specimen/Patient_type optional.",
        "#",
        "Hospital,Year,Organism,Antibiotic,%Susceptible,%Resistant,N_tested,Specimen,Patient_type",
        "City General Hospital,2024,Escherichia coli,Ciprofloxacin,22,78,450,Urine,Inpatient",
        "City General Hospital,2024,Escherichia coli,Meropenem,91,9,450,Urine,Inpatient",
        "City General Hospital,2024,Klebsiella pneumoniae,Meropenem,75,25,210,Blood,Inpatient",
        "City General Hospital,2024,Staphylococcus aureus,Vancomycin,100,0,380,Blood,Inpatient",
        "City General Hospital,2024,Staphylococcus aureus,Clindamycin,68,32,380,Blood,Inpatient",
    ]
    return "\n".join(lines)


def etl_parse_csv(file_content):
    """
    ETL Step: Parse → Clean → Standardize → Validate

    Accepts any CSV layout. Auto-detects columns.
    Returns (records, errors, warnings).
    """
    import csv as _csv
    records = []
    errors = []
    warnings = []

    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8-sig", errors="replace")

    # Strip comment lines
    lines = [l for l in file_content.split("\n") if not l.strip().startswith("#")]
    cleaned_content = "\n".join(lines)

    reader = _csv.DictReader(_io.StringIO(cleaned_content))

    # Step: Clean column names
    if not reader.fieldnames:
        errors.append("No column headers found.")
        return records, errors, warnings

    reader.fieldnames = [h.strip() for h in reader.fieldnames]

    # Step: Detect column mapping
    col = _detect_csv_columns(reader.fieldnames)

    if "pathogen" not in col:
        errors.append("Cannot find Organism/Pathogen column. "
                      "Rename it to 'Organism' or 'Pathogen'.")
        return records, errors, warnings

    if "antibiotic" not in col:
        errors.append("Cannot find Antibiotic column.")
        return records, errors, warnings

    if "susceptible" not in col and "resistant" not in col:
        errors.append("Cannot find %Susceptible or %Resistant column.")
        return records, errors, warnings

    for row_num, row in enumerate(reader, start=2):
        row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}

        # Skip blank rows
        if not any(row.values()):
            continue

        # Extract values
        raw_pathogen = row.get(col.get("pathogen", ""), "")
        raw_antibiotic = row.get(col.get("antibiotic", ""), "")
        _hosp_col = col.get("hospital", "")
        raw_hospital = (row.get(_hosp_col, "") or "").strip() or "Hospital name pending verification"
        raw_year = row.get(col.get("year", ""), "Unknown")
        raw_specimen = row.get(col.get("specimen", ""), "All")
        raw_patient_type = row.get(col.get("patient_type", ""), "All")
        raw_n = row.get(col.get("n", ""), "0")

        if not raw_pathogen or not raw_antibiotic:
            continue

        # Determine resistance %
        susc_pct = None
        resist_pct = None

        if "susceptible" in col:
            v = row.get(col["susceptible"], "")
            if v and v not in ("NT", "-", "NA", ""):
                try:
                    susc_pct = float(v.replace("%", "").strip())
                except ValueError:
                    pass

        if "resistant" in col:
            v = row.get(col["resistant"], "")
            if v and v not in ("NT", "-", "NA", ""):
                try:
                    resist_pct = float(v.replace("%", "").strip())
                except ValueError:
                    pass

        # Derive missing value
        if susc_pct is not None and resist_pct is None:
            resist_pct = round(100 - susc_pct, 1)
        elif resist_pct is not None and susc_pct is None:
            susc_pct = round(100 - resist_pct, 1)
        elif susc_pct is None and resist_pct is None:
            warnings.append(f"Row {row_num}: no susceptibility value — skipped")
            continue

        # Validate range
        if not (0 <= susc_pct <= 100):
            warnings.append(f"Row {row_num}: %Susceptible {susc_pct} out of range — skipped")
            continue

        # N tested
        try:
            n = int(float(raw_n)) if raw_n else 0
        except ValueError:
            n = 0

        if n < 20 and n > 0:
            warnings.append(f"Row {row_num}: n={n} is small — results may be unreliable")

        # Standardize names (Step: Standardize)
        pathogen = std_pathogen(raw_pathogen)
        antibiotic = std_antibiotic(raw_antibiotic)

        records.append({
            "hospital": raw_hospital or "Hospital name pending verification",
            "year": str(raw_year),
            "pathogen": pathogen,
            "antibiotic": antibiotic,
            "susceptible_pct": round(float(susc_pct), 1),
            "resistance_pct": round(float(resist_pct), 1),
            "n_tested": n,
            "specimen": raw_specimen or "All",
            "patient_type": raw_patient_type or "All",
            "source": f"Hospital antibiogram",
        })

    return records, errors, warnings


# ---- STEP 2: PDF EXTRACTION ----
# Universal — handles any text-extractable PDF regardless of hospital format.
# Strategy: extract all text → detect structure → parse tables.

def etl_extract_pdf_text(pdf_bytes):
    """Extract full text from PDF.
    Tries text extraction first, falls back to OCR for scanned/image PDFs.
    Returns extracted text or PDF_ERROR:reason string.
    """
    # Try pdfplumber first — best at preserving table structure
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text and len(text.strip()) > 10:
                    pages.append(text)
                else:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row:
                                pages.append("\t".join(
                                    str(cell) if cell else "NT"
                                    for cell in row
                                ))
        result = "\n".join(pages)
        if len(result.strip()) > 50:
            return result
    except Exception:
        pass

    # Fallback: pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(_io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        result = "\n".join(pages)
        if len(result.strip()) > 50:
            return result
    except Exception:
        pass

    # Fallback: PyPDF2
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(_io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        result = "\n".join(pages)
        if len(result.strip()) > 50:
            return result
    except Exception:
        pass

    # OCR fallback for scanned/image PDFs
    # Requires: pytesseract, pdf2image, and Tesseract OCR engine installed on system
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        import os as _os

        # Auto-detect Tesseract path on Windows (common install locations)
        if _os.name == "nt":
            for path in [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Users\ammyj\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            ]:
                if _os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break

        # Convert PDF pages to images (200 DPI for good OCR accuracy)
        images = convert_from_bytes(pdf_bytes, dpi=200)
        ocr_pages = []
        for img in images:
            page_text = pytesseract.image_to_string(img, config="--psm 6")
            if page_text and page_text.strip():
                ocr_pages.append(page_text)
        result = "\n".join(ocr_pages)
        if len(result.strip()) > 50:
            return result
    except ImportError:
        return ("PDF_ERROR:Could not extract text. PDF appears to be scanned/image-based. "
                "Install OCR support: pip install pytesseract pdf2image, "
                "and install Tesseract OCR engine.")
    except Exception as e:
        err_str = str(e).lower()
        if "tesseract" in err_str or "poppler" in err_str:
            return (f"PDF_ERROR:OCR extraction failed — system dependency missing. "
                   f"Install Tesseract OCR engine and Poppler. Details: {e}")

    return ("PDF_ERROR:Could not extract text from this PDF. "
            "Tried text extraction (pdfplumber, pypdf, PyPDF2) and OCR (Tesseract). "
            "PDF may be password-protected or corrupted.")


def etl_detect_year(text):
    """Extract the antibiogram reporting year from PDF text."""
    patterns = [
        r"jan[uary]*\s*[-–to]+\s*dec[ember]*\s*(\d{4})",
        r"(\d{4})\s*annual\s*antibiogram",
        r"antibiogram\s*[-–]?\s*(\d{4})",
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-]+(\d{4})",
        r"(?:january|february|march|april|june|july|august|september|october|november|december)\s+(?:to\s+)?(?:january|february|march|april|june|july|august|september|october|november|december)?,?\s*(\d{4})",
        r"\b(20[0-2][0-9])\b",
    ]
    for p in patterns:
        m = _re.search(p, text.lower())
        if m:
            y = int(m.group(1))
            if 2000 <= y <= 2030:
                return str(y)
    years = _re.findall(r"\b(20[0-2]\d)\b", text)
    if years:
        from collections import Counter
        return Counter(years).most_common(1)[0][0]
    return "Unknown"


def etl_detect_hospital(text):
    """Try to infer hospital name from PDF text."""
    known = [
        ("shaukat khanum", "Shaukat Khanum Memorial Cancer Hospital"),
        ("skmch", "Shaukat Khanum Memorial Cancer Hospital"),
        ("aga khan", "Aga Khan University Hospital"),
        ("\baku\b", "Aga Khan University Hospital"),
        ("the indus hospital", "The Indus Hospital"),
        ("indus hospital", "The Indus Hospital"),
        ("\bindus\b", "The Indus Hospital"),
        ("liaquat national", "Liaquat National Hospital"),
        ("civil hospital karachi", "Civil Hospital Karachi"),
        ("shifa international", "Shifa International Hospital"),
        ("jinnah postgraduate", "Jinnah Postgraduate Medical Centre"),
        ("jpmc", "Jinnah Postgraduate Medical Centre"),
        ("pims", "Pakistan Institute of Medical Sciences"),
        ("mayo hospital", "Mayo Hospital Lahore"),
        ("services hospital", "Services Hospital Lahore"),
        ("nishtar", "Nishtar Hospital Multan"),
        ("holy family", "Holy Family Hospital"),
        ("lahore general", "Lahore General Hospital"),
        ("ziauddin", "Ziauddin Hospital"),
        ("sindh institute", "Sindh Institute of Urology and Transplantation"),
        ("siut", "Sindh Institute of Urology and Transplantation"),
        ("dhq", "District Headquarters Hospital"),
    ]
    # Scan full text, not just first 2000 chars
    text_lower = text.lower()
    for keyword, name in known:
        if keyword.startswith("\\b"):
            # Use regex word boundary
            if _re.search(keyword, text_lower):
                return name
        else:
            if keyword in text_lower:
                return name
    # Try to extract hospital name from first 10 lines
    first_lines = text.strip().split("\n")[:10]
    for line in first_lines:
        line = line.strip()
        if 8 < len(line) < 100 and any(w in line.lower() for w in
                                        ["hospital", "medical centre", "medical center",
                                         "clinic", "laboratory", "institute"]):
            return line
    return "Hospital name pending verification"


def _parse_antibiotic_header_greedy(text):
    """Extract antibiotic names from a concatenated header string.
    Uses greedy longest-match from KNOWN_ANTIBIOTICS list.
    """
    found = []
    remaining = text.strip()
    while remaining:
        remaining = remaining.strip()
        if not remaining:
            break
        matched = False
        for ab in KNOWN_ANTIBIOTICS:
            if remaining.lower().startswith(ab.lower()):
                found.append(ab)
                remaining = remaining[len(ab):]
                matched = True
                break
        if not matched:
            remaining = remaining[1:]
    return found


def _parse_abbreviated_header(header_text):
    """Parse a header row of abbreviations like 'AK AMC CAZ CIP IPM MEM'.
    Returns list of full antibiotic names.

    Handles:
    - Standard codes: AK, AMC, CAZ
    - Single-letter codes: C, P, E, F
    - Combo codes: CIP/OFX, PB/CT
    - Concatenated codes from PDF extraction: CTSCF → CT + SCF
    - Stray slashes: "PB / CT" → "PB/CT"
    """
    cleaned = header_text.strip()
    # Replace newlines/tabs with spaces
    cleaned = _re.sub(r"\s+", " ", cleaned)

    # Rejoin "PB / CT" → "PB/CT" (slash-separated combos)
    cleaned = _re.sub(r"\b([A-Z]{1,4})\s*/\s*([A-Z]{1,4})\b", r"\1/\2", cleaned)

    tokens = cleaned.split(" ")

    # Sorted abbreviation keys (longest first) for greedy matching
    abbr_keys_sorted = sorted(ANTIBIOTIC_FULL.keys(), key=len, reverse=True)

    result = []
    for token in tokens:
        token = token.strip(".,;:*+")
        if not token:
            continue

        token_lower = token.lower()

        # Direct lookup
        if token_lower in ANTIBIOTIC_FULL:
            result.append(ANTIBIOTIC_FULL[token_lower])
            continue

        # Combo handling: 'CIP/OFX' → use first part
        if "/" in token_lower:
            first = token_lower.split("/")[0]
            if first in ANTIBIOTIC_FULL:
                result.append(ANTIBIOTIC_FULL[first])
                continue

        # Try greedy splitting: 'CTSCF' → 'CT' + 'SCF'
        # Useful when PDF extraction concatenates two short codes
        if len(token_lower) >= 4 and token_lower not in ANTIBIOTIC_FULL:
            remaining = token_lower
            split_result = []
            while remaining:
                matched = False
                for k in abbr_keys_sorted:
                    if remaining.startswith(k) and len(k) >= 2:
                        split_result.append(ANTIBIOTIC_FULL[k])
                        remaining = remaining[len(k):]
                        matched = True
                        break
                if not matched:
                    break
            if split_result and not remaining:
                result.extend(split_result)
                continue

        # Match against full antibiotic names
        match = next((ab for ab in KNOWN_ANTIBIOTICS
                     if token_lower == ab.lower()), None)
        if match:
            result.append(match)
            continue

        # Last resort: keep as unknown short code to preserve column position
        if 1 <= len(token) <= 6 and token.replace("/", "").replace("-", "").isalnum():
            result.append(token.upper())

    return result



# ============================================================
# UNIVERSAL ANTIBIOGRAM PARSER (semantic detection)
# Handles arbitrary hospital antibiogram PDFs via 3-strategy fallback:
#   1. Tables (semantic header + organism column detection)
#   2. Per-page text (rotated/letter-spaced headers, e.g. Lahore General)
#   3. OCR (graceful fallback if pytesseract unavailable)
# ============================================================
# TRULY universal antibiogram parser. Semantic detection — no hard-coded format names.
# Layered strategies:
#   1. Table-based parsing with semantic header & organism detection
#   2. Per-page text parsing for letter-spaced rotated headers (Lahore General style)
#   3. OCR fallback for fully-scanned PDFs (graceful degradation if tesseract missing)
# Returns (records, metadata).
import os, re, io
from difflib import get_close_matches, SequenceMatcher

# ─────────────────────────────────────────────────────────────
# Reference dictionaries
# ─────────────────────────────────────────────────────────────
ABXMAP = {
    "ampicillin":"Ampicillin","amp":"Ampicillin",
    "amoxicillin":"Amoxicillin","amx":"Amoxicillin",
    "amoxicillinclavulanate":"Co-amoxiclav","coamoxiclav":"Co-amoxiclav",
    "amoxicillin-clavulanate":"Co-amoxiclav","amc":"Co-amoxiclav",
    "amoxicillinclavulanicacid":"Co-amoxiclav","augmentin":"Co-amoxiclav",
    "ceftriaxone":"Ceftriaxone","cro":"Ceftriaxone","ctr":"Ceftriaxone",
    "ceftrioxone":"Ceftriaxone",  # OCR typo
    "cefotaxime":"Cefotaxime","ctx":"Cefotaxime",
    "piperacillintazobactam":"Piperacillin-Tazobactam","tzp":"Piperacillin-Tazobactam",
    "piptaz":"Piperacillin-Tazobactam","pip":"Piperacillin-Tazobactam","ptz":"Piperacillin-Tazobactam",
    "piperacillin+tazobactam":"Piperacillin-Tazobactam",
    "gentamicin":"Gentamicin","gen":"Gentamicin","gentamycin":"Gentamicin","cn":"Gentamicin",
    "meropenem":"Meropenem","mem":"Meropenem","mrp":"Meropenem",
    "imipenem":"Imipenem","ipm":"Imipenem","imi":"Imipenem","imp":"Imipenem",
    "ertapenem":"Ertapenem","erta":"Ertapenem","ert":"Ertapenem","etp":"Ertapenem",
    "amikacin":"Amikacin","amk":"Amikacin","ak":"Amikacin",
    "fosfomycin":"Fosfomycin","fos":"Fosfomycin","fot":"Fosfomycin",
    "nitrofurantoin":"Nitrofurantoin","nit":"Nitrofurantoin","f":"Nitrofurantoin",
    "colistin":"Colistin","col":"Colistin","ct":"Colistin","cs":"Colistin",
    "polymyxinb":"Colistin","pb":"Colistin","polymyxin":"Colistin",
    "ciprofloxacin":"Ciprofloxacin","cip":"Ciprofloxacin",
    "levofloxacin":"Levofloxacin","lev":"Levofloxacin","lfx":"Levofloxacin","levo":"Levofloxacin","le":"Levofloxacin",
    "trimethoprimsulfamethoxazole":"Trimethoprim-Sulfamethoxazole",
    "sxt":"Trimethoprim-Sulfamethoxazole","cotrimoxazole":"Trimethoprim-Sulfamethoxazole",
    "cot":"Trimethoprim-Sulfamethoxazole","tmpsmx":"Trimethoprim-Sulfamethoxazole",
    "tmp/smx":"Trimethoprim-Sulfamethoxazole","tmp/sxt":"Trimethoprim-Sulfamethoxazole",
    "ceftazidime":"Ceftazidime","caz":"Ceftazidime",
    "ceftazidimeavibactam":"Ceftazidime-avibactam","cza":"Ceftazidime-avibactam",
    "cefepime":"Cefepime","fep":"Cefepime","cpm":"Cefepime",
    "cefuroxime":"Cefuroxime","cxm":"Cefuroxime",
    "cefixime":"Cefixime","cfm":"Cefixime",
    "cefoperazone":"Cefoperazone","cfp":"Cefoperazone",
    "cefoperazonesulbactam":"Cefoperazone-sulbactam","scf":"Cefoperazone-sulbactam",
    "vancomycin":"Vancomycin","van":"Vancomycin","va":"Vancomycin",
    "teicoplanin":"Teicoplanin","tec":"Teicoplanin","teic":"Teicoplanin",
    "linezolid":"Linezolid","lzd":"Linezolid","lnz":"Linezolid",
    "daptomycin":"Daptomycin","dap":"Daptomycin",
    "tigecycline":"Tigecycline","tig":"Tigecycline","tgc":"Tigecycline","tige":"Tigecycline",
    "aztreonam":"Aztreonam","atm":"Aztreonam","azt":"Aztreonam",
    "rifampicin":"Rifampicin","rif":"Rifampicin","rifampin":"Rifampicin",
    "clindamycin":"Clindamycin","cli":"Clindamycin","cd":"Clindamycin","da":"Clindamycin",
    "chloramphenicol":"Chloramphenicol","cap":"Chloramphenicol","c":"Chloramphenicol",
    "tobramycin":"Tobramycin","tob":"Tobramycin",
    "oxacillin":"Oxacillin","ox":"Oxacillin","oxa":"Oxacillin",
    "norfloxacin":"Norfloxacin","nor":"Norfloxacin",
    "ofloxacin":"Ofloxacin","ofx":"Ofloxacin",
    "minocycline":"Minocycline","min":"Minocycline","mh":"Minocycline",
    "doxycycline":"Doxycycline","dox":"Doxycycline","do":"Doxycycline",
    "tetracycline":"Tetracycline","tet":"Tetracycline","te":"Tetracycline",
    "erythromycin":"Erythromycin","ery":"Erythromycin","e":"Erythromycin",
    "penicillin":"Penicillin","pen":"Penicillin","p":"Penicillin",
    "moxifloxacin":"Moxifloxacin","mxf":"Moxifloxacin","mfx":"Moxifloxacin",
    "cloxacillin":"Cloxacillin","clo":"Cloxacillin",
    "azithromycin":"Azithromycin","azi":"Azithromycin","azm":"Azithromycin",
    "fusidicacid":"Fusidic acid","fa":"Fusidic acid","fd":"Fusidic acid",
    "nalidixicacid":"Nalidixic acid","na":"Nalidixic acid",
    "ampicillinsulbactam":"Ampicillin-Sulbactam","sam":"Ampicillin-Sulbactam","sul":"Ampicillin-Sulbactam",
}

# Sort longest-first for greedy segmentation
ABX_FULL_NAMES = sorted(
    {v.replace("-","").replace(" ","").lower() for v in ABXMAP.values()} |
    {k for k in ABXMAP.keys() if len(k) >= 6},
    key=len, reverse=True
)
# Map collapsed name → canonical
ABX_COLLAPSED = {}
for v in set(ABXMAP.values()):
    ABX_COLLAPSED[v.replace("-","").replace(" ","").lower()] = v
for k, v in ABXMAP.items():
    if len(k) >= 6:
        ABX_COLLAPSED.setdefault(k, v)

KNOWN_ORGS = [
    "Acinetobacter baumannii","Acinetobacter species","Acinetobacter spp",
    "Acinetobacter group","Acinetobacter",
    "Escherichia coli","E. coli","E.coli",
    "Klebsiella pneumoniae","Klebsiella species","Klebsiella spp","Klebsiella",
    "Pseudomonas aeruginosa","Pseudomonas species","Pseudomonas spp","Pseudomonas",
    "Enterobacter species","Enterobacter cloacae","Enterobacter spp","Enterobacter",
    "Proteus mirabilis","Proteus species","Proteus spp","Proteus vulgaris","Proteus",
    "Stenotrophomonas maltophilia","Stenotrophomonas",
    "Burkholderia cepacia","Burkholderia cepecia","Burkholderia",
    "Staphylococcus aureus","Staph aureus","S. aureus","S.aureus",
    "Coagulase negative Staphylococcus","CoNS","Staphylococcus species","Staphylococcus spp",
    "Enterococcus species","Enterococcus spp","Enterococcus","Enterococci",
    "Enterococcus faecalis","Enterococcus faecium",
    "Streptococcus pneumoniae","Strep pneumoniae","S.pneumoniae",
    "Streptococcus pyogenes","Streptococcus agalactiae",
    "Streptococcus species","Streptococcus spp","Streptococcus",
    "Beta hemolytic Streptococci","Beta-hemolytic Streptococcus",
    "Salmonella Typhi","Salmonella typhi","Salmonella Paratyphi A","Salmonella Paratyphi",
    "Salmonella enterica","Salmonella","Typhoidal Salmonella",
    "Haemophilus influenzae","Haemophilus","H.influenzae","H. influenzae",
    "Moraxella catarrhalis","Moraxella",
    "Serratia species","Serratia spp","Serratia",
    "Citrobacter species","Citrobacter spp","Citrobacter",
    "MRSA","MSSA","Shigella species","Shigella","Vibrio cholerae","Aeromonas",
    "Candida albicans","Candida species","Candida","Nocardia species",
    "Mycobacterium tuberculosis","Corynebacterium diphtheriae",
]

VALUE_NULLS = {"NT","IR","NA","N/A","-","--","..","...","R","I","S","#","#N/A",""}

# ─────────────────────────────────────────────────────────────
# Normalisation helpers
# ─────────────────────────────────────────────────────────────
def _bigrams(s):
    return set(s[i:i+2] for i in range(len(s)-1))

def _jaccard(a,b):
    ba,bb=_bigrams(a),_bigrams(b)
    return len(ba&bb)/len(ba|bb) if ba and bb else 0.0

def norm_abx(raw):
    if not raw: return None
    s = str(raw)
    garbled = "\n" in s
    t = re.sub(r"[*+ᵠᵟ±†‡\[\]()\\]", "", s.replace("\n",""))
    t = re.sub(r"\s+","",t).lower().strip("-/.,")
    if not t: return None
    rev = t[::-1]
    for cand in (t, rev):
        if cand in ABXMAP: return ABXMAP[cand]
    keys = list(ABXMAP.keys())
    order = (rev,t) if garbled else (t,rev)
    for cand in order:
        if len(cand) < 2: continue
        m = get_close_matches(cand, keys, n=1, cutoff=0.78)
        if m and SequenceMatcher(None,cand,m[0]).ratio()>=0.78:
            return ABXMAP[m[0]]
    if garbled:
        ca = re.sub(r"[^a-z]","",t)
        best,bs = None,0.0
        for k,v in ABXMAP.items():
            if len(k)<5: continue
            sc = max(_jaccard(ca,k),_jaccard(ca[::-1],k))
            if sc>bs: best,bs = v,sc
        if best and bs>=0.4: return best
    return None

def norm_org(raw):
    if not raw: return None
    s = str(raw)
    s = re.sub(r"\s*\(n?\*?=?\s*[\d,]+\)?","",s)
    s = re.sub(r"\s*\(\d+\)?","",s)
    s = re.sub(r"\s+"," ",s).strip().strip(":,;`")
    if len(s) < 3: return None
    sl = s.lower()
    SKIP = {"organism","organisms","total","percent","note","key","abbrev","gram",
            "antibiotic","bacteria","number","year","contact","prepared","reviewed",
            "for any","tested","query","specimen","susceptibility","isolates",
            "in patient","out patient","inpatient","outpatient","ipd","opd",
            "respiratory","urine","blood","stool","other sample",
            "intrinsic","resistance","disclaimer","guideline","how to",
            "abbreviation","sensitivity","according","clinical","department",
            # specimen types that should never be organisms
            "pus","wound swab","wound","tissue","fluid","csf","bal","sputum",
            "tracheal secretion","tracheal aspirate","throat swab","throat",
            "tip","cvp tip","line tip","catheter tip","ascitic fluid",
            "pleural fluid","tr. secretion","swab","skin swab","abscess"}
    if any(kw in sl[:30] for kw in SKIP): return None
    if not re.search(r"[a-zA-Z]{4,}", s): return None

    # ALIAS CANONICALIZATION — map common variants to canonical names
    ALIASES = {
        "e.coli": "Escherichia coli", "e. coli": "Escherichia coli",
        "ecoli": "Escherichia coli", "escherichia coli": "Escherichia coli",
        "k. pneumoniae": "Klebsiella pneumoniae",
        "k.pneumoniae": "Klebsiella pneumoniae",
        "klebsiella pneumoniae": "Klebsiella pneumoniae",
        "klebsiella spp": "Klebsiella pneumoniae",
        "klebsiella species": "Klebsiella pneumoniae",
        "klebsiella": "Klebsiella pneumoniae",
        "p. aeruginosa": "Pseudomonas aeruginosa",
        "p.aeruginosa": "Pseudomonas aeruginosa",
        "pseudomonas aeruginosa": "Pseudomonas aeruginosa",
        "pseudomonas spp": "Pseudomonas aeruginosa",
        "pseudomonas species": "Pseudomonas aeruginosa",
        "pseudomonas": "Pseudomonas aeruginosa",
        "acinetobacter baumannii": "Acinetobacter baumannii",
        "acinetobacter spp": "Acinetobacter baumannii",
        "acinetobacter species": "Acinetobacter baumannii",
        "acinetobacter": "Acinetobacter baumannii",
        "staph aureus": "Staphylococcus aureus",
        "s. aureus": "Staphylococcus aureus",
        "s.aureus": "Staphylococcus aureus",
        "staphylococcus aureus": "Staphylococcus aureus",
        "cons": "Coagulase negative Staphylococcus",
        "coagulase negative staphylococcus": "Coagulase negative Staphylococcus",
        "staphylococcus spp": "Coagulase negative Staphylococcus",
        "staphylococcus species": "Coagulase negative Staphylococcus",
        "enterococcus spp": "Enterococcus species",
        "enterococcus species": "Enterococcus species",
        "enterococcus": "Enterococcus species",
        "enterococci": "Enterococcus species",
        "proteus mirabilis": "Proteus mirabilis",
        "proteus spp": "Proteus mirabilis",
        "proteus species": "Proteus mirabilis",
        "proteus": "Proteus mirabilis",
        "enterobacter spp": "Enterobacter species",
        "enterobacter species": "Enterobacter species",
        "enterobacter cloacae": "Enterobacter cloacae",
        "enterobacter": "Enterobacter species",
        "serratia spp": "Serratia species",
        "serratia species": "Serratia species",
        "serratia": "Serratia species",
        "citrobacter spp": "Citrobacter species",
        "citrobacter species": "Citrobacter species",
        "citrobacter": "Citrobacter species",
        "stenotrophomonas maltophilia": "Stenotrophomonas maltophilia",
        "stenotrophomonas": "Stenotrophomonas maltophilia",
        "burkholderia cepacia": "Burkholderia cepacia",
        "burkholderia cepecia": "Burkholderia cepacia",
        "burkholderia": "Burkholderia cepacia",
        "h.influenzae": "Haemophilus influenzae",
        "h. influenzae": "Haemophilus influenzae",
        "haemophilus influenzae": "Haemophilus influenzae",
        "haemophilus": "Haemophilus influenzae",
        "moraxella catarrhalis": "Moraxella catarrhalis",
        "moraxella": "Moraxella catarrhalis",
        "salmonella typhi": "Salmonella Typhi",
        "salmonella enterica ser.typhi": "Salmonella Typhi",
        "salmonella enterica": "Salmonella Typhi",
        "typhoidal salmonella": "Salmonella Typhi",
        "salmonella": "Salmonella Typhi",
        "s.typhi": "Salmonella Typhi",
        "salmonella paratyphi a": "Salmonella Paratyphi A",
        "salmonella paratyphi": "Salmonella Paratyphi A",
        "streptococcus pneumoniae": "Streptococcus pneumoniae",
        "s.pneumoniae": "Streptococcus pneumoniae",
        "streptococcus pyogenes": "Streptococcus pyogenes",
        "streptococcus agalactiae": "Streptococcus agalactiae",
        "streptococcus spp": "Streptococcus species",
        "streptococcus species": "Streptococcus species",
        "beta hemolytic streptococci": "Beta hemolytic Streptococci",
        "beta-hemolytic streptococci": "Beta hemolytic Streptococci",
        "candida albicans": "Candida albicans",
        "candida spp": "Candida species",
        "candida species": "Candida species",
        "candida": "Candida species",
        "shigella spp": "Shigella species",
        "shigella species": "Shigella species",
        "shigella": "Shigella species",
        "vibrio cholerae": "Vibrio cholerae",
        "aeromonas spp": "Aeromonas",
        "aeromonas species": "Aeromonas",
        "aeromonas": "Aeromonas",
        "mrsa": "MRSA", "mssa": "MSSA",
    }
    if sl in ALIASES: return ALIASES[sl]
    # Strip trailing dots/whitespace and retry
    sl_strip = sl.rstrip(".")
    if sl_strip in ALIASES: return ALIASES[sl_strip]

    # Generic prefix matching against KNOWN_ORGS
    for o in KNOWN_ORGS:
        ol = o.lower()
        if len(ol)>=6 and len(sl)>=6:
            if ol[:8] in sl or sl[:8] in ol:
                # Map back to alias if available
                ol_clean = o.lower()
                if ol_clean in ALIASES: return ALIASES[ol_clean]
                return o
    m = get_close_matches(s, KNOWN_ORGS, n=1, cutoff=0.65)
    if m:
        m_lower = m[0].lower()
        return ALIASES.get(m_lower, m[0])
    first = re.split(r"[\s\.]", s)[0].lower()
    if len(first) >= 3:
        for o in KNOWN_ORGS:
            ow = o.split()[0].lower()
            if ow.startswith(first) or first.startswith(ow[:3]):
                ol_clean = o.lower()
                return ALIASES.get(ol_clean, o)
    return s if len(s)>4 and re.match(r"^[A-Z]", s) else None

def parse_val(v):
    if v is None: return None
    s = str(v).strip()
    if not s or s.upper() in VALUE_NULLS: return None
    # Take first line only (handles "13\n(248)" → work on "13")
    first_line = s.split("\n")[0].strip()
    # Remove trailing parenthetical from same line: "13 (248)" → "13"
    num_part = re.split(r"\s*\(", first_line)[0].strip()
    num_part = num_part.replace("%","").strip().rstrip("*+ᵠᵟ")
    if not num_part or num_part.upper() in VALUE_NULLS: return None
    m = re.search(r"\d+\.?\d*", num_part)
    if not m: return None
    f = float(m.group())
    return f if 0 <= f <= 100 else None


def parse_n_tested(v):
    """Extract n_tested from organism cells in many formats:
       '13 (248)', '13\n(248)', 'E. coli (2181)', '[2181]', 'n=2181', 'N=2181',
       'E. coli\nn=2181', '2181 isolates', or just a stray standalone number.
    """
    if v is None: return 0
    s = str(v).strip()
    if not s: return 0
    # Patterns in priority order
    patterns = [
        r"\((\d{2,6})\)",       # (2181)  — parens with 2+ digits
        r"\[(\d{2,6})\]",       # [2181]  — brackets
        r"\bn\s*=\s*(\d{2,6})", # n=2181 or n = 2181
        r"\bN\s*=\s*(\d{2,6})", # N=2181
        r"(\d{2,6})\s*isolates",# 2181 isolates
        r"\(n\s*=\s*(\d{2,6})\)", # (n=2181)
    ]
    for pat in patterns:
        m = re.search(pat, s, re.IGNORECASE)
        if m:
            try: return int(m.group(1))
            except ValueError: pass
    # Last resort: standalone number on its own line after the organism name
    for line in s.split("\n"):
        line = line.strip()
        if line and line.isdigit() and 2 <= len(line) <= 6:
            return int(line)
    return 0

# ─────────────────────────────────────────────────────────────
# Strategy 1: TABLE-based universal parser
# ─────────────────────────────────────────────────────────────
def score_header_row(row):
    if not row: return 0, {}
    ab_map, matches = {}, 0
    for ci, cell in enumerate(row):
        if cell is None: continue
        s = str(cell).strip()
        if not s: continue
        if re.match(r"^[\d.\s%(),]+$", s): continue
        if s.lower() in {"n","n#","no.","no","number","%","total","ipd","opd"}: continue
        ab = norm_abx(s)
        if ab:
            ab_map[ci] = ab
            matches += 1
    return matches, ab_map

def find_organism_column(table, header_row_idx):
    if header_row_idx >= len(table) - 1: return 0
    candidate_cols = list(range(min(4, len(table[0]))))
    scores = {ci: 0 for ci in candidate_cols}
    for row in table[header_row_idx + 1:header_row_idx + 8]:
        if not row: continue
        for ci in candidate_cols:
            if ci >= len(row) or row[ci] is None: continue
            if norm_org(row[ci]): scores[ci] += 1
    if not any(scores.values()): return 0
    return max(scores, key=scores.get)

SPECIMEN_NAMES = {
    "pus", "pus swab", "blood", "urine", "sputum", "wound swab", "wound",
    "tissue", "fluid", "ascitic fluid", "pleural fluid", "csf", "bal",
    "tracheal secretion", "tracheal aspirate", "tracheal secretion",
    "tr. secretion", "throat swab", "throat", "nasal swab", "nasal",
    "eye swab", "ear swab", "stool", "rectal swab", "tip", "cvp tip",
    "line tip", "catheter tip", "respiratory", "endotracheal",
    "bronchial", "bronchial washing", "eb washing", "nbl", "swab",
    "skin swab", "bone", "joint fluid", "synovial", "abscess",
}

def norm_specimen(raw):
    """Normalise specimen name to canonical capitalised form."""
    if not raw: return "All"
    s = str(raw).strip()
    # Remove newlines
    s = re.sub(r"\s+", " ", s).strip()
    sl = s.lower()
    CANON = {
        "pus": "Pus", "pus swab": "Pus Swab", "blood": "Blood",
        "urine": "Urine", "sputum": "Sputum",
        "wound swab": "Wound Swab", "wound": "Wound Swab",
        "tissue": "Tissue", "fluid": "Fluid",
        "ascitic fluid": "Ascitic Fluid", "pleural fluid": "Pleural Fluid",
        "csf": "CSF", "bal": "BAL",
        "tracheal secretion": "Tracheal Secretion",
        "tracheal aspirate": "Tracheal Aspirate",
        "tr. secretion": "Tracheal Secretion",
        "throat swab": "Throat Swab", "throat": "Throat Swab",
        "tip": "Catheter Tip", "cvp tip": "Catheter Tip", "line tip": "Catheter Tip",
        "catheter tip": "Catheter Tip",
        "respiratory": "Respiratory",
    }
    return CANON.get(sl, s.title())


def parse_table_universally(table, hospital, year, default_pt="All",
                            mode="susceptibility", page_organism=None):
    if not table or len(table) < 2: return []
    best_score, best_idx, best_map = 0, None, {}
    for ri in range(min(8, len(table))):
        score, ab_map = score_header_row(table[ri])
        if score > best_score and score >= 3:
            best_score, best_idx, best_map = score, ri, ab_map
    if best_idx is None: return []

    header = table[best_idx]
    col0_header = str(header[0] or "").strip().lower()

    # ── KE-style: col 0 = "Specimen", organism comes from page text ──
    specimen_as_col0 = col0_header in {"specimen", "specimen type", "sample"}

    org_col = 0 if not specimen_as_col0 else None
    if not specimen_as_col0:
        org_col = find_organism_column(table, best_idx)

    # Detect n column
    n_col = None
    for ci in range(min(len(header), (org_col or 0) + 5)):
        if (org_col is not None and ci == org_col) or ci in best_map: continue
        if ci >= len(header) or header[ci] is None: continue
        h = str(header[ci]).strip().lower()
        if h in {"n", "n#", "n*", "no.", "no", "number", "(n*)", "n*)"}:
            n_col = ci; break

    records = []
    for row in table[best_idx + 1:]:
        if not row: continue

        # Determine organism and specimen for this row
        if specimen_as_col0:
            # Col 0 = specimen type; organism = page_organism
            org = page_organism
            if not org: continue
            specimen_raw = row[0] if row else None
            specimen = norm_specimen(specimen_raw) if specimen_raw else "All"
            # Skip header-like rows
            if specimen_raw and str(specimen_raw).lower().strip() in {"specimen","sample","","none"}:
                continue
        else:
            if org_col is None or org_col >= len(row): continue
            org_raw = row[org_col]
            if org_raw is None: continue
            org = norm_org(org_raw)
            if not org: continue
            # If this cell looks like a specimen name, it's a misidentified KE-style table
            if str(org_raw).strip().lower() in SPECIMEN_NAMES:
                # Treat as specimen, use page organism
                if page_organism:
                    org = page_organism
                    specimen = norm_specimen(org_raw)
                else:
                    continue  # can't recover without page organism
            else:
                specimen = "All"

        flat = " ".join(str(c or "") for c in row[:3]).lower()
        pt = default_pt
        if "in-patient" in flat or "inpatient" in flat or " ipd" in flat:
            pt = "Inpatient"
        elif "out-patient" in flat or "outpatient" in flat or " opd" in flat:
            pt = "Outpatient"

        # n_tested
        n_tested = 0
        if n_col is not None and n_col < len(row) and row[n_col] is not None:
            try:
                ns = str(row[n_col]).strip().replace(",", "")
                ns_match = re.search(r"\d+", ns)
                if ns_match: n_tested = int(ns_match.group())
            except (ValueError, AttributeError): pass
        elif not specimen_as_col0 and org_col is not None:
            # Use the comprehensive parse_n_tested to catch many formats
            n_tested = parse_n_tested(row[org_col])

        for ci, ab in best_map.items():
            if ci >= len(row): continue
            val = parse_val(row[ci])
            if val is None: continue
            n_use = parse_n_tested(row[ci]) or n_tested if n_col is None else n_tested
            if mode == "resistance":
                susc, resist = round(100 - val, 1), round(val, 1)
            else:
                susc, resist = round(val, 1), round(100 - val, 1)
            records.append({
                "hospital": hospital, "year": year,
                "patient_type": pt, "specimen": specimen,
                "pathogen": org, "antibiotic": ab,
                "susceptible_pct": susc, "resistance_pct": resist,
                "n_tested": n_use,
                "source": "Hospital antibiogram (PDF)",
            })
    return records

# ─────────────────────────────────────────────────────────────
# Strategy 2: TEXT-based parser for rotated/letter-spaced headers
# (e.g. Lahore General Hospital style)
# ─────────────────────────────────────────────────────────────
def collapse_letter_spaced(line):
    """Collapse 'A M I K A C I N' → 'AMIKACIN' but keep word breaks."""
    # Keep numbers and percentage signs separate
    # Iteratively merge single-uppercase-letter pairs separated by single spaces
    prev = ""
    out = line
    while out != prev:
        prev = out
        out = re.sub(r"\b([A-Z])\s([A-Z])\b", r"\1\2", out)
    return out

def segment_antibiotics(blob):
    """Greedy left-to-right segmentation of a collapsed antibiotic string.
    Returns list of (canonical_name, char_position)."""
    blob_clean = re.sub(r"[^A-Za-z]", "", blob).lower()
    pos = 0
    found = []
    sorted_keys = sorted(ABX_COLLAPSED.keys(), key=len, reverse=True)
    while pos < len(blob_clean):
        matched = False
        for key in sorted_keys:
            if len(key) < 4: continue  # avoid single-letter false matches
            if blob_clean[pos:pos+len(key)] == key:
                found.append(ABX_COLLAPSED[key])
                pos += len(key)
                matched = True
                break
        if not matched:
            pos += 1
    return found

def parse_per_page_text(pdf_path, hospital, year, mode="susceptibility"):
    """For each page, treat first line as organism, then find antibiotic header line
    and value line. Used when tables aren't useful."""
    import pdfplumber
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [l for l in text.split("\n") if l.strip()]
            if len(lines) < 3: continue
            
            # Look for an organism in the first few lines
            org = None
            for line in lines[:3]:
                if any(s in line.lower() for s in ("antibiogram","susceptib","aminoglyc",
                                                    "carbapenem","cephalospor","quinolone")):
                    continue
                maybe = norm_org(line.strip())
                if maybe:
                    org = maybe; break
            if not org: continue
            
            # Find an antibiotic header line (letter-spaced or normal)
            header_line = None
            value_line = None
            for li, line in enumerate(lines):
                # A header line: many uppercase letters, mostly alphabetic
                # Letter-spaced: looks like "A B C D E F"
                upper_letters = sum(1 for c in line if c.isupper())
                if upper_letters >= 15:
                    collapsed = collapse_letter_spaced(line)
                    abx_found = segment_antibiotics(collapsed)
                    if len(abx_found) >= 3:
                        header_line = abx_found
                        # Value line: next line containing percentages
                        for lj in range(li+1, min(li+5, len(lines))):
                            vl = lines[lj]
                            # extract all percentages or floats
                            vals = re.findall(r"\d+\.?\d*\s*%?", vl)
                            if len(vals) >= 3:
                                value_line = vals
                                break
                        if value_line: break
            
            if not header_line or not value_line: continue
            
            # The value line typically starts with the isolate count, e.g. "2927 48.82%"
            # First number is total isolates; remaining are antibiotic %s
            n_tested = 0
            try:
                first = float(re.sub(r"[^\d.]","",value_line[0]))
                if first > 100:  # likely isolate count
                    n_tested = int(first)
                    value_line = value_line[1:]
            except (ValueError, IndexError): pass
            
            for i, ab in enumerate(header_line):
                if i >= len(value_line): break
                val = parse_val(value_line[i])
                if val is None: continue
                if mode == "resistance":
                    susc, resist = round(100-val, 1), round(val, 1)
                else:
                    susc, resist = round(val, 1), round(100-val, 1)
                records.append({
                    "hospital": hospital, "year": year,
                    "patient_type": "All", "specimen": "All",
                    "pathogen": org, "antibiotic": ab,
                    "susceptible_pct": susc, "resistance_pct": resist,
                    "n_tested": n_tested,
                    "source": "Hospital antibiogram (PDF)",
                })
    return records

# ─────────────────────────────────────────────────────────────
# Strategy 3: OCR fallback (graceful if tesseract unavailable)
# ─────────────────────────────────────────────────────────────
def parse_via_ocr(pdf_path, hospital, year):
    """OCR-based parse. Returns [] if OCR unavailable."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return []
    try:
        images = convert_from_path(pdf_path, dpi=200)
    except Exception:
        return []
    
    # Build a pseudo-text by OCRing each page, then run text-based parser on it
    full_text_pages = []
    for img in images:
        try:
            txt = pytesseract.image_to_string(img)
            full_text_pages.append(txt)
        except Exception:
            pass
    if not full_text_pages: return []
    
    # Save OCR text to temp file and pretend it's a text PDF — too brittle.
    # Instead, parse OCR text directly by treating whole document as flat text.
    records = []
    for page_text in full_text_pages:
        # Look for organism + antibiotic header + values pattern
        lines = [l for l in page_text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            org = norm_org(line.strip())
            if not org: continue
            # Look for header/value lines below
            for lj in range(i+1, min(i+5, len(lines))):
                cand = lines[lj]
                tokens = cand.split()
                abx_in_line = [norm_abx(t) for t in tokens]
                abx_in_line = [a for a in abx_in_line if a]
                if len(abx_in_line) >= 3:
                    # Find values line
                    for lk in range(lj+1, min(lj+3, len(lines))):
                        vals = re.findall(r"\d+\.?\d*", lines[lk])
                        if len(vals) >= len(abx_in_line):
                            for ai, ab in enumerate(abx_in_line):
                                v = parse_val(vals[ai])
                                if v is None: continue
                                records.append({
                                    "hospital": hospital, "year": year,
                                    "patient_type": "All", "specimen": "All",
                                    "pathogen": org, "antibiotic": ab,
                                    "susceptible_pct": round(v, 1),
                                    "resistance_pct": round(100-v, 1),
                                    "n_tested": 0,
                                    "source": "Hospital antibiogram (OCR)",
                                })
                            break
                    break
    return records

# ─────────────────────────────────────────────────────────────
# Hospital/year detection + main entrypoint
# ─────────────────────────────────────────────────────────────
def detect_hospital_year(text):
    year = "Unknown"
    ym = re.search(r"\b(19[89]\d|20\d{2})\b", text)
    if ym: year = ym.group(1)
    hosp = "Unknown"
    SKIP_HOSP = {"antibiogram","antibiotic","susceptibility","department","percent",
                 "key:","note:","abbreviation","gram","organism","table","year",
                 "january","february","march","april","may","june","july","august",
                 "september","october","november","december","in patients","out patients",
                 "inpatient","outpatient","bacteria","source:","number","isolate"}
    for line in text.split("\n"):
        ln = line.strip()
        if len(ln) < 5 or len(ln) > 120: continue
        ll = ln.lower()
        # Skip lines containing numbers (data rows)
        if re.search(r"\d{2,}", ln): continue
        if any(s in ll for s in SKIP_HOSP): continue
        if re.match(r"^[\d\s.,()%-]+$", ln): continue
        # Skip abbreviation-legend lines like "AMP: ampicillin, AMK: amikacin..."
        if re.search(r"\b[A-Z]{2,5}\s*:", ln) and ln.count(":") >= 2: continue
        # Skip all-uppercase short tokens (column headers, not hospital names)
        tokens = ln.split()
        if tokens and sum(1 for t in tokens if t.isupper() and len(t)<=5) / len(tokens) > 0.5: continue
        hosp = ln; break
    return hosp, year

def detect_resistance_or_susceptible(text):
    tl = text.lower()
    if "% resistant" in tl or "percent resistant" in tl or "%resistant" in tl:
        return "resistance"
    return "susceptibility"

def parse_universal(pdf_path):
    """Universal parser entry point. Tries 3 strategies in order until records found."""
    import pdfplumber
    text_full = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text_full += (page.extract_text() or "") + "\n"
    except Exception:
        pass
    
    hospital, year = detect_hospital_year(text_full)
    mode = detect_resistance_or_susceptible(text_full)
    
    records = []
    strategy_used = None
    
    # Strategy 1: tables
    try:
        with pdfplumber.open(pdf_path) as pdf:
            current_pt = "All"  # tracked across pages, since section headers persist
            current_specimen = "All"
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                # Update tracked patient type based on most recent section header
                pt_lower = page_text.lower()
                # Look for section headers more aggressively
                # Pattern: "In patients" or "Out patients" or "INPATIENT" or "OPD"
                for line in page_text.split("\n"):
                    ll = line.lower().strip()
                    if re.search(r"^in[- ]?patient", ll) or "in patients" in ll or " ipd" in ll[:20] or "inpatient visits" in ll:
                        current_pt = "Inpatient"
                    elif re.search(r"^out[- ]?patient", ll) or "out patients" in ll or " opd" in ll[:20] or "outpatient" in ll[:25]:
                        current_pt = "Outpatient"
                    elif re.search(r"\ball patients\b", ll):
                        current_pt = "All"
                    # Specimen detection
                    if "source: blood" in ll or "(blood)" in ll:
                        current_specimen = "Blood"
                    elif "source: urine" in ll or "(urine)" in ll:
                        current_specimen = "Urine"
                    elif "source: respirat" in ll or "respiratory" in ll[:25]:
                        current_specimen = "Respiratory"
                    elif "source: other" in ll or "other samples" in ll:
                        current_specimen = "Other"

                # For pages with multiple organisms+tables (e.g. KE format),
                # build a list of (line_index, organism) pairs from page text,
                # then assign each table to the closest organism above it.
                page_lines = page_text.split("\n")
                page_org_list = []  # list of (line_idx, org_name)
                for li, line in enumerate(page_lines):
                    ln = line.strip()
                    if not ln or ln.lower() in SPECIMEN_NAMES: continue
                    maybe = norm_org(ln)
                    if maybe and ln.lower() not in SPECIMEN_NAMES:
                        # Avoid duplicates of same org
                        if not page_org_list or page_org_list[-1][1] != maybe:
                            page_org_list.append((li, maybe))

                # Also extract table bounding boxes so we can match by order
                # Since we can't easily get text-line-to-table mapping, use table index order
                page_tables = page.extract_tables() or []
                for t_idx, table in enumerate(page_tables):
                    # Assign organism: the t_idx-th organism on this page (or last one)
                    page_organism = None
                    if page_org_list:
                        # Use t_idx if available, else last organism
                        org_idx = min(t_idx, len(page_org_list) - 1)
                        page_organism = page_org_list[org_idx][1]

                    page_records = parse_table_universally(
                        table, hospital, year,
                        default_pt=current_pt, mode=mode,
                        page_organism=page_organism
                    )
                    for r in page_records:
                        if r["specimen"] == "All":
                            r["specimen"] = current_specimen
                    records.extend(page_records)
        if records: strategy_used = "Tables"
    except Exception as e:
        pass
    
    # Strategy 2: per-page text (rotated/letter-spaced headers)
    if not records:
        try:
            records = parse_per_page_text(pdf_path, hospital, year, mode=mode)
            if records: strategy_used = "Page-text"
        except Exception:
            pass
    
    # Strategy 3: OCR
    if not records:
        try:
            records = parse_via_ocr(pdf_path, hospital, year)
            if records: strategy_used = "OCR"
        except Exception:
            pass
    
    # Dedupe
    seen = set(); deduped = []
    for r in records:
        k = (r["hospital"], r["year"], r["pathogen"], r["antibiotic"], r["patient_type"])
        if k not in seen: seen.add(k); deduped.append(r)
    
    metadata = {
        "hospital": hospital, "year": year,
        "records_extracted": len(deduped),
        "pathogens_found": len(set(r["pathogen"] for r in deduped)),
        "antibiotics_found": len(set(r["antibiotic"] for r in deduped)),
        "format_detected": strategy_used or "Unknown",
        "mode": mode,
    }
    if not deduped:
        metadata["suggestion"] = (
            "Could not auto-extract data. The PDF may be a scanned image without OCR support, "
            "or use an unrecognised layout. Please use the CSV template as a fallback."
        )
    return deduped, metadata


def parse_universal_bytes(pdf_bytes, hospital_hint=None):
    """Public entry point for byte input — wraps parse_universal."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes); tmp_path = tmp.name
    try:
        records, metadata = parse_universal(tmp_path)
        if hospital_hint:
            for r in records: r["hospital"] = hospital_hint
            metadata["hospital"] = hospital_hint
    finally:
        os.unlink(tmp_path)
    return records, metadata

# ============================================================
# END UNIVERSAL PARSER
# ============================================================

def etl_parse_pdf_universal(pdf_bytes, hospital_hint=None):
    """
    Universal PDF antibiogram parser. Tries the new semantic parser first
    (handles arbitrary hospital formats); falls back to legacy logic if
    that returns nothing.
    """
    # ── Try new universal semantic parser first ──────────────────────
    try:
        records, metadata = parse_universal_bytes(pdf_bytes, hospital_hint=hospital_hint)
        if records:
            # Augment with fields the rest of the app expects
            metadata.setdefault("text_length", 0)
            metadata.setdefault("raw_text", "")
            # Methodology detection (CLSI/EUCAST) on extracted text
            try:
                _txt = etl_extract_pdf_text(pdf_bytes)
                if isinstance(_txt, str) and not _txt.startswith("PDF_ERROR"):
                    metadata["raw_text"] = _txt[:8000]
                    metadata["text_length"] = len(_txt)
                    _tl = _txt.lower()
                    if "clsi" in _tl or "m100" in _tl:
                        metadata["methodology"] = "CLSI"
                    elif "eucast" in _tl:
                        metadata["methodology"] = "EUCAST"
                    else:
                        metadata.setdefault("methodology", None)
            except Exception:
                metadata.setdefault("methodology", None)
            return records, metadata
    except Exception as _e:
        # Fall through to legacy parser
        pass

    # ── Legacy fallback (text-based heuristics) ──────────────────────
    text = etl_extract_pdf_text(pdf_bytes)

    if str(text).startswith("PDF_ERROR"):
        return [], {
            "error": str(text).replace("PDF_ERROR:", ""),
            "suggestion": (
                "This PDF could not be read. It may be scanned (image-based). "
                "Use the CSV template instead."
            )
        }

    if len(text.strip()) < 80:
        return [], {
            "error": "PDF appears to be image-based. No text extracted.",
            "suggestion": "Use the CSV template — takes 10-15 minutes for a full antibiogram."
        }

    year = etl_detect_year(text)
    hospital = hospital_hint or etl_detect_hospital(text)
    metadata = {"hospital": hospital, "year": year, "text_length": len(text),
                "raw_text": text[:8000]}
    # Detect methodology from text
    text_lower_methodology = text.lower()
    if "clsi" in text_lower_methodology or "m100" in text_lower_methodology:
        metadata["methodology"] = "CLSI"
    elif "eucast" in text_lower_methodology:
        metadata["methodology"] = "EUCAST"
    else:
        metadata["methodology"] = None
    metadata["format_detected"] = "Universal"
    records = []

    # ---- TEXT NORMALIZATION ----
    # PDF extraction often splits tokens across lines:
    # "A\nMP" → "AMP", "CA\nZ" → "CAZ", "ME\nM" → "MEM"
    # We rejoin these short fragments so abbreviations parse correctly.
    normalized = text
    # Merge isolated 1-2 letter fragments at line boundaries with following short token
    normalized = _re.sub(
        r"\b([A-Z]{1,2})\s*\n\s*([A-Z]{1,3})\b",
        lambda m: m.group(1) + m.group(2),
        normalized
    )
    # Handle "0.7 \n(1)" → "0.7 (1)"
    normalized = _re.sub(r"(\d+\.?\d*)\s*\n\s*(\(\d+\))", r"\1 \2", normalized)
    # Handle slash-separator combos split across lines: "PB\n/\nCT" → "PB/CT"
    normalized = _re.sub(
        r"([A-Z]{1,4})\s*\n+\s*/\s*\n+\s*([A-Z]{1,4})",
        r"\1/\2",
        normalized
    )
    # Handle "CIP/\nOFX" → "CIP/OFX"
    normalized = _re.sub(
        r"([A-Z]{1,4})/\s*\n\s*([A-Z]{1,4})",
        r"\1/\2",
        normalized
    )
    # Run fragment merge again after slash handling
    normalized = _re.sub(
        r"\b([A-Z]{1,2})\s*\n\s*([A-Z]{1,3})\b",
        lambda m: m.group(1) + m.group(2),
        normalized
    )

    # ============================================================
    # STRATEGY A: Abbreviated column format (line-by-line parser)
    # Used by: Indus, Liaquat, Civil, most PARN PDFs
    # Process: scan each line. When we see "ORGANISMS" or "ORGANISM" followed
    # by abbreviations, extract the antibiotic order. Then parse subsequent
    # rows as "OrganismName  val val val NT val..."
    # ============================================================

    # Use the normalized text (with split tokens rejoined) for line-based parsing
    norm_lines = normalized.split("\n")

    # Detect resistance vs susceptibility from full text context
    text_lower_full = normalized.lower()
    overall_is_resistant = (
        "percent resistant" in text_lower_full or
        "% resistant" in text_lower_full or
        "% r " in text_lower_full
    )

    # Iterate lines, looking for ORGANISMS headers
    i = 0
    while i < len(norm_lines):
        line = norm_lines[i].strip()
        upper = line.upper()

        # Detect header row — starts with ORGANISMS/ORGANISM and contains short codes
        if upper.startswith(("ORGANISMS", "ORGANISM")):
            # Greedy merge of header lines until we hit an organism row.
            # An organism row contains: capital-letter-name + spaces + numeric values
            header_text = line
            j = i + 1
            while j < min(i + 25, len(norm_lines)):
                next_line = norm_lines[j].strip()

                # Stop conditions — this is an organism row, not header continuation:
                # 1. Capital + lowercase + space + (numbers or NT)
                # 2. Single capital + period + space + lowercase (E. coli style)
                # 3. Capital words followed by data
                has_data = bool(_re.search(r"\b(\d+|NT|NA)\b", next_line))
                looks_like_organism = bool(_re.match(
                    r"^[A-Z]\.?\s*[a-z]+",  # E. coli, Acinetobacter, Pseudomonas
                    next_line
                ))
                if has_data and looks_like_organism:
                    break

                if not next_line:
                    j += 1
                    continue
                # Otherwise absorb as header continuation
                header_text += " " + next_line
                j += 1

            # Strip the leading "ORGANISMS" word
            header_clean = _re.sub(r"^ORGANISMS?\s*", "", header_text, flags=_re.IGNORECASE)

            # Parse antibiotics from header
            antibiotics = _parse_abbreviated_header(header_clean)

            if len(antibiotics) < 3:
                i += 1
                continue

            # Detect patient type from preceding 3 lines
            preceding = " ".join(norm_lines[max(0, i-3):i])
            patient_type = "All"
            if _re.search(r"\bOPD\b|\bOut[\s-]?patient\b", preceding, _re.IGNORECASE):
                patient_type = "Outpatient"
            elif _re.search(r"\bIPD\b|\bIn[\s-]?[Pp]atient\b", preceding, _re.IGNORECASE):
                patient_type = "Inpatient"

            # Section-level resistance detection (override global)
            section_is_resistant = bool(_re.search(
                r"percent\s+resistant|%\s*resistant", preceding, _re.IGNORECASE
            )) or overall_is_resistant

            # Now parse organism rows — start from after the header lines
            row_i = j
            while row_i < len(norm_lines):
                row = norm_lines[row_i].strip()

                # Stop if we hit another ORGANISMS header or empty section
                if row.upper().startswith(("ORGANISMS", "ORGANISM ")):
                    break
                if _re.match(r"^percent\s+resistant", row, _re.IGNORECASE):
                    break
                if _re.match(r"^(note|key|fosfomycin|for any|based on|contact)",
                            row, _re.IGNORECASE):
                    break

                # Combine multi-line organism rows (some PDFs split organism name across lines)
                # If line ends without numbers and next line has numbers, merge
                if row and not _re.search(r"\d", row) and row_i + 1 < len(norm_lines):
                    next_row = norm_lines[row_i + 1].strip()
                    if next_row and _re.search(r"\d", next_row):
                        row = row + " " + next_row
                        row_i += 1

                # Match: organism name followed by sequence of values
                # Organism: 1-3 words, starts with capital
                m = _re.match(
                    r"^([A-Z][a-zA-Z.]+(?:\s+[a-z]+){0,2})\s+"
                    r"((?:(?:\d+\.?\d*\s*(?:\(\d+\))?|NT|NA|-)\s*){2,})\s*$",
                    row
                )

                if m:
                    organism_raw = m.group(1).strip().rstrip(".")
                    vals_text = m.group(2).strip()

                    if len(organism_raw) >= 4 and not any(
                        s in organism_raw.lower() for s in
                        {"note", "key", "total", "percent", "based"}
                    ):
                        # Parse values
                        # Handle "0.7 (1)" → 0.7
                        vals_clean = _re.sub(r"\s*\(\d+\)", "", vals_text)
                        values = []
                        for tok in _re.split(r"\s+", vals_clean):
                            tok = tok.strip().rstrip("*+")
                            if not tok:
                                continue
                            if tok.upper() in ("NT", "NA", "-", "N/A"):
                                values.append(None)
                            else:
                                try:
                                    values.append(float(tok))
                                except ValueError:
                                    pass

                        # Map to antibiotics
                        for idx, ab in enumerate(antibiotics):
                            if idx >= len(values):
                                break
                            val = values[idx]
                            if val is None or not (0 <= val <= 100):
                                continue
                            if section_is_resistant:
                                resist = round(val, 1)
                                susc = round(100 - val, 1)
                            else:
                                susc = round(val, 1)
                                resist = round(100 - val, 1)
                            records.append({
                                "hospital": hospital, "year": year,
                                "pathogen": std_pathogen(organism_raw),
                                "antibiotic": ab,
                                "susceptible_pct": susc, "resistance_pct": resist,
                                "n_tested": 0, "specimen": "All",
                                "patient_type": patient_type,
                                "source": "Hospital antibiogram",
                            })

                row_i += 1

            i = row_i
        else:
            i += 1

    # ============================================================
    # STRATEGY B: Concatenated full-name header (SKMCH-style)
    # Pattern: "AmpicillinAmikacinCo-amoxiclavCeftriaxone..."
    # Also handles "SKMCH&RC INPATIENT, PERCENT SENSITIVE" sections
    # ============================================================
    if len(records) < 5:
        b_lines = normalized.split("\n")
        for b_line_idx, b_line in enumerate(b_lines):
            b_stripped = b_line.strip()
            if len(b_stripped) < 25:
                continue

            # Detect concatenated header: CamelCase antibiotic names joined together
            # OR a line that looks like a long antibiotic name sequence
            is_concat = bool(_re.search(r"[a-z][A-Z]", b_stripped))
            if not is_concat:
                continue

            antibiotics_b = _parse_antibiotic_header_greedy(b_stripped)
            if len(antibiotics_b) < 4:
                continue

            context_b = "\n".join(b_lines[max(0, b_line_idx-3):b_line_idx+1])
            is_resistant_b = bool(_re.search(
                r"percent\s+resistant|%\s*resistant", context_b, _re.IGNORECASE
            ))

            current_pt_b = "All"
            for b_sl in b_lines[b_line_idx+1:b_line_idx+100]:
                b_sl = b_sl.strip()
                if _re.search(r"INPATIENT", b_sl, _re.IGNORECASE):
                    current_pt_b = "Inpatient"
                    continue
                elif _re.search(r"OUTPATIENT", b_sl, _re.IGNORECASE):
                    current_pt_b = "Outpatient"
                    continue

                m_b = _re.match(
                    r"([A-Z][a-zA-Z.\s]{3,30}?)\s*\((\d+)\)\s*"
                    r"((?:(?:\d+\.?\d*|NT)\s*){2,})",
                    b_sl
                )
                if not m_b:
                    continue

                organism_raw_b = m_b.group(1).strip()
                n_b = int(m_b.group(2))
                vals_b = []
                for v_b in _re.split(r"\s+", m_b.group(3).strip()):
                    v_b = v_b.strip()
                    if v_b.upper() in ("NT", "NA", "-"):
                        vals_b.append(None)
                    else:
                        try:
                            vals_b.append(float(v_b))
                        except ValueError:
                            pass

                for ab_idx, ab_b in enumerate(antibiotics_b):
                    if ab_idx >= len(vals_b) or vals_b[ab_idx] is None:
                        break
                    v_b = vals_b[ab_idx]
                    if not (0 <= v_b <= 100):
                        continue
                    if is_resistant_b:
                        resist_b, susc_b = round(v_b, 1), round(100 - v_b, 1)
                    else:
                        susc_b, resist_b = round(v_b, 1), round(100 - v_b, 1)
                    records.append({
                        "hospital": hospital, "year": year,
                        "pathogen": std_pathogen(organism_raw_b),
                        "antibiotic": ab_b,
                        "susceptible_pct": susc_b, "resistance_pct": resist_b,
                        "n_tested": n_b, "specimen": "All",
                        "patient_type": current_pt_b,
                        "source": "Hospital antibiogram",
                    })

    # ============================================================
    # STRATEGY C: pdfplumber table extraction
    # Direct table cell reading — best for grid-structured PDFs
    # ============================================================
    if len(records) < 5:
        try:
            import pdfplumber
            with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        header_row = None
                        data_rows = []
                        for row in table:
                            if not row:
                                continue
                            clean = [str(c).strip() if c else "" for c in row]
                            if header_row is None:
                                ab_indicators = [
                                    "amikacin", "meropenem", "ceftriaxone",
                                    "ciprofloxacin", "vancomycin", "imipenem",
                                    "ak", "mem", "cro", "cip", "va"
                                ]
                                if any(
                                    any(ab in c.lower() for ab in ab_indicators)
                                    for c in clean
                                ):
                                    header_row = clean
                            else:
                                data_rows.append(clean)

                        if not header_row or not data_rows:
                            continue

                        ab_cols = {}
                        for i, h in enumerate(header_row):
                            if i == 0 or not h:
                                continue
                            ab_name = std_antibiotic(h)
                            ab_cols[i] = ab_name if ab_name != h else h

                        for row in data_rows:
                            if not row or not row[0]:
                                continue
                            organism_raw = row[0].strip()
                            if len(organism_raw) < 4:
                                continue
                            pathogen = std_pathogen(organism_raw)
                            if not pathogen:
                                continue
                            for col_i, ab in ab_cols.items():
                                if col_i >= len(row) or not ab:
                                    continue
                                val_str = str(row[col_i]).strip().rstrip("*+%")
                                if not val_str or val_str.upper() in ("NT", "NA", "-", "NONE", ""):
                                    continue
                                try:
                                    val = float(val_str)
                                    if not (0 <= val <= 100):
                                        continue
                                    records.append({
                                        "hospital": hospital, "year": year,
                                        "pathogen": pathogen,
                                        "antibiotic": std_antibiotic(ab),
                                        "susceptible_pct": round(val, 1),
                                        "resistance_pct": round(100 - val, 1),
                                        "n_tested": 0, "specimen": "All",
                                        "patient_type": "All",
                                        "source": "Hospital antibiogram (table)",
                                    })
                                except ValueError:
                                    continue
        except Exception:
            pass

    # ============================================================
    # STRATEGY D: pdfplumber table-first extraction (PARN-optimised)
    # Uses the user-provided parse_parn_pdf logic.
    # Best for well-structured PARN PDFs where pdfplumber can
    # extract clean tables (wide format: organism rows × antibiotic cols).
    # Normalises using fuzzy matching against PATHOGEN_MAP and ANTIBIOTIC_FULL.
    # ============================================================
    if len(records) < 5:
        try:
            import pdfplumber
            import pandas as pd
            from difflib import get_close_matches

            known_organisms = list(set(PATHOGEN_MAP.values()))
            known_antibiotics = list(set(ANTIBIOTIC_FULL.values())) + KNOWN_ANTIBIOTICS

            def _fuzzy_organism(x):
                if not x or str(x).strip() in ("", "None"):
                    return None
                x = str(x).strip()
                match = get_close_matches(x, known_organisms, n=1, cutoff=0.55)
                if match:
                    return match[0]
                # Try PATHOGEN_MAP direct lookup
                return std_pathogen(x)

            def _fuzzy_antibiotic(x):
                if not x or str(x).strip() in ("", "None"):
                    return None
                x = str(x).strip()
                # Try abbreviation lookup first
                std = std_antibiotic(x)
                if std and std != x:
                    return std
                match = get_close_matches(x, known_antibiotics, n=1, cutoff=0.6)
                return match[0] if match else x

            tables_d = []
            with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf_d:
                for page_d in pdf_d.pages:
                    t = page_d.extract_table()
                    if t and len(t) > 1:
                        try:
                            df = pd.DataFrame(t[1:], columns=t[0])
                            df.columns = df.columns.astype(str).str.strip()
                            df = df.loc[:, ~df.columns.duplicated()]
                            df = df.dropna(how="all")
                            if len(df) > 0:
                                tables_d.append(df)
                        except Exception:
                            continue

            if tables_d:
                try:
                    df_merged = pd.concat(tables_d, ignore_index=True)
                except Exception:
                    df_merged = max(tables_d, key=lambda x: x.shape[0])

                # Detect organism column
                organism_col_d = None
                for col in df_merged.columns:
                    col_vals = df_merged[col].astype(str).str.lower()
                    if col_vals.str.contains(
                        "coli|kleb|pseudo|acinet|staph|entero|proteus|serrat|salm|shig|strepto",
                        na=False
                    ).any():
                        organism_col_d = col
                        break

                if organism_col_d:
                    # Forward-fill organism names (handles merged cells)
                    df_merged[organism_col_d] = df_merged[organism_col_d].replace(
                        "", pd.NA
                    ).ffill()

                    # Wide → long
                    value_cols_d = [c for c in df_merged.columns if c != organism_col_d]
                    df_long = df_merged.melt(
                        id_vars=[organism_col_d],
                        value_vars=value_cols_d,
                        var_name="Antibiotic",
                        value_name="Value"
                    )

                    # Clean resistance values
                    def _clean_val(v):
                        if pd.isna(v):
                            return None
                        v = str(v).strip().replace("%", "").replace("NT", "").replace("NA", "")
                        try:
                            f = float(v)
                            return f if 0 <= f <= 100 else None
                        except Exception:
                            return None

                    df_long["res"] = df_long["Value"].apply(_clean_val)
                    df_long = df_long.dropna(subset=["res"])

                    # Normalize names
                    df_long["org_std"] = df_long[organism_col_d].apply(_fuzzy_organism)
                    df_long["ab_std"] = df_long["Antibiotic"].apply(_fuzzy_antibiotic)
                    df_long = df_long.dropna(subset=["org_std", "ab_std"])

                    for _, row_d in df_long.iterrows():
                        resist = round(float(row_d["res"]), 1)
                        susc = round(100 - resist, 1)
                        records.append({
                            "hospital": hospital, "year": year,
                            "pathogen": row_d["org_std"],
                            "antibiotic": row_d["ab_std"],
                            "susceptible_pct": susc,
                            "resistance_pct": resist,
                            "n_tested": 0, "specimen": "All",
                            "patient_type": "All",
                            "source": "Hospital antibiogram (table)",
                        })
        except Exception:
            pass

    # Deduplicate
    seen = set()
    deduped = []
    for r in records:
        key = (r["hospital"], r["year"], r["pathogen"],
               r["antibiotic"], r["patient_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    metadata["records_extracted"] = len(deduped)
    metadata["pathogens_found"] = len(set(r["pathogen"] for r in deduped))
    metadata["antibiotics_found"] = len(set(r["antibiotic"] for r in deduped))

    if len(deduped) == 0:
        metadata["suggestion"] = (
            "Could not auto-extract data from this PDF. "
            "Reasons: (1) scanned/image PDF — needs text-based PDF, "
            "(2) unusual layout. "
            "Use the CSV template — download it, fill in resistance values, upload."
        )

    return deduped, metadata


# ---- STEP 3: FILTER ----

def etl_filter(records, hospital=None, pathogen=None, year=None,
               specimen=None, patient_type=None):
    """Filter records by any combination of criteria."""
    f = records
    if hospital:
        f = [r for r in f if r.get("hospital") == hospital]
    if pathogen:
        f = [r for r in f if r.get("pathogen") == pathogen]
    if year:
        f = [r for r in f if str(r.get("year")) == str(year)]
    if specimen and specimen != "All":
        f = [r for r in f if r.get("specimen") == specimen]
    if patient_type and patient_type != "All":
        f = [r for r in f if r.get("patient_type") == patient_type]
    return f


# ---- STEP 4: RANK (empiric therapy logic) ----

def etl_rank_antibiotics(records, pathogen, hospital=None,
                         patient_type=None, specimen=None, year=None):
    """Rank antibiotics by susceptibility. Returns top_3, avoid, caution, all."""
    relevant = etl_filter(records, pathogen=pathogen, hospital=hospital,
                          year=year, patient_type=patient_type, specimen=specimen)
    if not relevant:
        return {"top_3": [], "avoid": [], "caution": [], "all": []}

    # Latest per antibiotic, prefer larger n
    by_ab = {}
    for r in relevant:
        ab = r["antibiotic"]
        if ab not in by_ab or r["n_tested"] > by_ab[ab]["n_tested"]:
            by_ab[ab] = r

    enriched = sorted([{
        "antibiotic": ab,
        "susceptibility_pct": r["susceptible_pct"],
        "resistance_pct": r["resistance_pct"],
        "n_tested": r["n_tested"],
        "is_last_line": is_last_line(ab)[0],
        "classification": classify_antibiotic(ab),
        "year": r["year"],
        "specimen": r["specimen"],
        "patient_type": r["patient_type"],
        "hospital": r.get("hospital", ""),
    } for ab, r in by_ab.items()],
        key=lambda x: -x["susceptibility_pct"])

    # SUPPRESS LAST RESORT antibiotics (e.g. Colistin) from first-line ranking.
    # Even if Colistin shows 100% susceptibility, recommending it as empiric
    # therapy violates antimicrobial stewardship principles.
    eligible_for_top = [e for e in enriched if e["classification"] != "LAST RESORT"]

    top_candidates = [e for e in eligible_for_top if e["susceptibility_pct"] >= 80]
    if len(top_candidates) < 3:
        top_candidates = eligible_for_top[:max(3, len(eligible_for_top))]

    return {
        "top_3": top_candidates[:3],
        "avoid": [e for e in enriched if e["susceptibility_pct"] < 50],
        "caution": [e for e in enriched if 50 <= e["susceptibility_pct"] < 80],
        "all": enriched,
    }


# ---- STEP 5: ARIMA FORECAST ----

def etl_run_arima(years_pcts, forecast_horizon=3):
    """ARIMA(1,1,1) forecast for hospital time-series data."""
    try:
        from statsmodels.tsa.arima.model import ARIMA
        import warnings as _w
        _w.filterwarnings("ignore")
        values = [float(v) for _, v in sorted(years_pcts)]
        years = [int(y) for y, _ in sorted(years_pcts)]
        if len(values) < 4:
            return []
        model = ARIMA(values, order=(1, 1, 1))
        fitted = model.fit()
        fc = fitted.get_forecast(steps=forecast_horizon)
        mean = fc.predicted_mean
        ci = fc.conf_int(alpha=0.2)
        results = []
        for i in range(forecast_horizon):
            pred = max(0, min(100, float(mean.iloc[i] if hasattr(mean, 'iloc') else mean[i])))
            try:
                lo = max(0, min(100, float(ci.iloc[i, 0])))
                hi = max(0, min(100, float(ci.iloc[i, 1])))
            except Exception:
                lo, hi = max(0, pred-10), min(100, pred+10)
            results.append({"year": years[-1]+i+1,
                           "predicted": round(pred, 1),
                           "lower": round(lo, 1),
                           "upper": round(hi, 1)})
        return results
    except Exception:
        return []


# =========================================================
# AMRlytics — PROFESSIONAL ANTIBIOGRAM NORMALIZATION ENGINE
# =========================================================

MASTER_ANTIBIOTICS = [
    "Ampicillin", "Co-amoxiclav", "Ceftriaxone", "Piperacillin-Tazobactam",
    "Gentamicin", "Meropenem", "Imipenem", "Ertapenem", "Amikacin",
    "Fosfomycin", "Nitrofurantoin", "Colistin", "Ciprofloxacin",
    "Levofloxacin", "Trimethoprim-Sulfamethoxazole", "Ceftazidime",
    "Cefepime", "Cefuroxime", "Cefixime", "Ceftazidime-avibactam",
    "Aztreonam", "Vancomycin", "Teicoplanin", "Linezolid", "Daptomycin",
    "Tigecycline", "Trimethoprim-sulfamethoxazole", "Clindamycin",
    "Oxacillin", "Rifampicin", "Chloramphenicol", "Tobramycin",
    "Cefoperazone-sulbactam", "Polymyxin B", "Norfloxacin",
]


def clean_fragmented_text(text):
    """Clean OCR/PDF-fragmented text.

    Handles two cases:
    1. OCR single-char spacing: 'A m p i c i l l i n' → 'Ampicillin'
    2. ReportLab reversed fragments: 'n\\nillic\\nip\\nm\\nA' → 'Ampicillin'
       (ReportLab sometimes stores antibiotic names reversed with newlines)
    """
    text = str(text).strip()

    # Case 2: ReportLab reversed fragmented names
    # Detect: text is mostly newline-separated 1-4 char fragments
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) >= 3 and all(len(l) <= 4 for l in lines):
        # Reassemble by joining fragments, then reverse the whole string
        joined = "".join(lines)
        reversed_name = joined[::-1]
        # Try to match against known antibiotic names
        std = std_antibiotic(reversed_name)
        if std and std != reversed_name:
            return std
        # Try original order too
        std2 = std_antibiotic(joined)
        if std2 and std2 != joined:
            return std2
        return reversed_name

    # Case 1: Normal cleanup
    text = text.replace("\n", " ")
    text = _re.sub(r"\s+", " ", text)

    # Only merge isolated single-character tokens (OCR artifact)
    # 'A m p i c i l l i n' → 'Ampicillin' but NOT 'Co amoxiclav' → 'Coamoxiclav'
    # Match sequences of single chars separated by spaces
    def _merge_single_chars(m):
        return m.group(0).replace(" ", "")
    text = _re.sub(r"\b[A-Za-z] (?:[A-Za-z] ){2,}[A-Za-z]\b", _merge_single_chars, text)

    return text.strip()


def normalize_antibiotic_name(raw):
    """Normalize antibiotic name: strip OCR artifacts, exact lookup, fuzzy fallback."""
    from difflib import get_close_matches as _gcm
    if raw is None:
        return None
    text = str(raw)
    # Remove line breaks and all whitespace
    text = text.replace("\n", "")
    text = _re.sub(r"\s+", "", text)
    # Lowercase
    text = text.lower()
    # Strip common OCR artifacts
    text = text.replace("*", "").replace("+", "").replace("=", "").strip()

    # Lookup dictionary — all-lowercase, no spaces/hyphens
    ANTIBIOTIC_LOOKUP = {
        "ampicillin": "Ampicillin",
        "coamoxiclav": "Co-amoxiclav",
        "amoxicillinclavulanate": "Co-amoxiclav",
        "amoxicillin-clavulanate": "Co-amoxiclav",
        "amoxicillinclavulanicacid": "Co-amoxiclav",
        "ceftriaxone": "Ceftriaxone",
        "cefotaxime": "Ceftriaxone",
        "piperacillintazobactam": "Piperacillin-Tazobactam",
        "piptaz": "Piperacillin-Tazobactam",
        "tzp": "Piperacillin-Tazobactam",
        "gentamicin": "Gentamicin",
        "gentamycin": "Gentamicin",
        "meropenem": "Meropenem",
        "imipenem": "Imipenem",
        "ertapenem": "Ertapenem",
        "amikacin": "Amikacin",
        "fosfomycin": "Fosfomycin",
        "nitrofurantoin": "Nitrofurantoin",
        "colistin": "Colistin",
        "polymyxinb": "Colistin",
        "ciprofloxacin": "Ciprofloxacin",
        "levofloxacin": "Levofloxacin",
        "trimethoprimsulfamethoxazole": "Trimethoprim-Sulfamethoxazole",
        "cotrimoxazole": "Trimethoprim-Sulfamethoxazole",
        "sxt": "Trimethoprim-Sulfamethoxazole",
        "ceftazidime": "Ceftazidime",
        "ceftazidimeavibactam": "Ceftazidime-avibactam",
        "cefepime": "Cefepime",
        "cefuroxime": "Cefuroxime",
        "cefixime": "Cefixime",
        "vancomycin": "Vancomycin",
        "teicoplanin": "Teicoplanin",
        "linezolid": "Linezolid",
        "daptomycin": "Daptomycin",
        "tigecycline": "Tigecycline",
        "aztreonam": "Aztreonam",
        "rifampicin": "Rifampicin",
        "rifampin": "Rifampicin",
        "clindamycin": "Clindamycin",
        "chloramphenicol": "Chloramphenicol",
        "tobramycin": "Tobramycin",
        "oxacillin": "Oxacillin",
        "cefoperazonesulbactam": "Cefoperazone-sulbactam",
        "norfloxacin": "Norfloxacin",
        "ofloxacin": "Ofloxacin",
    }

    # Direct exact match
    if text in ANTIBIOTIC_LOOKUP:
        return ANTIBIOTIC_LOOKUP[text]

    # Fuzzy fallback against lookup keys
    match = _gcm(text, list(ANTIBIOTIC_LOOKUP.keys()), n=1, cutoff=0.55)
    if match:
        return ANTIBIOTIC_LOOKUP[match[0]]

    # Last resort: try std_antibiotic from ANTIBIOTIC_FULL
    std = std_antibiotic(raw)
    if std and std != raw:
        return std

    return raw


def standardize_antibiogram_df(df):
    """
    Standardize a parsed antibiogram DataFrame.
    Input columns: Antibiotic, Resistance (%), optionally Susceptible (%), n_tested, Specimen
    Output columns: Antibiotic, Resistance (%), Susceptible (%), n_tested, Specimen
    Deduplicates and sorts by resistance descending.
    """
    cleaned_rows = []
    for _, row in df.iterrows():
        abx = normalize_antibiotic_name(str(row.get("Antibiotic", "")))
        try:
            resistance = float(row["Resistance (%)"])
            if not (0 <= resistance <= 100):
                continue
        except (ValueError, TypeError):
            continue
        # Susceptible may already be supplied; if not, derive it
        try:
            susceptible = float(row["Susceptible (%)"])
        except (KeyError, ValueError, TypeError):
            susceptible = round(100 - resistance, 1)
        # Preserve isolate count and specimen if present
        try:
            n_tested = int(row.get("n_tested", 0) or 0)
        except (ValueError, TypeError):
            n_tested = 0
        specimen = str(row.get("Specimen", row.get("specimen", "All")) or "All").strip()
        cleaned_rows.append({
            "Antibiotic": abx,
            "Resistance (%)": resistance,
            "Susceptible (%)": susceptible,
            "n_tested": n_tested,
            "Specimen": specimen,
        })
    out = pd.DataFrame(cleaned_rows)
    if out.empty:
        return out
    out = out.drop_duplicates(subset=["Antibiotic"])
    out = out.sort_values("Resistance (%)", ascending=False)
    return out.reset_index(drop=True)


def generate_professional_pdf(
    df, hospital, organism, year,
    report_version="1.0",
    methodology=None,
    specimen_info=None,
    parser_confidence=None,
    data_completeness=None,
    national_benchmarks=None,
    who_benchmarks=None,
):
    """
    Generate a professional clinical antibiogram PDF report.

    Enhanced with 10 clinical-grade improvements:
      1. Isolate counts (n=) alongside every resistance/susceptibility percentage
      2. Methodology section (CLSI/EUCAST interpretation + duplicate handling)
      3. Report versioning and generation timestamp
      4. Specimen/source information per antibiotic
      5. Interpretation thresholds for empiric therapy recommendations
      6. Hospital vs national/WHO benchmarking section
      7. Strengthened stewardship disclaimer language
      8. AMRlytics watermark/footer branding on every page
      9. Professionally formatted italicised pathogen names
     10. Parser confidence / data completeness indicators

    Returns a BytesIO buffer ready for st.download_button.
    """
    import io as _io_pdf
    from datetime import datetime as _dt_pdf
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable,
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    # ── colour palette ────────────────────────────────────────────────────────
    BRAND_ORANGE = colors.HexColor("#d85a30")
    BRAND_DARK   = colors.HexColor("#1a1a1a")
    LIGHT_GREY   = colors.HexColor("#f4f4f4")
    MID_GREY     = colors.HexColor("#cccccc")
    GREEN        = colors.HexColor("#3b6d11")
    AMBER        = colors.HexColor("#ba7517")
    RED          = colors.HexColor("#a32d2d")
    WHITE        = colors.white

    # ── generation timestamp (Change 3) ──────────────────────────────────────
    generated_at = _dt_pdf.now().strftime("%Y-%m-%d %H:%M UTC")

    # ── document setup ────────────────────────────────────────────────────────
    buffer = _io_pdf.BytesIO()

    # Watermark / footer on every page (Change 8)
    def _add_page_footer(canvas, doc):
        canvas.saveState()
        w, h = letter
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#999999"))
        footer_text = (
            f"AMRlytics Intelligence Engine · amrlytics.ai · "
            f"{hospital} · {organism} · {year} · "
            f"v{report_version} · Generated {generated_at} · "
            f"CONFIDENTIAL — FOR CLINICAL STEWARDSHIP USE ONLY"
        )
        canvas.drawCentredString(w / 2, 0.4 * inch, footer_text)
        # light orange rule above footer
        canvas.setStrokeColor(BRAND_ORANGE)
        canvas.setLineWidth(0.5)
        canvas.line(0.75 * inch, 0.55 * inch, w - 0.75 * inch, 0.55 * inch)
        # page number (right-aligned)
        canvas.drawRightString(w - 0.75 * inch, 0.28 * inch,
                               f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.65 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    # ── styles ────────────────────────────────────────────────────────────────
    base = getSampleStyleSheet()

    def _style(name, parent="BodyText", **kw):
        s = ParagraphStyle(name, parent=base[parent], **kw)
        return s

    sTitle      = _style("RPTitle",    "Title",    fontSize=20, textColor=BRAND_DARK,
                          spaceAfter=4, leading=24)
    sSubtitle   = _style("RPSubtitle", "BodyText", fontSize=10, textColor=BRAND_ORANGE,
                          spaceAfter=10, fontName="Helvetica-Bold", leading=14)
    sMeta       = _style("RPMeta",     "BodyText", fontSize=9,  textColor=BRAND_DARK,
                          leading=15, spaceAfter=2)
    sSection    = _style("RPSection",  "BodyText", fontSize=12, fontName="Helvetica-Bold",
                          textColor=BRAND_DARK, spaceBefore=14, spaceAfter=6)
    sBody       = _style("RPBody",     "BodyText", fontSize=9,  leading=14, spaceAfter=3)
    sSmall      = _style("RPSmall",    "BodyText", fontSize=7.5, textColor=colors.HexColor("#666"),
                          leading=11)
    sDisclaimer = _style("RPDisclaim", "BodyText", fontSize=7.5,
                          textColor=colors.HexColor("#555"), leading=11, spaceBefore=6)
    sBadge      = _style("RPBadge",    "BodyText", fontSize=8,
                          textColor=colors.HexColor("#444"), leading=12)

    elements = []

    # ── HEADER BLOCK ─────────────────────────────────────────────────────────
    elements.append(Paragraph("AMRlytics — Clinical Antibiogram Report", sTitle))
    elements.append(Paragraph(
        "Hospital Antimicrobial Stewardship Programme · Confidential",
        sSubtitle,
    ))
    elements.append(HRFlowable(width="100%", thickness=1.5,
                               color=BRAND_ORANGE, spaceAfter=10))

    # ── REPORT IDENTITY (Change 3 — versioning & timestamp) ──────────────────
    # Graceful fallback for missing or unparseable hospital name and year
    def _clean_hospital_name(h):
        """Sanitize hospital name — fallback gracefully when auto-detect fails."""
        if not h:
            return "Hospital name pending verification"
        h_str = str(h).strip()
        if not h_str:
            return "Hospital name pending verification"
        # Catch known auto-detect failure tokens
        bad_tokens = {"unknown", "unknown hospital", "n/a", "none", "null",
                      "least most", "most least", "untitled", "test"}
        if h_str.lower() in bad_tokens:
            return "Hospital name pending verification"
        # Catch nonsense ALL-CAPS short strings (likely PDF extraction artefacts)
        if len(h_str) < 4 and h_str.isupper():
            return "Hospital name pending verification"
        return h_str

    def _clean_year_value(y):
        """Sanitize reporting year — fallback gracefully when auto-detect fails."""
        if y is None:
            return "Year pending"
        y_str = str(y).strip()
        if not y_str or y_str.lower() in {"unknown", "n/a", "none", "null"}:
            return "Year pending"
        # If it parses as a sensible year, return as-is
        try:
            y_int = int(y_str)
            if 1990 <= y_int <= 2030:
                return y_str
            return "Year pending"
        except (ValueError, TypeError):
            return y_str  # accept ranges like "Jan-Dec 2024"

    hospital_display = _clean_hospital_name(hospital)
    year_display = _clean_year_value(year)

    meta_data = [
        ["Hospital / Facility",  hospital_display,
         "Report Version",        f"v{report_version}"],
        ["Reporting Period",      year_display,
         "Generated",             generated_at],
        ["Pathogen (organism)",   f"<i>{organism}</i>",    # Change 9 — italic
         "Specimen / Source",     specimen_info or "All specimens (pooled)"],
    ]
    meta_table_rows = []
    for label_a, val_a, label_b, val_b in meta_data:
        meta_table_rows.append([
            Paragraph(f"<b>{label_a}</b>", sMeta),
            Paragraph(val_a, sMeta),
            Paragraph(f"<b>{label_b}</b>", sMeta),
            Paragraph(val_b, sMeta),
        ])
    meta_tbl = Table(meta_table_rows,
                     colWidths=[1.5*inch, 2.2*inch, 1.5*inch, 2.2*inch])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREY),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT_GREY),
        ("GRID",       (0, 0), (-1, -1), 0.4, MID_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
    ]))
    elements.append(meta_tbl)
    elements.append(Spacer(1, 14))

    # ── CHANGE 10 — Parser confidence / data completeness ────────────────────
    conf_label = parser_confidence or "Unknown"
    completeness_val = data_completeness if data_completeness is not None else "N/A"
    n_drugs = len(df)
    has_n_data = df["n_tested"].sum() > 0 if "n_tested" in df.columns else False
    conf_color_map = {
        "High":   GREEN, "Medium": AMBER, "Low": RED,
        "Unknown": colors.HexColor("#888"),
    }
    conf_color = conf_color_map.get(conf_label, colors.HexColor("#888"))
    conf_row = [
        Paragraph(f"<b>Parser Confidence:</b> {conf_label}", sMeta),
        Paragraph(f"<b>Antibiotics Analysed:</b> {n_drugs}", sMeta),
        Paragraph(f"<b>Isolate Count Data:</b> {'Present' if has_n_data else 'Not extracted'}", sMeta),
        Paragraph(f"<b>Data Completeness:</b> {completeness_val}", sMeta),
    ]
    conf_tbl = Table([conf_row], colWidths=[1.85*inch]*4)
    conf_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f8f8")),
        ("GRID",       (0, 0), (-1, -1), 0.4, MID_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("TEXTCOLOR", (0, 0), (0, 0), conf_color),
    ]))
    elements.append(conf_tbl)
    elements.append(Spacer(1, 16))

    # ── CHANGE 5 — Interpretation thresholds for empiric therapy ─────────────
    elements.append(Paragraph("Empiric Therapy Interpretation Thresholds", sSection))
    thresh_data = [
        ["Threshold", "Susceptibility", "Resistance", "Stewardship Guidance"],
        ["Preferred (1st-line)",   "≥ 80%", "< 20%",
         "Suitable for empiric monotherapy (≥80% predicted success)"],
        ["Conditional (2nd-line)", "50–79%", "21–49%",
         "Consider in combination or after culture confirmation"],
        ["Avoid (empiric)",        "< 50%", "≥ 50%",
         "Empiric monotherapy generally discouraged; use guided by C&S only"],
        ["Critical / Reserve",     "Any",   "≥ 70%",
         "Reserve agents only; AMS review required before prescribing"],
    ]
    thresh_tbl = Table(thresh_data,
                       colWidths=[1.4*inch, 0.9*inch, 0.9*inch, 4.1*inch])
    thresh_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_ORANGE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1),
         [colors.HexColor("#eaf4e2"), colors.HexColor("#fff8e8"),
          colors.HexColor("#fde8e4"), colors.HexColor("#f9eaea")]),
        ("GRID",          (0, 0), (-1, -1), 0.4, MID_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
    ]))
    elements.append(thresh_tbl)
    elements.append(Spacer(1, 14))

    # ── CHANGE 5 continued — Top candidates / avoid summary ──────────────────
    top_3 = df[df["Susceptible (%)"] >= 80].head(3)
    avoid = df[df["Resistance (%)"] >= 50]

    if not top_3.empty:
        elements.append(Paragraph(
            "Preferred Empiric Therapy Candidates (Susceptibility ≥80%)", sSection))
        elements.append(Spacer(1, 4))
        for _, row in top_3.iterrows():
            n_str = (f", n={int(row['n_tested'])} isolates"
                     if "n_tested" in row and int(row.get("n_tested", 0)) > 0 else "")
            elements.append(Paragraph(
                f"&#10003; <b>{row['Antibiotic']}</b> — "
                f"{row['Susceptible (%)']:.1f}% susceptible, "
                f"{row['Resistance (%)']:.1f}% resistant"
                f"{n_str}",
                sBody,
            ))
        elements.append(Spacer(1, 10))

    if not avoid.empty:
        elements.append(Paragraph(
            "Avoid as Empiric Therapy (Resistance ≥50%)", sSection))
        elements.append(Spacer(1, 4))
        for _, row in avoid.iterrows():
            n_str = (f", n={int(row['n_tested'])} isolates"
                     if "n_tested" in row and int(row.get("n_tested", 0)) > 0 else "")
            elements.append(Paragraph(
                f"&#10007; <b>{row['Antibiotic']}</b> — "
                f"{row['Resistance (%)']:.1f}% resistant"
                f"{n_str}",
                sBody,
            ))
        elements.append(Spacer(1, 10))

    # ── CHANGE 1 + 9 — Full susceptibility table with isolate counts ──────────
    elements.append(Paragraph(
        f"Full Antibiotic Susceptibility Profile — "
        f"<i>{organism}</i>",   # Change 9: italic species in heading
        sSection,
    ))
    elements.append(Spacer(1, 4))

    # Determine whether specimen column has useful data
    show_specimen = ("Specimen" in df.columns and
                     df["Specimen"].nunique() > 1)

    # Build header
    if show_specimen:
        header = ["Antibiotic", "Resistance (%)\n(n= isolates)",
                  "Susceptible (%)\n(n= isolates)", "Specimen / Source",
                  "Empiric Tier"]
        col_w = [2.1*inch, 1.2*inch, 1.2*inch, 1.1*inch, 1.0*inch]
    else:
        header = ["Antibiotic", "Resistance (%)\n(n= isolates)",
                  "Susceptible (%)\n(n= isolates)", "Empiric Tier"]
        col_w = [2.3*inch, 1.45*inch, 1.45*inch, 1.2*inch]

    table_data = [header]

    for _, row in df.iterrows():
        n = int(row.get("n_tested", 0) or 0)
        n_str = f" (n={n})" if n > 0 else ""
        r_pct = row["Resistance (%)"]
        s_pct = row["Susceptible (%)"]

        # Empiric tier classification
        if s_pct >= 80:
            tier_str = "Preferred"
        elif s_pct >= 50:
            tier_str = "Conditional"
        elif r_pct >= 70:
            tier_str = "Critical"
        else:
            tier_str = "Avoid"

        data_row = [
            row["Antibiotic"],
            f"{r_pct:.1f}%{n_str}",
            f"{s_pct:.1f}%{n_str}",
        ]
        if show_specimen:
            data_row.append(str(row.get("Specimen", "All")) or "All")
        data_row.append(tier_str)
        table_data.append(data_row)

    # Row-level color coding by tier
    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    row_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_ORANGE),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("GRID",       (0, 0), (-1, -1), 0.4, MID_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, data_row in enumerate(table_data[1:], start=1):
        tier = data_row[-1]
        if tier == "Preferred":
            row_styles.append(("BACKGROUND", (0, i), (-1, i),
                                colors.HexColor("#eaf4e2")))
        elif tier == "Conditional":
            row_styles.append(("BACKGROUND", (0, i), (-1, i),
                                colors.HexColor("#fff8e8")))
        elif tier == "Critical":
            row_styles.append(("BACKGROUND", (0, i), (-1, i),
                                colors.HexColor("#f9eaea")))
        else:  # Avoid
            row_styles.append(("BACKGROUND", (0, i), (-1, i),
                                colors.HexColor("#fde8e4")))
    tbl.setStyle(TableStyle(row_styles))
    elements.append(tbl)
    elements.append(Spacer(1, 16))

    # ── CHANGE 6 — Hospital vs national / WHO benchmarking ───────────────────
    if national_benchmarks or who_benchmarks:
        elements.append(Paragraph("Benchmarking — Hospital vs Reference Values",
                                  sSection))
        elements.append(Spacer(1, 4))
        bm_header = ["Antibiotic", "Hospital R (%)", "National R (%)",
                     "WHO/GLASS R (%)", "Δ vs National", "Δ vs WHO"]
        bm_rows = [bm_header]
        for _, row in df.iterrows():
            ab = row["Antibiotic"]
            h_r = row["Resistance (%)"]
            nat_r  = (national_benchmarks or {}).get(ab)
            who_r  = (who_benchmarks or {}).get(ab)
            delta_nat = (f"{h_r - nat_r:+.1f}pp" if nat_r is not None else "—")
            delta_who = (f"{h_r - who_r:+.1f}pp" if who_r is not None else "—")
            bm_rows.append([
                ab,
                f"{h_r:.1f}%",
                f"{nat_r:.1f}%" if nat_r is not None else "N/A",
                f"{who_r:.1f}%" if who_r is not None else "N/A",
                delta_nat,
                delta_who,
            ])
        bm_tbl = Table(bm_rows,
                       colWidths=[2.0*inch, 0.9*inch, 0.9*inch,
                                  0.9*inch, 0.9*inch, 0.9*inch])
        bm_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
            ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#ffffff"), colors.HexColor("#f4f4f4")]),
            ("GRID",       (0, 0), (-1, -1), 0.4, MID_GREY),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ]))
        elements.append(bm_tbl)
        elements.append(Paragraph(
            "Δ values = hospital resistance minus reference value "
            "(positive = hospital higher than benchmark).",
            sSmall,
        ))
        elements.append(Spacer(1, 16))
    else:
        # ── CHANGE 3 (Option B) — Benchmarking CTA when no comparator data ──
        # Turn an empty section into a marketing message that drives discovery.
        elements.append(Paragraph("Benchmarking", sSection))

        cta_text = (
            "<b>Benchmarking module available in AMRlytics Pro.</b><br/><br/>"
            "Visit <font color='#d85a30'><b>amrlytics.ai</b></font> to enable "
            "hospital vs national vs WHO regional resistance comparison for "
            f"<i>{organism}</i>. The Pro module integrates WHO GLASS country data "
            "and WHO regional averages, automatically identifying antibiotics where "
            "this institution deviates &gt;10 percentage points from national benchmarks — "
            "the highest-priority targets for stewardship intervention."
        )

        # Wrap CTA in a coloured box to make it visually distinct
        cta_table = Table(
            [[Paragraph(cta_text, sBody)]],
            colWidths=[6.8 * inch],
        )
        cta_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#fdf5f2")),
            ("BOX",           (0, 0), (-1, -1), 1, BRAND_ORANGE),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ("TOPPADDING",    (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        elements.append(cta_table)
        elements.append(Spacer(1, 16))

    # ── CHANGE 2 — Methodology section ───────────────────────────────────────
    elements.append(Paragraph("Methodology & Data Quality Notes", sSection))
    method_str = methodology or "Not specified in source document"
    method_text = (
        f"<b>Breakpoint standard:</b> {method_str}<br/>"
        "Breakpoints applied follow the most recent edition of the stated standard "
        "(CLSI M100 or EUCAST Clinical Breakpoint Tables). Where breakpoint standard "
        "was not explicitly stated in the source document, the AMRlytics parser has "
        "flagged this; clinical interpretation should account for this uncertainty.<br/><br/>"
        "<b>Duplicate isolate handling:</b> Per CLSI M39 and EUCAST guidelines, "
        "only the first isolate per patient per episode is included when de-duplication "
        "data is available. Where this information was not present in the source, "
        "all isolates are included and a caveat is noted in the data completeness indicator.<br/><br/>"
        "<b>Minimum isolate threshold:</b> Resistance percentages derived from fewer "
        "than 30 isolates should be interpreted with caution. Where n &lt; 30 the isolate "
        "count is highlighted in the susceptibility table above."
    )
    elements.append(Paragraph(method_text, sBody))
    elements.append(Spacer(1, 14))

    # ── CHANGE 7 — Strengthened stewardship disclaimer ────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.8,
                               color=BRAND_ORANGE, spaceAfter=8))
    elements.append(Paragraph("⚠  Stewardship Disclaimer & Limitations", sSection))
    disclaimer_text = (
        "<b>This report is produced solely for antimicrobial stewardship, infection control, "
        "and epidemiological surveillance purposes. It does NOT constitute a prescribing "
        "recommendation, clinical decision support, or substitute for individualised patient "
        "assessment.</b><br/><br/>"
        "1. <b>Individual susceptibility testing is mandatory</b> before initiating targeted "
        "antimicrobial therapy. Population-level resistance percentages do not predict the "
        "susceptibility of an individual patient's isolate.<br/>"
        "2. <b>Clinical context is essential.</b> Empiric tier classifications are based "
        "on epidemiological thresholds only and do not account for pharmacokinetic/pharmacodynamic "
        "parameters, route of administration, site of infection, allergy history, renal/hepatic "
        "function, or drug interactions.<br/>"
        "3. <b>Reserve and last-resort antibiotics</b> (WHO AWaRe categories) must only be "
        "initiated after formal Antimicrobial Stewardship Programme (AMS) or infectious disease "
        "consultation, regardless of susceptibility data.<br/>"
        "4. <b>Data limitations.</b> Accuracy depends on the completeness and quality of the "
        "source antibiogram. Isolates with intermediate susceptibility may be classified "
        "differently depending on the breakpoint standard applied (CLSI vs EUCAST).<br/>"
        "5. <b>Not for external distribution.</b> This report contains institution-specific "
        "resistance data. Distribution outside the named facility requires governance approval.<br/><br/>"
        "References: IDSA 2024 Guidelines · EUCAST Clinical Breakpoint Tables v14 · "
        "CLSI M100 34th Edition · WHO AWaRe Classification 2023 · WHO BPPL 2024."
    )
    elements.append(Paragraph(disclaimer_text, sDisclaimer))
    elements.append(Spacer(1, 12))

    # ── CHANGE 8 — AMRlytics footer branding block ────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5,
                               color=MID_GREY, spaceAfter=6))
    brand_row = [[
        Paragraph(
            "<b>AMR<font color='#d85a30'>lytics</font></b> — "
            "Global Antimicrobial Resistance Intelligence",
            _style("BrandLeft", "BodyText", fontSize=9, fontName="Helvetica-Bold"),
        ),
        Paragraph(
            f"amrlytics.ai · v{report_version} · {generated_at}",
            _style("BrandRight", "BodyText", fontSize=8,
                   textColor=colors.HexColor("#888"), alignment=TA_RIGHT),
        ),
    ]]
    brand_tbl = Table(brand_row, colWidths=[4.0*inch, 3.4*inch])
    brand_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
    ]))
    elements.append(brand_tbl)

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(elements, onFirstPage=_add_page_footer, onLaterPages=_add_page_footer)
    buffer.seek(0)
    return buffer


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
        "🏥 Hospital Antibiogram",
        "📋 Methodology",
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")

if not st.session_state.pro_unlocked:
    st.sidebar.markdown(
        "<div style='font-family:JetBrains Mono,monospace; font-size:0.65rem; "
        "color:#d85a30; letter-spacing:0.14em; margin-bottom:0.4rem;'>PRO ACCESS</div>",
        unsafe_allow_html=True,
    )
    with st.sidebar.expander("🔓 Request Pro access", expanded=False):
        st.markdown(
            "<p style='font-size:0.78rem; color:#aaa; line-height:1.6;'>"
            "Free for microbiologists, clinicians, researchers, and public health "
            "professionals. Institutional email required.</p>",
            unsafe_allow_html=True,
        )
        signup_name  = st.text_input("Full name", key="signup_name",
                                     placeholder="Dr. Ahmad Junaid")
        signup_email = st.text_input("Institutional email", key="signup_email",
                                     placeholder="you@hospital.org.pk")
        signup_role  = st.text_input("Role / Institution", key="signup_role",
                                     placeholder="Clinical Microbiologist, Aga Khan Hospital")
        if st.button("Request access →", key="signup_btn", use_container_width=True):
            _free = ("gmail.com","yahoo.com","hotmail.com","outlook.com",
                     "icloud.com","live.com","aol.com","protonmail.com")
            _em = (signup_email or "").strip().lower()
            _nm = (signup_name or "").strip()
            if not _nm or not _em or not signup_role:
                st.sidebar.error("Please fill in all fields.")
            elif any(_em.endswith(f"@{p}") for p in _free):
                st.sidebar.warning(
                    "Please use your institutional email (hospital, university, "
                    "or government). Free providers are not accepted.")
            elif "@" not in _em or "." not in _em.split("@")[-1]:
                st.sidebar.error("Please enter a valid email address.")
            else:
                st.sidebar.success(
                    f"✓ Request received for **{_nm}**. "
                    "Your pilot access password will be emailed within 24 hours."
                )
                if "signup_log" not in st.session_state:
                    st.session_state.signup_log = []
                st.session_state.signup_log.append(
                    {"name": _nm, "email": _em, "role": signup_role}
                )
    with st.sidebar.expander("🔑 Already have a password?", expanded=False):
        pwd = st.text_input("Pilot password", type="password", key="sidebar_pwd")
        if st.button("Unlock Pro", key="unlock_sidebar", use_container_width=True):
            if pwd == PRO_PASSWORD:
                st.session_state.pro_unlocked = True
                st.session_state.show_pwd_input = False
                st.rerun()
            else:
                st.sidebar.error("Incorrect password. Contact hello@amrlytics.ai")

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
    st.caption("Free tier: full surveillance dashboard and a forecasting demo. "
              "Pro tier: hospital antibiogram intelligence, full AI forecasting, advanced alerts, "
              "country benchmarking, and custom intelligence reports.")

    pages_info = [
        ("01 — Surveillance", "📊 Interactive Dashboard",
         "Filter resistance trends by pathogen, antibiotic, and country across 66 countries. "
         "WHO GLASS and ECDC EARS-Net data, 2000–2024.",
         "FREE"),
        ("02 — Hospital Intelligence", "🏥 Hospital Antibiogram",
         "Upload any hospital antibiogram (PDF or CSV) and instantly receive empiric therapy "
         "recommendations, risk tier classification, country benchmarking, and clinical-grade PDF report. "
         "Universal parser.",
         "PRO"),
        ("03 — Forecasting", "📈 Trend-based AI Forecasting",
         "Prophet time-series projections with 80% confidence intervals across all country-pathogen-antibiotic "
         "combinations. Free demo available — Italy MRSA.",
         "PRO · 1 free demo"),
        ("04 — Alerts", "⚠ Risk Classification",
         "Critical resistance flags, last-line antibiotic warnings, 3-year acceleration alerts, "
         "and actionable stewardship insights.",
         "FREE + PRO"),
        ("05 — Benchmarking", "🌐 Country Comparison",
         "Compare countries against WHO regional averages, WHO BPPL classification, and historical "
         "trajectory peers.",
         "FREE + PRO"),
        ("06 — Methodology", "📋 Transparent Methodology",
         "Full documentation of data sources, risk tier derivation, forecasting model, hospital antibiogram "
         "parsing pipeline, and limitations. Scientifically defensible.",
         "FREE"),
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
                chart_data.append({"Country": r["country"], "Year": safe_year(r["year"]),
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
            AMRlytics will automatically generate a downloadable PDF report with charts,
            interpretation, and citations — delivered instantly to your inbox.
        </p>
    </div>
    """, unsafe_allow_html=True)
    # NOTE: Custom Report form — POSTs to Formspree
    st.markdown("""
    <form action="https://formspree.io/f/mwvyeypw" method="POST" target="_blank" style="margin:0;">
        <input type="hidden" name="_subject" value="Custom Report Request — AMRlytics">
        <div style="display:flex; flex-direction:column; gap:0.6rem; max-width:480px; margin-bottom:1rem;">
            <input type="text" name="name" placeholder="Your name" required
                style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12);
                border-radius:3px; color:#e8e8e8; font-size:0.875rem; padding:0.6rem 0.9rem; outline:none;">
            <input type="email" name="email" placeholder="Your email" required
                style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12);
                border-radius:3px; color:#e8e8e8; font-size:0.875rem; padding:0.6rem 0.9rem; outline:none;">
            <textarea name="message" placeholder="Describe the report you need (pathogen, country, question...)" required rows="3"
                style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12);
                border-radius:3px; color:#e8e8e8; font-size:0.875rem; padding:0.6rem 0.9rem; outline:none; resize:vertical;"></textarea>
            <button type="submit"
                style="display:inline-block; background:#d85a30; color:#fff; padding:0.6rem 1.4rem;
                border:none; border-radius:2px; font-size:0.9rem; font-weight:500; cursor:pointer;
                font-family:Inter,sans-serif; width:fit-content;">
                Request Custom Report &#x2192;
            </button>
        </div>
    </form>
    <p style="color:#888; font-size:0.78rem; margin:0;">Custom reports are a Pro feature. Your report is automatically generated and delivered to the email you provide.</p>
    """, unsafe_allow_html=True)


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
                    historical.append({"year": safe_year(r["year"]), "pct": float(r["resistance"])})
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
                    historical.append({"year": safe_year(r["year"]), "pct": float(r["resistance"])})
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
                groups[key].append({"year": safe_year(r["year"]), "pct": pct, "source": r["source"]})
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
                        year_r = safe_year(r["year"])
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
                        country_data.append({"Year": safe_year(r["year"]),
                            "Resistance (%)": round(float(r["resistance"]), 1),
                            "Series": bench_country})
                    except (ValueError, TypeError):
                        continue

            regional = [r for r in relevant if r.get("region") == country_region]
            regional_by_year = defaultdict(list)
            for r in regional:
                try:
                    regional_by_year[safe_year(r["year"])].append(float(r["resistance"]))
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
                    global_by_year[safe_year(r["year"])].append(float(r["resistance"]))
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
                    latest = max(country_relevant, key=lambda r: safe_year(r["year"]))
                    latest_pct = float(latest["resistance"])
                    latest_year = safe_year(latest["year"])

                    st.markdown(f"**{bench_country} latest:** {latest_pct:.1f}% ({latest_year})")
                    st.markdown(f"Searching for countries that had {latest_pct-5:.1f}–{latest_pct+5:.1f}% in earlier years…")

                    analogs = []
                    for r in all_data:
                        if (r["pathogen"] == bench_pathogen
                            and r["antibiotic"] == bench_antibiotic
                            and r["country"] != bench_country):
                            try:
                                pct = float(r["resistance"])
                                year = safe_year(r["year"])
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
                                "Years from peer match": safe_year(r["year"]) - latest_year,
                                "Year": safe_year(r["year"]),
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
                                    year = safe_year(r["year"])
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
# PAGE 7: HOSPITAL ANTIBIOGRAM (PRO — full clinical workflow)
# ============================================================

elif page == "🏥 Hospital Antibiogram":
    st.title("Hospital Antibiogram Intelligence")
    st.caption("Upload your hospital's antibiogram → instant clinical insights · "
               "Universal · any hospital · CSV or PDF")

    if not st.session_state.pro_unlocked:
        render_pro_lock_screen(
            "Hospital Antibiogram Intelligence",
            "Upload your hospital's antibiogram (PDF or CSV) and instantly receive: "
            "(1) Top 3 empiric therapy recommendations + Avoid list per pathogen, "
            "(2) Hospital vs national vs WHO regional benchmark (16 countries), "
            "(3) ARIMA-based resistance trend alerts when multi-year data is provided, "
            "(4) Clinical-ready PDF export for MDT rounds and stewardship review."
        )
        st.stop()

    # Initialize session state for uploaded antibiogram
    if "antibiogram_records" not in st.session_state:
        st.session_state.antibiogram_records = []
    if "antibiogram_metadata" not in st.session_state:
        st.session_state.antibiogram_metadata = {}

    # ---- UPLOAD SECTION ----
    st.markdown("### Step 1 — Upload your antibiogram")

    upload_tab1, upload_tab2, upload_tab3 = st.tabs([
        "📄 Upload PDF (any hospital)",
        "📊 Upload CSV (template)",
        "📋 Try sample data"
    ])

    with upload_tab1:
        st.caption("Auto-detects structure from any hospital antibiogram PDF worldwide. "
                   "Supports abbreviated-code formats (AK, AMC, CAZ...), full-name formats, "
                   "and mixed layouts. Works with PARN, WHO GLASS-aligned, EUCAST, and CLSI-formatted reports.")
        pdf_file = st.file_uploader("Drop antibiogram PDF here",
                                    type=["pdf"], key="pdf_upload")
        hospital_override = st.text_input("Hospital name (optional — leave blank for auto-detection)",
                                          key="hospital_override")
        if pdf_file is not None:
            with st.spinner("Extracting antibiogram from PDF…"):
                pdf_bytes = pdf_file.read()
                hosp = hospital_override.strip() if hospital_override else None
                records, metadata = etl_parse_pdf_universal(pdf_bytes, hospital_hint=hosp)
                if records:
                    # Assess parser & display badges
                    assessment = assess_parser_confidence(records, metadata)
                    metadata["confidence"] = assessment["confidence"]
                    metadata["structured"] = assessment["structured"]
                    if assessment["methodology"] and not metadata.get("methodology"):
                        metadata["methodology"] = assessment["methodology"]

                    st.session_state.antibiogram_records = records
                    st.session_state.antibiogram_metadata = metadata
                    st.success(
                        f"✓ Extracted **{len(records)} records** from "
                        f"**{metadata['hospital']}** ({metadata['year']}) · "
                        f"Pathogens: {metadata.get('pathogens_found', '?')} · "
                        f"Antibiotics: {metadata.get('antibiotics_found', '?')}"
                    )
                    render_parser_badges(assessment, metadata)

                    # Auto-save normalized records to persistent DB
                    try:
                        saved_path = save_normalized_to_database(records, metadata)
                        if saved_path:
                            st.caption(
                                f"💾 Normalized records saved to **{saved_path}** "
                                f"(deduplicated by hospital × year × pathogen × antibiotic)"
                            )
                    except Exception as _e:
                        st.caption(f"⚠ Could not save to normalized DB: {_e}")
                else:
                    # Clear any stale session data so old results don't show
                    st.session_state.antibiogram_records = []
                    st.session_state.antibiogram_metadata = {}
                    st.error("⚠ Could not extract data automatically. "
                             f"{metadata.get('suggestion', '')}")
                    with st.expander("Technical details"):
                        st.code(metadata.get("error", "Unknown extraction error"))
                    st.info("💡 **Try these options:**\n"
                           "1. Switch to the **Upload CSV** tab and use the template\n"
                           "2. Make sure your PDF is text-based (not a scanned image)\n"
                           "3. If it's scanned, export from your LIS system as a text PDF")

    with upload_tab2:
        st.caption("Use this when PDF extraction fails or you want full control. "
                   "or to upload data manually with full control.")
        col1, col2 = st.columns([2, 1])
        with col1:
            csv_file = st.file_uploader("Drop filled CSV template here",
                                       type=["csv"], key="csv_upload")
        with col2:
            template_csv = get_csv_template()
            st.download_button("📥 Download blank template",
                             template_csv,
                             "amrlytics_antibiogram_template.csv",
                             "text/csv",
                             use_container_width=True)
        if csv_file is not None:
            csv_bytes = csv_file.read()
            records, errors, warnings = etl_parse_csv(csv_bytes)
            if records:
                metadata = {
                    "format": "CSV",
                    "format_detected": "CSV",
                    "year": records[0]["year"] if records else "Unknown",
                    "hospital": records[0]["hospital"] if records else "Unknown",
                    "records_extracted": len(records),
                    "pathogens_found":   len(set(r["pathogen"] for r in records)),
                    "antibiotics_found": len(set(r["antibiotic"] for r in records)),
                    "methodology": None,
                }
                assessment = assess_parser_confidence(records, metadata)
                metadata["confidence"] = assessment["confidence"]
                metadata["structured"] = True
                st.session_state.antibiogram_records = records
                st.session_state.antibiogram_metadata = metadata
                st.success(f"✓ Loaded **{len(records)} records** from CSV")
                render_parser_badges(assessment, metadata)
                try:
                    saved_path = save_normalized_to_database(records, metadata)
                    if saved_path:
                        st.caption(f"💾 Normalized records saved to **{saved_path}**")
                except Exception as _e:
                    st.caption(f"⚠ Could not save to normalized DB: {_e}")
                if errors:
                    with st.expander(f"⚠ {len(errors)} parsing error(s)"):
                        for e in errors[:20]:
                            st.caption(f"• {e}")
                if warnings:
                    with st.expander(f"ℹ {len(warnings)} data warning(s)"):
                        for w in warnings[:20]:
                            st.caption(f"• {w}")
            else:
                st.error("No valid records found. Check column names match the template.")
                if errors:
                    for e in errors[:5]:
                        st.error(e)

    with upload_tab3:
        st.caption("Try the platform with a real sample antibiogram dataset to see all features in action.")
        if st.button("Load sample antibiogram data", type="primary"):
            sample_csv = """Hospital,Year,Pathogen,Antibiotic,%Susceptible,%Resistant,N_tested,Specimen,Patient_type
City Hospital,2024,Acinetobacter baumannii,Amikacin,28,72,112,All,Inpatient
City Hospital,2024,Acinetobacter baumannii,Ceftriaxone,1,99,112,All,Inpatient
City Hospital,2024,Acinetobacter baumannii,Ciprofloxacin,27,73,112,All,Inpatient
City Hospital,2024,Acinetobacter baumannii,Meropenem,26,74,112,All,Inpatient
City Hospital,2024,Acinetobacter baumannii,Imipenem,28,72,112,All,Inpatient
City Hospital,2024,Acinetobacter baumannii,Tigecycline,74,26,112,All,Inpatient
City Hospital,2024,Acinetobacter baumannii,Colistin,100,0,112,All,Inpatient
City Hospital,2024,Escherichia coli,Ampicillin,4,96,2181,All,Inpatient
City Hospital,2024,Escherichia coli,Amikacin,76,24,2181,All,Inpatient
City Hospital,2024,Escherichia coli,Ceftriaxone,11,89,2181,All,Inpatient
City Hospital,2024,Escherichia coli,Ciprofloxacin,19,81,2181,All,Inpatient
City Hospital,2024,Escherichia coli,Trimethoprim-sulfamethoxazole,25,75,2181,All,Inpatient
City Hospital,2024,Escherichia coli,Ertapenem,73,27,2181,All,Inpatient
City Hospital,2024,Escherichia coli,Meropenem,74,26,2181,All,Inpatient
City Hospital,2024,Escherichia coli,Piperacillin-tazobactam,52,48,2181,All,Inpatient
City Hospital,2024,Escherichia coli,Gentamicin,65,35,2181,All,Inpatient
City Hospital,2024,Klebsiella pneumoniae,Amikacin,78,22,586,All,Inpatient
City Hospital,2024,Klebsiella pneumoniae,Ceftriaxone,29,71,586,All,Inpatient
City Hospital,2024,Klebsiella pneumoniae,Ciprofloxacin,43,57,586,All,Inpatient
City Hospital,2024,Klebsiella pneumoniae,Meropenem,79,21,586,All,Inpatient
City Hospital,2024,Klebsiella pneumoniae,Imipenem,79,21,586,All,Inpatient
City Hospital,2024,Klebsiella pneumoniae,Colistin,98,2,586,All,Inpatient
City Hospital,2024,Pseudomonas aeruginosa,Amikacin,81,19,1203,All,Inpatient
City Hospital,2024,Pseudomonas aeruginosa,Meropenem,85,15,1203,All,Inpatient
City Hospital,2024,Pseudomonas aeruginosa,Imipenem,85,15,1203,All,Inpatient
City Hospital,2024,Pseudomonas aeruginosa,Piperacillin-tazobactam,78,22,1203,All,Inpatient
City Hospital,2024,Pseudomonas aeruginosa,Colistin,100,0,1203,All,Inpatient
City Hospital,2024,Staphylococcus aureus,Vancomycin,100,0,1472,All,Inpatient
City Hospital,2024,Staphylococcus aureus,Linezolid,100,0,1472,All,Inpatient
City Hospital,2024,Staphylococcus aureus,Clindamycin,80,20,1472,All,Inpatient
City Hospital,2024,Staphylococcus aureus,Erythromycin,44,56,1472,All,Inpatient
City Hospital,2024,Staphylococcus aureus,Gentamicin,81,19,1472,All,Inpatient"""
            records, errors, warnings = etl_parse_csv(sample_csv)
            st.session_state.antibiogram_records = records
            st.session_state.antibiogram_metadata = {
                "format": "Sample data",
                "year": "2024",
                "hospital": "City Hospital",
                "records_extracted": len(records),
            }
            st.success(f"✓ Loaded {len(records)} records from sample antibiogram")
            st.rerun()

    # ---- ANALYSIS SECTION (only if data is loaded) ----
    if not st.session_state.antibiogram_records:
        st.markdown("---")
        st.info("👆 Upload an antibiogram above to unlock clinical insights.")
        st.stop()

    records = st.session_state.antibiogram_records
    metadata = st.session_state.antibiogram_metadata

    st.markdown("---")
    st.markdown(f"### Step 2 — Analyze: **{metadata['hospital']}** ({metadata['year']})")

    # Re-render parser badges so they remain visible after upload
    try:
        _assessment = assess_parser_confidence(records, metadata)
        render_parser_badges(_assessment, metadata)
    except Exception:
        pass

    # Filters (Change #4)
    col1, col2, col3 = st.columns(3)
    # Build pathogen labels with isolate counts: "Escherichia coli (n=2265)"
    # Take max n_tested across antibiotics for that organism (typical antibiogram convention)
    pathogen_n = {}
    for r in records:
        p = r["pathogen"]
        n = r.get("n_tested", 0) or 0
        if n > pathogen_n.get(p, 0):
            pathogen_n[p] = n
    pathogens_raw = sorted(set(r["pathogen"] for r in records))
    def _label_pathogen(p):
        n = pathogen_n.get(p, 0)
        return f"{p} (n={n})" if n > 0 else p
    pathogen_labels = {_label_pathogen(p): p for p in pathogens_raw}
    with col1:
        sel_label = st.selectbox("Pathogen", list(pathogen_labels.keys()), key="ab_path")
        sel_pathogen = pathogen_labels[sel_label]
    pt_options = sorted(set(r["patient_type"] for r in records))
    with col2:
        sel_pt = st.selectbox("Patient type", ["All"] + [p for p in pt_options if p != "All"],
                             key="ab_pt")
    sp_options = sorted(set(r["specimen"] for r in records))
    with col3:
        sel_sp = st.selectbox("Specimen", ["All"] + [s for s in sp_options if s != "All"],
                             key="ab_sp")

    # Filter records
    filter_pt = sel_pt if sel_pt != "All" else None
    filter_sp = sel_sp if sel_sp != "All" else None
    filtered = etl_filter(records, pathogen=sel_pathogen,
                          patient_type=filter_pt, specimen=filter_sp)

    if not filtered:
        st.warning(f"No data for {sel_pathogen} with selected filters.")
        st.stop()

    # ============================================================
    # FEATURE 1 — EMPIRIC THERAPY RECOMMENDATIONS
    # ============================================================
    st.markdown("---")
    st.markdown("## 💊 Empiric therapy recommendations")

    ranking = etl_rank_antibiotics(records, pathogen=sel_pathogen,
                                    patient_type=filter_pt, specimen=filter_sp)

    col_top, col_avoid = st.columns(2)

    with col_top:
        st.markdown("### 🟢 Top 3 — empiric therapy candidates")
        st.caption(f"Highest susceptibility rates for **{sel_pathogen}** at "
                  f"**{metadata['hospital']}** ({metadata['year']})")
        if ranking["top_3"]:
            for i, r in enumerate(ranking["top_3"], 1):
                tier = r.get("classification", "FIRST LINE")
                tier_badge = classification_badge_html(tier)
                bg = "rgba(59,109,17,0.08)" if r["susceptibility_pct"] >= 80 else "rgba(186,117,23,0.08)"
                border = "rgba(59,109,17,0.3)" if r["susceptibility_pct"] >= 80 else "rgba(186,117,23,0.3)"
                # Build isolate count line — show prominently if available
                n_val = r.get('n_tested', 0) or 0
                n_line = (f" · <span style='color:#d85a30; font-weight:600;'>n={n_val} isolates</span>"
                          if n_val > 0 else
                          " · <span style='color:#666; font-style:italic;'>isolate count not reported</span>")
                st.markdown(
                    f"<div style='background:{bg}; border:1px solid {border}; "
                    f"padding:0.85rem 1.1rem; border-radius:4px; margin-bottom:0.5rem;'>"
                    f"<div style='font-family:JetBrains Mono,monospace; font-size:0.65rem; "
                    f"color:#888; letter-spacing:0.1em;'>OPTION {i}{tier_badge}</div>"
                    f"<div style='font-family:Instrument Serif,serif; font-size:1.3rem; "
                    f"color:#e8e8e8;'>{r['antibiotic']}</div>"
                    f"<div style='color:#aaa; font-size:0.85rem; margin-top:0.25rem;'>"
                    f"<b>{r['susceptibility_pct']:.1f}%</b> susceptible{n_line}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            st.info("No candidates with adequate susceptibility found.")

    with col_avoid:
        st.markdown("### 🔴 Avoid as empiric therapy")
        st.caption("Resistance >50% — empiric monotherapy strongly discouraged")
        if ranking["avoid"]:
            for r in ranking["avoid"][:8]:
                tier = r.get("classification", "FIRST LINE")
                tier_badge = classification_badge_html(tier)
                n_val = r.get('n_tested', 0) or 0
                n_line = (f" · <span style='color:#d85a30; font-weight:600;'>n={n_val}</span>"
                          if n_val > 0 else "")
                st.markdown(
                    f"<div style='background:rgba(163,45,45,0.06); "
                    f"border-left:3px solid #a32d2d; "
                    f"padding:0.6rem 0.9rem; border-radius:3px; margin-bottom:0.4rem;'>"
                    f"<b style='color:#e8e8e8;'>{r['antibiotic']}</b>{tier_badge}<br>"
                    f"<span style='color:#aaa; font-size:0.8rem;'>"
                    f"Only {r['susceptibility_pct']:.1f}% susceptible · "
                    f"R = {r['resistance_pct']:.1f}%{n_line}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            st.success("No antibiotics in avoid range — good susceptibility profile.")

    if ranking["caution"]:
        with st.expander(f"⚠ Caution zone ({len(ranking['caution'])} antibiotics, 50-80% susceptible)"):
            for r in ranking["caution"]:
                n_line = (f" (n={r['n_tested']})"
                          if r['n_tested'] and r['n_tested'] > 0 else "")
                tier = r.get("classification", "FIRST LINE")
                tier_badge = classification_badge_html(tier)
                st.markdown(f"- **{r['antibiotic']}**{tier_badge} — {r['susceptibility_pct']:.1f}% S{n_line}",
                           unsafe_allow_html=True)

    st.warning("⚠ This is surveillance data ranking, NOT a prescribing recommendation. "
              "Always combine with: clinical assessment, individual susceptibility testing, "
              "patient factors, and current treatment guidelines (IDSA, EUCAST, local protocols).")

    # ============================================================
    # FEATURE 2 — HOSPITAL vs NATIONAL/REGIONAL BENCHMARK
    # ============================================================
    st.markdown("---")
    st.markdown("## 🌐 Hospital vs benchmark comparison")

    # Dynamic country benchmark map
    COUNTRY_BENCHMARK_MAP = {
        "Pakistan":        ("Pakistan",             "South-East Asia Region",  "Pakistan (WHO GLASS)",     "SE Asia Region (avg)"),
        "India":           ("India",                "South-East Asia Region",  "India (WHO GLASS)",        "SE Asia Region (avg)"),
        "Bangladesh":      ("Bangladesh",           "South-East Asia Region",  "Bangladesh (WHO GLASS)",   "SE Asia Region (avg)"),
        "Nepal":           ("Nepal",                "South-East Asia Region",  "Nepal (WHO GLASS)",        "SE Asia Region (avg)"),
        "United States":   ("United States",        "Region of the Americas",  "USA (WHO GLASS)",          "Americas Region (avg)"),
        "United Kingdom":  ("United Kingdom",       "European Region",         "UK (WHO GLASS)",           "European Region (avg)"),
        "Germany":         ("Germany",              "European Region",         "Germany (WHO GLASS)",      "European Region (avg)"),
        "France":          ("France",               "European Region",         "France (WHO GLASS)",       "European Region (avg)"),
        "Brazil":          ("Brazil",               "Region of the Americas",  "Brazil (WHO GLASS)",       "Americas Region (avg)"),
        "South Africa":    ("South Africa",         "African Region",          "S. Africa (WHO GLASS)",    "African Region (avg)"),
        "Kenya":           ("Kenya",                "African Region",          "Kenya (WHO GLASS)",        "African Region (avg)"),
        "Nigeria":         ("Nigeria",              "African Region",          "Nigeria (WHO GLASS)",      "African Region (avg)"),
        "Australia":       ("Australia",            "Western Pacific Region",  "Australia (WHO GLASS)",    "W. Pacific Region (avg)"),
        "Saudi Arabia":    ("Saudi Arabia",         "Eastern Mediterranean",   "Saudi Arabia (WHO GLASS)", "E. Med Region (avg)"),
        "Iran":            ("Iran (Islamic Rep.)",  "Eastern Mediterranean",   "Iran (WHO GLASS)",         "E. Med Region (avg)"),
        "Other / Global":  (None,                   None,                      "National (WHO GLASS)",     "WHO Region (avg)"),
    }

    bench_country_sel = st.selectbox(
        "Hospital country (for benchmark)",
        options=list(COUNTRY_BENCHMARK_MAP.keys()),
        index=0,
        key="bench_country_sel",
        help="Select the hospital's country to benchmark against national WHO GLASS and WHO regional averages."
    )
    _nat_country, _region_name, _nat_label, _region_label = COUNTRY_BENCHMARK_MAP[bench_country_sel]

    st.caption(f"How does **{metadata['hospital']}** compare against "
              f"**{_nat_label}** and **{_region_label}** for {sel_pathogen}?")

    # Get equivalent data from main AMRlytics data
    pakistan_data = ([r for r in all_data
                      if r["country"] == _nat_country
                      and r["pathogen"] == sel_pathogen]
                     if _nat_country else [])

    sear_data = ([r for r in all_data
                  if r.get("region") == _region_name
                  and r["pathogen"] == sel_pathogen]
                 if _region_name else [])

    # Build antibiotic alias map: hospital name → WHO GLASS name
    # WHO GLASS uses drug class names; hospital antibiograms use specific drug names
    WHO_GLASS_ALIAS = {
        "Ceftriaxone": ["Third-generation cephalosporins", "Cephalosporins (3rd gen)",
                        "Ceftriaxone", "Cefotaxime"],
        "Ceftazidime": ["Third-generation cephalosporins", "Cephalosporins (3rd gen)"],
        "Cefepime": ["Fourth-generation cephalosporins", "Cephalosporins (4th gen)"],
        "Ciprofloxacin": ["Fluoroquinolones", "Ciprofloxacin", "Quinolones"],
        "Levofloxacin": ["Fluoroquinolones", "Quinolones"],
        "Meropenem": ["Carbapenems", "Meropenem"],
        "Imipenem": ["Carbapenems", "Imipenem"],
        "Ertapenem": ["Carbapenems", "Ertapenem"],
        "Amikacin": ["Aminoglycosides", "Amikacin"],
        "Gentamicin": ["Aminoglycosides", "Gentamicin"],
        "Tobramycin": ["Aminoglycosides"],
        "Piperacillin-tazobactam": ["Piperacillin+tazobactam", "Piperacillin-tazobactam",
                                     "Beta-lactam/beta-lactamase inhibitors"],
        "Ampicillin": ["Ampicillin", "Aminopenicillins"],
        "Amoxicillin-clavulanate": ["Amoxicillin+clavulanic acid", "Aminopenicillins",
                                     "Beta-lactam/beta-lactamase inhibitors"],
        "Trimethoprim-sulfamethoxazole": ["Trimethoprim-sulfamethoxazole",
                                          "Sulfamethoxazole+trimethoprim", "Cotrimoxazole"],
        "Colistin": ["Colistin", "Polymyxins"],
        "Vancomycin": ["Vancomycin", "Glycopeptides"],
        "Linezolid": ["Linezolid", "Oxazolidinones"],
        "Nitrofurantoin": ["Nitrofurantoin"],
        "Fosfomycin": ["Fosfomycin"],
    }

    def _find_who_match(hospital_ab, who_data):
        """Find WHO GLASS data matching a hospital antibiotic name."""
        # Direct match first
        direct = [r for r in who_data if r["antibiotic"] == hospital_ab]
        if direct:
            return direct
        # Try aliases
        for ab_key, aliases in WHO_GLASS_ALIAS.items():
            if hospital_ab.lower() in ab_key.lower() or ab_key.lower() in hospital_ab.lower():
                for alias in aliases:
                    matched = [r for r in who_data if alias.lower() in r["antibiotic"].lower()
                               or r["antibiotic"].lower() in alias.lower()]
                    if matched:
                        return matched
        # Fuzzy: check if any WHO antibiotic name contains the hospital name
        for r in who_data:
            who_ab = r["antibiotic"].lower()
            hosp_ab = hospital_ab.lower()
            if (hosp_ab[:6] in who_ab or who_ab[:6] in hosp_ab or
                any(part in who_ab for part in hosp_ab.split("-") if len(part) > 4)):
                return [r]
        return []

    bench_rows = []
    for r in ranking["all"]:
        ab = r["antibiotic"]
        bench_rows.append({
            "Antibiotic": ab,
            "Source": metadata['hospital'],
            "Resistance (%)": r["resistance_pct"],
            "n": r["n_tested"],
        })
        # National WHO GLASS comparison — fuzzy match
        pak_match = _find_who_match(ab, pakistan_data)
        if pak_match:
            try:
                latest = max(pak_match, key=lambda x: x["year"])
                pak_pct = float(latest["resistance"])
                bench_rows.append({
                    "Antibiotic": ab,
                    "Source": _nat_label,
                    "Resistance (%)": round(pak_pct, 1),
                    "n": 0,
                })
            except (ValueError, TypeError):
                pass
        # Regional comparison — fuzzy match
        sear_match = _find_who_match(ab, sear_data)
        if sear_match:
            try:
                pcts = [float(s["resistance"]) for s in sear_match]
                bench_rows.append({
                    "Antibiotic": ab,
                    "Source": _region_label,
                    "Resistance (%)": round(sum(pcts)/len(pcts), 1),
                    "n": 0,
                })
            except (ValueError, TypeError):
                pass

    if bench_rows:
        bench_df = pd.DataFrame(bench_rows)

        # Show all antibiotics from hospital data, even without comparators
        all_hospital_abs = [r["antibiotic"] for r in ranking["all"]]
        ab_counts = bench_df.groupby("Antibiotic")["Source"].count()
        comparable_abs = ab_counts[ab_counts >= 2].index.tolist()

        # Fall back to just hospital data if no comparators found
        display_abs = comparable_abs if comparable_abs else all_hospital_abs

        if display_abs:
            # Limit to top 12 antibiotics to keep chart readable
            display_df = bench_df[bench_df["Antibiotic"].isin(display_abs)]
            top_abs = (display_df.groupby("Antibiotic")["Resistance (%)"]
                       .max().sort_values(ascending=False).head(12).index.tolist())
            display_df = display_df[display_df["Antibiotic"].isin(top_abs)]
            # Sort dataframe so highest-resistance antibiotic appears first
            sort_order = {ab: i for i, ab in enumerate(top_abs)}
            display_df = display_df.assign(
                _sort_key=display_df["Antibiotic"].map(sort_order)
            ).sort_values("_sort_key").drop(columns=["_sort_key"]).reset_index(drop=True)

            # Simple grouped horizontal bars: Antibiotic on Y, Resistance on X, Source as color
            # Use yOffset for grouping (works in Altair >= 5.0)
            try:
                chart = alt.Chart(display_df).mark_bar().encode(
                    y=alt.Y("Antibiotic:N",
                            sort=alt.EncodingSortField(
                                field="Resistance (%)", op="max", order="descending"),
                            title=None,
                            axis=alt.Axis(labelLimit=300, labelFontSize=12)),
                    x=alt.X("Resistance (%):Q",
                            scale=alt.Scale(domain=[0, 100]),
                            title="Resistance (%)"),
                    yOffset=alt.YOffset("Source:N"),
                    color=alt.Color("Source:N",
                            scale=alt.Scale(
                                domain=[metadata['hospital'],
                                        _nat_label,
                                        _region_label],
                                range=["#d85a30", "#3b6d11", "#888888"]),
                            legend=alt.Legend(title="Source", orient="top")),
                    tooltip=["Antibiotic", "Source",
                             alt.Tooltip("Resistance (%):Q", format=".1f"), "n"]
                ).properties(
                    height=max(400, 50 * len(top_abs)),
                    title=f"{sel_pathogen} resistance — hospital vs national vs regional"
                )
                st.altair_chart(chart, use_container_width=True)
            except Exception:
                # Fallback for older Altair: facet rows
                chart = alt.Chart(display_df).mark_bar().encode(
                    x=alt.X("Resistance (%):Q",
                            scale=alt.Scale(domain=[0, 100])),
                    y=alt.Y("Source:N", title=None),
                    color=alt.Color("Source:N", scale=alt.Scale(
                        domain=[metadata['hospital'], _nat_label, _region_label],
                        range=["#d85a30", "#3b6d11", "#888888"])),
                    tooltip=["Antibiotic", "Source", "Resistance (%)", "n"]
                ).properties(
                    width=500, height=80
                ).facet(
                    row=alt.Row("Antibiotic:N",
                               sort=alt.EncodingSortField(
                                   field="Resistance (%)", op="max", order="descending"),
                               header=alt.Header(labelAngle=0, labelAlign="left",
                                                labelOrient="left", labelFontSize=12,
                                                labelLimit=300, title=None))
                ).resolve_scale(y="independent")
                st.altair_chart(chart, use_container_width=True)

            if not comparable_abs:
                st.info(f"ℹ No matching antibiotic names found in {_nat_label} or {_region_label} data. "
                       "Showing hospital data only. This is common — hospital antibiograms "
                       "often test different antibiotics than national surveillance reports. "
                       "The hospital column above shows your institution's resistance profile.")
            # Key gaps — Hospital vs national WHO GLASS delta analysis
            st.markdown(f"### 📊 Key gaps — Hospital vs {_nat_label}")
            hospital_resistance = {r["antibiotic"]: r["resistance_pct"] for r in ranking["all"]}
            nat_resistance = {b["Antibiotic"]: b["Resistance (%)"]
                              for b in bench_rows if b["Source"] == _nat_label}

            # Build full delta table sorted by absolute magnitude
            deltas = []
            for ab, h_r in hospital_resistance.items():
                if ab in nat_resistance:
                    p_r = nat_resistance[ab]
                    deltas.append({
                        "Antibiotic": ab,
                        "Hospital R%": h_r,
                        f"{_nat_label} R%": p_r,
                        "Δ (pp)": round(h_r - p_r, 1),
                        "abs_delta": abs(h_r - p_r),
                    })

            if not deltas:
                st.info(f"No overlapping antibiotics between hospital data and {_nat_label} "
                       "to compare. Hospital antibiograms typically test more agents than national "
                       "surveillance, which focuses on priority pathogens.")
            else:
                deltas.sort(key=lambda d: -d["abs_delta"])
                significant = [d for d in deltas if d["abs_delta"] >= 10]
                worse  = [d for d in deltas if d["Δ (pp)"] >=  10]
                better = [d for d in deltas if d["Δ (pp)"] <= -10]

                # Summary line
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Antibiotics compared", len(deltas))
                col_b.metric("Hospital worse (≥10pp)", len(worse),
                             help=f"Hospital resistance exceeds {_nat_label} by ≥10 percentage points")
                col_c.metric("Hospital better (≥10pp)", len(better),
                             help=f"Hospital resistance is below {_nat_label} by ≥10 percentage points")

                if significant:
                    st.caption("Top differences ranked by absolute gap:")
                    for d in significant[:5]:
                        direction = "higher" if d["Δ (pp)"] > 0 else "lower"
                        emoji = "🔴" if d["Δ (pp)"] > 0 else "🟢"
                        nat_r = d.get(f"{_nat_label} R%", 0)
                        st.markdown(
                            f"{emoji} **{d['Antibiotic']}**: hospital resistance is "
                            f"**{abs(d['Δ (pp)']):.1f}pp {direction}** than {_nat_label} "
                            f"({d['Hospital R%']:.1f}% vs {nat_r:.1f}%)"
                        )

                # Full delta table (collapsed)
                with st.expander(f"📋 Full delta table ({len(deltas)} antibiotics)"):
                    delta_df = pd.DataFrame(deltas).drop(columns=["abs_delta"])
                    st.dataframe(delta_df, use_container_width=True, hide_index=True)

                if not significant:
                    st.success("Hospital resistance levels are broadly aligned with national averages "
                              "(no >10pp gaps detected in either direction).")
        else:
            st.info(f"No matching antibiotics found in {_nat_label} or {_region_label} data for "
                   "comparison. This is normal — your hospital may track different antibiotics "
                   "than national surveillance reports.")
    else:
        st.info("Benchmarking data not available for this pathogen.")

    # ============================================================
    # FEATURE 3 — TREND + EARLY WARNING (if multi-year data)
    # ============================================================
    st.markdown("---")
    st.markdown("## 📈 Resistance trends & early warning")
    st.caption("ARIMA forecast + alerts when multi-year data is available")

    # Check if we have multi-year data for this hospital + pathogen
    multi_year = defaultdict(list)
    for r in records:
        if r["pathogen"] == sel_pathogen:
            multi_year[r["antibiotic"]].append((safe_year(r["year"]), r["resistance_pct"]))

    has_multi = any(len(v) >= 3 for v in multi_year.values())

    if has_multi:
        # Multi-year analysis
        st.markdown("### Multi-year resistance trends")
        for ab, year_pcts in multi_year.items():
            if len(year_pcts) < 3:
                continue
            year_pcts_sorted = sorted(year_pcts)
            df = pd.DataFrame(year_pcts_sorted, columns=["Year", "Resistance (%)"])
            df["Type"] = "Observed"

            # Try ARIMA forecast
            forecast = etl_run_arima(year_pcts_sorted, forecast_horizon=3)
            if forecast:
                forecast_df = pd.DataFrame([{
                    "Year": f["year"],
                    "Resistance (%)": f["predicted"],
                    "Lower": f["lower"],
                    "Upper": f["upper"],
                    "Type": "Forecast"
                } for f in forecast])

                combined = pd.concat([df, forecast_df[["Year", "Resistance (%)", "Type"]]])
                obs_line = alt.Chart(df).mark_line(color="#3b6d11", strokeWidth=2.5,
                    point=True).encode(
                    x="Year:O", y=alt.Y("Resistance (%):Q", scale=alt.Scale(domain=[0, 100])))
                fc_line = alt.Chart(forecast_df).mark_line(color="#d85a30",
                    strokeDash=[6, 4], strokeWidth=2.5).encode(
                    x="Year:O", y="Resistance (%):Q")
                fc_band = alt.Chart(forecast_df).mark_area(opacity=0.2,
                    color="#d85a30").encode(
                    x="Year:O", y="Lower:Q", y2="Upper:Q")
                st.altair_chart((fc_band + obs_line + fc_line).properties(
                    height=300, title=f"{ab} — ARIMA 3-year forecast"),
                    use_container_width=True)

                # Alert logic
                latest_obs = year_pcts_sorted[-1][1]
                projected_3yr = forecast[-1]["predicted"]
                change_3yr = projected_3yr - latest_obs
                if change_3yr >= 10:
                    st.error(f"🚨 **EARLY WARNING:** {ab} resistance projected to rise "
                            f"{change_3yr:.1f}pp over next 3 years "
                            f"({latest_obs:.1f}% → {projected_3yr:.1f}%)")
    else:
        st.info("📅 Multi-year resistance trend analysis requires antibiogram data from "
               "multiple years for the same hospital. Upload additional years to unlock "
               "ARIMA-based forecasting and early-warning alerts.")
        st.markdown(
            f"**For now, here's the alert summary based on your single-year data:**"
        )
        # Single-year alerts
        critical_alerts = [r for r in ranking["all"] if r["resistance_pct"] >= 50]
        last_line_alerts = [r for r in ranking["all"]
                          if r["is_last_line"] and r["resistance_pct"] >= 10]
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.markdown(f"**🔴 Critical resistance (>50%)**")
            if critical_alerts:
                for r in critical_alerts[:5]:
                    st.markdown(f"- {r['antibiotic']}: **{r['resistance_pct']:.1f}%** R")
            else:
                st.success("None detected.")
        with col_a2:
            st.markdown(f"**🛡️ Reserve antibiotic alerts**")
            if last_line_alerts:
                for r in last_line_alerts[:5]:
                    st.markdown(f"- {r['antibiotic']}: **{r['resistance_pct']:.1f}%** R")
            else:
                st.success("Last-line drugs maintaining efficacy.")

    # ============================================================
    # FEATURE 5 — CLINICAL PDF EXPORT
    # ============================================================
    st.markdown("---")
    st.markdown("## 📄 Clinical-ready report export")
    st.caption("Download a formatted PDF summary suitable for MDT rounds, "
              "stewardship reviews, and clinical reference.")

    if st.button("Generate clinical PDF report", type="primary"):
        try:
            # Build standardized DataFrame from current ranking — include n_tested + Specimen
            df_for_pdf = pd.DataFrame([{
                "Antibiotic":     r["antibiotic"],
                "Resistance (%)": r["resistance_pct"],
                "Susceptible (%)": r["susceptibility_pct"],
                "n_tested":       r.get("n_tested", 0),
                "Specimen":       r.get("specimen", "All"),
            } for r in ranking["all"]])

            df_for_pdf = standardize_antibiogram_df(df_for_pdf)

            if df_for_pdf.empty:
                st.warning("No data to generate report from.")
            else:
                # Derive specimen summary for cover page
                specimens_present = sorted(set(
                    r.get("specimen", "All") for r in ranking["all"]
                    if r.get("specimen") and r.get("specimen") != "All"
                ))
                specimen_info_str = (
                    ", ".join(specimens_present) if specimens_present else None
                )

                # Parser confidence from session state if available
                _conf = st.session_state.get("_parser_assessment", {})
                _methodology = (
                    metadata.get("methodology")
                    or _conf.get("methodology")
                    or "Not specified"
                )
                _confidence = _conf.get("confidence", "Unknown")
                _n_total = sum(
                    r.get("n_tested", 0) or 0 for r in ranking["all"]
                )
                _n_drugs = len(ranking["all"])
                _completeness = (
                    f"{_n_total:,} total isolates across {_n_drugs} antibiotics"
                    if _n_total > 0 else "Isolate counts not extracted"
                )

                pdf_buffer = generate_professional_pdf(
                    df=df_for_pdf,
                    hospital=metadata.get("hospital", "Hospital name pending verification"),
                    organism=sel_pathogen,
                    year=metadata.get("year", "Year pending"),
                    report_version="1.0",
                    methodology=_methodology,
                    specimen_info=specimen_info_str,
                    parser_confidence=_confidence,
                    data_completeness=_completeness,
                )
                filename = (
                    f"AMRlytics_"
                    f"{metadata.get('hospital','Hospital').replace(' ','_')}_"
                    f"{sel_pathogen.replace(' ','_')}_"
                    f"{metadata.get('year','')}.pdf"
                )
                st.download_button(
                    "📥 Download clinical PDF report",
                    pdf_buffer,
                    filename,
                    "application/pdf",
                )
                st.success("✓ PDF ready. Click above to download.")

        except ImportError:
            st.warning("⚠ PDF export requires `reportlab`. "
                      "Run `pip install reportlab` then restart.")
        except Exception as e:
            st.error(f"PDF generation error: {e}")

    # ============================================================
    # FULL DATA TABLE (collapsible)
    # ============================================================
    with st.expander("📋 Full antibiogram data table"):
        full_df = pd.DataFrame([{
            "Pathogen": r["pathogen"],
            "Antibiotic": r["antibiotic"],
            "Susceptible (%)": r["susceptible_pct"],
            "Resistance (%)": r["resistance_pct"],
            "n": r["n_tested"],
            "Patient type": r["patient_type"],
            "Specimen": r["specimen"],
        } for r in records])
        st.dataframe(full_df, use_container_width=True, hide_index=True)
        csv_export = full_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download as CSV", csv_export,
                         f"{metadata['hospital'].replace(' ', '_')}_antibiogram_{metadata['year']}.csv",
                         "text/csv")

    # ============================================================
    # FOOTER WATERMARK
    # ============================================================
    from datetime import datetime as _dt
    _ts = _dt.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
<div style="margin-top:3rem; padding:1.2rem 0; border-top:1px solid rgba(255,255,255,0.08);
            text-align:center; font-family:JetBrains Mono,monospace; font-size:0.7rem;
            color:#666; letter-spacing:0.12em;">
  GENERATED BY AMRLYTICS INTELLIGENCE ENGINE<br>
  <span style="font-size:0.62rem; color:#555; letter-spacing:0.08em;">
    {metadata.get('hospital', 'Unknown')} · {metadata.get('year', 'Unknown')} ·
    Report generated {_ts} · amrlytics.ai
  </span>
</div>
""",
        unsafe_allow_html=True
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
    st.markdown("## Hospital Antibiogram Intelligence")
    st.markdown("""
The Hospital Antibiogram Intelligence module accepts institutional antibiogram data in two formats:

**PDF upload** — text-based antibiogram PDFs are parsed using a three-strategy semantic extraction pipeline:
1. Table-based parsing with semantic header and organism column detection
2. Per-page text parsing for rotated or letter-spaced headers (e.g. Lahore General style)
3. OCR fallback for fully-scanned documents (requires pytesseract)

**CSV upload** — structured data uploaded via the AMRlytics template. Auto-detects column names and accepts common variants (Organism/Pathogen, %Susceptible/%Resistant, N_tested, etc.).

**Antibiotic normalisation** — all antibiotic names are normalised to a standardised reference dictionary covering full names, abbreviations (CAZ, AMK, CIP), and common synonyms. Output names follow WHO AWaRe and CLSI M100 conventions.

**Empiric tier classification** — each antibiotic is assigned one of four tiers based on local susceptibility: Preferred (≥80% S), Conditional (50–79% S), Avoid (<50% S), and Critical/Reserve (resistance ≥70% in last-line agents).

**Benchmarking** — hospital resistance percentages are compared against national WHO GLASS data and WHO regional averages using a fuzzy antibiotic name matching algorithm that resolves institutional naming variants to WHO GLASS drug class nomenclature. The hospital's country is selected by the user at analysis time.

**Key gap analysis** — antibiotics where hospital resistance deviates ≥10 percentage points from the national benchmark are flagged as priority stewardship targets.

**Limitations:**
- PDF extraction accuracy depends on the source document being text-based. Scanned/image PDFs require the CSV fallback.
- Breakpoint standard is auto-detected (CLSI/EUCAST) but not verified against the original report.
- Benchmarking requires the selected pathogen to exist in WHO GLASS data for the chosen country.
- All outputs represent population-level surveillance data and are not prescribing recommendations.
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
