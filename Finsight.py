
import streamlit as st

st.set_page_config(
    page_title="FinSight",
    page_icon="📊",
    layout="wide"
)

st.title("📊 FinSight")
st.subheader("Financial Insight for Smarter Businesses")

st.write(
    "Welcome to FinSight! Your SME financial health "
    "intelligence system."
)

st.divider()

st.header("Your Financial Dashboard")

col1, col2, col3 = st.columns(3)

col1.metric("Total Revenue", "₦0.00")
col2.metric("Total Expenses", "₦0.00")
col3.metric("Estimated Profit", "₦0.00")

st.info(
    "Your financial dashboard is ready. "
    "CSV transaction analysis is our next step!"
)