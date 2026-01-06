import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="Metrics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }
    </style>
    """, unsafe_allow_html=True)

# Sidebar configuration
st.sidebar.title("⚙️ Configuration")
api_endpoint = st.sidebar.text_input(
    "API Endpoint URL",
    placeholder="https://api.example.com/metrics",
    help="Enter the URL of your metrics API endpoint"
)

refresh_rate = st.sidebar.selectbox(
    "Auto-refresh interval",
    ["Manual", "30 seconds", "1 minute", "5 minutes"],
    index=0
)

# Date range filter
st.sidebar.subheader("📅 Date Range")
date_from = st.sidebar.date_input("From", datetime.now() - timedelta(days=30))
date_to = st.sidebar.date_input("To", datetime.now())

# Function to fetch data from API
@st.cache_data(ttl=30)
def fetch_metrics_data(api_url):
    """Fetch metrics data from API endpoint"""
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {str(e)}")
        return None

# Function to generate mock data for demonstration
def generate_mock_data():
    """Generate sample data for demonstration purposes"""
    dates = pd.date_range(start=date_from, end=date_to, freq='D')
    return {
        'current_metrics': {
            'hours_logged': 156.5,
            'reviews_done': 342,
            'writing_units_done': 89,
            'pass_rate': 94.2,
            'tasks_completed': 127,
            'aht': 12.3
        },
        'previous_metrics': {
            'hours_logged': 142.0,
            'reviews_done': 298,
            'writing_units_done': 76,
            'pass_rate': 91.5,
            'tasks_completed': 115,
            'aht': 13.8
        },
        'time_series': [
            {
                'date': date.strftime('%Y-%m-%d'),
                'hours_logged': 5 + (i % 8),
                'reviews_done': 10 + (i % 15),
                'writing_units_done': 2 + (i % 5),
                'pass_rate': 88 + (i % 10),
                'tasks_completed': 3 + (i % 6),
                'aht': 10 + (i % 8)
            }
            for i, date in enumerate(dates)
        ]
    }

# Main dashboard
st.title("📊 Metrics Dashboard")
st.markdown("---")

# Fetch data button
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    fetch_button = st.button("🔄 Refresh Data", type="primary")
with col2:
    use_mock = st.checkbox("Use Mock Data", value=True)

# Fetch or generate data
if fetch_button or 'data' not in st.session_state:
    if use_mock or not api_endpoint:
        data = generate_mock_data()
        if not api_endpoint:
            st.info("💡 Enter an API endpoint in the sidebar or use mock data to explore the dashboard")
    else:
        data = fetch_metrics_data(api_endpoint)
        if data is None:
            data = generate_mock_data()
            st.warning("⚠️ Using mock data due to API error")
    
    st.session_state['data'] = data

data = st.session_state.get('data', generate_mock_data())

# Display metric cards
st.subheader("📈 Key Metrics")
col1, col2, col3, col4, col5, col6 = st.columns(6)

current = data['current_metrics']
previous = data['previous_metrics']

with col1:
    delta_hours = current['hours_logged'] - previous['hours_logged']
    st.metric(
        "Hours Logged",
        f"{current['hours_logged']:.1f}h",
        f"{delta_hours:+.1f}h"
    )

with col2:
    delta_reviews = current['reviews_done'] - previous['reviews_done']
    st.metric(
        "Reviews Done",
        f"{current['reviews_done']}",
        f"{delta_reviews:+d}"
    )

with col3:
    delta_writing = current['writing_units_done'] - previous['writing_units_done']
    st.metric(
        "Writing Units",
        f"{current['writing_units_done']}",
        f"{delta_writing:+d}"
    )

with col4:
    delta_pass = current['pass_rate'] - previous['pass_rate']
    st.metric(
        "Pass Rate",
        f"{current['pass_rate']:.1f}%",
        f"{delta_pass:+.1f}%"
    )

with col5:
    delta_tasks = current['tasks_completed'] - previous['tasks_completed']
    st.metric(
        "Tasks Completed",
        f"{current['tasks_completed']}",
        f"{delta_tasks:+d}"
    )

with col6:
    delta_aht = current['aht'] - previous['aht']
    st.metric(
        "AHT (mins)",
        f"{current['aht']:.1f}",
        f"{delta_aht:+.1f}",
        delta_color="inverse"
    )

st.markdown("---")

# Charts section
st.subheader("📊 Trends & Visualizations")

# Convert time series data to DataFrame
df = pd.DataFrame(data['time_series'])
df['date'] = pd.to_datetime(df['date'])

# Create tabs for different chart views
tab1, tab2, tab3 = st.tabs(["📈 Time Series", "📊 Comparisons", "🎯 Performance"])

with tab1:
    # Time series charts
    col1, col2 = st.columns(2)
    
    with col1:
        fig_hours = px.line(df, x='date', y='hours_logged', 
                           title='Hours Logged Over Time',
                           markers=True)
        fig_hours.update_layout(height=300)
        st.plotly_chart(fig_hours, use_container_width=True)
        
        fig_reviews = px.line(df, x='date', y='reviews_done', 
                             title='Reviews Done Over Time',
                             markers=True,
                             color_discrete_sequence=['#00CC96'])
        fig_reviews.update_layout(height=300)
        st.plotly_chart(fig_reviews, use_container_width=True)
    
    with col2:
        fig_writing = px.line(df, x='date', y='writing_units_done', 
                             title='Writing Units Over Time',
                             markers=True,
                             color_discrete_sequence=['#AB63FA'])
        fig_writing.update_layout(height=300)
        st.plotly_chart(fig_writing, use_container_width=True)
        
        fig_tasks = px.line(df, x='date', y='tasks_completed', 
                           title='Tasks Completed Over Time',
                           markers=True,
                           color_discrete_sequence=['#FFA15A'])
        fig_tasks.update_layout(height=300)
        st.plotly_chart(fig_tasks, use_container_width=True)

with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        # Bar chart comparing current vs previous
        comparison_data = pd.DataFrame({
            'Metric': ['Hours', 'Reviews', 'Writing Units', 'Tasks'],
            'Current': [
                current['hours_logged'],
                current['reviews_done'],
                current['writing_units_done'],
                current['tasks_completed']
            ],
            'Previous': [
                previous['hours_logged'],
                previous['reviews_done'],
                previous['writing_units_done'],
                previous['tasks_completed']
            ]
        })
        
        fig_comparison = go.Figure(data=[
            go.Bar(name='Previous', x=comparison_data['Metric'], y=comparison_data['Previous']),
            go.Bar(name='Current', x=comparison_data['Metric'], y=comparison_data['Current'])
        ])
        fig_comparison.update_layout(
            title='Current vs Previous Period',
            barmode='group',
            height=400
        )
        st.plotly_chart(fig_comparison, use_container_width=True)
    
    with col2:
        # Pie chart for task distribution
        task_dist = pd.DataFrame({
            'Category': ['Reviews', 'Writing Units', 'Other Tasks'],
            'Count': [
                current['reviews_done'],
                current['writing_units_done'],
                current['tasks_completed']
            ]
        })
        
        fig_pie = px.pie(task_dist, values='Count', names='Category',
                        title='Task Distribution')
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)

with tab3:
    col1, col2 = st.columns(2)
    
    with col1:
        # Pass rate over time
        fig_pass = px.line(df, x='date', y='pass_rate', 
                          title='Pass Rate Trend',
                          markers=True,
                          color_discrete_sequence=['#00CC96'])
        fig_pass.update_layout(height=300)
        fig_pass.add_hline(y=90, line_dash="dash", line_color="red", 
                          annotation_text="Target: 90%")
        st.plotly_chart(fig_pass, use_container_width=True)
    
    with col2:
        # AHT over time
        fig_aht = px.line(df, x='date', y='aht', 
                         title='Average Handle Time (AHT)',
                         markers=True,
                         color_discrete_sequence=['#EF553B'])
        fig_aht.update_layout(height=300)
        fig_aht.add_hline(y=15, line_dash="dash", line_color="orange", 
                         annotation_text="Target: 15 mins")
        st.plotly_chart(fig_aht, use_container_width=True)
    
    # Performance gauge chart
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = current['pass_rate'],
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Current Pass Rate"},
        delta = {'reference': previous['pass_rate']},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 70], 'color': "lightgray"},
                {'range': [70, 85], 'color': "gray"},
                {'range': [85, 100], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig_gauge.update_layout(height=300)
    st.plotly_chart(fig_gauge, use_container_width=True)

st.markdown("---")

# Data table section
st.subheader("📋 Detailed Data Table")

# Format the dataframe for display
display_df = df.copy()
display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
display_df = display_df.rename(columns={
    'date': 'Date',
    'hours_logged': 'Hours Logged',
    'reviews_done': 'Reviews Done',
    'writing_units_done': 'Writing Units',
    'pass_rate': 'Pass Rate (%)',
    'tasks_completed': 'Tasks Completed',
    'aht': 'AHT (mins)'
})

# Display with formatting
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Pass Rate (%)": st.column_config.NumberColumn(
            format="%.1f%%"
        ),
        "AHT (mins)": st.column_config.NumberColumn(
            format="%.1f"
        ),
        "Hours Logged": st.column_config.NumberColumn(
            format="%.1f"
        )
    }
)

# Download button
csv = display_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Download Data as CSV",
    data=csv,
    file_name=f'metrics_data_{datetime.now().strftime("%Y%m%d")}.csv',
    mime='text/csv',
)

# Footer
st.markdown("---")
st.caption("🔄 Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
