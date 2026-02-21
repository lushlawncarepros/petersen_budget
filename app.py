import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import calendar
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS: High-Contrast Layout with Exact Measurements
st.markdown("""
    <style>
    /* Hide Sidebar Nav */
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* LAYOUT SPACING - Streamlit Internal Block Gap: 0rem */
    [data-testid="stVerticalBlock"] { gap: 0rem !important; }
    
    /* --- TAB STYLING --- */
    button[data-baseweb="tab"] p {
        font-size: 1.15rem !important; 
        font-weight: 800 !important;
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
    
    /* Filter UI Tweaks */
    div[data-testid="stPopover"] { width: 100%; margin-top: 15px !important; margin-bottom: 15px !important; }
    .stButton>button { border-radius: 12px; }

    /* Decoy CSS for Focus Fix */
    .decoy-focus {
        height: 0; width: 0; opacity: 0; position: absolute; pointer-events: none;
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
            if remember_me:
                st.query_params["user"] = u
            st.rerun()
        else:
            st.error("Invalid credentials.")
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
        
        # Transactions Clean
        if t_df is not None and not t_df.empty:
            t_df.columns = [str(c).strip().title() for c in t_df.columns]
            for col in ["Date", "Type", "Category", "Amount", "User", "Memo"]:
                if col not in t_df.columns: t_df[col] = ""
            t_df["Amount"] = t_df["Amount"].apply(safe_float)
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            t_df = t_df.dropna(subset=['Date']).reset_index(drop=True)
        else: t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User", "Memo"])
        
        # Categories Clean
        if c_df is not None and not c_df.empty:
            c_df.columns = [str(c).strip().title() for c in c_df.columns]
            for col in ["Type", "Name", "Order", "Color"]:
                if col not in c_df.columns: 
                    if col == "Order": c_df[col] = 10
                    elif col == "Color": c_df[col] = "#4682B4"
                    else: c_df[col] = ""
            c_df["Order"] = pd.to_numeric(c_df["Order"], errors='coerce').fillna(10)
        else:
            c_df = pd.DataFrame(columns=["Type", "Name", "Order", "Color"])
            
        # Budgets Clean
        try:
            b_df = conn.read(worksheet="budgets", ttl=0)
            if b_df is not None and not b_df.empty:
                b_df.columns = [str(c).strip().title() for c in b_df.columns]
                for col in ["Month", "Category", "Amount"]:
                    if col not in b_df.columns: b_df[col] = ""
                b_df["Amount"] = b_df["Amount"].apply(safe_float)
                b_df["Month"] = b_df["Month"].astype(str)
            else: b_df = pd.DataFrame(columns=["Month", "Category", "Amount"])
        except: b_df = pd.DataFrame(columns=["Month", "Category", "Amount"])
            
        return t_df, c_df, b_df
    except: return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User", "Memo"]), pd.DataFrame(columns=["Type", "Name", "Order", "Color"]), pd.DataFrame(columns=["Month", "Category", "Amount"])

df_t, df_c, df_b = load_data_clean()

# 🛡️ BUG FIX: Force 'Date' into datetime format globally to prevent the AttributeError
df_t['Date'] = pd.to_datetime(df_t['Date'], errors='coerce')

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    
    # Family & Pets
    if "ethan" in n: return "🧔"
    if "alesa" in n: return "👩"
    if "gabe" in n: return "👦"
    if "mel" in n or "kimmy" in n: return "👧"
    if "wes" in n: return "👶"
    if "kid" in n or "child" in n: return "🧒"
    if "luna" in n or "dog" in n: return "🐕"
    if "kevin" in n or "cat" in n: return "🐈"
    if "pet" in n or "vet" in n: return "🐾"
    
    # Housing & Utilities
    if "mortgage" in n or "rent" in n or "home" in n or "house" in n: return "🏠"
    if "electric" in n or "power" in n: return "⚡"
    if "water" in n or "trash" in n or "sewer" in n: return "💧"
    if "internet" in n or "wifi" in n: return "🌐"
    if "phone" in n or "cell" in n: return "📱"
    
    # Food & Dining
    if "groc" in n: return "🛒"
    if "rest" in n or "dine" in n or "eat" in n or "food" in n: return "🍽️"
    
    # Transportation
    if "gas" in n or "fuel" in n: return "⛽"
    if "car" in n or "auto" in n or "truck" in n: return "🚗"
    if "repair" in n or "maint" in n: return "🔧"
    
    # Religion & Charity
    if "tithe" in n or "church" in n or "fast" in n: return "⛪"
    if "charity" in n or "give" in n: return "🤲"
    
    # Health & Fitness
    if "med" in n or "doc" in n or "health" in n or "dent" in n: return "🏥"
    if "gym" in n or "fitness" in n or "train" in n: return "🏋️"
    
    # Hobbies & Entertainment
    if "camp" in n or "tent" in n: return "⛺"
    if "game" in n or "play" in n: return "🎲"
    if "book" in n or "audio" in n or "audible" in n: return "🎧"
    if "date" in n or "fun" in n: return "🍿"
    
    # Shopping & Misc
    if "cloth" in n or "shoe" in n: return "👕"
    if "amazon" in n or "shop" in n: return "📦"
    
    # Business, Savings & Income
    if "lush" in n or "lawn" in n or "yard" in n: return "🌿"
    if "pay" in n or "salary" in n or "check" in n or "wage" in n: return "💵"
    if "save" in n or "invest" in n: return "📈"
    
    return "💸" if row_type == "Expense" else "💰"

@st.dialog("Manage Entry")
def edit_dialog(row_index, row_data):
    st.markdown('<div class="decoy-focus"><button nonce="focus-fix"></button></div>', unsafe_allow_html=True)
    st.write(f"Editing: **{row_data['Category']}** &nbsp; | &nbsp; Entry Created by: **{row_data.get('User', 'Unknown')}**")
    
    e_date = st.date_input("Date", row_data["Date"])
    
    # Sort dropdown by Order (Filter out Headers!)
    valid_cats = df_c[df_c["Type"] == row_data["Type"]].sort_values(by=["Order", "Name"])
    cat_list = valid_cats["Name"].tolist()
    
    c_idx = cat_list.index(row_data["Category"]) if row_data["Category"] in cat_list else 0
    e_cat = st.selectbox("Category", cat_list, index=c_idx)
    
    raw_memo = str(row_data.get("Memo", ""))
    memo_val = "" if raw_memo.lower() == "nan" else raw_memo
    e_memo = st.text_input("Memo", value=memo_val)
    
    e_amt = st.number_input("Amount ($)", value=int(float(row_data["Amount"])), step=1)
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Update", use_container_width=True):
            df_t.at[row_index, "Date"] = pd.to_datetime(e_date)
            df_t.at[row_index, "Category"] = e_cat
            df_t.at[row_index, "Amount"] = e_amt
            df_t.at[row_index, "Memo"] = e_memo
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
                # 1. Update Category List
                mask_c = (df_c["Type"] == cat_type) & (df_c["Name"] == old_name)
                df_c.loc[mask_c, "Name"] = new_name
                df_c.loc[mask_c, "Type"] = new_type
                conn.update(worksheet="categories", data=df_c)
                
                # 2. Sync existing transactions
                mask_t = (df_t["Category"] == old_name)
                df_t.loc[mask_t, "Category"] = new_name
                df_t.loc[mask_t, "Type"] = new_type
                df_t['Date'] = df_t['Date'].dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=df_t)
                
                if not df_b.empty:
                    mask_b = (df_b["Category"] == old_name)
                    if mask_b.any():
                        df_b.loc[mask_b, "Category"] = new_name
                        conn.update(worksheet="budgets", data=df_b)

                st.success("Updated everywhere!")
                time.sleep(1)
                st.rerun()
            else: st.warning("No changes made.")
    with c2:
        if st.button("🗑️ Delete", use_container_width=True):
            new_c = df_c[~((df_c["Type"] == cat_type) & (df_c["Name"] == old_name))]
            conn.update(worksheet="categories", data=new_c)
            
            if not df_b.empty:
                new_b = df_b[df_b["Category"] != old_name]
                conn.update(worksheet="budgets", data=new_b)
                
            st.success("Category Removed!")
            time.sleep(1)
            st.rerun()

# --- MAIN APP ---
st.title("📊 Petersen Budget")
st.markdown('<div style="margin-bottom: 40px;"></div>', unsafe_allow_html=True)

tab1, tab_budget, tab2, tab3 = st.tabs(["Add Entry", "Budget", "Visuals", "History"])

with tab1:
    st.subheader("Add Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        
        # Sort Categories by Order, EXCLUDING Headers
        valid_cats = df_c[df_c["Type"] == t_type].sort_values(by=["Order", "Name"])
        f_cats = valid_cats["Name"].tolist()
        
        f_cat = st.selectbox("Category", f_cats if f_cats else ["(Add categories in sidebar)"])
        f_memo = st.text_input("Memo", placeholder="Optional details")
        f_amt = st.number_input("Amount ($)", value=None, placeholder="0", step=1)
        st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
        if st.form_submit_button("Save", use_container_width=True):
            if f_cats and f_amt is not None:
                latest_t, _, _ = load_data_clean()
                new_entry = pd.DataFrame([{
                    "Date": pd.to_datetime(f_date), "Type": t_type, "Category": f_cat,
                    "Amount": int(f_amt), "User": st.session_state["user"],
                    "Memo": f_memo
                }])
                updated = pd.concat([latest_t, new_entry], ignore_index=True)
                updated['Date'] = updated['Date'].dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=updated)
                st.success(f"Saved {f_cat}!")
                time.sleep(1)
                st.rerun()
            elif f_amt is None: st.error("Please enter an amount.")
            else: st.error("Please add a category first!")

# --- BUDGET TAB (Profit & Loss Style with Custom Centered Headings) ---
with tab_budget:
    st.subheader("Monthly Budget Planner")
    
    now = datetime.now()
    years = list(range(2023, 2035))
    months = list(calendar.month_name)[1:]
    
    c1, c2 = st.columns(2)
    selected_month = c1.selectbox("Month", months, index=now.month - 1)
    selected_year = c2.selectbox("Year", years, index=years.index(now.year))
    
    month_num = months.index(selected_month) + 1
    month_str = f"{selected_year}-{month_num:02d}"
    
    # Use the globally clean df_t
    t_month = df_t[(df_t['Date'].dt.year == selected_year) & (df_t['Date'].dt.month == month_num)]
    actuals = t_month.groupby('Category')['Amount'].sum().to_dict()
    
    b_month = df_b[df_b['Month'] == month_str] if not df_b.empty else pd.DataFrame(columns=["Month", "Category", "Amount"])
    
    # BUDGET ROLLOVER
    if b_month.empty and not df_b.empty:
        valid_months = df_b['Month'].dropna().astype(str).tolist()
        if valid_months:
            recent_month = max(valid_months)
            recent_b = df_b[df_b['Month'] == recent_month]
            planned = recent_b.set_index('Category')['Amount'].to_dict()
            st.info(f"💡 **New Month!** Pre-filled with budget data from **{recent_month}**. Click 'Save Budget Planner' below to lock it in.")
        else:
            planned = {}
    else:
        planned = b_month.set_index('Category')['Amount'].to_dict() if not b_month.empty else {}
    
    # Calculate global Net Totals (Ignoring headers)
    tot_inc_p = sum(float(planned.get(c, 0.0)) for c in df_c[df_c["Type"] == "Income"]["Name"])
    tot_inc_a = sum(float(actuals.get(c, 0.0)) for c in df_c[df_c["Type"] == "Income"]["Name"])
    tot_exp_p = sum(float(planned.get(c, 0.0)) for c in df_c[df_c["Type"] == "Expense"]["Name"])
    tot_exp_a = sum(float(actuals.get(c, 0.0)) for c in df_c[df_c["Type"] == "Expense"]["Name"])
    
    st.markdown("### Net Balance")
    nc1, nc2, nc3 = st.columns(3)
    nc1.metric("Planned Net", f"${tot_inc_p - tot_exp_p:,.0f}")
    nc2.metric("Actual Net", f"${tot_inc_a - tot_exp_a:,.0f}")
    nc3.metric("Variance", f"${(tot_inc_a - tot_exp_a) - (tot_inc_p - tot_exp_p):,.0f}")
    
    col_config = {
        "Order": st.column_config.NumberColumn("Sort", step=1, help="Lower numbers appear first"),
        "Category": st.column_config.TextColumn("Category", disabled=True),
        "Planned": st.column_config.NumberColumn("Planned ($)", format="%d", step=1),
        "Actual": st.column_config.NumberColumn("Actual ($)", format="%d", disabled=True),
        "Diff": st.column_config.NumberColumn("Diff", format="%d", disabled=True)
    }

    all_budget_edits = []
    
    def highlight_actual_diff(row):
        styles = [''] * len(row)
        try:
            diff = float(row['Diff'])
            color = ''
            
            if diff > 0: color = 'color: #2e7d32; font-weight: 600;' # Green
            elif diff < 0: color = 'color: #d32f2f; font-weight: 600;' # Red
            
            if color:
                styles[row.index.get_loc('Actual')] = color
                styles[row.index.get_loc('Diff')] = color
        except Exception:
            pass
        return styles

    def render_budget_section(base_type, icon):
        st.markdown(f"### {icon} {base_type.upper()}")
        
        items = df_c[df_c["Type"].isin([base_type, f"{base_type} Header"])].sort_values(by=["Order", "Name"])
        
        current_cats = []
        editor_idx = 0
        
        def flush_cats(idx):
            if current_cats:
                data = []
                for item in current_cats:
                    c = item["Name"]
                    o = item["Order"]
                    p = float(planned.get(c, 0.0))
                    a = float(actuals.get(c, 0.0))
                    diff = float(a - p) if base_type == "Income" else float(p - a)
                    data.append({"Order": o, "Category": c, "Planned": p, "Actual": a, "Diff": diff})
                
                df_to_edit = pd.DataFrame(data)
                styled_df = df_to_edit.style.apply(highlight_actual_diff, axis=1)
                
                ed = st.data_editor(styled_df, hide_index=True, column_config=col_config, use_container_width=True, key=f"ed_{base_type}_{idx}_{month_str}")
                all_budget_edits.append(ed)
                current_cats.clear()
                return idx + 1
            return idx

        for _, item in items.iterrows():
            if item["Type"] == f"{base_type} Header":
                editor_idx = flush_cats(editor_idx)
                
                st.markdown(f"""
                    <div style='background-color:{item['Color']}; color:#ffffff; text-align:center; 
                    padding:8px; border-radius:6px; font-weight:800; font-size:1.1rem; 
                    margin-top:10px; margin-bottom:10px; text-shadow: 1px 1px 2px rgba(0,0,0,0.4);'>
                        {item['Name']}
                    </div>
                """, unsafe_allow_html=True)
            else:
                current_cats.append(item)
                
        flush_cats(editor_idx)
        st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)

    render_budget_section("Income", "💰")
    render_budget_section("Expense", "💸")

    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    if st.button("💾 Save Budget Planner", use_container_width=True):
        new_b = []
        updated_c = df_c.copy()
        
        for ed_df in all_budget_edits:
            if not ed_df.empty:
                for _, r in ed_df.iterrows(): 
                    new_b.append({"Month": month_str, "Category": r["Category"], "Amount": r["Planned"]})
                    updated_c.loc[updated_c["Name"] == r["Category"], "Order"] = r["Order"]
                    
        new_b_df = pd.DataFrame(new_b)
        
        if df_b.empty:
            updated_b = new_b_df
        else:
            latest_b = df_b[df_b["Month"] != month_str]
            updated_b = pd.concat([latest_b, new_b_df], ignore_index=True)
            
        conn.update(worksheet="budgets", data=updated_b)
        conn.update(worksheet="categories", data=updated_c) 
        st.success(f"Budget & Ordering saved for {selected_month} {selected_year}!")
        time.sleep(1)
        st.rerun()

    st.divider()
    st.markdown("### 🏷️ Manage Budget Headings")
    hc1, hc2 = st.columns(2)
    
    with hc1:
        st.markdown("**Create New Heading**")
        with st.form("add_heading_form", clear_on_submit=True):
            h_type = st.radio("Section", ["Expense", "Income"], horizontal=True)
            h_name = st.text_input("Heading Text", placeholder="e.g. Fixed Expenses")
            
            sc1, sc2 = st.columns(2)
            h_order = sc1.number_input("Sort Order", value=1, step=1, help="Place amongst categories")
            h_color = sc2.color_picker("Background Color", "#4682B4")
            
            st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
            if st.form_submit_button("Add Heading", use_container_width=True):
                if h_name:
                    new_h = pd.DataFrame([{"Type": f"{h_type} Header", "Name": h_name, "Order": h_order, "Color": h_color}])
                    updated_c = pd.concat([df_c, new_h], ignore_index=True)
                    conn.update(worksheet="categories", data=updated_c)
                    st.success("Heading Added!")
                    time.sleep(1)
                    st.rerun()
                    
    with hc2:
        st.markdown("**Existing Headings**")
        headers = df_c[df_c["Type"].str.contains("Header")]
        if headers.empty:
            st.caption("No headings yet.")
        else:
            inc_headers = headers[headers["Type"] == "Income Header"].sort_values(by="Order")
            exp_headers = headers[headers["Type"] == "Expense Header"].sort_values(by="Order")
            
            if not inc_headers.empty:
                st.caption("💰 Income Headings")
                for _, r in inc_headers.iterrows():
                    cc1, cc2 = st.columns([4, 1])
                    cc1.markdown(f"<div style='background-color:{r['Color']}; color:#fff; text-align:center; padding:4px; border-radius:4px; font-weight:bold; font-size:0.85rem; margin-bottom:5px;'>{r['Name']} (Order: {r['Order']})</div>", unsafe_allow_html=True)
                    if cc2.button("🗑️", key=f"del_h_{r['Name']}"):
                        new_c = df_c[df_c["Name"] != r["Name"]]
                        conn.update(worksheet="categories", data=new_c)
                        st.rerun()
            
            if not exp_headers.empty:
                st.caption("💸 Expense Headings")
                for _, r in exp_headers.iterrows():
                    cc1, cc2 = st.columns([4, 1])
                    cc1.markdown(f"<div style='background-color:{r['Color']}; color:#fff; text-align:center; padding:4px; border-radius:4px; font-weight:bold; font-size:0.85rem; margin-bottom:5px;'>{r['Name']} (Order: {r['Order']})</div>", unsafe_allow_html=True)
                    if cc2.button("🗑️", key=f"del_h_{r['Name']}"):
                        new_c = df_c[df_c["Name"] != r["Name"]]
                        conn.update(worksheet="categories", data=new_c)
                        st.rerun()

with tab2:
    if not df_t.empty:
        viz_df = df_t.copy()
        viz_df["Memo"] = viz_df["Memo"].apply(lambda x: "Unspecified" if str(x).lower() == "nan" or str(x).strip() == "" else str(x))
        inc_val = viz_df[viz_df["Type"] == "Income"]["Amount"].sum()
        exp_val = viz_df[viz_df["Type"] == "Expense"]["Amount"].sum()
        st.metric("All-Time Net Balance", f"${(inc_val - exp_val):,.0f}", delta=f"${inc_val:,.0f} In")
        c1, c2 = st.columns(2)
        with c1:
            dx = viz_df[viz_df["Type"] == "Expense"]
            if not dx.empty:
                fig_ex = px.sunburst(dx, path=['Category', 'Memo'], values='Amount', title="Expenses Breakdown")
                st.plotly_chart(fig_ex, use_container_width=True)
        with c2:
            di = viz_df[viz_df["Type"] == "Income"]
            if not di.empty:
                fig_in = px.sunburst(di, path=['Category', 'Memo'], values='Amount', title="Income Breakdown")
                st.plotly_chart(fig_in, use_container_width=True)
    else: st.info("No data yet.")

with tab3:
    if not df_t.empty:
        today = date.today()
        first_day = today.replace(day=1)
        last_day_num = calendar.monthrange(today.year, today.month)[1]
        last_day = today.replace(day=last_day_num)
        
        with st.expander("🔍 Filter View"):
            # 🛡️ WRAP IN FORM TO PREVENT LAG
            with st.form("history_filter_form"):
                c1, c2 = st.columns(2)
                with c1: start_f = st.date_input("From", first_day)
                with c2: end_f = st.date_input("To", last_day)
                
                with st.popover("Select Categories"):
                    st.markdown("**Income Categories**")
                    inc_df = df_c[df_c["Type"] == "Income"].sort_values(by=["Order", "Name"])
                    sel_inc = [cat for cat in inc_df["Name"] if st.checkbox(cat, value=True, key=f"f_inc_{cat}")]
                    
                    st.divider()
                    st.markdown("**Expense Categories**")
                    exp_df = df_c[df_c["Type"] == "Expense"].sort_values(by=["Order", "Name"])
                    sel_exp = [cat for cat in exp_df["Name"] if st.checkbox(cat, value=True, key=f"f_exp_{cat}")]
                
                st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
                apply_filters = st.form_submit_button("✅ Apply Filters", use_container_width=True)
                all_selected = sel_inc + sel_exp
                
        work_df = df_t.copy()
        work_df = work_df[(work_df["Date"].dt.date >= start_f) & (work_df["Date"].dt.date <= end_f) & (work_df["Category"].isin(all_selected))]
        f_net = work_df[work_df["Type"] == "Income"]["Amount"].sum() - work_df[work_df["Type"] == "Expense"]["Amount"].sum()
        st.markdown(f"**Filtered Net:** `${f_net:,.0f}`")
        
        work_df = work_df.sort_values(by="Date", ascending=False)
        st.markdown('<div class="hist-header"><div style="width:20%">DATE</div><div style="width:50%">CATEGORY</div><div style="width:30%; text-align:right">AMOUNT</div></div>', unsafe_allow_html=True)
        for i, row in work_df.iterrows():
            if pd.isnull(row['Date']): continue
            d_str = row['Date'].strftime('%m/%d')
            is_ex = row['Type'] == 'Expense'
            amt_val = row['Amount']
            icon = get_icon(row['Category'], row['Type'])
            price_color = "#d32f2f" if is_ex else "#2e7d32" 
            prefix = "-" if is_ex else "+"
            memo_display = f" ({row['Memo']})" if str(row.get('Memo', '')) != 'nan' and str(row.get('Memo', '')).strip() != '' else ''
            st.markdown('<div class="row-container">', unsafe_allow_html=True)
            st.markdown(f'<div class="trans-row"><div class="tr-date"><span>{d_str}</span></div><div class="tr-cat">{icon} {row["Category"]}{memo_display}</div><div class="tr-amt" style="color:{price_color};">{prefix}${amt_val:,.0f}</div></div>', unsafe_allow_html=True)
            if st.button(" ", key=f"h_{i}", use_container_width=True): edit_dialog(i, row)
            st.markdown('</div>', unsafe_allow_html=True)
    else: st.info("No data yet.")

with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    if st.button("🔄 Force Sync", use_container_width=True):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()
        
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
        
    st.divider()
    st.header("Categories")
    with st.form("cat_form", clear_on_submit=True):
        ct = st.selectbox("Type", ["Expense", "Income"])
        cn = st.text_input("Name")
        st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
        if st.form_submit_button("Add Category", use_container_width=True):
            if cn:
                st.cache_resource.clear()
                _, latest_c, _ = load_data_clean()
                # Order defaults to 10 for new entries
                new_cat = pd.DataFrame([{"Type": ct, "Name": cn, "Order": 10}])
                updated_c = pd.concat([latest_c, new_cat], ignore_index=True)
                conn.update(worksheet="categories", data=updated_c)
                st.success("Added!")
                time.sleep(0.5)
                st.rerun()
                
    st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
    st.header("Manage Existing Category")
    with st.container(border=True):
        manage_type = st.selectbox("View Type", ["Expense", "Income"], key="m_type")
        m_df_sorted = df_c[df_c["Type"] == manage_type].sort_values(by=["Order", "Name"])
        manage_list = m_df_sorted["Name"].tolist()
        
        target_cat = st.selectbox("Select Category", manage_list, key="m_list")
        st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
        if st.button("🔧 Manage Category", use_container_width=True):
            if target_cat: manage_cat_dialog(target_cat, manage_type)
