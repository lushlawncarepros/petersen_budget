import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS: minimal tweaks, mostly relying on native dataframe now
st.markdown("""
    <style>
    /* Clean up the dataframe look */
    [data-testid="stDataFrame"] { width: 100%; }
    
    /* Bigger buttons for easy tapping */
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; }
    
    /* Hide Sidebar Nav */
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* Dialog Radius */
    div[data-testid="stDialog"] { border-radius: 20px; }
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
        # Read as String to keep it safe
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
            # We add a hidden ID column to track rows safely
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
    # Get category list for this type
    clist = get_cat_list(row_data["Type"])
    # Default to current category, or index 0 if missing
    c_idx = clist.index(row_data["Category"]) if row_data["Category"] in clist else 0
    e_cat = st.selectbox("Category", clist, index=c_idx)
    e_amt = st.number_input("Amount ($)", value=float(row_data["Amount"]))
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Save Changes"):
            # Update the specific row using the index
            df_t.at[row_index, "Date"] = pd.to_datetime(e_date)
            df_t.at[row_index, "Category"] = e_cat
            df_t.at[row_index, "Amount"] = e_amt
            
            # Format Date for Sheet Consistency
            df_t['Date'] = df_t['Date'].dt.strftime('%Y-%m-%d')
            
            conn.update(worksheet="transactions", data=df_t)
            st.success("Updated!")
            time.sleep(0.5)
            st.rerun()
            
    with c2:
        if st.button("🗑️ Delete"):
            # Drop the row and save
            new_df = df_t.drop(row_index)
            # Fix date format before save
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
    st.subheader("Tap a row to Edit")
    if not df_t.empty:
        # Prepare Data for Display
        display_df = df_t.copy().sort_values(by="Date", ascending=False)
        
        # Add Icons to Category Name for display
        display_df['IconCat'] = display_df.apply(lambda x: f"{get_icon(x['Category'], x['Type'])} {x['Category']}", axis=1)
        
        # Color Logic for Amount (Red/Green)
        def color_amounts(val):
            color = 'red' if val < 0 else 'green'
            return f'color: {color}; font-weight: bold;'

        # Create a display-only view with calculated columns
        # We start with negative amounts for expenses to make them Red/Green logically
        display_df['DisplayAmount'] = display_df.apply(lambda x: -x['Amount'] if x['Type'] == 'Expense' else x['Amount'], axis=1)
        
        # Final DataFrame for the UI
        ui_df = display_df[['Date', 'IconCat', 'DisplayAmount']].copy()
        ui_df.columns = ["Date", "Category", "Amount"] # Nice Headers
        
        # --- THE INTERACTIVE TABLE ---
        selection = st.dataframe(
            ui_df.style.format({
                "Date": lambda t: t.strftime("%m/%d"), # Short Date
                "Amount": "${:,.0f}" # Whole Dollars
            }).map(lambda x: 'color: #d63031; font-weight:bold' if x < 0 else 'color: #00b894; font-weight:bold', subset=['Amount']),
            use_container_width=True,
            hide_index=True,
            on_select="rerun", # This makes it clickable!
            selection_mode="single-row"
        )
        
        # Handle Selection
        if selection.selection.rows:
            selected_visual_index = selection.selection.rows[0]
            # Map back to the original dataframe index
            # Since ui_df is sorted, we grab the index from the sorted dataframe
            actual_index = ui_df.index[selected_visual_index]
            
            # Open Dialog
            edit_dialog(actual_index, df_t.loc[actual_index])

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


