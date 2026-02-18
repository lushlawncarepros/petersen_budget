import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Forced Horizontal Rows & Mobile Polish
st.markdown("""
    <style>
    /* Force rows to stay horizontal even on narrow mobile screens */
    .row-container {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        padding: 10px 0;
        border-bottom: 1px solid #f0f2f6;
        width: 100%;
    }
    .col-date { width: 15%; font-size: 0.75rem; color: #888; }
    .col-info { width: 50%; font-size: 0.9rem; line-height: 1.2; }
    .col-amt { width: 25%; text-align: right; font-weight: bold; font-size: 0.95rem; }
    .col-edit { width: 10%; text-align: right; }

    /* Button Styling */
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
    .edit-btn-small button { 
        height: 2em !important; 
        padding: 0 5px !important; 
        font-size: 0.7rem !important;
        background-color: #f0f2f6 !important;
    }
    
    /* Dialog / Pop-up Styling */
    div[data-testid="stDialog"] { border-radius: 15px; }
    .delete-btn button { background-color: #ff4b4b !important; color: white !important; border: none !important; }
    .update-btn button { background-color: #28a745 !important; color: white !important; border: none !important; }
    
    /* Hide Default Sidebar Nav */
    div[data-testid="stSidebarNav"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENT AUTHENTICATION ---
USERS = {"ethan": "petersen1", "alesa": "petersen2"}

# Logic to remember the user via URL Query Parameters
if "authenticated" not in st.session_state:
    params = st.query_params
    if "user" in params and params["user"] in USERS:
        st.session_state["authenticated"] = True
        st.session_state["user"] = params["user"].capitalize()
    else:
        st.session_state["authenticated"] = False

def login_screen():
    st.title("🔐 Petersen Budget")
    u = st.text_input("Username").lower()
    p = st.text_input("Password", type="password")
    rem = st.checkbox("Remember me on this device", value=True)
    if st.button("Login"):
        if u in USERS and USERS[u] == p:
            st.session_state["authenticated"] = True
            st.session_state["user"] = u.capitalize()
            if rem:
                st.query_params["user"] = u  # Saves 'user=ethan' in the URL
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state["authenticated"]:
    login_screen()
    st.stop()

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource(ttl=60)
def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception:
        return None

conn = get_connection()

def load_data():
    if not conn: return pd.DataFrame(), pd.DataFrame()
    try:
        try:
            t = conn.read(worksheet="transactions", ttl=0)
            if t.empty: t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        except:
            t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        
        try:
            c = conn.read(worksheet="categories", ttl=0)
            if c.empty or "Name" not in c.columns:
                c = pd.DataFrame(columns=["Type", "Name"])
        except:
            c = pd.DataFrame(columns=["Type", "Name"])
            
        if not t.empty:
            t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
            t['Date'] = pd.to_datetime(t['Date'])
        return t, c
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

df_t, df_c = load_data()

def get_cat_list(type_filter):
    if df_c.empty: return []
    return df_c[df_c["Type"] == type_filter]["Name"].unique().tolist()

# --- EDIT/DELETE DIALOG ---
@st.dialog("Edit Transaction")
def edit_dialog(idx, row):
    st.write(f"Editing **{row['Type']}** Entry")
    e_date = st.date_input("Date", row["Date"])
    cats = get_cat_list(row["Type"])
    e_cat = st.selectbox("Category", cats, index=cats.index(row["Category"]) if row["Category"] in cats else 0)
    e_amt = st.number_input("Amount ($)", value=float(row["Amount"]))
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="update-btn">', unsafe_allow_html=True)
        if st.button("Save Changes"):
            df_t.at[idx, "Date"] = e_date.strftime('%Y-%m-%d')
            df_t.at[idx, "Category"] = e_cat
            df_t.at[idx, "Amount"] = e_amt
            conn.update(worksheet="transactions", data=df_t)
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
        if st.button("Delete"):
            updated = df_t.drop(idx)
            conn.update(worksheet="transactions", data=updated)
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- APP LAYOUT ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add", "Visuals", "History"])

with tab1:
    t_type = st.radio("Entry Type", ["Expense", "Income"], horizontal=True)
    with st.form("add_entry", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", clist if clist else ["No categories found"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save to Sheets"):
            if clist:
                new_row = pd.DataFrame([{"Date": f_date.strftime('%Y-%m-%d'), "Type": t_type, "Category": f_cat, "Amount": f_amt, "User": st.session_state["user"]}])
                conn.update(worksheet="transactions", data=pd.concat([df_t, new_row], ignore_index=True))
                st.success("Entry Saved!")
                st.cache_resource.clear()
                st.rerun()

with tab2:
    if not df_t.empty:
        total_in = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        total_ex = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        net = total_in - total_ex
        st.metric("Family Net", f"${net:,.2f}", delta=f"${total_in:,.2f} In")
        st.divider()
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.write("**Expenses**")
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", hole=0.4), use_container_width=True)
        with col_chart2:
            st.write("**Income**")
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", hole=0.4), use_container_width=True)
    else:
        st.info("No data for charts yet.")

with tab3:
    if not df_t.empty:
        # Search functionality
        search = st.text_input("🔍 Filter by Category", "")
        
        # Prepare filtered dataframe
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        if search:
            work_df = work_df[work_df['Category'].str.contains(search, case=False)]
        
        # Header Row
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding-bottom:5px; border-bottom:2px solid #eee; font-weight:bold; color:grey; font-size:0.75rem;">
                <div style="width:15%;">DATE</div>
                <div style="width:50%;">TYPE / CATEGORY</div>
                <div style="width:25%; text-align:right;">AMOUNT</div>
                <div style="width:10%;"></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in work_df.iterrows():
            # Logical Formatting
            is_expense = row['Type'] == 'Expense'
            amt_prefix = "-" if is_expense else "+"
            amt_color = "#dc3545" if is_expense else "#28a745"
            type_icon = "💸" if is_expense else "💰"
            
            # Row Layout
            col_d, col_i, col_a, col_e = st.columns([1.5, 4.5, 3, 1])
            with col_d:
                st.write(f"{row['Date'].strftime('%m/%d')}")
            with col_i:
                st.write(f"{type_icon} {row['Category']}")
            with col_a:
                st.markdown(f"<p style='color:{amt_color}; text-align:right; font-weight:bold;'>{amt_prefix}${row['Amount']:,.0f}</p>", unsafe_allow_html=True)
            with col_e:
                st.markdown('<div class="edit-btn-small">', unsafe_allow_html=True)
                if st.button("Edit", key=f"btn_{i}"):
                    edit_dialog(i, row)
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("History is empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    st.divider()
    st.subheader("Manage Categories")
    c_type = st.selectbox("For Type", ["Expense", "Income"])
    c_new = st.text_input("Add Name")
    if st.button("Add Category"):
        if c_new and c_new not in get_cat_list(c_type):
            new_c_row = pd.DataFrame([{"Type": c_type, "Name": c_new}])
            conn.update(worksheet="categories", data=pd.concat([df_c, new_c_row], ignore_index=True))
            st.success(f"Added {c_new}")
            st.cache_resource.clear()
            st.rerun()

