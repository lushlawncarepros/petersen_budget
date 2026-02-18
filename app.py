import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Family Budget", page_icon="💰", layout="centered")

# CSS for Mobile Optimization & Floating Dialogs
st.markdown("""
    <style>
    /* Global Button Style */
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; transition: 0.3s; }
    
    /* Transaction Card Style */
    .t-card {
        background-color: #ffffff;
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #eee;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* Sidebar Hide */
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* Dialog / Pop-up Styling */
    div[data-testid="stDialog"] { border-radius: 20px; }
    
    /* Specific Button Colors */
    .delete-btn button { background-color: #ff4b4b !important; color: white !important; border: none !important; }
    .update-btn button { background-color: #28a745 !important; color: white !important; border: none !important; }
    .edit-btn button { 
        height: 2.2em !important; 
        width: 60px !important; 
        font-size: 0.8rem !important; 
        background-color: #f0f2f6 !important; 
        color: #31333F !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- AUTHENTICATION ---
USERS = {"ethan": "petersen1", "alesa": "petersen2"}

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login():
    st.title("🔐 Petersen Budget Login")
    user = st.text_input("Username").lower()
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if user in USERS and USERS[user] == password:
            st.session_state["authenticated"] = True
            st.session_state["user"] = user.capitalize()
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
    except Exception as e:
        st.error(f"⚠️ Connection Error: {e}")
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
    except Exception as e:
        st.error(f"❌ Data Loading Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_transactions, df_cats = load_data()

def get_cat_list(type_filter):
    if df_cats.empty: return []
    return df_cats[df_cats["Type"] == type_filter]["Name"].unique().tolist()

# --- THE POP-UP DIALOG (MANAGEMENT WINDOW) ---
@st.dialog("Manage Transaction")
def manage_transaction(idx, row):
    st.write(f"Editing: **{row['Category']}**")
    
    # Edit Fields
    new_date = st.date_input("Date", row["Date"])
    new_cat = st.selectbox("Category", get_cat_list(row["Type"]), index=get_cat_list(row["Type"]).index(row["Category"]) if row["Category"] in get_cat_list(row["Type"]) else 0)
    new_amt = st.number_input("Amount ($)", value=float(row["Amount"]))
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="update-btn">', unsafe_allow_html=True)
        if st.button("Save Changes"):
            df_transactions.at[idx, "Date"] = new_date.strftime('%Y-%m-%d')
            df_transactions.at[idx, "Category"] = new_cat
            df_transactions.at[idx, "Amount"] = new_amt
            conn.update(worksheet="transactions", data=df_transactions)
            st.success("Updated!")
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
        if st.button("Delete"):
            updated_df = df_transactions.drop(idx)
            conn.update(worksheet="transactions", data=updated_df)
            st.success("Deleted!")
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()
    st.divider()
    st.header("⚙️ Settings")
    cat_type = st.selectbox("Category Type", ["Expense", "Income"])
    new_cat = st.text_input("New Category Name")
    if st.button("Add Category"):
        if new_cat and new_cat not in get_cat_list(cat_type):
            new_row = pd.DataFrame([{"Type": cat_type, "Name": new_cat}])
            updated_cats = pd.concat([df_cats, new_row], ignore_index=True)
            conn.update(worksheet="categories", data=updated_cats)
            st.success(f"Added {new_cat}")
            st.cache_resource.clear()
            st.rerun()

# --- MAIN APP ---
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
        # Filter Logic
        with st.expander("🔍 Search & Filter"):
            s_term = st.text_input("Search Category", "")
            s_date = st.date_input("Date Range", [datetime.now() - timedelta(days=30), datetime.now()])
        
        # Apply filters
        dff = df_transactions.copy()
        if s_term: dff = dff[dff['Category'].str.contains(s_term, case=False)]
        if len(s_date) == 2:
            dff = dff[(dff['Date'].dt.date >= s_date[0]) & (dff['Date'].dt.date <= s_date[1])]
        
        dff = dff.sort_values(by="Date", ascending=False)
        
        st.write(f"Showing {len(dff)} items:")
        
        # New Mobile-Friendly Row Layout
        for i, row in dff.iterrows():
            with st.container():
                # We use HTML for the card layout to force it to stay horizontal
                col_data, col_btn = st.columns([4, 1])
                with col_data:
                    st.markdown(f"""
                        <div style="line-height:1.2;">
                            <span style="font-size:0.8rem; color:grey;">{row['Date'].strftime('%m/%d')}</span><br>
                            <b>{row['Category']}</b><br>
                            <span style="color:#007bff;">${row['Amount']:,.2f}</span>
                        </div>
                    """, unsafe_allow_html=True)
                with col_btn:
                    st.markdown('<div class="edit-btn">', unsafe_allow_html=True)
                    if st.button("Edit", key=f"edit_{i}"):
                        manage_transaction(i, row)
                    st.markdown('</div>', unsafe_allow_html=True)
                st.divider()
    else:
        st.info("History is empty.")

