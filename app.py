import os
from datetime import date

import altair as alt
import pandas as pd
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Basket Craft Dashboard", layout="wide")
st.title("Basket Craft Dashboard")


@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )


HEADLINE_SQL = """
WITH latest AS (
  SELECT DATE_TRUNC('month', MAX(date_key)) AS current_month
  FROM basket_craft.analytics.fct_order_items
)
SELECT
  DATE_TRUNC('month', f.date_key)        AS month,
  SUM(f.net_revenue_usd)                 AS total_revenue,
  COUNT(DISTINCT f.order_id)             AS total_orders,
  COUNT(*)                               AS total_items
FROM basket_craft.analytics.fct_order_items f
CROSS JOIN latest l
WHERE DATE_TRUNC('month', f.date_key) BETWEEN DATEADD(month, -1, l.current_month) AND l.current_month
GROUP BY 1
ORDER BY 1
"""


@st.cache_data(ttl=600)
def headline_metrics() -> pd.DataFrame:
    with get_connection().cursor() as cur:
        cur.execute(HEADLINE_SQL)
        cols = [c[0].lower() for c in cur.description]
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    df["total_revenue"] = df["total_revenue"].astype(float)
    df["aov"] = df["total_revenue"] / df["total_orders"]
    return df


DAILY_REVENUE_SQL = """
SELECT
  date_key,
  SUM(net_revenue_usd) AS revenue
FROM basket_craft.analytics.fct_order_items
GROUP BY 1
ORDER BY 1
"""


@st.cache_data(ttl=600)
def daily_revenue() -> pd.DataFrame:
    with get_connection().cursor() as cur:
        cur.execute(DAILY_REVENUE_SQL)
        cols = [c[0].lower() for c in cur.description]
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    df["date_key"] = pd.to_datetime(df["date_key"])
    df["revenue"] = df["revenue"].astype(float)
    return df


PRODUCT_REVENUE_SQL = """
SELECT
  f.date_key,
  p.product_name,
  SUM(f.net_revenue_usd) AS revenue
FROM basket_craft.analytics.fct_order_items f
JOIN basket_craft.analytics.dim_product p ON p.product_id = f.product_id
GROUP BY 1, 2
"""


@st.cache_data(ttl=600)
def daily_revenue_by_product() -> pd.DataFrame:
    with get_connection().cursor() as cur:
        cur.execute(PRODUCT_REVENUE_SQL)
        cols = [c[0].lower() for c in cur.description]
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    df["date_key"] = pd.to_datetime(df["date_key"])
    df["revenue"] = df["revenue"].astype(float)
    return df


ORDER_ITEMS_SQL = """
SELECT
  f.order_id,
  p.product_name,
  f.date_key
FROM basket_craft.analytics.fct_order_items f
JOIN basket_craft.analytics.dim_product p ON p.product_id = f.product_id
"""


@st.cache_data(ttl=600)
def order_items() -> pd.DataFrame:
    with get_connection().cursor() as cur:
        cur.execute(ORDER_ITEMS_SQL)
        cols = [c[0].lower() for c in cur.description]
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    df["date_key"] = pd.to_datetime(df["date_key"])
    return df


def fmt_delta(curr: float, prior: float | None, kind: str) -> str | None:
    if prior is None or prior == 0:
        return None
    diff = curr - prior
    pct = diff / prior * 100
    sign = "+" if diff >= 0 else "-"
    mag = abs(diff)
    if kind == "money":
        body = f"${mag:,.0f}"
    elif kind == "money2":
        body = f"${mag:,.2f}"
    else:
        body = f"{mag:,.0f}"
    return f"{sign}{body} ({pct:+.1f}%)"


df = headline_metrics()

if df.empty:
    st.warning("No rows in fct_order_items.")
    st.stop()

current = df.iloc[-1]
prior = df.iloc[-2] if len(df) >= 2 else None
current_month: date = current["month"]
prior_month = prior["month"] if prior is not None else None

caption = current_month.strftime("%B %Y")
if prior_month is not None:
    caption += f" vs {prior_month.strftime('%B %Y')}"
