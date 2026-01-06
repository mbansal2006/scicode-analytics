import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from environment
AIRTABLE_API_KEY = os.getenv("AIRTABLE_PAT") or os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appSYdmGYOQ1Wh8rA")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID", "tblSxnhXPhkR3MI7B")

# CSV paths
PROJECT_ROOT = Path(__file__).parent.parent
CSV_PATH_1 = str(PROJECT_ROOT / "Times1.csv")
CSV_PATH_2 = str(PROJECT_ROOT / "Times2.csv")

# Expert name aliases - maps various names to canonical name
# Format: "alias": "canonical_name"
EXPERT_ALIASES = {
    # Totrakool / Ta Khongsap
    "Totrakool Khongsap": "Ta Khongsap",
    "totrakool khongsap": "Ta Khongsap",
    
    # József / Jozsef Vass (accent differences)
    "József Vass": "Jozsef Vass",
    "jozsef vass": "Jozsef Vass",
    "józsef vass": "Jozsef Vass",
    
    # Behzad variations
    "Behzad Ansarinejad - Physics": "Behzad",
    "Behzad Ansarinejad": "Behzad",
    "behzad ansarinejad - physics": "Behzad",
    "behzad ansarinejad": "Behzad",
}

# Experts to exclude from AHT calculations (admins, managers, etc.)
EXCLUDED_FROM_AHT = [
    "Mahir Bansal",
]

def normalize_expert_name(name: str) -> str:
    """Normalize expert name using alias mapping"""
    if not name:
        return name
    
    # Check exact match first
    if name in EXPERT_ALIASES:
        return EXPERT_ALIASES[name]
    
    # Check case-insensitive match
    name_lower = name.lower().strip()
    for alias, canonical in EXPERT_ALIASES.items():
        if alias.lower() == name_lower:
            return canonical
    
    return name.strip()

