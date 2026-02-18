import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS: Transform Buttons into "List Items" for the History Tab
st.markdown("""
    <style>
    /* Hide Sidebar Nav */
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* Dialog Radius */
    div[data-testid="stDialog"] { border-radius: 20px; }
    
    /* Standard Action Buttons (Save, Add, Login) */
    .stButton>button { 
        width: 100%; 
        border-radius: 12px; 
        height: 3em; 
        font-weight: 500;
    }
    
    /* HISTORY LIST STYLING - The Magic Class */
    /* We target buttons inside the history container to look like rows */
    div[data-testid="stVerticalBlock"] > div > div > div > div > .stButton > button {
        text-align: left; /* Align text to left like a list */
        justify-content: flex-start;
        height: auto;
        padding: 12px 10px;
        background-color: white;
        border: 1px solid #f0f2f6;
        border-radius: 8px;
        margin-bottom: 2px;
        color: #31333F;
        font-family: "Source Sans Pro", sans-serif;
        font-size: 0.9rem;
    }
    
    /* Hover effect for history items */
    div[data-testid="stVerticalBlock"] > div > div > div > div > .stButton > button:hover {
        border-color: #007bff;
        color: #007bff;
        background-color: #f8f9fa;
    }
    
    /* Header Styling */
    .history-header {
        font-size: 0.8rem;
        font-weight: bold;
        color: #888;
        padding-bottom: 5px;
        border-bottom: 2px solid #eee;
        margin-bottom: 10px;
    }
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

if not st.session_state["authenticated"]:
    st.title("🔐 Login")
    u = st.text_input("Username").lower()
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u in USERS and USERS[u] == p:
            st.session_state["authenticated"] = True
            st.session_state["user"] = u.capitalize()
            st.query_params["user"] = u
            st.rerun()
    st.stop()

# --- DATA ENGINE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data_robust():
    st.cache_data.clear()
    try:
        # Read as Strings
        t_df = conn.read(worksheet="transactions", ttl=0, dtype=str)
        c_df = conn.read(worksheet="categories", ttl=0, dtype=str)
        
        # --- TRANSACTIONS ---
        if t_df is not None and not t_df.empty:
            t_df.columns = [str(c).strip().title() for c in t_df.columns]
            for col in ["Date", "Type", "Category", "Amount", "User"]:
                if col not in t_df.columns: t_df[col] = ""

            t_df["Amount"] = t_df["Amount"].str.replace(r'[$,]', '', regex=True)
            t_df["Amount"] = pd.to_numeric(t_df["Amount"], errors='coerce').fillna(0)
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            t_df = t_df.dropna(subset=['Date'])
            # Add index for safe editing
            t_df = t_df.reset_index(drop=True)
        else:
            t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])

        # --- CATEGORIES ---
        if c_df is not None and not c_df.empty:
            c_df.columns = [str(c).strip().title() for c in c_df.columns]
        else:
            c_df = pd.DataFrame(columns=["Type", "Name"])
            
        return t_df, c_df
    except Exception:
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

df_t, df_c = load_data_robust()

def get_cat_list(t_filter):
    if df_c.empty or "Name" not in df_c.columns: return []
    cats = df_c[df_c["Type"] == t_filter]["Name"].unique().tolist()
    return sorted(cats, key=str.lower)

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tithe" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    return "💸" if row_type == "Expense" else "💰"

# --- EDITOR DIALOG ---
@st.dialog("Manage Entry")
def edit_dialog(row_index, row_data):
    st.write(f"Editing: **{row_data['Category']}**")
    
    # Form inputs
    e_date = st.date_input("Date", row_data["Date"])
    clist = get_cat_list(row_data["Type"])
    # Default to current category or first item
    c_idx = clist.index(row_data["Category"]) if row_data["Category"] in clist else 0
    e_cat = st.selectbox("Category", clist, index=c_idx)
    e_amt = st.number_input("Amount ($)", value=float(row_data["Amount"]))
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Update"):
            df_t.at[row_index, "Date"] = pd.to_datetime(e_date)
            df_t.at[row_index, "Category"] = e_cat
            df_t.at[row_index, "Amount"] = e_amt
            
            # Format Date for Sheet
            df_t['Date'] = df_t['Date'].dt.strftime('%Y-%m-%d')
            
            conn.update(worksheet="transactions", data=df_t)
            st.success("Updated!")
            time.sleep(0.5)
            st.rerun()
            
    with c2:
        if st.button("🗑️ Delete"):
            new_df = df_t.drop(row_index)
            new_df['Date'] = new_df['Date'].dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=new_df)
            st.success("Deleted!")
            time.sleep(0.5)
            st.rerun()

# --- APP TABS ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("Add Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save"):
            if f_clist:
                latest_t, _ = load_data_robust()
                new_entry = pd.DataFrame([{
                    "Date": pd.to_datetime(f_date),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                updated = pd.concat([latest_t, new_entry], ignore_index=True)
                updated['Date'] = updated['Date'].dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=updated)
                st.success(f"Saved {f_cat}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please add a category first!")

with tab2:
    if not df_t.empty:
        inc = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} In")
        c1, c2 = st.columns(2)
        with c1:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with c2:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("No data yet.")

with tab3:
    st.markdown("<div class='history-header'>TAP ROW TO EDIT</div>", unsafe_allow_html=True)
    if not df_t.empty:
        # Sort display but keep index alignment
        work_df = df_t.copy()
        work_df['sort_date'] = pd.to_datetime(work_df['Date'])
        work_df = work_df.sort_values(by="sort_date", ascending=False)
        
        # Iterate through rows and create a button for each
        for i, row in work_df.iterrows():
            # Format the button label to look like a row
            # Format: "02/18  🔴  -$50   🛒 Groceries"
            
            d_str = row['Date'].strftime('%m/%d')
            is_ex = row['Type'] == 'Expense'
            
            # Indicator Emoji (Red/Green Circle)
            status = "🔴" if is_ex else "🟢"
            # Icon
            icon = get_icon(row['Category'], row['Type'])
            # Amount String
            amt_prefix = "-" if is_ex else "+"
            amt_str = f"{amt_prefix}${row['Amount']:,.0f}"
            
            # Construct Label with non-breaking spaces for alignment
            # Note: Buttons center text by default, CSS above forces left-align
            label = f"{d_str}  {status} {amt_str}   {icon} {row['Category']}"
            
            # The button itself
            if st.button(label, key=f"hist_{i}", use_container_width=True):
                edit_dialog(i, row)
                
    else:
        st.info("History is empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("🔄 Force Sync"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()
    
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()
    
    st.divider()
    st.header("Categories")
    with st.form("cat_form", clear_on_submit=True):
        ct = st.selectbox("Type", ["Expense", "Income"])
        cn = st.text_input("Name")
        if st.form_submit_button("Add Category"):
            if cn:
                st.cache_resource.clear()
                _, latest_c = load_data_robust()
                updated_c = pd.concat([latest_c, pd.DataFrame([{"Type": ct, "Name": cn}])], ignore_index=True)
                conn.update(worksheet="categories", data=updated_c)
                st.success("Added!")
                time.sleep(0.5)
                st.rerun()


