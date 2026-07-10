import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
import calendar
import plotly.express as px

# ==========================================
# PAGE CONFIGURATION & PREMIUM GLASSMORPHISM UI
# ==========================================
st.set_page_config(page_title="Finance OS Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp {
        background: linear-gradient(rgba(15, 23, 42, 0.85), rgba(15, 23, 42, 0.85)), 
                    url('https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1920&auto=format&fit=crop') no-repeat center center fixed;
        background-size: cover;
        font-family: 'Inter', sans-serif;
        color: #f8fafc;
    }
    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.6) !important;
        backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    div[data-testid="stVerticalBlock"] > div:has(div.stForm), 
    .stTabs, .glass-card, [data-testid="stMetricV9"] {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 20px !important;
        margin-bottom: 15px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }
    h1, h2, h3, h4, h5, h6, label, .stMetric label { color: #f1f5f9 !important; font-weight: 600 !important; }
    .stDataFrame, div[data-testid="stGrid"] { background: rgba(255, 255, 255, 0.02) !important; border-radius: 12px; }
    .stButton>button {
        background: rgba(59, 130, 246, 0.15) !important;
        color: #ffffff !important;
        border: 1px solid rgba(59, 130, 246, 0.4) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: rgba(59, 130, 246, 0.35) !important;
        border-color: #60a5fa !important;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# HYBRID DATABASE ENGINE & MIGRATION CACHE
# ==========================================
IS_POSTGRES = "postgres" in st.secrets

def get_db_connection():
    if IS_POSTGRES:
        import psycopg2
        return psycopg2.connect(st.secrets["postgres"]["url"])
    else:
        import sqlite3
        return sqlite3.connect('finance_v4.db', check_same_thread=False)

# اجرای دیتابیس فقط و فقط یک بار هنگام روشن شدن سرور برای جلوگیری از کرش
@st.cache_resource
def init_db_once():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    id_type = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    cursor.execute(f'''CREATE TABLE IF NOT EXISTS users (id {id_type}, username TEXT UNIQUE, password TEXT)''')
    cursor.execute(f'''CREATE TABLE IF NOT EXISTS income (
                        id {id_type}, user_id INTEGER, source TEXT, amount REAL, inc_type TEXT, 
                        start_month INTEGER, start_year INTEGER, end_month INTEGER, end_year INTEGER, timestamp TEXT)''')
    cursor.execute(f'''CREATE TABLE IF NOT EXISTS fixed_expenses (id {id_type}, user_id INTEGER, name TEXT, amount REAL, month INTEGER, year INTEGER, timestamp TEXT)''')
    cursor.execute(f'''CREATE TABLE IF NOT EXISTS variable_expenses (id {id_type}, user_id INTEGER, category TEXT, description TEXT, amount REAL, month INTEGER, year INTEGER, timestamp TEXT)''')
    
    if IS_POSTGRES:
        cursor.execute('''
            ALTER TABLE income ADD COLUMN IF NOT EXISTS start_month INTEGER DEFAULT 1;
            ALTER TABLE income ADD COLUMN IF NOT EXISTS start_year INTEGER DEFAULT 2025;
            ALTER TABLE income ADD COLUMN IF NOT EXISTS end_month INTEGER DEFAULT 12;
            ALTER TABLE income ADD COLUMN IF NOT EXISTS end_year INTEGER DEFAULT 2030;
        ''')
    else:
        cursor.execute("PRAGMA table_info(income)")
        columns = [info[1] for info in cursor.fetchall()]
        if "start_month" not in columns:
            cursor.execute("ALTER TABLE income ADD COLUMN start_month INTEGER DEFAULT 1")
            cursor.execute("ALTER TABLE income ADD COLUMN start_year INTEGER DEFAULT 2025")
            cursor.execute("ALTER TABLE income ADD COLUMN end_month INTEGER DEFAULT 12")
            cursor.execute("ALTER TABLE income ADD COLUMN end_year INTEGER DEFAULT 2030")
            
    conn.commit()
    conn.close()
    return True

# راه‌اندازی اولیه
init_db_once()

# ایجاد کانکشن اختصاصی برای هر سشن (بدون نیاز به بستن دستی)
conn = get_db_connection()
cursor = conn.cursor()

def db_execute(query, params=()):
    if IS_POSTGRES:
        query = query.replace('?', '%s')
    cursor.execute(query, params)

# ==========================================
# AUTHENTICATION & SESSION FUNCTIONS
# ==========================================
def make_hashes(password): 
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text): 
    return make_hashes(password) == hashed_text

if "inc_key" not in st.session_state: st.session_state.inc_key = 0
if "fix_key" not in st.session_state: st.session_state.fix_key = 0
if "var_key" not in st.session_state: st.session_state.var_key = 0

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['username'] = ""
    st.session_state['auth_mode'] = "Login"

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; margin-top: 5rem; margin-bottom: 2rem;'>Finance OS Pro</h2>", unsafe_allow_html=True)
        mode = st.radio("Select Authentication Mode:", ["Login", "Sign Up"], horizontal=True, index=0 if st.session_state['auth_mode'] == "Login" else 1)
        
        if mode == "Login":
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type='password')
                submitted = st.form_submit_button("Log In", use_container_width=True)
                if submitted:
                    db_execute('SELECT id, password FROM users WHERE username = ?', (username,))
                    user_data = cursor.fetchone()
                    if user_data and check_hashes(password, user_data[1]):
                        st.session_state['logged_in'] = True
                        st.session_state['user_id'] = user_data[0]
                        st.session_state['username'] = username
                        st.rerun()
                    else:
                        st.error("Invalid Username or Password.")
                        
        elif mode == "Sign Up":
            with st.form("signup_form"):
                new_user = st.text_input("Choose Username")
                new_password = st.text_input("Choose Password", type='password')
                submitted = st.form_submit_button("Create Premium Account", use_container_width=True)
                if submitted:
                    try:
                        db_execute('INSERT INTO users(username, password) VALUES (?,?)', (new_user, make_hashes(new_password)))
                        conn.commit()
                        st.success("Account created successfully! Switching to Login Mode...")
                        st.session_state['auth_mode'] = "Login"
                        st.rerun()
                    except Exception:
                        st.error("Username already taken or database error.")
    st.stop()

