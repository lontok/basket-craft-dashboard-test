# Basket Craft Dashboard

**Live app:** https://basket-craft-dashboard-test.streamlit.app/

A Streamlit dashboard for the `basket_craft` Snowflake warehouse. It reads from the `analytics` schema (`fct_order_items`, `dim_product`, `dim_date`).

## What's on it

- Headline metrics: total revenue, orders, average order value, and items sold for the latest month with data, each with a delta vs the prior month
- Revenue trend: a daily net revenue line chart, filtered by the sidebar date range
- Top products by revenue: a horizontal bar chart, also filtered by the date range
- Bundle finder: pick a product and see what gets bought with it most often, ranked by the number of orders containing both

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` with your Snowflake credentials:

```
SNOWFLAKE_ACCOUNT=...
SNOWFLAKE_USER=...
SNOWFLAKE_PASSWORD=...
SNOWFLAKE_ROLE=...
SNOWFLAKE_WAREHOUSE=...
SNOWFLAKE_DATABASE=...
SNOWFLAKE_SCHEMA=...
```

Then:

```bash
streamlit run app.py
```

The dashboard opens at http://localhost:8501.

## Deployment

Hosted on Streamlit Community Cloud. Secrets go in the app's **Secrets** TOML box using the same keys as `.env`. Since `app.py` reads from `os.environ`, this shim at startup bridges Cloud secrets into the existing code path:

```python
for k, v in st.secrets.items():
    os.environ.setdefault(k, str(v))
```
