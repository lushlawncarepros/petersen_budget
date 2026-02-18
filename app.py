import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Strict Mobile Rows & Layout
st.markdown("""
    <style>
    /* Force horizontal rows on S25 and Tablets */
    .ledger-row {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 12px 5px;
        border-bottom: 1px solid #eee;
        width: 100%;
    }
    .l-date { width: 18%; font-size: 0.8rem; color: #888; flex-shrink: 0; }
    .l-cat  { width: 52%; font-size: 0.95rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .l-amt  { width: 30%; font-size: 0.95rem; font-weight: bold; text-align: right; flex-shrink: 0; }

    /* Button Styling */
    .stButton>button { width: 100%; border-radius: 12px; height: 3.2em; background-color: #007bff; color: white; border: none; }
    div[data-testid="stSidebarNav"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# --- AUTHENTICATION ---
USERS = {"ethan": "petersen1", "alesa": "petersen2"}

if "authenticated" not in st.session_state:
    params = st.query_params
    if "user" in params and params["user"] in USERS:
        st.session_state["authenticated"] = True
        st.session_state["user"] = params["user"].capitalize()
    else:
        st.session_state["authenticated"] = False

def login_screen():
    st.title("🔐 Petersen Budget Login")
    u = st.text_input("Username").lower()
    p = st.text_input("Password", type="password")
    rem = st.checkbox("Remember me", value=True)
    if st.button("Login"):
        if u in USERS and USERS[u] == p:
            st.session_state["authenticated"] = True
            st.session_state["user"] = u.capitalize()
            if rem: st.query_params["user"] = u
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state["authenticated"]:
    login_screen()
    st.stop()

# --- DATA CONNECTION ---
# We use st.connection directly without extra caching wrappers to ensure freshness
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # ttl=0 forces a fresh download from Google every time the page refreshes
        t = conn.read(worksheet="transactions", ttl=0)
        c = conn.read(worksheet="categories", ttl=0)
        
        if t is None or t.empty:
            t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        if c is None or c.empty:
            c = pd.DataFrame(columns=["Type", "Name"])
        
        # Ensure numbers and dates are processed correctly
        t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
        t['Date'] = pd.to_datetime(t['Date'], errors='coerce')
        t = t.dropna(subset=['Date'])
        return t, c
    except Exception:
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

df_t, df_c = load_data()

def get_cat_list(t_filter):
    if df_c.empty: return []
    return sorted(df_c[df_c["Type"] == t_filter]["Name"].unique().tolist())

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tith" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    if "salary" in n or "pay" in n: return "💵"
    return "💸" if row_type == "Expense" else "💰"

# --- MAIN INTERFACE ---
st.title("📊 Petersen Family Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("Add New Transaction")
    t_type = st.radio("Is this an Income or Expense?", ["Expense", "Income"], horizontal=True)
    
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("Save to Google Sheets"):
            if f_clist:
                # 1. FETCH FRESH: Get the absolute latest sheet before adding to it
                latest_sheet = conn.read(worksheet="transactions", ttl=0)
                if latest_sheet is None: 
                    latest_sheet = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
                
                # 2. CREATE: Build the new transaction row
                new_entry = pd.DataFrame([{
                    "Date": f_date.strftime('%Y-%m-%d'),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                
                # 3. APPEND: Combine the old list with the new entry
                final_ledger = pd.concat([latest_sheet, new_entry], ignore_index=True)
                
                # 4. PUSH: Overwrite the worksheet with the full updated list
                conn.update(worksheet="transactions", data=final_ledger)
                
                st.success(f"Successfully recorded {f_cat}!")
                st.cache_resource.clear() # Clear all caches to force a total reload
                st.rerun()
            else:
                st.error("Please add a category in the sidebar first!")

with tab2:
    if not df_t.empty:
        inc_sum = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp_sum = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Family Net Balance", f"${(inc_sum - exp_sum):,.2f}", delta=f"${inc_sum:,.2f} Total Income")
        st.divider()
        col_ex, col_in = st.columns(2)
        with col_ex:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: 
                st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with col_in:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: 
                st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("No data logged yet.")

with tab3:
    st.subheader("Transaction History")
    st.caption("Showing all recorded transactions (no filters).")
    
    if not df_t.empty:
        # Sort so the newest transactions are always at the top
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        
        # Column Headers
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.75rem;">
                <div style="width:18%;">DATE</div>
                <div style="width:52%;">CATEGORY</div>
                <div style="width:30%; text-align:right;">AMOUNT</div>
            </div>
        """, unsafe_allow_html=True)

        # Ledger Rows
        for i, row in work_df.iterrows():
            is_expense = row['Type'] == 'Expense'
            color = "#dc3545" if is_expense else "#28a745"
            prefix = "-" if is_expense else "+"
            icon = get_icon(row['Category'], row['Type'])
            
            st.markdown(f"""
                <div class="ledger-row">
                    <div class="l-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="l-cat">{row['Category']} {icon}</div>
                    <div class="l-amt" style="color:{color};">{prefix}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("The ledger is currently empty. Try adding a transaction in the first tab.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    st.divider()
    st.header("Manage Categories")
    c_type = st.selectbox("Type", ["Expense", "Income"])
    c_name = st.text_input("New Category Name")
    if st.button("Add Category"):
        if c_name and c_name not in get_cat_list(c_type):
            latest_cats = conn.read(worksheet="categories", ttl=0)
            new_cat_row = pd.DataFrame([{"Type": c_type, "Name": c_name}])
            updated_cats = pd.concat([latest_cats, new_cat_row], ignore_index=True)
            conn.update(worksheet="categories", data=updated_cats)
            st.success(f"Added {c_name}!")
            st.cache_resource.clear()
            st.rerun()