# ==========================================
# CORE CALCULATION ENGINE
# ==========================================
user_id = st.session_state['user_id']

def get_monthly_income(m, y):
    db_execute('SELECT amount, inc_type, start_month, start_year, end_month, end_year FROM income WHERE user_id = ?', (user_id,))
    records = cursor.fetchall()
    total_monthly = 0.0
    for amount, inc_type, sm, sy, em, ey in records:
        start_valid = (sy < y) or (sy == y and sm <= m)
        end_valid = (ey > y) or (ey == y and em >= m)
        if start_valid and end_valid:
            if inc_type == "Annual": total_monthly += (amount / 12)
            else: total_monthly += amount
    return total_monthly

def get_total_expenses(m, y):
    db_execute('SELECT SUM(amount) FROM fixed_expenses WHERE user_id = ? AND month = ? AND year = ?', (user_id, m, y))
    res_f = cursor.fetchone()
    fixed = res_f[0] or 0.0 if res_f else 0.0
    
    db_execute('SELECT SUM(amount) FROM variable_expenses WHERE user_id = ? AND month = ? AND year = ?', (user_id, m, y))
    res_v = cursor.fetchone()
    var = res_v[0] or 0.0 if res_v else 0.0
    return fixed + var

def get_previous_savings(current_m, current_y):
    total_savings = 0.0
    for m in range(1, current_m):
        monthly_inc = get_monthly_income(m, current_y)
        m_expenses = get_total_expenses(m, current_y)
        total_savings += (monthly_inc - m_expenses)
    return total_savings

# --- SIDEBAR COMPONENT ---
now = datetime.now()
st.sidebar.markdown(f"### 📅 {now.strftime('%A, %d %B %Y')}")
st.sidebar.markdown(f"**Session Operator:** {st.session_state['username']}")
st.sidebar.divider()

st.sidebar.markdown("### 🔍 Historical Archive")
sel_year = st.sidebar.selectbox("Select Year", [now.year - 1, now.year, now.year + 1], index=1)
sel_month = st.sidebar.selectbox("Select Month", list(range(1, 13)), index=now.month - 1, format_func=lambda x: calendar.month_name[x])

m_income = get_monthly_income(sel_month, sel_year)
m_expenses = get_total_expenses(sel_month, sel_year)
m_balance = m_income - m_expenses

