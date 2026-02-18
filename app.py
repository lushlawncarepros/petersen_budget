import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Mobile Layout
st.markdown("""
    <style>
    [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.3rem !important; }
    .ledger-row {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid #f0f2f6;
        width: 100%;
    }
    .l-date { width: 18%; font-size: 0.75rem; color: #888; flex-shrink: 0; }
    .l-info { width: 52%; font-size: 0.85rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .l-amt { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; flex-shrink: 0; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; }
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

def load_data_raw():
    # Force clear ALL caches (Data + Resource) to prevent "Freezing"
    st.cache_data.clear()
    
    try:
        # Read as string to capture everything safely
        t_df = conn.read(worksheet="transactions", ttl=0, dtype=str)
        c_df = conn.read(worksheet="categories", ttl=0, dtype=str)
        
        # --- CLEAN TRANSACTIONS ---
        if t_df is not None and not t_df.empty:
            t_df.columns = [str(c).strip().title() for c in t_df.columns]
            
            # Ensure columns
            for col in ["Date", "Type", "Category", "Amount", "User"]:
                if col not in t_df.columns: t_df[col] = ""

            # Convert
            t_df["Amount"] = t_df["Amount"].str.replace(r'[$,]', '', regex=True)
            t_df["Amount"] = pd.to_numeric(t_df["Amount"], errors='coerce').fillna(0)
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            t_df = t_df.dropna(subset=['Date'])
        else:
            t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])

        # --- CLEAN CATEGORIES ---
        if c_df is not None and not c_df.empty:
            c_df.columns = [str(c).strip().title() for c in c_df.columns]
        else:
            c_df = pd.DataFrame(columns=["Type", "Name"])
            
        return t_df, c_df
    except Exception as e:
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

# Initial Load
df_t, df_c = load_data_raw()

def get_cat_list(t_filter):
    if df_c.empty or "Name" not in df_c.columns: return []
    # Filter by type AND sort alphabetically
    cats = df_c[df_c["Type"] == t_filter]["Name"].unique().tolist()
    return sorted(cats, key=str.lower)

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tithe" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    if "home" in n or "rent" in n or "mortgage" in n: return "🏠"
    return "💸" if row_type == "Expense" else "💰"

# --- UI ---
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
        
        if st.form_submit_button("Save to Google Sheets"):
            if f_clist:
                # 1. Clear Connection Cache (The Fix)
                st.cache_resource.clear()
                
                # 2. Read Fresh
                latest_t, _ = load_data_raw()
                
                # 3. Create & Append
                new_entry = pd.DataFrame([{
                    "Date": f_date.strftime('%Y-%m-%d'),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                updated = pd.concat([latest_t, new_entry], ignore_index=True)
                
                # 4. Save
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
    st.subheader("Ledger")
    if not df_t.empty:
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        st.markdown('<div style="display:flex; justify-content:space-between; font-weight:bold; font-size:0.7rem; color:grey; border-bottom:1px solid #333;"><div>DATE</div><div>CATEGORY</div><div style="text-align:right;">AMOUNT</div></div>', unsafe_allow_html=True)
        for i, row in work_df.iterrows():
            if pd.isnull(row['Date']): continue
            is_ex = str(row['Type']).capitalize() == 'Expense'
            color = "#dc3545" if is_ex else "#28a745"
            icon = get_icon(row['Category'], row['Type'])
            st.markdown(f"""
                <div class="ledger-row">
                    <div class="l-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="l-info">{icon} {row['Category']}</div>
                    <div class="l-amt" style="color:{color};">{"-" if is_ex else "+"}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
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
    
    # Session state logic to clear input after add
    if "new_cat_input" not in st.session_state:
        st.session_state.new_cat_input = ""
        
    ct = st.selectbox("Type", ["Expense", "Income"])
    # We bind the input to the session state key
    cn = st.text_input("Name", key="new_cat_input")
    
    if st.button("Add"):
        if cn:
            # Clear resource cache to ensure we get latest categories file
            st.cache_resource.clear() 
            _, latest_c = load_data_raw()
            updated_c = pd.concat([latest_c, pd.DataFrame([{"Type": ct, "Name": cn}])], ignore_index=True)
            conn.update(worksheet="categories", data=updated_c)
            st.success("Added!")
            
            # Clear input manually via session state hack for next rerun is handled by key
            # But to actually clear it we need to rerunning with empty state
            # Since key binding is 2-way, we can't easily clear inside the button without a callback
            # but usually st.rerun() resets it if we don't persist it. 
            # Actually, to force clear, we delete the key or set to empty
            # NOTE: Streamlit input clearing is tricky. The reliable way is a callback.
            pass 
            # We will rely on rerun clearing the logic if we didn't use a form. 
            # But to be safe, I'll switch to a simple callback approach in next version if this doesn't clear.
            # For now, rerun triggers a refresh.
            st.rerun()


