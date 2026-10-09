
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="FinSight | SME Intelligence",
    page_icon="📊",
    layout="wide",
)

DATA_FILE = Path(__file__).parent / "finsight_cleaned.csv"

MONEY_COLUMNS = [
    "amount",
    "cash_inflow_ngn",
    "cash_outflow_ngn",
    "net_cash_movement_ngn",
    "transfer_in_ngn",
    "transfer_out_ngn",
]


# --------------------------------------------------
# LOAD AND PREPARE DATA
# --------------------------------------------------
@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path)

    for col in MONEY_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(
            df["datetime"], errors="coerce"
        )

    if "is_synthetic_anomaly" in df.columns:
        df["is_synthetic_anomaly"] = (
            df["is_synthetic_anomaly"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["1", "true", "yes"])
        )

    if "review_required" in df.columns:
        df["review_required"] = (
            df["review_required"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["1", "true", "yes"])
        )

    return df


if not DATA_FILE.exists():
    st.error(f"Data file not found: {DATA_FILE}")
    st.info(
        "Place finsight_cleaned.csv in the same folder as app.py."
    )
    st.stop()

df = load_data(str(DATA_FILE))

required_columns = {
    "date",
    "industry",
    "type",
    "amount",
    "cash_inflow_ngn",
    "cash_outflow_ngn",
    "net_cash_movement_ngn",
}

missing = required_columns - set(df.columns)

if missing:
    st.error(f"Missing required columns: {', '.join(sorted(missing))}")
    st.stop()

# Only completed transactions are used in cash calculations.
# Exclude records explicitly marked as duplicates.
status = df.get(
    "cash_movement_status",
    pd.Series("", index=df.index),
).astype(str).str.strip().str.lower()

duplicate_ids = df.get(
    "duplicate_of_transaction_id",
    pd.Series(index=df.index, dtype="object"),
)

completed = status.isin(["completed", "complete", "successful", "success"])
not_duplicate = duplicate_ids.isna() | duplicate_ids.astype(str).str.strip().eq("")

df["cash_eligible"] = completed & not_duplicate

st.title("📊 FinSight")
st.caption("Financial intelligence for smarter businesses")
st.write(
    "Explore cash movement, spending, revenue patterns, "
    "transaction reviews, and preliminary forecasts."
)

st.info(
    "Dataset note: this is demo data. Confirm transaction and invoice "
    "records before using results for financial decisions. Cash inflow "
    "is not necessarily accounting revenue, and net cash movement is "
    "not the same as profit."
)


# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------
st.sidebar.header("Dashboard filters")

industries = ["All industries"] + sorted(
    df["industry"].dropna().astype(str).unique().tolist()
)

selected_industry = st.sidebar.selectbox(
    "Industry",
    industries,
)

valid_dates = df["date"].dropna()

if valid_dates.empty:
    st.error("No valid dates were found in the dataset.")
    st.stop()

start_date, end_date = st.sidebar.date_input(
    "Transaction date range",
    value=(valid_dates.min().date(), valid_dates.max().date()),
    min_value=valid_dates.min().date(),
    max_value=valid_dates.max().date(),
)

if start_date > end_date:
    st.error("The start date must be on or before the end date.")
    st.stop()

filtered = df[
    df["date"].dt.date.between(start_date, end_date)
].copy()

if selected_industry != "All industries":
    filtered = filtered[
        filtered["industry"] == selected_industry
    ].copy()

# Eligible records for actual cash calculations.
cash_df = filtered[filtered["cash_eligible"]].copy()

if cash_df.empty:
    st.warning(
        "No completed, non-duplicate transactions match these filters. "
        "Try a different industry or date range."
    )


# --------------------------------------------------
# FINANCIAL SUMMARY
# --------------------------------------------------
st.header("1. Financial overview")

inflows = cash_df["cash_inflow_ngn"].sum()
outflows = cash_df["cash_outflow_ngn"].sum()
net_cash = cash_df["net_cash_movement_ngn"].sum()

income_rows = cash_df[
    cash_df["type"].astype(str).str.strip().str.lower().isin(
        ["income", "sale", "sales", "revenue"]
    )
]

