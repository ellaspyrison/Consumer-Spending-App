import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Advanced Consumer Spending Explorer", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    /* Main app background */
    .stApp {
        background-color: #fce4ec;
    }
    /* Sidebar background */
    [data-testid="stSidebar"] {
        background-color: #fce4ec; 
    }
    /* Top header bar background */
    [data-testid="stHeader"] {
        background-color: #fce4ec;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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

st.title("Advanced Consumer Market Spending Analysis")
st.markdown("Explore how household demographics impact spending priorities.")

st.sidebar.header("Filter Demographics")

def add_filter(column_name, label):
    options = ["All"] + sorted(df[column_name].dropna().unique().tolist())
    choice = st.sidebar.selectbox(label, options)
    return choice

sel_region = add_filter('region', 'Region')
sel_education = add_filter('education_level', 'Education Level')
sel_marital = add_filter('marital_status', 'Marital Status')
sel_housing = add_filter('housing_tenure', 'Housing Tenure')
sel_sex = add_filter('sex', 'Reference Person Sex')

# Drop missing values first to ensure we get actual numbers
clean_income = df['income_before_taxes'].dropna()

# Add a safety check in case the column is entirely empty/NaN
if not clean_income.empty:
    min_inc = int(clean_income.min())
    max_inc = int(clean_income.max())
else:
    # Default values if no valid data exists
    min_inc, max_inc = 0, 100000
sel_income = st.sidebar.slider("Income Before Taxes ($)", min_value=min_inc, max_value=max_inc, value=(min_inc, max_inc))

# Drop missing values first to ensure we get actual numbers
clean_age = df['age'].dropna()

# Add a safety check in case the column is entirely empty/NaN
if not clean_age.empty:
    min_age = int(clean_age.min())
    max_age = int(clean_age.max())
else:
    # Default values if no valid data exists
    min_age, max_age = 18, 100
sel_age = st.sidebar.slider("Age of Reference Person", min_value=min_age, max_value=max_age, value=(min_age, max_age))

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

# --- Predictive Budget Calculator (Sidebar) ---
st.sidebar.divider()
st.sidebar.header("Predictive Budget Calculator")
st.sidebar.caption("Estimate a personalized budget based on your filtered dataset's averages.")

calc_income = st.sidebar.number_input(
    "Hypothetical Annual Income ($)",
    min_value=10000,
    max_value=1000000,
    value=75000,
    step=5000
)

edu_options = sorted(df['education_level'].dropna().unique().tolist())
calc_edu = st.sidebar.selectbox("Hypothetical Education Level", edu_options)

# Filter the current dataset by the chosen education level
calc_cohort = filtered_df[filtered_df['education_level'] == calc_edu]

# Fallback: if the main sidebar filter excluded that education level, use the full dataset for that education level
if calc_cohort.empty:
    st.sidebar.info(f"No '{calc_edu}' households in current filters—using overall dataset averages for this group.")
    calc_cohort = df[df['education_level'] == calc_edu]

cohort_avg_income = calc_cohort.drop_duplicates(subset=['household_id'])['income_before_taxes'].mean()

if pd.notna(cohort_avg_income) and cohort_avg_income > 0:
    # Calculate each category's average % of income, then scale to the hypothetical income
    pred_df = calc_cohort.groupby(['category_name', 'expense_type'])['annual_amount'].mean().reset_index()
    pred_df['income_share'] = pred_df['annual_amount'] / cohort_avg_income
    pred_df['Annual ($)'] = pred_df['income_share'] * calc_income
    pred_df['Monthly ($)'] = pred_df['Annual ($)'] / 12

    total_pred_annual = pred_df['Annual ($)'].sum()
    est_savings = calc_income - total_pred_annual

    # Summary metrics in the sidebar
    c1, c2 = st.sidebar.columns(2)
    c1.metric("Est. Annual Spend", f"${total_pred_annual:,.0f}")
    c2.metric("Est. Margin", f"${est_savings:,.0f}")

    # Compact predicted budget table
    display_pred = pred_df[['category_name', 'Monthly ($)', 'Annual ($)']].sort_values(
        by='Annual ($)', ascending=False
    ).rename(columns={'category_name': 'Category'})

    st.sidebar.dataframe(
        display_pred.style.format({
            'Monthly ($)': '${:,.0f}',
            'Annual ($)': '${:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )
else:
    st.sidebar.warning("Not enough income data to generate a prediction for this group.")

unique_households = filtered_df['household_id'].nunique()
avg_income = filtered_df.drop_duplicates(subset=['household_id'])['income_before_taxes'].mean()
avg_total_spending = filtered_df.groupby('household_id')['annual_amount'].sum().mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Households in Segment", f"{unique_households:,}")
col2.metric("Avg. Household Income", f"${avg_income:,.0f}")
col3.metric("Avg. Tracked Spending", f"${avg_total_spending:,.0f}")
col4.metric("Savings/Unallocated Margin", f"${(avg_income - avg_total_spending):,.0f}")

st.subheader("Correlation: Income vs. Spending by Education Level")
scatter_df = filtered_df.groupby(['household_id', 'education_level', 'income_before_taxes'])['annual_amount'].sum().reset_index()
fig_scatter = px.scatter(
    scatter_df, 
    x="income_before_taxes", 
    y="annual_amount", 
    color="education_level",
    opacity=0.6,
    labels={"income_before_taxes": "Income Before Taxes ($)", "annual_amount": "Total Annual Spending ($)", "education_level": "Education"},
    template="plotly_white"
)
fig_scatter.update_traces(marker=dict(size=8, line=dict(width=0.5, color='DarkSlateGrey')))
st.plotly_chart(fig_scatter, use_container_width=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Core Visualizations", 
    "Demographic Deep Dives", 
    "Detailed Data Tables", 
    "Extremes Analysis", 
    "Treat Yourself Index"
])

with tab1:
    st.subheader("Spending Breakdown by Category")
    
    cat_spending = filtered_df.groupby(['category_name', 'expense_type'])['annual_amount'].mean().reset_index()
    
    fig_bar = px.bar(
        cat_spending.sort_values(by='annual_amount', ascending=True), 
        x='annual_amount', 
        y='category_name', 
        color='expense_type',
        orientation='h', 
        height=500,
        text='annual_amount',
        labels={'annual_amount': 'Avg Annual Spending ($)', 'category_name': '', 'expense_type': 'Expense Type'},
        color_discrete_map={'Essential': '#C2185B', 'Discretionary': '#F48FB1'},
        template="plotly_white"
    )
    
    fig_bar.update_traces(
        texttemplate='$%{text:,.0f}', 
        textposition='outside',
        marker_line_width=0 
    )
    
    fig_bar.update_layout(
        xaxis=dict(showgrid=False, showticklabels=False, title=''), 
        yaxis=dict(title='', tickfont=dict(size=13)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=80, t=30, b=0)
    )
    
    st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    col_pie, col_sun = st.columns(2)
    
    with col_pie:
        st.subheader("Budget Allocation")
        type_spending = filtered_df.groupby('expense_type')['annual_amount'].sum().reset_index()
        
        fig_pie = px.pie(
            type_spending, 
            names='expense_type', 
            values='annual_amount', 
            hole=0.65,
            color='expense_type',
            color_discrete_map={'Essential': '#C2185B', 'Discretionary': '#F48FB1'}
        )
        
        fig_pie.update_traces(
            textposition='outside', 
            textinfo='label+percent',
            marker=dict(line=dict(color='#FFFFFF', width=2.5)), 
            hovertemplate="<b>%{label}</b><br>Amount: $%{value:,.0f}<extra></extra>"
        )
        
        fig_pie.update_layout(
            showlegend=False,
            margin=dict(t=30, b=30, l=30, r=30),
            annotations=[dict(text='Total<br>Spending', x=0.5, y=0.5, font_size=16, showarrow=False, font=dict(color='#C2185B'))]
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_sun:
        st.subheader("Demographic Sunburst")
        sun_df = filtered_df.groupby(['region', 'education_level', 'expense_type'])['annual_amount'].sum().reset_index()
        
        fig_sun = px.sunburst(
            sun_df, 
            path=['region', 'education_level', 'expense_type'], 
            values='annual_amount',
            color='expense_type', 
            color_discrete_map={'Essential': '#C2185B', 'Discretionary': '#F48FB1', '(?)': '#F8BBD0'}
        )
        
        fig_sun.update_traces(
            textinfo='label',
            insidetextorientation='radial',
            marker=dict(line=dict(color='#FFFFFF', width=1.5)),
            hovertemplate="<b>%{label}</b><br>Total Spending: $%{value:,.0f}<br>Share of Parent Category: %{percentParent:.1%}<extra></extra>"
        )
        
        fig_sun.update_layout(
            margin=dict(t=20, b=20, l=20, r=20)
        )
        
        st.plotly_chart(fig_sun, use_container_width=True)

with tab3:
    st.markdown("Explore the detailed numbers behind the visualizations. These tables break down average category costs and summarize individual household financial profiles.")
    col_table1, col_table2 = st.columns(2)
    
    with col_table1:
        st.subheader("Category Spend Matrix")
        st.caption("Average annual spending per category, split by essential vs. discretionary needs.")
        
        pivot_df = filtered_df.pivot_table(
            index='category_name', columns='expense_type', 
            values='annual_amount', aggfunc='mean', fill_value=0
        ).reset_index()
        
        pivot_df['Total Avg Spending'] = pivot_df.sum(axis=1, numeric_only=True)
        pivot_df = pivot_df.sort_values(by='Total Avg Spending', ascending=False)
        
        pivot_df = pivot_df.rename(columns={
            'category_name': 'Category',
            'Discretionary': 'Discretionary ($)',
            'Essential': 'Essential ($)'
        })
        
        st.dataframe(
            pivot_df.style.format({col: "${:,.2f}" for col in pivot_df.columns if col != 'Category'})
                          .background_gradient(cmap='RdPu', subset=['Total Avg Spending']),
            use_container_width=True, hide_index=True
        )

        st.download_button(
            label="Download Category Matrix (CSV)",
            data=pivot_df.to_csv(index=False).encode('utf-8'),
            file_name="category_spend_matrix.csv",
            mime="text/csv"
        )

    with col_table2:
        st.subheader("Household Financial Summary")
        st.caption("A summary of individual household incomes, education, and the percentage of their income dedicated to tracked spending.")
        
        hh_df = filtered_df.groupby(['household_id', 'income_before_taxes', 'education_level'])['annual_amount'].sum().reset_index()
        
        hh_df.rename(columns={
            'household_id': 'Household ID',
            'income_before_taxes': 'Pre-Tax Income',
            'education_level': 'Education',
            'annual_amount': 'Total Tracked Spend'
        }, inplace=True)
        
        hh_df['Spend % of Income'] = (hh_df['Total Tracked Spend'] / hh_df['Pre-Tax Income']) * 100
        
        st.dataframe(
            hh_df.style.format({
                'Pre-Tax Income': "${:,.0f}", 
                'Total Tracked Spend': "${:,.0f}",
                'Spend % of Income': "{:.1f}%"
            }).background_gradient(cmap='RdPu', subset=['Spend % of Income']),
            use_container_width=True, hide_index=True
        )

        st.download_button(
            label="Download Household Summary (CSV)",
            data=hh_df.to_csv(index=False).encode('utf-8'),
            file_name="household_financial_summary.csv",
            mime="text/csv"
        )

    st.divider()
    st.download_button(
        label="Download Full Filtered Dataset (CSV)",
        data=filtered_df.to_csv(index=False).encode('utf-8'),
        file_name="filtered_consumer_spending.csv",
        mime="text/csv",
        use_container_width=True
    )

with tab4:
    st.subheader("High Rollers vs. Budget Savers")
    st.markdown("Comparing the top 10% highest spenders against the bottom 10% lowest spenders in your current filtered view.")
    
    # Calculate total spending per household to find percentiles
    hh_totals = filtered_df.groupby('household_id')['annual_amount'].sum().reset_index()
    
    if len(hh_totals) < 10:
        st.info("Not enough households in the current filter to calculate meaningful top/bottom 10% percentiles. Broaden your filters to view this analysis.")
    else:
        p90 = hh_totals['annual_amount'].quantile(0.9)
        p10 = hh_totals['annual_amount'].quantile(0.1)
        
        high_ids = hh_totals[hh_totals['annual_amount'] >= p90]['household_id']
        low_ids = hh_totals[hh_totals['annual_amount'] <= p10]['household_id']
        
        hr_df = filtered_df[filtered_df['household_id'].isin(high_ids)]
        bs_df = filtered_df[filtered_df['household_id'].isin(low_ids)]
        
        # --- 1. Essential vs. Discretionary Split Metrics ---
        def get_discretionary_pct(sub_df):
            total = sub_df['annual_amount'].sum()
            disc = sub_df[sub_df['expense_type'] == 'Discretionary']['annual_amount'].sum()
            return (disc / total * 100) if total > 0 else 0

        hr_avg = hr_df.groupby('household_id')['annual_amount'].sum().mean()
        bs_avg = bs_df.groupby('household_id')['annual_amount'].sum().mean()
        hr_disc_pct = get_discretionary_pct(hr_df)
        bs_disc_pct = get_discretionary_pct(bs_df)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("High Rollers Avg Spend", f"${hr_avg:,.0f}")
        m2.metric("High Rollers Discretionary %", f"{hr_disc_pct:.1f}%", delta=f"{hr_disc_pct - bs_disc_pct:+.1f}% vs. Savers")
        m3.metric("Budget Savers Avg Spend", f"${bs_avg:,.0f}")
        m4.metric("Budget Savers Discretionary %", f"{bs_disc_pct:.1f}%")

        st.divider()

        # --- 2. Toggle for Raw Dollars vs. Proportional Share ---
        view_mode = st.radio(
            "Radar Chart Metric",
            ["Share of Total Spend (%)", "Average Annual Spend ($)"],
            horizontal=True
        )

        hr_cat = hr_df.groupby(['category_name', 'expense_type'])['annual_amount'].mean().reset_index()
        hr_cat['Cohort'] = 'High Rollers (Top 10%)'
        hr_cat['pct_share'] = (hr_cat['annual_amount'] / hr_cat['annual_amount'].sum()) * 100

        bs_cat = bs_df.groupby(['category_name', 'expense_type'])['annual_amount'].mean().reset_index()
        bs_cat['Cohort'] = 'Budget Savers (Bottom 10%)'
        bs_cat['pct_share'] = (bs_cat['annual_amount'] / bs_cat['annual_amount'].sum()) * 100

        radar_df = pd.concat([hr_cat, bs_cat])

        if view_mode == "Share of Total Spend (%)":
            r_col = 'pct_share'
            hover_fmt = "<b>%{theta}</b><br>Share of Spend: %{r:.1f}%<extra></extra>"
        else:
            r_col = 'annual_amount'
            hover_fmt = "<b>%{theta}</b><br>Avg Spend: $%{r:,.0f}<extra></extra>"

        fig_radar = px.line_polar(
            radar_df,
            r=r_col,
            theta='category_name',
            color='Cohort',
            line_close=True,
            color_discrete_map={
                'High Rollers (Top 10%)': '#C2185B',
                'Budget Savers (Bottom 10%)': '#F48FB1'
            },
            template="plotly_white"
        )

        fig_radar.update_traces(
            fill='toself',
            opacity=0.65,
            hovertemplate=hover_fmt
        )

        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, showticklabels=True, tickfont=dict(size=10)),
                angularaxis=dict(tickfont=dict(size=13, color='black'))
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5)
        )

        st.plotly_chart(fig_radar, use_container_width=True)

with tab5:
    st.subheader("The Treat Yourself Index")
    st.markdown("Stripping away essentials to focus purely on discretionary spending. Bubble size reflects household income.")

    # Isolate discretionary spending only
    disc_df = filtered_df[filtered_df['expense_type'] == 'Discretionary']

    if disc_df.empty:
        st.info("No discretionary spending data available for the current filters.")
    else:
        # Aggregate discretionary spend per household
        bubble_df = disc_df.groupby(
            ['household_id', 'age', 'income_before_taxes', 'education_level', 'region', 'marital_status']
        )['annual_amount'].sum().reset_index()

        # Filter out zero/negative incomes so Plotly bubble sizing doesn't error
        bubble_df = bubble_df[bubble_df['income_before_taxes'] > 0].copy()
        bubble_df['treat_yourself_index'] = (bubble_df['annual_amount'] / bubble_df['income_before_taxes']) * 100

        # Top KPI row
        avg_disc = bubble_df['annual_amount'].mean()
        avg_index = bubble_df['treat_yourself_index'].mean()
        top_disc_cat = disc_df.groupby('category_name')['annual_amount'].mean().idxmax()

        t1, t2, t3 = st.columns(3)
        t1.metric("Avg. Discretionary Spend", f"${avg_disc:,.0f}")
        t2.metric("Avg. \"Treat Yourself\" Index", f"{avg_index:.1f}%", help="Discretionary spend as a % of pre-tax income")
        t3.metric("Top Splurge Category", top_disc_cat)

        st.divider()

        # Let the user choose how to color the bubbles
        color_choice = st.selectbox(
            "Color Bubbles By",
            options=["education_level", "region", "marital_status"],
            format_func=lambda x: x.replace("_", " ").title()
        )

        fig_bubble = px.scatter(
            bubble_df,
            x="age",
            y="annual_amount",
            size="income_before_taxes",
            color=color_choice,
            size_max=45,
            opacity=0.7,
            hover_name="household_id",
            hover_data={
                "age": True,
                "annual_amount": ":$,.0f",
                "income_before_taxes": ":$,.0f",
                "treat_yourself_index": ":.1f%"
            },
            labels={
                "age": "Age of Reference Person",
                "annual_amount": "Annual Discretionary Spend ($)",
                "income_before_taxes": "Pre-Tax Income",
                "treat_yourself_index": "Treat Yourself Index (%)",
                color_choice: color_choice.replace("_", " ").title()
            },
            template="plotly_white"
        )

        fig_bubble.update_traces(marker=dict(line=dict(width=1, color='#FFFFFF')))
        fig_bubble.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=40, b=20, l=20, r=20)
        )

        st.plotly_chart(fig_bubble, use_container_width=True)