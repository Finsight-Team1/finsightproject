import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# ==========================================
# FINSIGHT CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="FinSight",
    page_icon="📊",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
MASTER_FILE = BASE_DIR / "finsight_cleaned.csv"

st.title("📊 FinSight")
st.subheader("Financial Insight for Smarter Businesses")

st.write(
    "Welcome to FinSight! Your SME financial health "
    "intelligence system."
)

st.divider()


# ==========================================
# LOAD CLEANED TRANSACTION DATA
# ==========================================

@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path)

    # Standardize column names
    df.columns = (
        df.columns.str.strip().str.lower()
        .str.replace(" ", "_")
    )

    # Convert available financial columns to numbers
    numeric_columns = [
        "amount",
        "cash_inflow_ngn",
        "cash_outflow_ngn",
        "net_cash_movement_ngn",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column], errors="coerce"
            )

    return df


if not MASTER_FILE.exists():
    st.error(
        "The cleaned dataset was not found. "
        "Run clean_data.py first to create "
        "finsight_cleaned.csv."
    )
    st.stop()

try:
    master_df = load_data(str(MASTER_FILE))
except Exception as error:
    st.error(f"Could not load the dataset: {error}")
    st.stop()

if "industry" not in master_df.columns:
    st.error(
        "The dataset does not contain an industry column."
    )
    st.stop()


# ==========================================
# INDUSTRY FILTER
# ==========================================

st.sidebar.header("Dashboard Filters")

industry_options = ["All Industries"] + sorted(
    master_df["industry"].dropna().unique().tolist()
)

selected_industry = st.sidebar.selectbox(
    "Choose an industry",
    industry_options,
)

if selected_industry == "All Industries":
    df = master_df.copy()
else:
    df = master_df[
        master_df["industry"] == selected_industry
    ].copy()


# ==========================================
# FINANCIAL DASHBOARD
# ==========================================

st.header("Your Financial Dashboard")

col1, col2, col3 = st.columns(3)

# Use cash inflow/outflow when available.
# Fall back to transaction amounts and types.
if "cash_inflow_ngn" in df.columns:
    revenue = df["cash_inflow_ngn"].sum()
elif {"amount", "type"}.issubset(df.columns):
    incoming = df["type"].astype("string").str.lower().isin(
        ["income", "inflow", "credit", "cash_in"]
    )
    revenue = df.loc[incoming, "amount"].sum()
else:
    revenue = 0.0

if "cash_outflow_ngn" in df.columns:
    expenses = df["cash_outflow_ngn"].sum()
elif {"amount", "type"}.issubset(df.columns):
    outgoing = df["type"].astype("string").str.lower().isin(
        ["expense", "outflow", "debit", "cash_out"]
    )
    expenses = df.loc[outgoing, "amount"].sum()
else:
    expenses = 0.0

profit = revenue - expenses

col1.metric("Total Cash Inflow", f"₦{revenue:,.2f}")
col2.metric("Total Cash Outflow", f"₦{expenses:,.2f}")
col3.metric("Net Cash Movement", f"₦{profit:,.2f}")

st.caption(
    "These are cash movement indicators, not necessarily "
    "accounting revenue, expenses, or net profit."
)

st.metric("Total Transactions", f"{len(df):,}")


# ==========================================
# INDUSTRY COMPARISON
# ==========================================

if selected_industry == "All Industries":
    st.divider()
    st.header("Industry Comparison")

    metrics = [
        column for column in [
            "cash_inflow_ngn",
            "cash_outflow_ngn",
            "net_cash_movement_ngn",
        ]
        if column in master_df.columns
    ]

    if metrics:
        comparison_metric = st.selectbox(
            "Choose a financial measure",
            metrics,
            format_func=lambda value: value.replace(
                "_", " "
            ).title(),
        )

        comparison = (
            master_df.groupby("industry", dropna=False)[
                comparison_metric
            ]
            .sum()
            .reset_index()
        )

        fig = px.bar(
            comparison,
            x="industry",
            y=comparison_metric,
            title=comparison_metric.replace(
                "_", " "
            ).title(),
            labels={
                "industry": "Industry",
                comparison_metric: "Amount (NGN)",
            },
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )
    else:
        st.info(
            "No cash movement columns were found "
            "for the comparison chart."
        )


# ==========================================
# TRANSACTION RECORDS
# ==========================================

st.divider()
st.header("Transaction Records")

st.write(
    f"Showing {len(df):,} records for "
    f"{selected_industry}."
)

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    label="Download filtered transactions",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="finsight_transactions.csv",
    mime="text/csv",
)


# ==========================================
# ASK FINSIGHT - NEXT INTEGRATION
# ==========================================

st.divider()
st.header("💬 Ask FinSight")

st.write(
    "Soon, you will be able to ask questions about "
    "your business transactions in plain English."
)

st.info(
    "Example: Which industry has the highest cash inflow? "
    "The next step is connecting an AI model to answer "
    "questions using verified calculations from your data."
)