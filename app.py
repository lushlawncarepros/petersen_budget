import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import calendar
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# --- INITIALIZE STATE ---
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = 0 # 0: Add Entry, 1: Visuals, 2: History

# CSS: High-Contrast Layout & Custom Navigation Styling
st.markdown("""
    <style>
    /* Hide Sidebar Nav */
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* LAYOUT SPACING */
    [data-testid="stVerticalBlock"] { gap: 0rem !important; }
    
    /* --- CUSTOM TAB STYLING --- */
    .nav-container {
        display: flex;
        justify-content: flex-start;
        gap: 25px;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        padding-bottom: 10px;
        margin-bottom: 30px;
    }
    .nav-item {
        font-size: 1.1rem;
        font-weight: 800;
        color: rgba(128, 128, 128, 0.6);
        cursor: pointer;
        padding: 5px 2px;
        text-decoration: none;
        border-bottom: 3px solid transparent;
        transition: all 0.3s;
    }
    .nav-item-active {
        color: #2e7d32 !important;
        border-bottom: 3px solid #2e7d32 !important;
    }
    
    /* Ledger Header - No bottom line */
    .hist-header {
        display: flex;
        justify-content: space-between;
        padding: 10px;
        font-size: 1.0rem; 
        font-weight: 800;
        text-transform: uppercase;
        background-color: transparent;
    }

    /* 3. LAYOUT SPACING - Row Container Height: 25px; margin-bottom: 0px */
    .row-container {
        position: relative; 
        height: 25px; 
        margin-bottom: 0px; 
        width: 100%;
        background-color: transparent; 
    }
    
    /* 1. VISUAL TEXT ROW (.trans-row) */
    .trans-row {
        display: flex;
        align-items: center; 
        justify-content: space-between;
        background-color: var(--secondary-background-color);
        border-radius: 8px;
        padding: 0px 12px 0px 12px !important; 
        height: 40px; 
        width: 100%;
        position: absolute;
        top: 0; left: 0; z-index: 1;
        pointer-events: none; 
        font-family: "Source Sans Pro", sans-serif;
        border: 1px solid rgba(128, 128, 128, 0.1);
        box-sizing: border-box;
    }
    
    .tr-date { width: 20%; font-size: 0.85rem; font-weight: 700; opacity: 0.8; }
    .tr-cat { width: 50%; font-size: 0.95rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tr-amt { width: 30%; font-size: 1.05rem; font-weight: 800; text-align: right; }
    
    /* 2. INVISIBLE CLICK BUTTON Overlay */
    .row-container div[data-testid="element-container"] {
        position: absolute !important;
        top: 0 !important; left: 0 !important;
        width: 100% !important; height: 45px !important; 
        z-index: 5 !important; margin: 0 !important; padding: 0 !important;
    }

    .row-container .stButton button {
        background-color: transparent !important;
        color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        width: 100% !important; height: 45px !important; 
        padding: 0px !important; margin: 0px !important;  
        display: block !important;
        cursor: pointer;
    }
    
    .row-container .stButton button:hover {
        background-color: rgba(128,128,128,0.05) !important;
    }
    
    /* General UI Tweaks */
    div[data-testid="stPopover"] { width: 100%; margin-top: 15px !important; margin-bottom: 15px !important; }
    .stButton>button { border-radius: 12px; }

    /* Decoy for Focus Fix */
    .decoy-focus { height: 0; width: 0; opacity: 0; position: absolute; pointer-events: none; }
    </style>
    """, unsafe_allow_html=True)

# --- JAVASCRIPT: SWIPE ENGINE ---
# Detects swipes and clicks invisible Streamlit buttons to change state
st.components.v1.html("""
<script>
    let touchstartX = 0;
    let touchendX = 0;
    const minDistance = 80;

    function handleSwipe() {
        if (touchendX < touchstartX - minDistance) {
            window.parent.document.querySelector('button[key="next_tab"]').click();
        }
        if (touchendX > touchstartX + minDistance) {
            window.parent.document.querySelector('button[key="prev_tab"]').click();
        }
    }

    window.parent.document.addEventListener('touchstart', e => {
        touchstartX = e.changedTouches[0].screenX;
    }, {passive: true});

    window.parent.document.addEventListener('touchend', e => {
        touchendX = e.changedTouches[0].screenX;
        handleSwipe();
    }, {passive: true});
</script>
""", height=0)

# Hidden triggers for the JS engine
if st.button("next", key="next_tab", help="hidden"):
    st.session_state.active_tab = min(st.session_state.active_tab + 1, 2)
    st.rerun()