sales_revenue = income_rows["amount"].sum()

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Cash received",
    f"₦{inflows:,.2f}",
)
col2.metric(
    "Cash spent",
    f"₦{outflows:,.2f}",
)
col3.metric(
    "Net cash movement",
    f"₦{net_cash:,.2f}",
)
col4.metric(
    "Income transaction amount",
    f"₦{sales_revenue:,.2f}",
)

st.caption(
    f"Eligible completed transactions: {len(cash_df):,}. "
    "Income transaction amount is based on the transaction type; "
    "verify categories before treating it as sales revenue."
)


# --------------------------------------------------
# SPENDING ANALYSIS
# --------------------------------------------------
st.header("2. What did the business spend money on?")

expense_df = cash_df[
    cash_df["cash_outflow_ngn"] > 0
].copy()

if not expense_df.empty:
    if "category" in expense_df.columns:
        expense_summary = (
            expense_df.groupby("category", dropna=False)
            ["cash_outflow_ngn"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )

        expense_summary["category"] = (
            expense_summary["category"]
            .fillna("Uncategorized")
        )

        fig = px.bar(
            expense_summary,
            x="category",
            y="cash_outflow_ngn",
            title="Cash outflow by expense category",
            labels={
                "category": "Category",
                "cash_outflow_ngn": "Cash outflow (₦)",
            },
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(expense_summary, use_container_width=True)
    else:
        st.warning("No expense category column is available.")

    st.subheader("Transactions with the largest outflows")

    expense_details = [
        c for c in [
            "date", "business_name", "description",
            "category", "counterparty", "cash_outflow_ngn",
        ]
        if c in expense_df.columns
    ]

    st.dataframe(
        expense_df.sort_values(
            "cash_outflow_ngn", ascending=False
        )[expense_details].head(20),
        use_container_width=True,
    )
else:
    st.write("No completed cash outflows match these filters.")


# --------------------------------------------------
# MONTHLY CASH FLOW AND EXPENSE TRENDS
# --------------------------------------------------
st.header("3. Cash flow and expense trends")

if not cash_df.empty:
    monthly = cash_df.copy()
    monthly["month"] = monthly["date"].dt.to_period("M").astype(str)

    monthly_summary = (
        monthly.groupby("month")
        .agg(
            Cash_in=("cash_inflow_ngn", "sum"),
            Cash_out=("cash_outflow_ngn", "sum"),
            Net_cash=("net_cash_movement_ngn", "sum"),
        )
        .reset_index()
    )

    fig = px.line(
        monthly_summary,
        x="month",
        y=["Cash_in", "Cash_out", "Net_cash"],
        markers=True,
        title="Monthly cash movement",
        labels={
            "month": "Month",
            "value": "Amount (₦)",
            "variable": "Measure",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Which expenses are increasing?")

    if not expense_df.empty and "category" in expense_df.columns:
        monthly_expenses = expense_df.copy()
        monthly_expenses["month"] = (
            monthly_expenses["date"].dt.to_period("M").astype(str)
        )

        expense_trends = (
            monthly_expenses.groupby(["month", "category"])
            ["cash_outflow_ngn"]
            .sum()
            .reset_index()
        )

        if expense_trends["month"].nunique() >= 2:
            fig = px.line(
                expense_trends,
                x="month",
                y="cash_outflow_ngn",
                color="category",
                markers=True,
                title="Monthly expenses by category",
                labels={
                    "month": "Month",
                    "cash_outflow_ngn": "Cash outflow (₦)",
                    "category": "Category",
                },
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(
                "At least two months are needed to compare expense trends."
            )
else:
    st.info("No eligible transactions are available for trend analysis.")


# --------------------------------------------------
# REVENUE GENERATORS
# --------------------------------------------------
st.header("4. Who generates the most income?")

if not income_rows.empty and "counterparty" in income_rows.columns:
    revenue_by_counterparty = (
        income_rows.assign(
            counterparty=income_rows["counterparty"].fillna(
                "Unknown counterparty"
            )
        )
        .groupby("counterparty")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )

    fig = px.bar(
        revenue_by_counterparty,
        x="amount",
        y="counterparty",
        orientation="h",
        title="Top counterparties by income transaction amount",
        labels={
            "amount": "Income transaction amount (₦)",
            "counterparty": "Counterparty",
        },
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Counterparties are not necessarily verified customers, and "
        "these amounts are not product-level revenue."
    )
else:
    st.info(
        "Income transactions or counterparty information are unavailable."
    )

st.warning(
    "Product-level rankings require a product or service identifier. "
    "The current dataset does not show a dedicated product column."
)


# --------------------------------------------------
# OUTSTANDING DEBTS / INVOICES
# --------------------------------------------------
st.header("5. Outstanding customer payments")

st.write(
    "The current dataset has invoice references, but those references "
    "do not prove that money is still owed."
)

st.info(
    "To calculate receivables reliably, FinSight needs invoice amount, "
    "amount paid, outstanding balance, customer identity, due date, "
    "and payment status. Do not treat every invoice reference as unpaid."
)

if "invoice_id" in filtered.columns:
    linked_invoices = filtered["invoice_id"].notna().sum()
    st.metric("Records with invoice references", f"{linked_invoices:,}")


# --------------------------------------------------
# ANOMALIES AND REVIEW FLAGS
# --------------------------------------------------
st.header("6. Unusual transactions and review flags")

anomaly_mask = filtered.get(
    "is_synthetic_anomaly",
    pd.Series(False, index=filtered.index),
).fillna(False).astype(bool)

review_mask = filtered.get(
    "review_required",
    pd.Series(False, index=filtered.index),
).fillna(False).astype(bool)

flagged = filtered[anomaly_mask | review_mask].copy()

a, b, c = st.columns(3)
a.metric("Synthetic anomaly flags", f"{int(anomaly_mask.sum()):,}")
b.metric("Review-required records", f"{int(review_mask.sum()):,}")
c.metric("Records needing attention", f"{len(flagged):,}")

if not flagged.empty:
    detail_cols = [
        c for c in [
            "transaction_id", "date", "business_name", "amount",
            "type", "description", "counterparty", "anomaly_type",
            "review_reason", "cash_movement_status_note",
        ]
        if c in flagged.columns
    ]

    st.dataframe(
        flagged[detail_cols],
        use_container_width=True,
    )

st.caption(
    "Anomaly flags are leads for investigation, not proof of fraud. "
    "Synthetic demo anomalies must not be presented as real fraud cases."
)


# --------------------------------------------------
# PRELIMINARY CASH-FLOW FORECAST
# --------------------------------------------------
st.header("7. Preliminary cash-flow forecast")

st.write(
    "This simple baseline projects future net cash movement using the "
    "average of the most recent monthly results. It is not a forecast "
    "of the bank account balance."
)

if not cash_df.empty:
    forecast_data = cash_df.copy()
    forecast_data["month"] = (
        forecast_data["date"].dt.to_period("M")
    )

    monthly_net = (
        forecast_data.groupby("month")["net_cash_movement_ngn"]
        .sum()
        .sort_index()
    )

    if len(monthly_net) >= 2:
        recent = monthly_net.tail(3)
        projected_monthly_net = recent.mean()

        st.metric(
            "Baseline projected monthly net movement",
            f"₦{projected_monthly_net:,.2f}",
        )

        st.caption(
            "Assumes recent monthly net movement continues. "
            "This does not account for seasonality, future obligations, "
            "or expected customer payments."
        )

        forecast_table = pd.DataFrame({
            "Month": recent.index.astype(str),
            "Historical net movement (₦)": recent.values,
        })

        st.dataframe(forecast_table, use_container_width=True)
    else:
        st.info(
            "At least two distinct months of completed transaction data "
            "are needed for this baseline."
        )
else:
    st.info("No completed transactions are available for forecasting.")


# --------------------------------------------------
# ASK FINSIGHT: RULE-BASED QUESTION ANSWERING
# --------------------------------------------------
st.header("8. Ask FinSight")
st.write(
    "Ask a question about the selected industry and date range. "
    "This first version uses transparent calculations and keywords; "
    "it is not yet connected to a generative AI model."
)

question = st.text_input(
    "Your financial question",
    placeholder="Example: How much did we spend?",
)

if st.button("Ask FinSight", type="primary"):
    q = question.lower().strip()

    if not q:
        st.warning("Please enter a question.")
    elif any(word in q for word in ["owe", "owed", "unpaid", "overdue", "debt"]):
        st.info(
            "I cannot reliably identify who owes money from this dataset "
            "alone. Invoice amounts, payments, balances, and due dates "
            "are needed."
        )
    elif any(word in q for word in ["product", "products"]):
        st.info(
            "There is no dedicated product identifier in the current "
            "columns, so I cannot reliably rank products by revenue."
        )
    elif any(word in q for word in ["forecast", "future", "predict", "cash position"]):
        if not cash_df.empty:
            monthly_values = (
                cash_df.assign(
                    month=cash_df["date"].dt.to_period("M")
                )
                .groupby("month")["net_cash_movement_ngn"]
                .sum()
            )
            if len(monthly_values) >= 2:
                result = monthly_values.tail(3).mean()
                st.write(
                    "The baseline estimate for monthly net cash movement "
                    f"is **₦{result:,.2f}**, based on recent months. "
                    "This is not a projected account balance."
                )
            else:
                st.info("More monthly history is needed.")
        else:
            st.info("No completed transactions match your filters.")
    elif any(word in q for word in ["unusual", "anomal", "suspicious", "fraud", "review"]):
        st.write(
            f"**{len(flagged):,}** records are flagged for review or "
            "as synthetic anomalies within the selected filters."
        )
        if not flagged.empty:
            st.dataframe(flagged.head(20), use_container_width=True)
    elif any(word in q for word in ["increase", "increasing", "trend", "rising"]):
        if not expense_df.empty:
            st.write(
                "Review the monthly expense charts above to identify "
                "categories whose spending rises across months."
            )
        else:
            st.info("No eligible expenses match these filters.")
    elif any(word in q for word in ["category", "categories", "spent on", "spending on"]):
        if not expense_df.empty and "category" in expense_df.columns:
            answer = (
                expense_df.groupby("category")["cash_outflow_ngn"]
                .sum()
                .sort_values(ascending=False)
            )
            st.dataframe(
                answer.rename("Cash outflow (₦)").reset_index(),
                use_container_width=True,
            )
        else:
            st.info("No expense categories are available for these filters.")
    elif any(word in q for word in ["customer", "customers", "counterparty", "revenue generator", "who generates"]):
        if not revenue_by_counterparty.empty:
            st.dataframe(revenue_by_counterparty, use_container_width=True)
        else:
            st.info("No income counterparty results are available.")
    elif any(word in q for word in ["net cash", "cash flow", "cashflow", "inflow", "outflow"]):
        st.write(f"Cash received: **₦{inflows:,.2f}**")
        st.write(f"Cash spent: **₦{outflows:,.2f}**")
        st.write(f"Net cash movement: **₦{net_cash:,.2f}**")
    elif any(word in q for word in ["make", "made", "income", "revenue", "sales", "earn", "earned"]):
        st.write(
            f"Income transaction amount: **₦{sales_revenue:,.2f}**"
        )
        st.write(
            f"Total cash received: **₦{inflows:,.2f}**"
        )
        st.caption(
            "These measures can differ. Confirm transaction categories "
            "before treating income transaction amount as sales revenue."
        )
    elif any(word in q for word in ["spend", "spent", "expense", "expenses", "cost"]):
        st.write(f"Total completed cash outflow: **₦{outflows:,.2f}**")
    else:
        st.info(
            "I couldn't match that question to a supported calculation. "
            "Try asking about cash received, spending, expense categories, "
            "net cash flow, top counterparties, unusual transactions, "
            "increasing expenses, unpaid invoices, or forecasting."
        )


# --------------------------------------------------
# TRANSACTION EXPLORER
# --------------------------------------------------
st.header("9. Explore transactions")

show_data = st.checkbox("Show filtered transaction records")

if show_data:
    st.dataframe(filtered, use_container_width=True)

    csv_data = filtered.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download filtered transactions",
        data=csv_data,
        file_name="finsight_filtered_transactions.csv",
        mime="text/csv",
    )

st.caption(
    "FinSight demo | Verify source records before relying on "
    "financial decisions or forecasts."
)