# Page configuration
st.set_page_config(
    page_title="SciCode Analytics Dashboard",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS - works for both light and dark themes
st.markdown("""
    <style>
    /* Metric cards with proper contrast */
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 700;
        color: inherit !important;
    }
    div[data-testid="stMetricLabel"] {
        color: inherit !important;
    }
    div[data-testid="stMetricDelta"] {
        color: inherit !important;
    }
    
    /* Ensure dataframes are readable */
    .stDataFrame {
        color: inherit !important;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================
# DATA LOADING FUNCTIONS
# ============================================

def parse_time_to_hours(time_str: str) -> float:
    """Convert HH:MM format to decimal hours"""
    if pd.isna(time_str) or time_str == "":
        return 0.0
    try:
        parts = str(time_str).split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours + minutes / 60
    except (ValueError, IndexError):
        return 0.0


def load_time_logs(csv_paths: list) -> pd.DataFrame:
    """Load and aggregate time logs from multiple CSV files"""
    all_data = []
    
    for path in csv_paths:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                # Normalize column names
                df.columns = df.columns.str.strip()
                if 'Employee Name' in df.columns and 'Total Time [h]' in df.columns:
                    df['hours'] = df['Total Time [h]'].apply(parse_time_to_hours)
                    df['employee_name'] = df['Employee Name'].str.strip().str.strip('"').apply(normalize_expert_name)
                    all_data.append(df[['employee_name', 'hours']])
            except Exception as e:
                st.warning(f"Error loading {path}: {e}")
    
    if not all_data:
        return pd.DataFrame(columns=['employee_name', 'hours'])
    
    combined = pd.concat(all_data, ignore_index=True)
    aggregated = combined.groupby('employee_name', as_index=False)['hours'].sum()
    return aggregated.sort_values('hours', ascending=False)


@st.cache_data(ttl=300)
def fetch_airtable_tasks(api_key: str, base_id: str, table_id: str) -> tuple[pd.DataFrame, list]:
    """Fetch all tasks from Airtable. Returns (dataframe, raw_records for debugging)"""
    if not api_key or not base_id:
        return pd.DataFrame(), []
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    all_records = []
    offset = None
    
    while True:
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            all_records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        except requests.exceptions.RequestException as e:
            st.error(f"Airtable API error: {e}")
            break
    
    if not all_records:
        return pd.DataFrame(), []
    
    # Parse records into DataFrame
    parsed = []
    for record in all_records:
        fields = record.get("fields", {})
        
        # Extract expert name and email from nested structure
        expert_user = fields.get("expert__user", [])
        expert_name = ""
        expert_email = ""
        if expert_user and len(expert_user) > 0:
            if isinstance(expert_user[0], dict):
                expert_name = normalize_expert_name(expert_user[0].get("name", ""))
                expert_email = expert_user[0].get("email", "").lower()
            else:
                expert_name = normalize_expert_name(str(expert_user[0]))
        
        # Extract primary reviewer name
        reviewer_user = fields.get("expert_reviewer__user", [])
        reviewer_name = ""
        if reviewer_user and len(reviewer_user) > 0:
            if isinstance(reviewer_user[0], dict):
                reviewer_name = normalize_expert_name(reviewer_user[0].get("name", ""))
            else:
                reviewer_name = normalize_expert_name(str(reviewer_user[0]))
        
        # Get all unique reviewer emails (excluding the expert) for this task
        # reviews__reviewer_users contains all reviewers for each review action
        reviewer_users = fields.get("reviews__reviewer_users", [])
        unique_reviewer_emails = set()
        for reviewer in reviewer_users:
            if isinstance(reviewer, dict):
                email = reviewer.get("email", "").lower()
                if email and email != expert_email:
                    unique_reviewer_emails.add(email)
        unique_reviewers_count = len(unique_reviewer_emails)
        
        parsed.append({
            "record_id": record.get("id"),
            "task_id": fields.get("task_id"),
            "title": fields.get("title", ""),
            "task_status": fields.get("task_status", ""),
            "expert_name": expert_name,
            "expert_email": expert_email,
            "reviewer_name": reviewer_name,
            "reviewer_emails": list(unique_reviewer_emails),  # Store actual emails for global unique count
            "time_claimed": fields.get("time_claimed"),
            "time_in_progress": fields.get("time_in_progress"),
            "time_ready_for_review": fields.get("time_ready_for_review"),
            "time_first_ready_for_review": fields.get("time_first_ready_for_review"),
            "time_merged": fields.get("time_merged"),
            "reviews_count": fields.get("reviews__count", 0),  # Raw count (all review actions)
            "unique_reviewers": unique_reviewers_count,  # Unique reviewers for this task
            "reviews_approved_count": fields.get("reviews__approved_count", 0),
            "reviews_sent_back_count": fields.get("reviews__sent_back_count", 0),
        })
    
    df = pd.DataFrame(parsed)
    
    # Convert datetime columns
    date_cols = ["time_claimed", "time_in_progress", "time_ready_for_review", 
                 "time_first_ready_for_review", "time_merged"]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
    
    return df, all_records


def calculate_cycle_times(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate cycle time metrics for each task"""
    df = df.copy()
    
    # Claimed to Ready for Review (work time)
    df['hours_claimed_to_review'] = (
        df['time_ready_for_review'] - df['time_claimed']
    ).dt.total_seconds() / 3600
    
    # Ready for Review to Merged (review time)
    df['hours_review_to_merged'] = (
        df['time_merged'] - df['time_ready_for_review']
    ).dt.total_seconds() / 3600
    
    # Total cycle time (claimed to merged)
    df['hours_total_cycle'] = (
        df['time_merged'] - df['time_claimed']
    ).dt.total_seconds() / 3600
    
    # Clean up negative or unreasonable values
    for col in ['hours_claimed_to_review', 'hours_review_to_merged', 'hours_total_cycle']:
        df.loc[df[col] < 0, col] = None
        df.loc[df[col] > 720, col] = None  # Cap at 30 days
    
    # Mark first task for each expert (by earliest time_claimed)
    df['is_first_task'] = False
    for expert in df['expert_name'].dropna().unique():
        expert_tasks = df[df['expert_name'] == expert]
        if not expert_tasks.empty and expert_tasks['time_claimed'].notna().any():
            first_task_idx = expert_tasks['time_claimed'].idxmin()
            if pd.notna(first_task_idx):
                df.loc[first_task_idx, 'is_first_task'] = True
    
    return df


# ============================================
# MAIN DASHBOARD
# ============================================

st.title("SciCode Analytics Dashboard")
st.markdown("Track expert performance, task completion, and review cycle times.")

# Check for API key
if not AIRTABLE_API_KEY:
    st.error("Missing Airtable API key. Please add `AIRTABLE_PAT` to your `.env` file.")
    st.code("""
# Create a .env file in the project root with:
AIRTABLE_PAT=your_personal_access_token_here
AIRTABLE_BASE_ID=appSYdmGYOQ1Wh8rA
AIRTABLE_TABLE_ID=tblSxnhXPhkR3MI7B
    """, language="bash")
    st.stop()

st.markdown("---")

# Load data
time_logs = load_time_logs([CSV_PATH_1, CSV_PATH_2])

# Load Airtable data
with st.spinner("Fetching data from Airtable..."):
    tasks_df, raw_records = fetch_airtable_tasks(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID)

if not tasks_df.empty:
    tasks_df = calculate_cycle_times(tasks_df)
else:
    st.warning("No tasks found in Airtable")
    tasks_df = pd.DataFrame()

# Use all tasks (no status filter for now, to debug)
filtered_tasks = tasks_df

# ============================================
# OVERALL METRICS
# ============================================

st.subheader("Overall Metrics")

# Calculate overall metrics
total_hours = time_logs['hours'].sum() if not time_logs.empty else 0
total_experts = time_logs[time_logs['hours'] > 0]['employee_name'].nunique() if not time_logs.empty else 0

# Hours excluding admins (for AHT calculations)
if not time_logs.empty:
    aht_time_logs = time_logs[~time_logs['employee_name'].isin(EXCLUDED_FROM_AHT)]
    total_hours_for_aht = aht_time_logs['hours'].sum()
else:
    total_hours_for_aht = 0

if not filtered_tasks.empty:
    total_tasks = len(filtered_tasks)
    merged_tasks = len(filtered_tasks[filtered_tasks['task_status'] == 'Merged'])
    
    # Written tasks = Ready for Review, Revising, Approved, or Merged
    written_statuses = ['Ready for Review', 'Revising', 'Approved', 'Merged']
    written_tasks = len(filtered_tasks[filtered_tasks['task_status'].isin(written_statuses)])
    
    # Calculate truly unique reviewers across ALL tasks (for Reviewer AHT denominator)
    all_reviewer_emails = set()
    for emails in filtered_tasks['reviewer_emails']:
        if isinstance(emails, list):
            all_reviewer_emails.update(emails)
    total_unique_reviews = len(all_reviewer_emails)
    
    avg_cycle_time = filtered_tasks['hours_total_cycle'].mean()
else:
    total_tasks = 0
    merged_tasks = 0
    written_tasks = 0
    total_unique_reviews = 0
    avg_cycle_time = 0

# Calculate AHTs (using hours excluding admins)
writer_aht_overall = total_hours_for_aht / written_tasks if written_tasks > 0 else None
reviewer_aht_overall = total_hours_for_aht / total_unique_reviews if total_unique_reviews > 0 else None
overall_aht = total_hours_for_aht / merged_tasks if merged_tasks > 0 else None

# Row 1: Basic counts
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Hours Logged", f"{total_hours:.1f}h")

with col2:
    st.metric("Active Experts", total_experts)

with col3:
    st.metric("Written Tasks", written_tasks, help="Tasks in Ready for Review, Revising, Approved, or Merged")

with col4:
    st.metric("Merged Tasks", merged_tasks)

with col5:
    excluded_names = ", ".join(EXCLUDED_FROM_AHT) if EXCLUDED_FROM_AHT else "None"
    st.metric(
        "Overall AHT", 
        f"{overall_aht:.1f}h" if overall_aht else "N/A",
        help=f"Hours / Merged Tasks (excluding: {excluded_names})"
    )

st.markdown("---")

# ============================================
# TABS FOR DIFFERENT VIEWS
# ============================================

tab1, tab2, tab3, tab4 = st.tabs(["Expert Performance", "Cycle Times", "Task Details", "Charts"])

# --------------------------------------------
# TAB 1: Expert Performance
# --------------------------------------------
with tab1:
    st.subheader("Expert-Level Metrics")
    
    # Build expert metrics table
    expert_metrics = []
    
    # Get unique experts from both time logs and tasks
    all_experts = set()
    if not time_logs.empty:
        all_experts.update(time_logs['employee_name'].unique())
    if not filtered_tasks.empty:
        all_experts.update(filtered_tasks['expert_name'].dropna().unique())
        all_experts.update(filtered_tasks['reviewer_name'].dropna().unique())
    
    # Define written statuses (tasks that have been submitted)
    written_statuses = ['Ready for Review', 'Revising', 'Approved', 'Merged']
    
    for expert in all_experts:
        if not expert:
            continue
            
        # Time logged
        time_row = time_logs[time_logs['employee_name'] == expert]
        hours_logged = time_row['hours'].sum() if not time_row.empty else 0
        
        if not filtered_tasks.empty:
            # Tasks by this expert (as author/writer)
            expert_tasks = filtered_tasks[filtered_tasks['expert_name'] == expert]
            
            # Written tasks = Ready for Review, Revising, Approved, or Merged
            tasks_written = len(expert_tasks[expert_tasks['task_status'].isin(written_statuses)])
            tasks_merged = len(expert_tasks[expert_tasks['task_status'] == 'Merged'])
            
            # Tasks reviewed (as reviewer) - only count merged tasks
            reviewer_tasks = filtered_tasks[filtered_tasks['reviewer_name'] == expert]
            reviews_done = len(reviewer_tasks[reviewer_tasks['task_status'] == 'Merged'])
            
            # Writer AHT = hours logged / written tasks
            writer_aht = hours_logged / tasks_written if tasks_written > 0 else None
            
            # Reviewer AHT = hours logged / reviewed merged tasks
            reviewer_aht = hours_logged / reviews_done if reviews_done > 0 else None
            
            # Overall AHT = hours logged / merged tasks
            overall_aht_expert = hours_logged / tasks_merged if tasks_merged > 0 else None
        else:
            tasks_written = 0
            tasks_merged = 0
            reviews_done = 0
            writer_aht = None
            reviewer_aht = None
            overall_aht_expert = None
        
        expert_metrics.append({
            'Expert': expert,
            'Hours Logged': round(hours_logged, 1),
            'Tasks Written': tasks_written,
            'Tasks Merged': tasks_merged,
            'Writer AHT': round(writer_aht, 1) if writer_aht is not None else None,
            'Reviews Done': reviews_done,
            'Reviewer AHT': round(reviewer_aht, 1) if reviewer_aht is not None else None,
            'Overall AHT': round(overall_aht_expert, 1) if overall_aht_expert is not None else None,
        })
    
    expert_df = pd.DataFrame(expert_metrics)
    
    if not expert_df.empty:
        # Sort by hours logged
        expert_df = expert_df.sort_values('Hours Logged', ascending=False)
        
        # Filter out experts with no activity
        expert_df_active = expert_df[
            (expert_df['Hours Logged'] > 0) | 
            (expert_df['Tasks Written'] > 0) | 
            (expert_df['Tasks Merged'] > 0) | 
            (expert_df['Reviews Done'] > 0)
        ]
        
        # Expert filter
        selected_expert = st.selectbox(
            "Select Expert for Details",
            ["All Experts"] + list(expert_df_active['Expert'].unique()),
            key="expert_select"
        )
        
        if selected_expert == "All Experts":
            st.dataframe(
                expert_df_active,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Hours Logged": st.column_config.NumberColumn(format="%.1f h"),
                    "Writer AHT": st.column_config.NumberColumn(format="%.1f h", help="Hours / Written Tasks"),
                    "Reviewer AHT": st.column_config.NumberColumn(format="%.1f h", help="Hours / Reviews Done"),
                    "Overall AHT": st.column_config.NumberColumn(format="%.1f h", help="Hours / Merged Tasks"),
                }
            )
        else:
            # Show detailed view for selected expert
            expert_row = expert_df[expert_df['Expert'] == selected_expert].iloc[0]
            
            # Row 1: Basic counts
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Hours Logged", f"{expert_row['Hours Logged']:.1f}h")
            with col2:
                st.metric("Tasks Written", expert_row['Tasks Written'], help="Ready for Review + Revising + Approved + Merged")
            with col3:
                st.metric("Tasks Merged", expert_row['Tasks Merged'])
            with col4:
                st.metric("Reviews Done", expert_row['Reviews Done'], help="Merged tasks reviewed")
            
            # Row 2: AHT metrics
            st.markdown("##### AHT Metrics")
            col1, col2, col3 = st.columns(3)
            with col1:
                writer_aht = expert_row['Writer AHT']
                st.metric("Writer AHT", f"{writer_aht:.1f}h" if pd.notna(writer_aht) else "N/A", help="Hours / Tasks Written")
            with col2:
                reviewer_aht = expert_row['Reviewer AHT']
                st.metric("Reviewer AHT", f"{reviewer_aht:.1f}h" if pd.notna(reviewer_aht) else "N/A", help="Hours / Reviews Done")
            with col3:
                overall_aht_val = expert_row['Overall AHT']
                st.metric("Overall AHT", f"{overall_aht_val:.1f}h" if pd.notna(overall_aht_val) else "N/A", help="Hours / Merged Tasks")
            
            if not filtered_tasks.empty:
                st.markdown("#### Tasks by this Expert")
                expert_task_list = filtered_tasks[filtered_tasks['expert_name'] == selected_expert][
                    ['title', 'task_status', 'time_claimed', 'time_merged', 'hours_total_cycle', 'unique_reviewers']
                ].copy()
                expert_task_list['time_claimed'] = expert_task_list['time_claimed'].dt.strftime('%Y-%m-%d %H:%M')
                expert_task_list['time_merged'] = expert_task_list['time_merged'].dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(expert_task_list, use_container_width=True, hide_index=True)
    else:
        st.info("No expert data available")

# --------------------------------------------
# TAB 2: Cycle Times
# --------------------------------------------
with tab2:
    st.subheader("Task Cycle Time Analysis")
    
    if not filtered_tasks.empty:
        # Only consider tasks with valid cycle times (merged tasks)
        cycle_df = filtered_tasks[filtered_tasks['task_status'] == 'Merged'].copy()
        
        if not cycle_df.empty:
            # Split into all tasks and excluding first tasks
            cycle_df_no_first = cycle_df[cycle_df['is_first_task'] == False].copy()
            
            first_task_count = cycle_df['is_first_task'].sum()
            st.caption(f"{len(cycle_df)} merged tasks total, {first_task_count} are first-time tasks")
            
            # --- ALL TASKS ---
            st.markdown("### All Tasks")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                avg_claim_to_review = cycle_df['hours_claimed_to_review'].mean()
                st.metric(
                    "Avg Work Time",
                    f"{avg_claim_to_review:.1f}h" if pd.notna(avg_claim_to_review) else "N/A",
                    help="Claimed → Ready for Review"
                )
            
            with col2:
                avg_review_to_merged = cycle_df['hours_review_to_merged'].mean()
                st.metric(
                    "Avg Review Time",
                    f"{avg_review_to_merged:.1f}h" if pd.notna(avg_review_to_merged) else "N/A",
                    help="Ready for Review → Merged"
                )
            
            with col3:
                avg_total = cycle_df['hours_total_cycle'].mean()
                st.metric(
                    "Avg Total Cycle",
                    f"{avg_total:.1f}h" if pd.notna(avg_total) else "N/A",
                    help="Claimed → Merged"
                )
            
            # --- EXCLUDING FIRST TASKS ---
            st.markdown("### Excluding First Tasks")
            st.caption("*First task = earliest claimed task per expert (learning curve excluded)*")
            
            if not cycle_df_no_first.empty:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    avg_claim_to_review_nf = cycle_df_no_first['hours_claimed_to_review'].mean()
                    delta_work = None
                    if pd.notna(avg_claim_to_review_nf) and pd.notna(avg_claim_to_review):
                        delta_work = avg_claim_to_review_nf - avg_claim_to_review
                    st.metric(
                        "Avg Work Time",
                        f"{avg_claim_to_review_nf:.1f}h" if pd.notna(avg_claim_to_review_nf) else "N/A",
                        delta=f"{delta_work:+.1f}h" if delta_work else None,
                        delta_color="inverse",
                        help="Claimed → Ready for Review (excl. first tasks)"
                    )
                
                with col2:
                    avg_review_to_merged_nf = cycle_df_no_first['hours_review_to_merged'].mean()
                    delta_review = None
                    if pd.notna(avg_review_to_merged_nf) and pd.notna(avg_review_to_merged):
                        delta_review = avg_review_to_merged_nf - avg_review_to_merged
                    st.metric(
                        "Avg Review Time",
                        f"{avg_review_to_merged_nf:.1f}h" if pd.notna(avg_review_to_merged_nf) else "N/A",
                        delta=f"{delta_review:+.1f}h" if delta_review else None,
                        delta_color="inverse",
                        help="Ready for Review → Merged (excl. first tasks)"
                    )
                
                with col3:
                    avg_total_nf = cycle_df_no_first['hours_total_cycle'].mean()
                    delta_total = None
                    if pd.notna(avg_total_nf) and pd.notna(avg_total):
                        delta_total = avg_total_nf - avg_total
                    st.metric(
                        "Avg Total Cycle",
                        f"{avg_total_nf:.1f}h" if pd.notna(avg_total_nf) else "N/A",
                        delta=f"{delta_total:+.1f}h" if delta_total else None,
                        delta_color="inverse",
                        help="Claimed → Merged (excl. first tasks)"
                    )
            else:
                st.info("Not enough data (all tasks are first tasks)")
            
            st.markdown("---")
            
            # Cycle time by expert (with both versions)
            st.markdown("#### Cycle Times by Expert")
            
            # All tasks
            cycle_by_expert = cycle_df.groupby('expert_name').agg({
                'hours_claimed_to_review': 'mean',
                'hours_review_to_merged': 'mean',
                'hours_total_cycle': 'mean',
                'task_id': 'count'
            }).reset_index()
            cycle_by_expert.columns = ['Expert', 'Avg Work (h)', 'Avg Review (h)', 'Avg Total (h)', 'Tasks']
            
            # Excluding first tasks
            if not cycle_df_no_first.empty:
                cycle_by_expert_nf = cycle_df_no_first.groupby('expert_name').agg({
                    'hours_claimed_to_review': 'mean',
                    'hours_review_to_merged': 'mean',
                    'hours_total_cycle': 'mean',
                    'task_id': 'count'
                }).reset_index()
                cycle_by_expert_nf.columns = ['Expert', 'Work (No 1st)', 'Review (No 1st)', 'Total (No 1st)', 'Tasks (No 1st)']
                
                # Merge both
                cycle_by_expert = cycle_by_expert.merge(cycle_by_expert_nf, on='Expert', how='left')
            
            cycle_by_expert = cycle_by_expert.sort_values('Avg Total (h)')
            
            st.dataframe(
                cycle_by_expert,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Avg Work (h)": st.column_config.NumberColumn(format="%.1f"),
                    "Avg Review (h)": st.column_config.NumberColumn(format="%.1f"),
                    "Avg Total (h)": st.column_config.NumberColumn(format="%.1f"),
                    "Work (No 1st)": st.column_config.NumberColumn(format="%.1f"),
                    "Review (No 1st)": st.column_config.NumberColumn(format="%.1f"),
                    "Total (No 1st)": st.column_config.NumberColumn(format="%.1f"),
                }
            )
        else:
            st.info("No merged tasks to calculate cycle times")
    else:
        st.info("No task data available")

