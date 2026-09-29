
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="E-commerce Executive Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# CUSTOM STYLING
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    .main {padding-top: 1rem;}
    [data-testid="stMetric"] {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------
@st.cache_data
def load_data(file_bytes=None):
    """
    Loads the Online Retail CSV.
    The provided dataset is encoded as Windows-1252.
    """
    if file_bytes is not None:
        from io import BytesIO
        raw = BytesIO(file_bytes)
        df = pd.read_csv(raw, encoding="cp1252")
    else:
        data_path = Path("data.csv")
        if not data_path.exists():
            raise FileNotFoundError(
                "data.csv was not found. Upload the CSV from the sidebar "
                "or place data.csv in the same folder as this app."
            )
        df = pd.read_csv(data_path, encoding="cp1252")

    # Standardize column names
    df.columns = [str(c).strip() for c in df.columns]

    required = {
        "InvoiceNo",
        "StockCode",
        "Description",
        "Quantity",
        "InvoiceDate",
        "UnitPrice",
        "CustomerID",
        "Country",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            "The CSV is missing required columns: "
            + ", ".join(sorted(missing))
        )

    # Clean types
    df["InvoiceDate"] = pd.to_datetime(
        df["InvoiceDate"], errors="coerce", dayfirst=False
    )
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
    df["CustomerID"] = pd.to_numeric(df["CustomerID"], errors="coerce")

    df = df.dropna(subset=["InvoiceDate", "Quantity", "UnitPrice"])
    df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
    df["Description"] = df["Description"].fillna("Unknown Product").astype(str).str.strip()
    df["Country"] = df["Country"].fillna("Unknown").astype(str).str.strip()

    # Revenue at transaction-line level
    df["Sales"] = df["Quantity"] * df["UnitPrice"]

    # Exclude cancelled invoices and non-positive transactions from sales KPIs.
    # In this dataset, cancelled invoices normally start with "C".
    df = df[~df["InvoiceNo"].str.upper().str.startswith("C")]
    df = df[(df["Quantity"] > 0) & (df["UnitPrice"] > 0)].copy()

    # Remove rows without a usable customer ID only from customer metrics.
    # Sales KPIs still retain those transactions.
    df["OrderDate"] = df["InvoiceDate"].dt.date

    return df


# ---------------------------------------------------------
# HEURISTIC PRODUCT CATEGORIZATION
# ---------------------------------------------------------
def assign_category(description):
    """
    Creates a transparent, rule-based category from product descriptions.
    The source dataset has no native Category column, so these are derived
    categories and should be presented to clients as such.
    """
    text = str(description).upper()

    category_keywords = {
        "Lighting & Home Decor": [
            "LAMP", "LIGHT", "CANDLE", "LANTERN", "HEART", "FRAME",
            "MIRROR", "SIGN", "DECORATION", "ORNAMENT"
        ],
        "Kitchen & Dining": [
            "CUP", "MUG", "PLATE", "BOWL", "SPOON", "FORK", "KNIFE",
            "GLASS", "KITCHEN", "TEA", "COFFEE", "BOTTLE", "JUG"
        ],
        "Fashion & Accessories": [
            "BAG", "PURSE", "NECKLACE", "BRACELET", "EARRING", "RING",
            "HAT", "SCARF", "WALLET", "UMBRELLA"
        ],
        "Stationery & Office": [
            "PEN", "PENCIL", "NOTEBOOK", "PAPER", "CARD", "BOOK",
            "DIARY", "DESK", "CALCULATOR", "STATIONERY"
        ],
        "Toys & Games": [
            "TOY", "GAME", "PUZZLE", "DOLL", "PLAYING", "CHILDREN",
            "KIDS", "BINGO"
        ],
        "Garden & Outdoor": [
            "GARDEN", "PLANT", "FLOWER", "POT", "BIRD", "PICNIC",
            "BEACH", "OUTDOOR"
        ],
        "Seasonal & Gifts": [
            "CHRISTMAS", "EASTER", "HALLOWEEN", "VALENTINE", "GIFT",
            "PARTY", "BIRTHDAY", "BABY"
        ],
    }

    for category, keywords in category_keywords.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "Other"


# ---------------------------------------------------------
# APP HEADER
# ---------------------------------------------------------
st.title("📊 E-commerce Sales & Executive Dashboard")
st.caption(
    "Interactive sales intelligence dashboard for revenue, orders, products, "
    "customers, and geographic performance."
)

# ---------------------------------------------------------
# OPTIONAL UPLOAD
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Dashboard Controls")
    uploaded_file = st.file_uploader(
        "Upload another CSV (optional)",
        type=["csv"],
        help="If no file is uploaded, the app reads data.csv from the repository.",
    )

try:
    file_bytes = uploaded_file.getvalue() if uploaded_file else None
    df = load_data(file_bytes)
except Exception as e:
    st.error(f"Could not load the dataset: {e}")
    st.stop()

# Derived category
df["Category"] = df["Description"].map(assign_category)

# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------
with st.sidebar:
    min_date = df["InvoiceDate"].min().date()
    max_date = df["InvoiceDate"].max().date()

    date_range = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    countries = sorted(df["Country"].dropna().unique().tolist())
    selected_countries = st.multiselect(
        "Region / Country",
        options=countries,
        default=countries,
        help="This dataset contains Country rather than a true Region field.",
    )

    categories = sorted(df["Category"].unique().tolist())
    selected_categories = st.multiselect(
        "Product Category",
        options=categories,
        default=categories,
    )

    trend_granularity = st.radio(
        "Revenue trend",
        ["Monthly", "Daily"],
        horizontal=True,
    )

# Apply filters
filtered = df[
    (df["InvoiceDate"].dt.date >= start_date)
    & (df["InvoiceDate"].dt.date <= end_date)
    & (df["Country"].isin(selected_countries))
    & (df["Category"].isin(selected_categories))
].copy()

# ---------------------------------------------------------
# KPI CALCULATIONS
# ---------------------------------------------------------
total_revenue = filtered["Sales"].sum()
total_orders = filtered["InvoiceNo"].nunique()
aov = total_revenue / total_orders if total_orders else 0

customer_df = filtered.dropna(subset=["CustomerID"]).copy()

if not customer_df.empty:
    orders_per_customer = (
        customer_df.groupby("CustomerID")["InvoiceNo"]
        .nunique()
        .sort_values(ascending=False)
    )
    total_customers = len(orders_per_customer)
    repeat_customers = int((orders_per_customer > 1).sum())
    one_time_customers = int((orders_per_customer == 1).sum())
    repeat_rate = (
        repeat_customers / total_customers * 100 if total_customers else 0
    )
else:
    orders_per_customer = pd.Series(dtype="int64")
    total_customers = repeat_customers = one_time_customers = 0
    repeat_rate = 0

# ---------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Total Revenue", f"£{total_revenue:,.2f}")
k2.metric("Total Orders", f"{total_orders:,}")
k3.metric("Average Order Value", f"£{aov:,.2f}")
k4.metric("Unique Customers", f"{total_customers:,}")
k5.metric("Repeat Customer Rate", f"{repeat_rate:.1f}%")

st.divider()

# ---------------------------------------------------------
# REVENUE TREND
# ---------------------------------------------------------
if filtered.empty:
    st.warning("No transactions match the selected filters.")
    st.stop()

if trend_granularity == "Monthly":
    trend = (
        filtered.assign(Period=filtered["InvoiceDate"].dt.to_period("M").dt.to_timestamp())
        .groupby("Period", as_index=False)["Sales"]
        .sum()
    )
    x_title = "Month"
else:
    trend = (
        filtered.assign(Period=filtered["InvoiceDate"].dt.floor("D"))
        .groupby("Period", as_index=False)["Sales"]
        .sum()
    )
    x_title = "Date"

fig_trend = px.line(
    trend,
    x="Period",
    y="Sales",
    markers=True,
    title=f"{trend_granularity} Revenue Trend",
    labels={"Period": x_title, "Sales": "Revenue (£)"},
    template="plotly_white",
)
fig_trend.update_layout(hovermode="x unified")
st.plotly_chart(fig_trend, use_container_width=True)

# ---------------------------------------------------------
# PRODUCT / CATEGORY ANALYSIS
# ---------------------------------------------------------
left, right = st.columns(2)

with left:
    category_sales = (
        filtered.groupby("Category", as_index=False)["Sales"]
        .sum()
        .sort_values("Sales", ascending=False)
        .head(10)
    )

    fig_category = px.bar(
        category_sales.sort_values("Sales"),
        x="Sales",
        y="Category",
        orientation="h",
        title="Top Product Categories by Revenue",
        labels={"Sales": "Revenue (£)", "Category": "Derived Category"},
        text_auto=".2s",
        template="plotly_white",
    )
    st.plotly_chart(fig_category, use_container_width=True)

with right:
    product_sales = (
        filtered.groupby("Description", as_index=False)
        .agg(
            Revenue=("Sales", "sum"),
            Units=("Quantity", "sum"),
        )
        .sort_values("Revenue", ascending=False)
        .head(10)
    )

    fig_products = px.bar(
        product_sales.sort_values("Revenue"),
        x="Revenue",
        y="Description",
        orientation="h",
        title="Top 10 Products by Revenue",
        labels={"Revenue": "Revenue (£)", "Description": "Product"},
        text_auto=".2s",
        template="plotly_white",
    )
    st.plotly_chart(fig_products, use_container_width=True)

# ---------------------------------------------------------
# CUSTOMER REPEAT ANALYSIS
# ---------------------------------------------------------
st.subheader("👥 Customer Order Distribution & Repeat Metrics")

c1, c2 = st.columns(2)

with c1:
    repeat_data = pd.DataFrame(
        {
            "Customer Type": ["One-time", "Repeat"],
            "Customers": [one_time_customers, repeat_customers],
        }
    )

    fig_repeat = px.pie(
        repeat_data,
        names="Customer Type",
        values="Customers",
        hole=0.55,
        title="One-time vs Repeat Customers",
        template="plotly_white",
    )
    st.plotly_chart(fig_repeat, use_container_width=True)

with c2:
    if not orders_per_customer.empty:
        distribution = (
            orders_per_customer
            .value_counts()
            .sort_index()
            .reset_index()
        )
        distribution.columns = ["Orders per Customer", "Customers"]

        # Keep the chart readable by grouping customers with 10+ orders.
        distribution["Order Bucket"] = distribution["Orders per Customer"].apply(
            lambda x: "10+" if x >= 10 else str(int(x))
        )

        bucketed = (
            distribution.groupby("Order Bucket", as_index=False)["Customers"]
            .sum()
        )

        bucket_order = [str(i) for i in range(1, 10)] + ["10+"]
        bucketed["sort"] = bucketed["Order Bucket"].map(
            {v: i for i, v in enumerate(bucket_order)}
        )
        bucketed = bucketed.sort_values("sort")

        fig_distribution = px.bar(
            bucketed,
            x="Order Bucket",
            y="Customers",
            title="Customer Order Frequency",
            labels={
                "Order Bucket": "Number of Orders",
                "Customers": "Customers",
            },
            text_auto=True,
            template="plotly_white",
        )
        st.plotly_chart(fig_distribution, use_container_width=True)
    else:
        st.info("Customer ID data is unavailable for the selected filters.")

# ---------------------------------------------------------
# GEOGRAPHIC PERFORMANCE
# ---------------------------------------------------------
st.subheader("🌍 Geographic Revenue Performance")

country_sales = (
    filtered.groupby("Country", as_index=False)
    .agg(
        Revenue=("Sales", "sum"),
        Orders=("InvoiceNo", "nunique"),
    )
    .sort_values("Revenue", ascending=False)
    .head(15)
)

fig_country = px.bar(
    country_sales.sort_values("Revenue"),
    x="Revenue",
    y="Country",
    orientation="h",
    title="Top Countries by Revenue",
    labels={"Revenue": "Revenue (£)", "Country": "Country"},
    text_auto=".2s",
    template="plotly_white",
)
st.plotly_chart(fig_country, use_container_width=True)

# ---------------------------------------------------------
# EXECUTIVE SUMMARY
# ---------------------------------------------------------
st.subheader("💡 Executive Summary")

top_category = (
    category_sales.iloc[0]["Category"] if not category_sales.empty else "N/A"
)
top_product = (
    product_sales.iloc[0]["Description"] if not product_sales.empty else "N/A"
)
top_country = (
    country_sales.iloc[0]["Country"] if not country_sales.empty else "N/A"
)

s1, s2, s3 = st.columns(3)
s1.info(f"**Top Category by Revenue**\n\n{top_category}")
s2.info(f"**Top Product by Revenue**\n\n{top_product}")
s3.info(f"**Top Country by Revenue**\n\n{top_country}")

st.caption(
    "Data note: the source CSV has no native Region or Product Category columns. "
    "Country is therefore used as the geographic filter, while Product Category "
    "is derived from product-description keywords. Treat derived categories as "
    "analytical groupings, not source-system master data."
)
