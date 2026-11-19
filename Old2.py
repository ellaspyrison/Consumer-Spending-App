import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# Configuration for a better-looking layout
st.set_page_config(page_title="Advanced Consumer Spending Explorer", page_icon="🛍️", layout="wide", initial_sidebar_state="expanded")

# Connect to database and load all data into a master dataframe
@st.cache_data
def load_data():
    conn = sqlite3.connect('/workspaces/Consumer-Spending-App/expanded_consumer_data (1).db', check_same_thread=False)
    query = """
        SELECT 
            d.household_id, d.income_before_taxes, d.age, d.family_size, 
            d.num_earners, d.num_vehicles, d.region, d.sex, d.marital_status, 
            d.race, d.housing_tenure, d.education_level,
            s.annual_amount,
            c.category_name, c.expense_type
        FROM demographics d
        JOIN spending s ON d.household_id = s.household_id
        JOIN categories c ON s.category_id = c.category_id
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

df = load_data()

# --- HEADER ---
st.title("🛍️ Advanced Consumer Market Spending Analysis")
st.markdown("Explore how household demographics—from education to housing tenure—impact spending priorities.")

# --- SIDEBAR FILTERS ---
st.sidebar.header("🎯 Filter Demographics")

# Dynamic dropdown filter function
def add_filter(column_name, label):
    options = ["All"] + sorted(df[column_name].dropna().unique().tolist())
    choice = st.sidebar.selectbox(label, options)
    return choice

sel_region = add_filter('region', 'Region')
sel_education = add_filter('education_level', 'Education Level')
sel_marital = add_filter('marital_status', 'Marital Status')
sel_housing = add_filter('housing_tenure', 'Housing Tenure')
sel_sex = add_filter('sex', 'Reference Person Sex')

# Sliders for continuous variables
min_inc, max_inc = int(df['income_before_taxes'].min()), int(df['income_before_taxes'].max())
sel_income = st.sidebar.slider("Income Before Taxes ($)", min_value=min_inc, max_value=max_inc, value=(min_inc, max_inc))

min_age, max_age = int(df['age'].min()), int(df['age'].max())
sel_age = st.sidebar.slider("Age of Reference Person", min_value=min_age, max_value=max_age, value=(min_age, max_age))

# --- APPLY FILTERS ---
filtered_df = df.copy()
if sel_region != "All": filtered_df = filtered_df[filtered_df['region'] == sel_region]
if sel_education != "All": filtered_df = filtered_df[filtered_df['education_level'] == sel_education]
if sel_marital != "All": filtered_df = filtered_df[filtered_df['marital_status'] == sel_marital]
if sel_housing != "All": filtered_df = filtered_df[filtered_df['housing_tenure'] == sel_housing]
if sel_sex != "All": filtered_df = filtered_df[filtered_df['sex'] == sel_sex]

filtered_df = filtered_df[
    (filtered_df['income_before_taxes'] >= sel_income[0]) & 
    (filtered_df['income_before_taxes'] <= sel_income[1]) &
    (filtered_df['age'] >= sel_age[0]) &
    (filtered_df['age'] <= sel_age[1])
]

if filtered_df.empty:
    st.warning("No households match this specific combination of filters. Try broadening your selection.")
    st.stop()

# --- DASHBOARD METRICS ---
unique_households = filtered_df['household_id'].nunique()
avg_income = filtered_df.drop_duplicates(subset=['household_id'])['income_before_taxes'].mean()
avg_total_spending = filtered_df.groupby('household_id')['annual_amount'].sum().mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Households in Segment", f"{unique_households:,}")
col2.metric("Avg. Household Income", f"${avg_income:,.0f}")
col3.metric("Avg. Tracked Spending", f"${avg_total_spending:,.0f}")
col4.metric("Savings/Unallocated Margin", f"${(avg_income - avg_total_spending):,.0f}")

st.markdown("---")

# --- UI TABS ---
tab1, tab2, tab3 = st.tabs(["📈 Core Visualizations", "🍩 Demographic Deep Dives", "📋 Prettier Data Tables"])

with tab1:
    st.subheader("Spending Breakdown by Category")
    
    # Horizontal Bar Chart for better label readability
    cat_spending = filtered_df.groupby(['category_name', 'expense_type'])['annual_amount'].mean().reset_index()
    fig_bar = px.bar(
        cat_spending.sort_values(by='annual_amount', ascending=True), 
        x='annual_amount', y='category_name', color='expense_type',
        orientation='h', height=500,
        labels={'annual_amount': 'Avg Annual Spending ($)', 'category_name': 'Category', 'expense_type': 'Type'},
        color_discrete_map={'Essential': '#1f77b4', 'Discretionary': '#ff7f0e'},
        template="plotly_white"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    col_pie, col_sun = st.columns(2)
    
    with col_pie:
        st.subheader("Budget Allocation")
        type_spending = filtered_df.groupby('expense_type')['annual_amount'].sum().reset_index()
        fig_pie = px.pie(
            type_spending, names='expense_type', values='annual_amount', hole=0.45,
            color_discrete_map={'Essential': '#1f77b4', 'Discretionary': '#ff7f0e'}
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_sun:
        st.subheader("Demographic Sunburst")
        # Sunburst Chart: Region -> Education Level -> Expense Type
        sun_df = filtered_df.groupby(['region', 'education_level', 'expense_type'])['annual_amount'].sum().reset_index()
        fig_sun = px.sunburst(
            sun_df, path=['region', 'education_level', 'expense_type'], values='annual_amount',
            color='expense_type', color_discrete_map={'Essential': '#1f77b4', 'Discretionary': '#ff7f0e'}
        )
        st.plotly_chart(fig_sun, use_container_width=True)

with tab3:
    col_table1, col_table2 = st.columns(2)
    
    with col_table1:
        st.subheader("Category Spend Matrix")
        # Pivot table showing Essential vs Discretionary cleanly side-by-side
        pivot_df = filtered_df.pivot_table(
            index='category_name', columns='expense_type', 
            values='annual_amount', aggfunc='mean', fill_value=0
        ).reset_index()
        pivot_df['Total Avg Spending'] = pivot_df.sum(axis=1, numeric_only=True)
        pivot_df = pivot_df.sort_values(by='Total Avg Spending', ascending=False)
        
        # Apply Pandas Styling for a gradient heat map and currency formatting
        st.dataframe(
            pivot_df.style.format({col: "${:,.2f}" for col in pivot_df.columns if col != 'category_name'})
                          .background_gradient(cmap='Blues', subset=['Total Avg Spending']),
            use_container_width=True, hide_index=True
        )

    with col_table2:
        st.subheader("Household Financial Summary")
        # Grouped summary of specific households without exposing every raw row
        hh_df = filtered_df.groupby(['household_id', 'income_before_taxes', 'education_level'])['annual_amount'].sum().reset_index()
        hh_df.rename(columns={'annual_amount': 'Total Tracked Spend'}, inplace=True)
        hh_df['Spend % of Income'] = (hh_df['Total Tracked Spend'] / hh_df['income_before_taxes']) * 100
        
        st.dataframe(
            hh_df.style.format({
                'income_before_taxes': "${:,.0f}", 
                'Total Tracked Spend': "${:,.0f}",
                'Spend % of Income': "{:.1f}%"
            }).background_gradient(cmap='Oranges', subset=['Spend % of Income']),
            use_container_width=True, hide_index=True
        )