# --------------------------------------------
# TAB 3: Task Details
# --------------------------------------------
with tab3:
    st.subheader("Task Details")
    
    if not filtered_tasks.empty:
        # Status counts
        status_counts = filtered_tasks['task_status'].value_counts()
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("#### Status Breakdown")
            for status, count in status_counts.items():
                st.write(f"**{status}**: {count}")
        
        with col2:
            fig_status = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title='Task Status Distribution',
                hole=0.4
            )
            fig_status.update_layout(height=300)
            st.plotly_chart(fig_status, use_container_width=True)
        
        st.markdown("---")
        
        # Full task table
        st.markdown("#### All Tasks")
        display_cols = ['title', 'expert_name', 'reviewer_name', 'task_status', 
                       'time_claimed', 'time_merged', 'unique_reviewers', 'hours_total_cycle']
        display_df = filtered_tasks[display_cols].copy()
        display_df['time_claimed'] = display_df['time_claimed'].dt.strftime('%Y-%m-%d')
        display_df['time_merged'] = display_df['time_merged'].dt.strftime('%Y-%m-%d')
        display_df.columns = ['Title', 'Expert', 'Reviewer', 'Status', 'Claimed', 'Merged', 'Reviewers', 'Cycle (h)']
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Cycle (h)": st.column_config.NumberColumn(format="%.1f"),
            }
        )
        
        # Download button
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Task Data",
            csv,
            f"tasks_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
    else:
        st.info("No task data available")

