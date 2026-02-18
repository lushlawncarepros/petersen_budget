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
    /* Force rows to stay horizontal on mobile */
    .t-row {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        padding: 12px 0;
        border-bottom: 1px solid #f0f2f6;
        width: 100%;
        gap: 5px;
    }
    .t-date { width: 18%; font-size: 0.75rem; color: #888; flex-shrink: 0; }
    .t-info { width: 47%; font-size: 0.85rem; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
    .t-amt { width: 20%; text-align: right; font-weight: bold; font-size: 0.9rem; flex-shrink: 0; }
    .t-action { width: 15%; text-align: right; flex-shrink: 0; }

    /* Button Styling */
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
    .edit-btn-small button { 
        height: 2.2em !important; 
        padding: 0 8px !important; 
        font-size: 0.75rem !important;
        background-color: #f0f2f6 !important;
        border: 1px solid #dcdfe3 !important;
    }
    
    /* Dialog Styling */
    div[data-testid="stDialog"] { border-radius: 20px; }
    .delete-btn button { background-color: #ff4b4b !important; color: white !important; }
    .update-btn button { background-color: #28a745 !important; color: white !important; }
    
    /* Hide Default Nav */
    div[data-testid="stSidebarNav"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENT AUTHENTICATION ---
USERS = {"ethan": "petersen1", "alesa": "petersen2"}

if "authenticated" not in st.session_state:
    # Check URL for ?user=ethan
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
            if rem: st.query_params["user"] = u
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state["authenticated"]:
    login_screen()
    st.stop()

# --- GOOGLE SHEETS CONNECTION ---
# No extra caching here to prevent the "Empty Connection" bug
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection Failed: {e}")
    st.stop()

def load_data():
    try:
        # Load transactions
        try:
            t = conn.read(worksheet="transactions", ttl=0)
            if t.empty: t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        except:
            t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        
        # Load categories
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
    except Exception as e:
        st.error(f"Data Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_transactions, df_cats = load_data()

def get_cat_list(type_filter):
    if df_cats.empty: return []
    return df_cats[df_cats["Type"] == type_filter]["Name"].unique().tolist()

# --- EDIT DIALOG ---
@st.dialog("Manage Entry")
def edit_dialog(idx, row):
    st.write(f"Editing: **{row['Category']}**")
    e_date = st.date_input("Date", row["Date"])
    clist = get_cat_list(row["Type"])
    e_cat = st.selectbox("Category", clist, index=clist.index(row["Category"]) if row["Category"] in clist else 0)
    e_amt = st.number_input("Amount ($)", value=float(row["Amount"]))
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="update-btn">', unsafe_allow_html=True)
        if st.button("Save Changes"):
            df_transactions.at[idx, "Date"] = e_date.strftime('%Y-%m-%d')
            df_transactions.at[idx, "Category"] = e_cat
            df_transactions.at[idx, "Amount"] = e_amt
            conn.update(worksheet="transactions", data=df_transactions)
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
        if st.button("Delete"):
            new_df = df_transactions.drop(idx)
            conn.update(worksheet="transactions", data=new_df)
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- MAIN INTERFACE ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add", "Visuals", "History"])

with tab1:
    t_type = st.radio("Entry Type", ["Expense", "Income"], horizontal=True)
    with st.form("add_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add one in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save to Sheets"):
            if f_clist:
                new_row = pd.DataFrame([{"Date": f_date.strftime('%Y-%m-%d'), "Type": t_type, "Category": f_cat, "Amount": f_amt, "User": st.session_state["user"]}])
                conn.update(worksheet="transactions", data=pd.concat([df_transactions, new_row], ignore_index=True))
                st.success("Entry Saved!")
                st.cache_resource.clear()
                st.rerun()
            else:
                st.error("Please add a category first!")

with tab2:
    if not df_transactions.empty:
        inc = df_transactions[df_transactions["Type"] == "Income"]["Amount"].sum()
        exp = df_transactions[df_transactions["Type"] == "Expense"]["Amount"].sum()
        st.metric("Family Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} Income")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Expenses**")
            dx = df_transactions[df_transactions["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", hole=0.4), use_container_width=True)
        with c2:
            st.write("**Income**")
            di = df_transactions[df_transactions["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", hole=0.4), use_container_width=True)
    else:
        st.info("Log data to see charts.")

with tab3:
    if not df_transactions.empty:
        # Search
        search = st.text_input("🔍 Search Categories", "")
        
        # Filter Logic
        work_df = df_transactions.copy().sort_values(by="Date", ascending=False)
        if search: work_df = work_df[work_df['Category'].str.contains(search, case=False)]
        
        # Custom Header
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #eee; font-weight:bold; color:grey; font-size:0.7rem;">
                <div style="width:18%;">DATE</div>
                <div style="width:47%;">CATEGORY</div>
                <div style="width:20%; text-align:right;">AMOUNT</div>
                <div style="width:15%;"></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in work_df.iterrows():
            is_ex = row['Type'] == 'Expense'
            color = "#dc3545" if is_ex else "#28a745"
            prefix = "-" if is_ex else "+"
            icon = "💸" if is_ex else "💰"
            
            # Using a single container with HTML for the "No-Stack" Row
            st.markdown(f"""
                <div class="t-row">
                    <div class="t-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="t-info">{icon} {row['Category']}</div>
                    <div class="t-amt" style="color:{color};">{prefix}${row['Amount']:,.0f}</div>
                    <div class="t-action" id="btn_container_{i}"></div>
                </div>
            """, unsafe_allow_html=True)
            
            # We place the real Streamlit button in the last slot of a row using columns
            # to maintain interactivity while the rest is forced HTML.
            _, _, _, btn_col = st.columns([18, 47, 20, 15])
            with btn_col:
                st.markdown('<div class="edit-btn-small" style="margin-top:-45px;">', unsafe_allow_html=True)
                if st.button("Edit", key=f"edit_btn_{i}"):
                    edit_dialog(i, row)
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("History is currently empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    st.divider()
    st.subheader("Manage Categories")
    c_type = st.selectbox("Type", ["Expense", "Income"])
    c_new = st.text_input("Category Name")
    if st.button("Add Category"):
        if c_new and c_new not in get_cat_list(c_type):
            new_c = pd.DataFrame([{"Type": c_type, "Name": c_new}])
            conn.update(worksheet="categories", data=pd.concat([df_cats, new_c], ignore_index=True))
            st.success(f"Added {c_new}")
            st.cache_resource.clear()
            st.rerun()

