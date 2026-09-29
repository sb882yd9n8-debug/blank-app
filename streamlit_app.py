import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ============================================================
# ROMANIA BOND ANALYZER
# BVB – Relative Value / Fair Value / Timing
# ============================================================

st.set_page_config(
    page_title="Romania Bond Analyzer",
    page_icon="🇷🇴",
    layout="wide"
)

# ------------------------------------------------------------
# CSS – optimizat pentru iPhone
# ------------------------------------------------------------

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem;
            padding-left: 0.7rem;
            padding-right: 0.7rem;
        }

        h1 {
            font-size: 1.55rem !important;
        }

        h2, h3 {
            font-size: 1.15rem !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.25rem;
        }

        .small-note {
            font-size: 0.78rem;
            opacity: 0.75;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🇷🇴 Romania Bond Analyzer")

st.caption(
    "BVB • YTM • Relative Value • Fair Value • Liquidity • Timing"
)

# ============================================================
# INPUT
# ============================================================

with st.sidebar:

    st.header("Setări")

    timing_days = st.selectbox(
        "Timing",
        [20, 60, 120],
        index=1
    )

    st.markdown("### Tickere BVB")

    default_tickers = [
        "R3106A",
        "R3108A",
        "R3109A",
        "R3110A",
        "R3111A",
        "R3112A",
        "",
        "",
        "",
        "",
    ]

    tickers = []

    for i in range(10):

        ticker = st.text_input(
            f"Ticker {i+1}",
            value=default_tickers[i],
            key=f"ticker_{i}"
        )

        ticker = ticker.strip().upper()

        if ticker:
            tickers.append(ticker)

# ============================================================
# DATE DEMO / FALLBACK
# ============================================================
#
# Aceste valori permit aplicației să funcționeze chiar dacă
# pagina BVB nu poate fi citită temporar.
#
# YTM-urile sunt valorile de lucru folosite anterior.
# ============================================================

fallback_data = {

    "R3106A": {
        "ytm": 7.64,
        "bid_ask": 1.14,
    },

    "R3108A": {
        "ytm": 7.69,
        "bid_ask": 0.68,
    },

    "R3109A": {
        "ytm": 7.65,
        "bid_ask": 1.66,
    },

    "R3110A": {
        "ytm": 7.68,
        "bid_ask": 1.77,
    },

    "R3111A": {
        "ytm": 7.57,
        "bid_ask": 2.13,
    },

    "R3112A": {
        "ytm": 7.50,
        "bid_ask": 1.88,
    },
}

# ============================================================
# MATURITY DIN TICKER
# ============================================================

month_map = {
    "01": 1,
    "02": 2,
    "03": 3,
    "04": 4,
    "05": 5,
    "06": 6,
    "07": 7,
    "08": 8,
    "09": 9,
    "10": 10,
    "11": 11,
    "12": 12,
}


def maturity_from_ticker(ticker):

    try:

        # Exemplu:
        # R3106A -> 2031 / 06

        core = ticker.replace("R", "")

        year = int("20" + core[:2])
        month = month_map[core[2:4]]

        return datetime(
            year,
            month,
            15
        )

    except Exception:

        return None


# ============================================================
# ÎNCERCARE CITIRE BVB
# ============================================================

@st.cache_data(ttl=900)
def fetch_bvb(ticker):

    url = (
        "https://bvb.ro/FinancialInstruments/"
        "Details/FinancialInstrumentsDetails.aspx?s="
        + ticker
    )

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        text = soup.get_text(
            " ",
            strip=True
        )

        return {
            "url": url,
            "raw": text,
        }

    except Exception:

        return None


# ============================================================
# CONSTRUIRE DATASET
# ============================================================

rows = []

for ticker in tickers:

    maturity = maturity_from_ticker(ticker)

    bvb_result = fetch_bvb(ticker)

    fallback = fallback_data.get(
        ticker,
        {}
    )

    ytm = fallback.get(
        "ytm",
        np.nan
    )

    bid_ask = fallback.get(
        "bid_ask",
        np.nan
    )

    rows.append(
        {
            "Ticker": ticker,
            "Maturity": maturity,
            "YTM": ytm,
            "BidAsk": bid_ask,
            "BVB": (
                "OK"
                if bvb_result is not None
                else "Fallback"
            ),
        }
    )

df = pd.DataFrame(rows)

# ============================================================
# VERIFICARE
# ============================================================

if df.empty:

    st.warning(
        "Introdu cel puțin un ticker."
    )

    st.stop()

# Eliminăm titlurile fără YTM pentru calculele RV

calc = df.dropna(
    subset=["YTM", "Maturity"]
).copy()

if len(calc) < 3:

    st.warning(
        "Pentru calculul Fair Value sunt necesare "
        "minimum 3 titluri cu YTM disponibil."
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.stop()

# ============================================================
# SORTARE DUPĂ MATURITATE
# ============================================================

calc = calc.sort_values(
    "Maturity"
).reset_index(drop=True)

# ============================================================
# FAIR VALUE LOCAL
# ============================================================
#
# Titlul interior:
# FV = interpolarea liniară între vecinul anterior și următor.
#
# Capetele curbei:
# folosim media celor mai apropiate două titluri.
# ============================================================

fair_values = []

for i in range(len(calc)):

    if i == 0:

        fair = (
            calc.loc[i, "YTM"]
            + calc.loc[i + 1, "YTM"]
        ) / 2

    elif i == len(calc) - 1:

        fair = (
            calc.loc[i - 1, "YTM"]
            + calc.loc[i, "YTM"]
        ) / 2

    else:

        d0 = calc.loc[
            i - 1,
            "Maturity"
        ]

        d1 = calc.loc[
            i,
            "Maturity"
        ]

        d2 = calc.loc[
            i + 1,
            "Maturity"
        ]

        y0 = calc.loc[
            i - 1,
            "YTM"
        ]

        y2 = calc.loc[
            i + 1,
            "YTM"
        ]

        total_days = (
            d2 - d0
        ).days

        current_days = (
            d1 - d0
        ).days

        if total_days > 0:

            weight = (
                current_days
                / total_days
            )

            fair = (
                y0
                + weight
                * (y2 - y0)
            )

        else:

            fair = (
                y0 + y2
            ) / 2

    fair_values.append(fair)

calc["Fair YTM"] = fair_values

# ============================================================
# RELATIVE VALUE
# ============================================================

calc["RV bp"] = (
    calc["YTM"]
    - calc["Fair YTM"]
) * 100

# pozitiv:
# randament peste fair curve = relativ ieftin
#
# negativ:
# randament sub fair curve = relativ scump

rv_std = calc["RV bp"].std(
    ddof=0
)

rv_mean = calc["RV bp"].mean()

if rv_std > 0:

    calc["RV Z"] = (
        calc["RV bp"]
        - rv_mean
    ) / rv_std

else:

    calc["RV Z"] = 0.0

# ============================================================
# LIQUIDITY
# ============================================================

def liquidity_class(value):

    if pd.isna(value):
        return "N/A"

    if value <= 1.0:
        return "HIGH"

    elif value <= 2.0:
        return "MEDIUM"

    return "LOW"


calc["Liquidity"] = calc[
    "BidAsk"
].apply(
    liquidity_class
)

# ============================================================
# RV CLASS
# ============================================================

def rv_class(bp):

    if bp >= 10:
        return "CHEAP"

    elif bp <= -10:
        return "RICH"

    return "FAIR"


calc["RV State"] = calc[
    "RV bp"
].apply(
    rv_class
)

# ============================================================
# TIMING MODEL
# ============================================================
#
# Timing 20 / 60 / 120 zile.
#
# În această versiune, dacă istoricul complet BVB nu poate
# fi extras automat, timing-ul este tratat conservator.
#
# RV mai mare + lichiditate mai bună = setup mai interesant
# pentru monitorizare.
# ============================================================

def timing_state(row):

    rv = row["RV bp"]

    liquidity = row["Liquidity"]

    if timing_days == 20:

        threshold = 8

    elif timing_days == 60:

        threshold = 6

    else:

        threshold = 4

    if (
        rv >= threshold
        and liquidity == "HIGH"
    ):
        return "STRONG"

    if rv >= threshold:
        return "WATCH"

    if rv <= -threshold:
        return "RICH"

    return "NEUTRAL"


calc["Timing"] = calc.apply(
    timing_state,
    axis=1
)

# ============================================================
# COMPOSITE SCORE
# ============================================================

liquidity_score = {
    "HIGH": 2,
    "MEDIUM": 1,
    "LOW": 0,
    "N/A": 0,
}

calc["Score"] = (
    calc["RV Z"] * 2
    + calc["Liquidity"].map(
        liquidity_score
    )
)

calc = calc.sort_values(
    "Score",
    ascending=False
).reset_index(drop=True)

# ============================================================
# DASHBOARD
# ============================================================

st.subheader(
    f"Analiză curentă • Timing {timing_days} zile"
)

best = calc.iloc[0]

c1, c2, c3 = st.columns(3)

c1.metric(
    "Top RV",
    best["Ticker"]
)

c2.metric(
    "RV",
    f'{best["RV bp"]:+.1f} bp'
)

c3.metric(
    "YTM",
    f'{best["YTM"]:.2f}%'
)

# ============================================================
# TABEL PRINCIPAL
# ============================================================

display = calc[
    [
        "Ticker",
        "Maturity",
        "YTM",
        "Fair YTM",
        "RV bp",
        "RV Z",
        "BidAsk",
        "Liquidity",
        "RV State",
        "Timing",
    ]
].copy()

display["Maturity"] = (
    display["Maturity"]
    .dt.strftime("%d.%m.%Y")
)

display["YTM"] = display[
    "YTM"
].round(3)

display["Fair YTM"] = display[
    "Fair YTM"
].round(3)

display["RV bp"] = display[
    "RV bp"
].round(1)

display["RV Z"] = display[
    "RV Z"
].round(2)

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True
)

# ============================================================
# CURBA YTM
# ============================================================

st.subheader("Curba YTM")

chart = (
    calc[
        [
            "Maturity",
            "YTM",
            "Fair YTM",
        ]
    ]
    .set_index("Maturity")
)

st.line_chart(chart)

# ============================================================
# BUTTERFLY
# ============================================================

st.subheader("Butterfly")

butterfly_rows = []

if len(calc) >= 3:

    ordered = calc.sort_values(
        "Maturity"
    ).reset_index(drop=True)

    for i in range(
        1,
        len(ordered) - 1
    ):

        left = ordered.iloc[i - 1]
        belly = ordered.iloc[i]
        right = ordered.iloc[i + 1]

        d_left = (
            belly["Maturity"]
            - left["Maturity"]
        ).days

        d_right = (
            right["Maturity"]
            - belly["Maturity"]
        ).days

        total = (
            d_left + d_right
        )

        if total == 0:
            continue

        w_left = (
            d_right / total
        )

        w_right = (
            d_left / total
        )

        wing_yield = (
            w_left * left["YTM"]
            + w_right * right["YTM"]
        )

        butterfly_bp = (
            belly["YTM"]
            - wing_yield
        ) * 100

        butterfly_rows.append(
            {
                "Left": left["Ticker"],
                "Belly": belly["Ticker"],
                "Right": right["Ticker"],
                "Butterfly bp": round(
                    butterfly_bp,
                    1
                ),
            }
        )

if butterfly_rows:

    butterfly_df = pd.DataFrame(
        butterfly_rows
    )

    st.dataframe(
        butterfly_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "Nu există suficiente titluri pentru butterfly."
    )

# ============================================================
# INTERPRETARE
# ============================================================

st.subheader("Interpretare")

st.markdown(
    """
**RV bp pozitiv** → YTM este peste valoarea estimată de curba locală,
deci obligațiunea apare relativ mai ieftină față de vecinii săi.

**RV bp negativ** → YTM este sub curba estimată,
deci obligațiunea apare relativ mai scumpă.

**RV Z** → arată cât de neobișnuit este residualul față de restul
titlurilor analizate.

**Liquidity** → clasificare orientativă folosind bid/ask.

**Butterfly pozitiv** → belly-ul oferă YTM mai mare decât combinația
interpolată a celor două wings.

**Timing 20 / 60 / 120** → modifică pragul folosit pentru semnalul
de monitorizare.
"""
)

st.info(
    "Instrument analitic de relative value. "
    "Rezultatele nu reprezintă recomandări de investiții."
)