if st.button("prev", key="prev_tab", help="hidden"):
    st.session_state.active_tab = max(st.session_state.active_tab - 1, 0)
    st.rerun()

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
    st.markdown('<div style="margin-bottom: 20px;"></div>', unsafe_allow_html=True)
    u = st.text_input("Username").lower()
    p = st.text_input("Password", type="password")
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    remember_me = st.checkbox("Remember me", value=True)
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    if st.button("Login", use_container_width=True):
        if u in USERS and USERS[u] == p:
            st.session_state["authenticated"] = True
            st.session_state["user"] = u.capitalize()
            if remember_me: st.query_params["user"] = u
            st.rerun()
        else: st.error("Invalid credentials.")
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
            for col in ["Date", "Type", "Category", "Amount", "User", "Memo"]:
                if col not in t_df.columns: t_df[col] = ""
            t_df["Amount"] = t_df["Amount"].apply(safe_float)
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            t_df = t_df.dropna(subset=['Date']).reset_index(drop=True)
        else: t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User", "Memo"])
        if c_df is not None and not c_df.empty:
            c_df.columns = [str(c).strip().title() for c in c_df.columns]
        else: c_df = pd.DataFrame(columns=["Type", "Name"])
        return t_df, c_df
    except: return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User", "Memo"]), pd.DataFrame(columns=["Type", "Name"])

df_t, df_c = load_data_clean()

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tithe" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    return "💸" if row_type == "Expense" else "💰"

@st.dialog("Manage Entry")
def edit_dialog(row_index, row_data):
    st.markdown('<div class="decoy-focus"><button nonce="focus-fix"></button></div>', unsafe_allow_html=True)
    st.write(f"Editing: **{row_data['Category']}** &nbsp; | &nbsp; Entry Created by: **{row_data.get('User', 'Unknown')}**")
    e_date = st.date_input("Date", row_data["Date"])
    cat_list = sorted(df_c[df_c["Type"] == row_data["Type"]]["Name"].unique().tolist(), key=str.lower)
    c_idx = cat_list.index(row_data["Category"]) if row_data["Category"] in cat_list else 0
    e_cat = st.selectbox("Category", cat_list, index=c_idx)
    raw_memo = str(row_data.get("Memo", ""))
    memo_val = "" if raw_memo.lower() == "nan" else raw_memo
    e_memo = st.text_input("Memo", value=memo_val)
    e_amt = st.number_input("Amount ($)", value=float(row_data["Amount"]))
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Update", use_container_width=True):
            df_t.at[row_index, "Date"] = pd.to_datetime(e_date); df_t.at[row_index, "Category"] = e_cat
            df_t.at[row_index, "Amount"] = e_amt; df_t.at[row_index, "Memo"] = e_memo
            df_t['Date'] = df_t['Date'].dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=df_t); st.success("Updated!"); time.sleep(0.5); st.rerun()
    with c2:
        if st.button("🗑️ Delete", use_container_width=True):
            new_df = df_t.drop(row_index); new_df['Date'] = new_df['Date'].dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=new_df); st.success("Deleted!"); time.sleep(0.5); st.rerun()

@st.dialog("Manage Category")
def manage_cat_dialog(old_name, cat_type):
    st.write(f"Managing **{cat_type}**: {old_name}")
    new_type = st.selectbox("Designation", ["Expense", "Income"], index=0 if cat_type == "Expense" else 1)
    new_name = st.text_input("Category Name", value=old_name)
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Save Changes", use_container_width=True):
            if new_name and (new_name != old_name or new_type != cat_type):
                mask_c = (df_c["Type"] == cat_type) & (df_c["Name"] == old_name)
                df_c.loc[mask_c, "Name"] = new_name; df_c.loc[mask_c, "Type"] = new_type
                conn.update(worksheet="categories", data=df_c)
                mask_t = (df_t["Category"] == old_name)
                df_t.loc[mask_t, "Category"] = new_name; df_t.loc[mask_t, "Type"] = new_type
                df_t['Date'] = df_t['Date'].dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=df_t); st.success("Updated!"); time.sleep(1); st.rerun()
    with c2:
        if st.button("🗑️ Delete", use_container_width=True):
            new_c = df_c[~((df_c["Type"] == cat_type) & (df_c["Name"] == old_name))]
            conn.update(worksheet="categories", data=new_c); st.success("Removed!"); time.sleep(1); st.rerun()

# --- MAIN APP ---
st.title("📊 Petersen Budget")
st.markdown('<div style="margin-bottom: 40px;"></div>', unsafe_allow_html=True)

# --- CUSTOM NAVIGATION BAR ---
cols = st.columns([1,1,1,2])
with cols[0]:
    if st.button("Add Entry", type="secondary", use_container_width=True): st.session_state.active_tab = 0; st.rerun()
with cols[1]:
    if st.button("Visuals", type="secondary", use_container_width=True): st.session_state.active_tab = 1; st.rerun()
with cols[2]:
    if st.button("History", type="secondary", use_container_width=True): st.session_state.active_tab = 2; st.rerun()

# Visual Indicator for Active Tab
active_label = ["Add Entry", "Visuals", "History"][st.session_state.active_tab]
st.markdown(f"""
    <div style="margin-top: -15px; margin-bottom: 25px;">
        <span style="color: #2e7d32; font-weight: 800; border-bottom: 3px solid #2e7d32; padding-bottom: 5px;">
            {active_label} View
        </span>
    </div>
""", unsafe_allow_html=True)