# --------------------------------------------
# TAB 4: Charts
# --------------------------------------------
with tab4:
    st.subheader("Visualizations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Hours logged bar chart
        if not time_logs.empty:
            top_n = st.slider("Top N Experts by Hours", 5, 20, 10)
            top_experts = time_logs.head(top_n)
            
            fig_hours = px.bar(
                top_experts,
                x='employee_name',
                y='hours',
                title=f'Top {top_n} Experts by Hours Logged',
                color='hours',
                color_continuous_scale='Blues'
            )
            fig_hours.update_layout(
                xaxis_title='Expert',
                yaxis_title='Hours',
                xaxis_tickangle=-45,
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig_hours, use_container_width=True)
        else:
            st.info("No time log data available")
    
    with col2:
        # Tasks by expert
        if not filtered_tasks.empty:
            tasks_by_expert = filtered_tasks.groupby('expert_name').size().reset_index(name='count')
            tasks_by_expert = tasks_by_expert.sort_values('count', ascending=False).head(10)
            
            fig_tasks = px.bar(
                tasks_by_expert,
                x='expert_name',
                y='count',
                title='Top 10 Experts by Task Count',
                color='count',
                color_continuous_scale='Greens'
            )
            fig_tasks.update_layout(
                xaxis_title='Expert',
                yaxis_title='Tasks',
                xaxis_tickangle=-45,
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig_tasks, use_container_width=True)
        else:
            st.info("No task data available")
    
    # Reviewer activity
    if not filtered_tasks.empty:
        st.markdown("#### Reviewer Activity")
        reviews_by_reviewer = filtered_tasks[filtered_tasks['reviewer_name'] != ''].groupby('reviewer_name').size().reset_index(name='reviews_done')
        reviews_by_reviewer = reviews_by_reviewer.sort_values('reviews_done', ascending=False)
        
        if not reviews_by_reviewer.empty:
            fig_reviews = px.bar(
                reviews_by_reviewer.head(10),
                x='reviewer_name',
                y='reviews_done',
                title='Top Reviewers by Tasks Reviewed',
                color='reviews_done',
                color_continuous_scale='Oranges'
            )
            fig_reviews.update_layout(
                xaxis_title='Reviewer',
                yaxis_title='Tasks Reviewed',
                xaxis_tickangle=-45,
                height=350,
                showlegend=False
            )
            st.plotly_chart(fig_reviews, use_container_width=True)
    
# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
