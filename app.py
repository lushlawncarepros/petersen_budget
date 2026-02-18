import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Ultra-Compact Mobile View & Persistent Styling
st.markdown("""
    <style>
    /* Force Horizontal Rows on Mobile */
    .t-row-container {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #f0f2f6;
        font-size: 0.85rem;
    }
    .t-date { width: 15%; color: #888; font-family: monospace; }
    .t-cat { width: 45%; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 5px; }
    .t-amt { width: 25%; text-align: right; font-weight: bold; color: #007bff; }
    .t-btn { width: 15%; text-align: right; }
    
    /* Login & Buttons */
    .stButton>button { width: 100%; border-radius: 10px; transition: 0.2s; }
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* Dialog Styling */
    div[data-testid="stDialog"] { border-radius: 15px; }
    .delete-btn button { background-color: #ff4b4b !important; color: white !important; border: none !important; }
    .update-btn button { background-color: #28a745 !important; color: white !important; border: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENT AUTHENTICATION ---
USERS = {"ethan": "petersen1", "alesa": "petersen2"}

# Check if we have a "token" in the URL to auto-login
if "authenticated" not in st.session_state:
    query_params = st.query_params
    if "user" in query_params and query_params["user"] in USERS:
        st.session_state["authenticated"] = True
        st.session_state["user"] = query_params["user"].capitalize()
    else:
        st.session_state["authenticated"] = False

def login():
    st.title("🔐 Petersen Budget")
    user_input = st.text_input("Username").lower()
    pass_input = st.text_input("Password", type="password")
    remember = st.checkbox("Remember me on this device", value=True)
    
    if st.button("Login"):
        if user_input in USERS and USERS[user_input] == pass_input:
            st.session_state["authenticated"] = True
            st.session_state["user"] = user_input.capitalize()
            if remember:
                st.query_params["user"] = user_input # Adds ?user=ethan to the URL
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state["authenticated"]:
    login()
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

df_transactions, df_cats = load_data()

def get_cat_list(type_filter):
    if df_cats.empty: return []
    return df_cats[df_cats["Type"] == type_filter]["Name"].unique().tolist()

# --- POP-UP DIALOG ---
@st.dialog("Manage Transaction")
def manage_transaction(idx, row):
    st.write(f"Editing: **{row['Category']}**")
    new_date = st.date_input("Date", row["Date"])
    cats = get_cat_list(row["Type"])
    new_cat = st.selectbox("Category", cats, index=cats.index(row["Category"]) if row["Category"] in cats else 0)
    new_amt = st.number_input("Amount ($)", value=float(row["Amount"]))
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="update-btn">', unsafe_allow_html=True)
        if st.button("Save Changes"):
            df_transactions.at[idx, "Date"] = new_date.strftime('%Y-%m-%d')
            df_transactions.at[idx, "Category"] = new_cat
            df_transactions.at[idx, "Amount"] = new_amt
            conn.update(worksheet="transactions", data=df_transactions)
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
        if st.button("Delete"):
            updated_df = df_transactions.drop(idx)
            conn.update(worksheet="transactions", data=updated_df)
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- MAIN INTERFACE ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add", "Visuals", "History"])

with tab1:
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("add_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_cat_list = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_cat_list if f_cat_list else ["Add one in sidebar"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save Entry"):
            if f_cat_list:
                new_entry = pd.DataFrame([{"Date": f_date.strftime('%Y-%m-%d'), "Type": t_type, "Category": f_cat, "Amount": f_amt, "User": st.session_state["user"]}])
                updated_df = pd.concat([df_transactions, new_entry], ignore_index=True)
                conn.update(worksheet="transactions", data=updated_df)
                st.success("Saved!")
                st.cache_resource.clear()
                st.rerun()

with tab2:
    if not df_transactions.empty:
        inc = df_transactions[df_transactions["Type"] == "Income"]["Amount"].sum()
        exp = df_transactions[df_transactions["Type"] == "Expense"]["Amount"].sum()
        st.metric("Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} Income")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Expenses**")
            df_ex = df_transactions[df_transactions["Type"] == "Expense"]
            if not df_ex.empty:
                st.plotly_chart(px.pie(df_ex, values="Amount", names="Category", hole=0.4), use_container_width=True)
        with c2:
            st.write("**Income**")
            df_in = df_transactions[df_transactions["Type"] == "Income"]
            if not df_in.empty:
                st.plotly_chart(px.pie(df_in, values="Amount", names="Category", hole=0.4), use_container_width=True)
    else:
        st.info("Log data to see charts.")

with tab3:
    if not df_transactions.empty:
        # Sort history
        dff = df_transactions.copy().sort_values(by="Date", ascending=False)
        
        # Search & Filter
        with st.expander("🔍 Search & Filter"):
            s_term = st.text_input("Category Search", "")
            if s_term: dff = dff[dff['Category'].str.contains(s_term, case=False)]
        
        # Horizontal Header
        st.markdown("""
            <div style="display:flex; flex-direction:row; padding-bottom:5px; border-bottom:2px solid #eee; font-weight:bold; color:grey; font-size:0.7rem;">
                <div style="width:15%;">DATE</div>
                <div style="width:45%;">CATEGORY</div>
                <div style="width:25%; text-align:right;">AMOUNT</div>
                <div style="width:15%;"></div>
            </div>
        """, unsafe_allow_html=True)

        # Transaction Rows
        for i, row in dff.iterrows():
            # Use columns but with custom CSS classes to prevent wrapping
            col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
            with col1: st.write(f"**{row['Date'].strftime('%m/%d')}**")
            with col2: st.write(f"{row['Category']}")
            with col3: st.write(f"**${row['Amount']:,.0f}**") # Dropped cents for more space
            with col4:
                if st.button("📝", key=f"ed_{i}"):
                    manage_transaction(i, row)
    else:
        st.info("History is empty.")

# --- SIDEBAR FOR LOGOUT & CATEGORIES ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Logout & Clear Memory"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    st.divider()
    st.header("Manage Categories")
    cat_type = st.selectbox("Type", ["Expense", "Income"])
    new_cat = st.text_input("Name")
    if st.button("Add Category"):
        if new_cat and new_cat not in get_cat_list(cat_type):
            new_row = pd.DataFrame([{"Type": cat_type, "Name": new_cat}])
            conn.update(worksheet="categories", data=pd.concat([df_cats, new_row], ignore_index=True))
            st.success(f"Added {new_cat}")
            st.cache_resource.clear()
            st.rerun()