st.sidebar.divider()
st.sidebar.markdown(f"### 📊 Quick Metrics: {calendar.month_name[sel_month]}")
st.sidebar.metric("Income Pool", f"€ {m_income:,.2f}")
st.sidebar.metric("Total Debits", f"€ {m_expenses:,.2f}")
st.sidebar.metric("Net Balance", f"€ {m_balance:,.2f}")

st.sidebar.divider()
if st.sidebar.button("🚪 Terminate Session", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("PRO FINANCIAL MANAGEMENT ENVIRONMENT")
st.markdown(f"**Active Workspace Context:** {calendar.month_name[sel_month]} {sel_year}")

tab_dash, tab_inc, tab_fix, tab_var = st.tabs([
    "📈 Operational Dashboard & Analytics", 
    "💼 Income Management", 
    "📌 Fixed Debits Input", 
    "🛒 Variable Debits Input"
])

# ==========================================
# TAB 1: OPERATIONAL DASHBOARD & ANALYTICS
# ==========================================
with tab_dash:
    savings = get_previous_savings(sel_month, sel_year)
    total_available = m_balance + savings
    
    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric("Income Allocation", f"€ {m_income:,.2f}")
    r1c2.metric("Monthly Expenses", f"€ {m_expenses:,.2f}")
    r1c3.metric("Month's Net Balance", f"€ {m_balance:,.2f}")
    
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    
    r2c1, r2c2 = st.columns(2)
    r2c1.metric("Archived Savings Pool", f"€ {savings:,.2f}")
    balance_color = "normal" if total_available >= 0 else "inverse"
    r2c2.metric("Total Capital Available", f"€ {total_available:,.2f}", delta=f"€ {total_available:,.2f}", delta_color=balance_color)
    
    st.divider()
    
    if m_income > 0:
        spend_percent = (m_expenses / m_income) * 100
        st.markdown(f"#### ⚡ Budget Consumption Velocity: **{spend_percent:.1f}%**")
        bar_color = "#10b981" if spend_percent <= 70 else ("#f59e0b" if spend_percent <= 90 else "#ef4444")
        capped_percent = min(spend_percent, 100)
        st.markdown(f"""
            <div style="width: 100%; background-color: rgba(255,255,255,0.05); border-radius: 10px; margin-top: 10px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.1);">
                <div style="width: {capped_percent}%; background-color: {bar_color}; height: 16px; border-radius: 10px; transition: width 0.4s ease;"></div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Establish an active Income Stream first to visualize budget velocity metrics.")
        
    st.divider()
    
    st.markdown("### 📊 Distribution Analysis")
    db_execute('SELECT name, amount FROM fixed_expenses WHERE user_id = ? AND month = ? AND year = ?', (user_id, sel_month, sel_year))
    f_data = cursor.fetchall()
    db_execute('SELECT category, SUM(amount) FROM variable_expenses WHERE user_id = ? AND month = ? AND year = ? GROUP BY category', (user_id, sel_month, sel_year))
    v_data = cursor.fetchall()
    
    chart_data = [{'Segment': row[0], 'Amount': row[1]} for row in f_data] + [{'Segment': row[0], 'Amount': row[1]} for row in v_data]
                 
    if chart_data and sum(item['Amount'] for item in chart_data) > 0:
        df_chart = pd.DataFrame(chart_data)
        soft_colors = ['#A7F3D0', '#93C5FD', '#FDE68A', '#FCA5A5', '#C084FC', '#F472B6', '#CBD5E1']
        fig = px.pie(df_chart, values='Amount', names='Segment', hole=0.4, color_discrete_sequence=soft_colors)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Awaiting structural financial input data to calculate charts.")
        
    st.divider()
    
    st.markdown("### 📜 Granular Ledger Reports")
    st.markdown("#### 🔹 Fixed Expenses Breakdown")
    db_execute('SELECT name, amount FROM fixed_expenses WHERE user_id = ? AND month = ? AND year = ?', (user_id, sel_month, sel_year))
    f_ledger = cursor.fetchall()
    if f_ledger:
        df_f_ledger = pd.DataFrame(f_ledger, columns=['Name', 'Amount (€)'])
        total_f_row = pd.DataFrame([['TOTAL FIXED', df_f_ledger['Amount (€)'].sum()]], columns=['Name', 'Amount (€)'])
        df_f_ledger = pd.concat([df_f_ledger, total_f_row], ignore_index=True)
        st.dataframe(df_f_ledger, hide_index=True, use_container_width=True)
    else:
        st.caption("No fixed entries recorded.")
        
    st.markdown("<br>", unsafe_allow_html=True)
        
    st.markdown("#### 🔹 Variable Expenses Breakdown")
    db_execute('SELECT category, description, amount FROM variable_expenses WHERE user_id = ? AND month = ? AND year = ?', (user_id, sel_month, sel_year))
    v_ledger = cursor.fetchall()
    if v_ledger:
        df_v_ledger = pd.DataFrame(v_ledger, columns=['Category', 'Description', 'Amount (€)'])
        for cat in df_v_ledger['Category'].unique():
            st.markdown(f"**Category: {cat}**")
            df_sub = df_v_ledger[df_v_ledger['Category'] == cat][['Description', 'Amount (€)']]
            total_v_row = pd.DataFrame([['TOTAL SEGMENT', df_sub['Amount (€)'].sum()]], columns=['Description', 'Amount (€)'])
            df_sub = pd.concat([df_sub, total_v_row], ignore_index=True)
            st.dataframe(df_sub, hide_index=True, use_container_width=True)
    else:
        st.caption("No variable entries recorded.")

# ==========================================
# TAB 2: INCOME STRATEGY ARCHITECTURE
# ==========================================
with tab_inc:
    st.markdown("### Add Income Vector")
    with st.container():
        with st.form(f"add_income_pro_{st.session_state.inc_key}"):
            col_type, col_name, col_val = st.columns([1, 2, 1.5])
            i_type = col_type.radio("Income Horizon Type:", ["Annual", "Monthly"], horizontal=True)
            i_src = col_name.text_input("Income Vector Title (e.g., Main Salary, Grant)")
            i_amt = col_val.number_input("Absolute Numerical Amount (€)", min_value=0.0, step=100.0)
            
            st.markdown("**Contract Validity / Duration Window:**")
            col_sm, col_sy, col_em, col_ey = st.columns(4)
            start_m = col_sm.selectbox("Start Month", list(range(1, 13)), index=0, format_func=lambda x: calendar.month_name[x])
            start_y = col_sy.selectbox("Start Year", [2025, 2026, 2027, 2028, 2029], index=1)
            end_m = col_em.selectbox("End Month", list(range(1, 13)), index=11, format_func=lambda x: calendar.month_name[x])
            end_y = col_ey.selectbox("End Year", [2025, 2026, 2027, 2028, 2029], index=2)
            
            if st.form_submit_button("Inject Income Asset"):
                if i_src and i_amt > 0:
                    db_execute('''INSERT INTO income (user_id, source, amount, inc_type, start_month, start_year, end_month, end_year, timestamp) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                               (user_id, i_src, i_amt, i_type, start_m, start_y, end_m, end_y, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success(f"Successfully committed {i_type} asset vector with timeline.")
                    st.session_state.inc_key += 1
                    st.rerun()

    st.markdown("### Active Income Infrastructure Asset Matrix")
    db_execute('SELECT id, source, amount, inc_type, start_month, start_year, end_month, end_year FROM income WHERE user_id = ?', (user_id,))
    raw_inc = cursor.fetchall()
    if raw_inc:
        processed_inc_data = []
        for rid, src, amt, itype, sm, sy, em, ey in raw_inc:
            ann_equiv = amt if itype == "Annual" else amt * 12
            mon_equiv = amt / 12 if itype == "Annual" else amt
            duration_text = f"{calendar.month_name[sm]} {sy} ➔ {calendar.month_name[em]} {ey}"
            processed_inc_data.append([rid, src, itype, amt, duration_text, ann_equiv, mon_equiv])
            
        df_inc_matrix = pd.DataFrame(processed_inc_data, columns=['Asset ID', 'Source Vector', 'Horizon Type', 'Stated Amount (€)', 'Contract Window', 'Annual Equiv (€)', 'Monthly Equiv (€)'])
        total_row = pd.DataFrame([['TOTALS', '', '', 0.0, '', df_inc_matrix['Annual Equiv (€)'].sum(), df_inc_matrix['Monthly Equiv (€)'].sum()]], columns=['Asset ID', 'Source Vector', 'Horizon Type', 'Stated Amount (€)', 'Contract Window', 'Annual Equiv (€)', 'Monthly Equiv (€)'])
        df_display_inc = pd.concat([df_inc_matrix, total_row], ignore_index=True)
        st.dataframe(df_display_inc, hide_index=True, use_container_width=True)
        
        with st.expander("✏️ Administrative Modifications & Asset Liquidation"):
            col_id, col_src, col_amt, col_action = st.columns([1, 2, 2, 2])
            target_id = col_id.selectbox("Select Asset ID to Modify", df_inc_matrix['Asset ID'], key='ctrl_inc_id')
            selected_asset = df_inc_matrix[df_inc_matrix['Asset ID'] == target_id].iloc[0]
            
            up_src = col_src.text_input("Update Source Title", value=selected_asset['Source Vector'])
            up_amt = col_amt.number_input("Update Numeric Value (€)", value=float(selected_asset['Stated Amount (€)']), step=100.0)
            
            if col_action.button("Commit Strategic Update", key='btn_inc_upd', use_container_width=True):
                db_execute('UPDATE income SET source=?, amount=? WHERE id=?', (up_src, up_amt, target_id))
                conn.commit()
                st.rerun()
            if col_action.button("Liquidate/Delete Asset", key='btn_inc_del', type="primary", use_container_width=True):
                db_execute('DELETE FROM income WHERE id=?', (target_id,))
                conn.commit()
                st.rerun()
    else:
        st.info("System awaiting population of Income Infrastructure vectors.")

# ==========================================
# TAB 3: FIXED DEBITS MATRIX
# ==========================================
with tab_fix:
    st.markdown(f"### Log Fixed Structural Debit Vector ({calendar.month_name[sel_month]} {sel_year})")
    with st.container():
        with st.form(f"add_fixed_debit_{st.session_state.fix_key}"):
            col_fn, col_fa = st.columns(2)
            fixed_title = col_fn.text_input("Debit Label Identifier (e.g., Rent, Utility Bond)")
            fixed_val = col_fa.number_input("Absolute Volume Debit (€)", min_value=0.0, step=10.0)
            if st.form_submit_button("Commit Fixed Structural Entry"):
                if fixed_title and fixed_val > 0:
                    db_execute('INSERT INTO fixed_expenses (user_id, name, amount, month, year, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
                               (user_id, fixed_title, fixed_val, sel_month, sel_year, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success("Fixed structural entry synchronized.")
                    st.session_state.fix_key += 1
                    st.rerun()

    st.markdown("### Active Fixed Debit Structural Matrix")
    db_execute('SELECT id, name, amount, timestamp FROM fixed_expenses WHERE user_id = ? AND month = ? AND year = ?', (user_id, sel_month, sel_year))
    raw_fix = cursor.fetchall()
    if raw_fix:
        df_fix_matrix = pd.DataFrame(raw_fix, columns=['Debit ID', 'Identifier Label', 'Absolute Cost (€)', 'Temporal Timestamp'])
        total_fix_row = pd.DataFrame([['TOTALS', '', df_fix_matrix['Absolute Cost (€)'].sum(), '']], columns=['Debit ID', 'Identifier Label', 'Absolute Cost (€)', 'Temporal Timestamp'])
        df_display_fix = pd.concat([df_fix_matrix, total_fix_row], ignore_index=True)
        st.dataframe(df_display_fix, hide_index=True, use_container_width=True)
        
        with st.expander("✏️ Structural Adjustments & Debit Deletion"):
            col_id, col_lbl, col_val, col_act = st.columns([1, 2, 2, 2])
            target_f_id = col_id.selectbox("Select Debit ID to Modify", df_fix_matrix['Debit ID'], key='ctrl_fix_id')
            selected_fix = df_fix_matrix[df_fix_matrix['Debit ID'] == target_f_id].iloc[0]
            
            up_f_lbl = col_lbl.text_input("Update Identifier Label", value=selected_fix['Identifier Label'])
            up_f_val = col_val.number_input("Update Cost Value (€)", value=float(selected_fix['Absolute Cost (€)']), step=10.0)
            
            if col_act.button("Modify Entry Structure", key='btn_fix_upd', use_container_width=True):
                db_execute('UPDATE fixed_expenses SET name=?, amount=? WHERE id=?', (up_f_lbl, up_f_val, target_f_id))
                conn.commit()
                st.rerun()
            if col_act.button("Wipe Entry Record", key='btn_fix_del', type="primary", use_container_width=True):
                db_execute('DELETE FROM fixed_expenses WHERE id=?', (target_f_id,))
                conn.commit()
                st.rerun()
    else:
        st.info("No fixed infrastructure commitments configured for this specific operational month.")

# ==========================================
# TAB 4: VARIABLE DEBITS MATRIX
# ==========================================
with tab_var:
    st.markdown(f"### Log Dynamic Variable Flow Debit ({calendar.month_name[sel_month]} {sel_year})")
    categories = ["Groceries & Food", "Household Items", "Entertainment & Cafe", "Pets", "Other"]
    
    with st.container():
        with st.form(f"add_var_debit_{st.session_state.var_key}"):
            col_v1, col_v2, col_v3 = st.columns([1.2, 2, 1])
            v_category_selection = col_v1.selectbox("Structural Segment Classifier", categories)
            v_description_field = col_v2.text_input("Operational Context Details")
            v_amount_field = col_v3.number_input("Transaction Cash Metric (€)", min_value=0.0, step=5.0)
            
            if st.form_submit_button("Commit Transaction Entry"):
                if v_amount_field > 0 and v_description_field:
                    db_execute('INSERT INTO variable_expenses (user_id, category, description, amount, month, year, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)',
                               (user_id, v_category_selection, v_description_field, v_amount_field, sel_month, sel_year, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success("Variable flow debit updated globally.")
                    st.session_state.var_key += 1
                    st.rerun()

    st.markdown("### Fragmented Category Segment Matrix Reports")
    db_execute('SELECT id, category, description, amount, timestamp FROM variable_expenses WHERE user_id = ? AND month = ? AND year = ?', (user_id, sel_month, sel_year))
    raw_var = cursor.fetchall()
    
    if raw_var:
        df_var_matrix = pd.DataFrame(raw_var, columns=['Transaction ID', 'Segment Category', 'Description Ledger', 'Absolute Value (€)', 'Timestamp'])
        for current_segment in df_var_matrix['Segment Category'].unique():
            st.markdown(f"#### 📦 Ledger Segment: {current_segment}")
            df_segmented_view = df_var_matrix[df_var_matrix['Segment Category'] == current_segment][['Transaction ID', 'Description Ledger', 'Absolute Value (€)', 'Timestamp']]
            subtotal_row = pd.DataFrame([['SEGMENT TOTAL', '', df_segmented_view['Absolute Value (€)'].sum(), '']], columns=['Transaction ID', 'Description Ledger', 'Absolute Value (€)', 'Timestamp'])
            df_display_segmented = pd.concat([df_segmented_view, subtotal_row], ignore_index=True)
            st.dataframe(df_display_segmented, hide_index=True, use_container_width=True)
            
        with st.expander("✏️ Dynamic Ledger Refactoring Controls"):
            col_id, col_cat, col_desc, col_amt, col_act = st.columns([1, 1.5, 2, 1.5, 2])
            target_v_id = col_id.selectbox("Select Transaction ID to Modify", df_var_matrix['Transaction ID'], key='ctrl_var_id')
            selected_var = df_var_matrix[df_var_matrix['Transaction ID'] == target_v_id].iloc[0]
            
            up_v_cat = col_cat.selectbox("Change Category Segment", categories, index=categories.index(selected_var['Segment Category']))
            up_v_dsc = col_desc.text_input("Modify Narrative Description", value=selected_var['Description Ledger'])
            up_v_amt = col_amt.number_input("Modify Numerical Metric (€)", value=float(selected_var['Absolute Value (€)']), step=5.0)
            
            if col_act.button("Modify Matrix Entry", key='btn_var_upd', use_container_width=True):
                db_execute('UPDATE variable_expenses SET category=?, description=?, amount=? WHERE id=?', (up_v_cat, up_v_dsc, up_v_amt, target_v_id))
                conn.commit()
                st.rerun()
            if col_act.button("Purge Entry Completely", key='btn_var_del', type="primary", use_container_width=True):
                db_execute('DELETE FROM variable_expenses WHERE id=?', (target_v_id,))
                conn.commit()
                st.rerun()
    else:
        st.info("No variable transactional workflows initiated for this operational context time period.")
