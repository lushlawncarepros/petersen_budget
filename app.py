import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import calendar
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS: High-Contrast Layout with Fixed Filter & Ledger Spacing
st.markdown("""
    <style>
    /* Hide Sidebar Nav */
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* Remove vertical gaps between block elements */
    [data-testid="stVerticalBlock"] { gap: 0rem !important; }
    
    /* THE ROW CONTAINER */
    .row-container {
        position: relative; 
        height: 60px; 
        margin-bottom: 2px; /* Restored to "Nailed It" spacing */
        width: 100%;
        background-color: white; 
    }
    
    /* 1. VISUAL LAYER (Text) */
    .trans-row {
        display: flex;
        align-items: center; 
        justify-content: space-between;
        background-color: white;
        border-bottom: 1px solid #f0f0f0;
        padding: 0 12px;
        height: 60px;
        width: 100%;
        position: absolute;
        top: 0;
        left: 0;
        z-index: 1;
        pointer-events: none;
        font-family: "Source Sans Pro", sans-serif;
    }
    
    .tr-date { width: 20%; font-size: 0.85rem; color: #111; font-weight: 700; }
    .tr-cat { width: 50%; font-size: 0.95rem; color: #222; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tr-amt { width: 30%; font-size: 1.05rem; font-weight: 800; text-align: right; }
    
    /* 2. THE CLICK LAYER (Button Overlay) */
    .row-container .stButton {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 60px;
        z-index: 5;
    }
    
    .row-container .stButton button {
        background-color: transparent !important;
        color: transparent !important;
        border: none !important;
        width: 100% !important;
        height: 60px !important;
        padding: 0 !important;
        margin: 0 !important;
        display: block !important;
        cursor: pointer;
    }
    
    /* Ledger Header */
    .hist-header {
        display: flex;
        justify-content: space-between;
        padding: 10px;
        border-bottom: 2px solid #333;
        color: #444;
        font-size: 0.75rem;
        font-weight: 800;
        text-transform: uppercase;
        background-color: white;
    }

    /* --- FILTER UI SPACING --- */
    
    /* Spacing for the Filter Categories Button */
    div[data-testid="stPopover"] { 
        width: 100%; 
        margin-top: 25px !important; /* Pushes it down from the dates */
    }
    
    /* Spacing for checkboxes inside the popover */
    div[data-testid="stCheckbox"] { 
        margin-bottom: 12px !important; 
        padding-top: 5px !important;
    }
    
    /* Formatting for standard buttons */
    .stButton>button { border-radius: 12px; }
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

def safe_float(val):
    try:
        if isinstance(val, (int, float)): return float(val)
        if isinstance(val, str):
            clean = val.replace('$', '').replace(',', '').strip()
            return float(clean) if clean else 0.0
        return 0.0
    except: return 0.0

def load_data_clean():
    st.cache_data.clear()
    try:
        t_df = conn.read(worksheet="transactions", ttl=0)
        c_df = conn.read(worksheet="categories", ttl=0)
        if t_df is not None and not t_df.empty:
            t_df.columns = [str(c).strip().title() for c in t_df.columns]
            for col in ["Date", "Type", "Category", "Amount", "User"]:
                if col not in t_df.columns: t_df[col] = ""
            t_df["Amount"] = t_df["Amount"].apply(safe_float)
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            t_df = t_df.dropna(subset=['Date']).reset_index(drop=True)
        else: t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        if c_df is not None and not c_df.empty:
            c_df.columns = [str(c).strip().title() for c in c_df.columns]
        else:
            c_df = pd.DataFrame(columns=["Type", "Name"])
        return t_df, c_df
    except: return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

df_t, df_c = load_data_clean()

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tithe" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    return "💸" if row_type == "Expense" else "💰"

@st.dialog("Manage Entry")
def edit_dialog(row_index, row_data):
    st.write(f"Editing: **{row_data['Category']}**")
    e_date = st.date_input("Date", row_data["Date"])
    cat_list = sorted(df_c[df_c["Type"] == row_data["Type"]]["Name"].unique().tolist(), key=str.lower)
    c_idx = cat_list.index(row_data["Category"]) if row_data["Category"] in cat_list else 0
    e_cat = st.selectbox("Category", cat_list, index=c_idx)
    e_amt = st.number_input("Amount ($)", value=float(row_data["Amount"]))
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Update", use_container_width=True):
            df_t.at[row_index, "Date"] = pd.to_datetime(e_date)
            df_t.at[row_index, "Category"] = e_cat
            df_t.at[row_index, "Amount"] = e_amt
            df_t['Date'] = df_t['Date'].dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=df_t)
            st.success("Updated!")
            time.sleep(0.5)
            st.rerun()
    with c2:
        if st.button("🗑️ Delete", use_container_width=True):
            new_df = df_t.drop(row_index)
            new_df['Date'] = new_df['Date'].dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=new_df)
            st.success("Deleted!")
            time.sleep(0.5)
            st.rerun()

# --- MAIN APP ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("Add Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_cats = sorted(df_c[df_c["Type"] == t_type]["Name"].unique().tolist(), key=str.lower)
        f_cat = st.selectbox("Category", f_cats if f_cats else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save"):
            if f_cats:
                latest_t, _ = load_data_clean()
                new_entry = pd.DataFrame([{
                    "Date": pd.to_datetime(f_date), "Type": t_type, "Category": f_cat,
                    "Amount": float(f_amt), "User": st.session_state["user"]
                }])
                updated = pd.concat([latest_t, new_entry], ignore_index=True)
                updated['Date'] = updated['Date'].dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=updated)
                st.success(f"Saved {f_cat}!")
                time.sleep(1)
                st.rerun()
            else: st.error("Please add a category first!")

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
    else: st.info("No data yet.")

with tab3:
    if not df_t.empty:
        today = date.today()
        first_day = today.replace(day=1)
        last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])

        with st.expander("🔍 Filter History", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                start_f = st.date_input("From", first_day)
            with c2:
                end_f = st.date_input("To", last_day)
            
            with st.popover("Select Categories"):
                st.markdown("**Income Categories**")
                inc_list = sorted(df_c[df_c["Type"] == "Income"]["Name"].unique().tolist())
                sel_inc = [cat for cat in inc_list if st.checkbox(cat, value=True, key=f"filter_inc_{cat}")]
                
                st.divider()
                st.markdown("**Expense Categories**")
                exp_list = sorted(df_c[df_c["Type"] == "Expense"]["Name"].unique().tolist())
                sel_exp = [cat for cat in exp_list if st.checkbox(cat, value=True, key=f"filter_exp_{cat}")]
                
                all_selected = sel_inc + sel_exp

            work_df = df_t.copy()
            work_df = work_df[
                (work_df["Date"].dt.date >= start_f) & 
                (work_df["Date"].dt.date <= end_f) & 
                (work_df["Category"].isin(all_selected))
            ]
            
            f_net = work_df[work_df["Type"] == "Income"]["Amount"].sum() - work_df[work_df["Type"] == "Expense"]["Amount"].sum()
            st.markdown(f"**Filtered Net:** `${f_net:,.2f}`")

        work_df = work_df.sort_values(by="Date", ascending=False)
        st.markdown('<div class="hist-header"><div style="width:20%">DATE</div><div style="width:50%">CATEGORY</div><div style="width:30%; text-align:right">PRICE</div></div>', unsafe_allow_html=True)
        
        # Wrapped in a white container to ensure background doesn't peek through the 2px margins
        st.markdown('<div style="background-color:white; width:100%;">', unsafe_allow_html=True)
        for i, row in work_df.iterrows():
            if pd.isnull(row['Date']): continue
            d_str = row['Date'].strftime('%m/%d')
            is_ex = row['Type'] == 'Expense'
            amt_val = row['Amount']
            icon = get_icon(row['Category'], row['Type'])
            price_color = "#d32f2f" if is_ex else "#2e7d32" 
            prefix = "-" if is_ex else "+"
            
            st.markdown('<div class="row-container">', unsafe_allow_html=True)
            st.markdown(f"""
                <div class="trans-row">
                    <div class="tr-date">{d_str}</div>
                    <div class="tr-cat">{icon} {row['Category']}</div>
                    <div class="tr-amt" style="color:{price_color};">{prefix}${amt_val:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button(" ", key=f"h_{i}", use_container_width=True):
                edit_dialog(i, row)
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else: st.info("No data yet.")

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
                _, latest_c = load_data_clean()
                updated_c = pd.concat([latest_c, pd.DataFrame([{"Type": ct, "Name": cn}])], ignore_index=True)
                conn.update(worksheet="categories", data=updated_c)
                st.success("Added!")
                time.sleep(0.5)
                st.rerun()