# --- CONTENT SECTIONS ---
if st.session_state.active_tab == 0:
    st.subheader("Add Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_cats = sorted(df_c[df_c["Type"] == t_type]["Name"].unique().tolist(), key=str.lower)
        f_cat = st.selectbox("Category", f_cats if f_cats else ["(Add categories in sidebar)"])
        f_memo = st.text_input("Memo", placeholder="Optional details")
        f_amt = st.number_input("Amount ($)", value=None, placeholder="0.00", step=0.01)
        st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
        if st.form_submit_button("Save", use_container_width=True):
            if f_cats and f_amt is not None:
                new_entry = pd.DataFrame([{"Date": pd.to_datetime(f_date), "Type": t_type, "Category": f_cat, "Amount": float(f_amt), "User": st.session_state["user"], "Memo": f_memo}])
                latest_t, _ = load_data_clean()
                updated = pd.concat([latest_t, new_entry], ignore_index=True)
                updated['Date'] = updated['Date'].dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=updated); st.success("Saved!"); time.sleep(1); st.rerun()

elif st.session_state.active_tab == 1:
    if not df_t.empty:
        viz_df = df_t.copy()
        viz_df["Memo"] = viz_df["Memo"].apply(lambda x: "Unspecified" if str(x).lower() == "nan" or str(x).strip() == "" else str(x))
        st.metric("Net Balance", f"${(viz_df[viz_df['Type'] == 'Income']['Amount'].sum() - viz_df[viz_df['Type'] == 'Expense']['Amount'].sum()):,.2f}")
        c1, c2 = st.columns(2)
        with c1:
            dx = viz_df[viz_df["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.sunburst(dx, path=['Category', 'Memo'], values='Amount', title="Expenses"), use_container_width=True)
        with c2:
            di = viz_df[viz_df["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.sunburst(di, path=['Category', 'Memo'], values='Amount', title="Income"), use_container_width=True)
    else: st.info("No data yet.")

elif st.session_state.active_tab == 2:
    if not df_t.empty:
        today = date.today(); first_day = today.replace(day=1)
        last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        with st.expander("🔍 Filter View"):
            c1, c2 = st.columns(2)
            start_f = c1.date_input("From", first_day); end_f = c2.date_input("To", last_day)
            with st.popover("Select Categories"):
                all_cats = sorted(df_c["Name"].unique().tolist())
                sel_cats = [cat for cat in all_cats if st.checkbox(cat, value=True, key=f"f_{cat}")]
            work_df = df_t.copy()
            work_df = work_df[(work_df["Date"].dt.date >= start_f) & (work_df["Date"].dt.date <= end_f) & (work_df["Category"].isin(sel_cats))]
        work_df = work_df.sort_values(by="Date", ascending=False)
        st.markdown('<div class="hist-header"><div style="width:20%">DATE</div><div style="width:50%">CATEGORY</div><div style="width:30%; text-align:right">AMOUNT</div></div>', unsafe_allow_html=True)
        for i, row in work_df.iterrows():
            if pd.isnull(row['Date']): continue
            d_str = row['Date'].strftime('%m/%d'); is_ex = row['Type'] == 'Expense'
            price_color = "#d32f2f" if is_ex else "#2e7d32"; prefix = "-" if is_ex else "+"
            memo_display = f" ({row['Memo']})" if str(row.get('Memo', '')) != 'nan' and str(row.get('Memo', '')).strip() != '' else ''
            st.markdown('<div class="row-container">', unsafe_allow_html=True)
            st.markdown(f'<div class="trans-row"><div class="tr-date"><span>{d_str}</span></div><div class="tr-cat">{get_icon(row["Category"], row["Type"])} {row["Category"]}{memo_display}</div><div class="tr-amt" style="color:{price_color};">{prefix}${row["Amount"]:,.0f}</div></div>', unsafe_allow_html=True)
            if st.button(" ", key=f"h_{i}", use_container_width=True): edit_dialog(i, row)
            st.markdown('</div>', unsafe_allow_html=True)

with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    if st.button("🔄 Force Sync", use_container_width=True):
        st.cache_resource.clear(); st.cache_data.clear(); st.rerun()
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True):
        st.session_state["authenticated"] = False; st.query_params.clear(); st.rerun()
    st.divider()
    st.header("Categories")
    with st.form("cat_form", clear_on_submit=True):
        ct = st.selectbox("Type", ["Expense", "Income"]); cn = st.text_input("Name")
        st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
        if st.form_submit_button("Add Category", use_container_width=True):
            if cn:
                st.cache_resource.clear(); _, latest_c = load_data_clean()
                updated_c = pd.concat([latest_c, pd.DataFrame([{"Type": ct, "Name": cn}])], ignore_index=True)
                conn.update(worksheet="categories", data=updated_c); st.success("Added!"); time.sleep(0.5); st.rerun()
    st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
    st.header("Manage Existing Category")
    with st.container(border=True):
        manage_type = st.selectbox("View Type", ["Expense", "Income"], key="m_type")
        target_cat = st.selectbox("Select Category", sorted(df_c[df_c["Type"] == manage_type]["Name"].unique().tolist()), key="m_list")
        st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
        if st.button("🔧 Manage Category", use_container_width=True):
            if target_cat: manage_cat_dialog(target_cat, manage_type)