else:
    caption += " (no prior month data)"
st.caption(caption)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total revenue",
    f"${current['total_revenue']:,.0f}",
    fmt_delta(current["total_revenue"], prior["total_revenue"] if prior is not None else None, "money"),
)
c2.metric(
    "Total orders",
    f"{int(current['total_orders']):,}",
    fmt_delta(current["total_orders"], prior["total_orders"] if prior is not None else None, "count"),
)
c3.metric(
    "Avg order value",
    f"${current['aov']:,.2f}",
    fmt_delta(current["aov"], prior["aov"] if prior is not None else None, "money2"),
)
c4.metric(
    "Total items sold",
    f"{int(current['total_items']):,}",
    fmt_delta(current["total_items"], prior["total_items"] if prior is not None else None, "count"),
)

st.divider()
st.subheader("Revenue trend")

trend = daily_revenue()
min_date = trend["date_key"].min().date()
max_date = trend["date_key"].max().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
)
st.sidebar.caption(f"Data available {min_date:%Y-%m-%d} → {max_date:%Y-%m-%d}")

if not (isinstance(date_range, tuple) and len(date_range) == 2):
    st.info("Pick a start and end date.")
    st.stop()

start, end = date_range
mask = (trend["date_key"].dt.date >= start) & (trend["date_key"].dt.date <= end)
filtered = (
    trend.loc[mask]
    .rename(columns={"revenue": "Revenue (USD)"})
    .set_index("date_key")
)

if filtered.empty:
    st.info("No revenue in the selected range.")
else:
    st.line_chart(filtered["Revenue (USD)"])
    st.caption(
        f"{len(filtered):,} days · "
        f"total ${filtered['Revenue (USD)'].sum():,.0f} · "
        f"daily avg ${filtered['Revenue (USD)'].mean():,.0f}"
    )

st.divider()
st.subheader("Top products by revenue")

product_daily = daily_revenue_by_product()
prod_mask = (product_daily["date_key"].dt.date >= start) & (product_daily["date_key"].dt.date <= end)
top_products = (
    product_daily.loc[prod_mask]
    .groupby("product_name", as_index=False)["revenue"]
    .sum()
    .sort_values("revenue", ascending=False)
    .head(10)
)

if top_products.empty:
    st.info("No product revenue in the selected range.")
else:
    chart = (
        alt.Chart(top_products)
        .mark_bar()
        .encode(
            x=alt.X("revenue:Q", title="Revenue (USD)"),
            y=alt.Y("product_name:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("product_name:N", title="Product"),
                alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
            ],
        )
    )
    st.altair_chart(chart, width="stretch")

st.divider()
st.subheader("Bundle finder")

items = order_items()
all_products = sorted(items["product_name"].unique().tolist())
anchor = st.selectbox("Find products bought with…", all_products)

window = items[(items["date_key"].dt.date >= start) & (items["date_key"].dt.date <= end)]
anchor_orders = window.loc[window["product_name"] == anchor, "order_id"].unique()

if len(anchor_orders) == 0:
    st.info(f"No orders containing **{anchor}** in the selected date range.")
else:
    bundles = (
        window[(window["order_id"].isin(anchor_orders)) & (window["product_name"] != anchor)]
        .groupby("product_name", as_index=False)["order_id"]
        .nunique()
        .rename(columns={"order_id": "co_orders"})
        .sort_values("co_orders", ascending=False)
        .head(10)
    )

    if bundles.empty:
        st.info(f"**{anchor}** is never bought with another product in the selected range.")
    else:
        bundle_chart = (
            alt.Chart(bundles)
            .mark_bar()
            .encode(
                x=alt.X("co_orders:Q", title="Orders containing both"),
                y=alt.Y("product_name:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("product_name:N", title="Bought with"),
                    alt.Tooltip("co_orders:Q", title="Co-orders", format=","),
                ],
            )
        )
        st.altair_chart(bundle_chart, width="stretch")
        st.caption(
            f"{len(anchor_orders):,} orders contained **{anchor}** in the selected range."
        )
