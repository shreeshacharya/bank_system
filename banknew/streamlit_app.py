import streamlit as st
import bank_database as db
from types import SimpleNamespace
from datetime import datetime
import posthog_client as ph

st.set_page_config(page_title="Bank Management System", layout="wide")

# Initialize session state
if 'username' not in st.session_state:
    st.session_state.username = None
if 'login_time' not in st.session_state:
    st.session_state.login_time = None

def login_page():
    """Login and Signup page."""
    st.title("Bank Management System")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if db.validate_user(username, password):
                st.session_state.username = username
                st.session_state.login_time = datetime.now().isoformat()

                # ── PostHog: identify + login event ──────────────────────
                ph.identify(username, {"username": username})
                ph.track('user_logged_in', username, {
                    "login_time": st.session_state.login_time,
                    "platform": "streamlit",
                })
                # ─────────────────────────────────────────────────────────

                st.success("Logged in successfully!")
                st.rerun()
            else:
                # ── PostHog: failed login ─────────────────────────────────
                ph.track('login_failed', username or 'unknown', {"platform": "streamlit"})
                # ─────────────────────────────────────────────────────────
                st.error("Invalid credentials")
    
    with tab2:
        st.subheader("Sign Up")
        new_user = st.text_input("New Username", key="signup_user")
        new_pass = st.text_input("New Password", type="password", key="signup_pass")
        if st.button("Sign Up"):
            if db.register_user(new_user, new_pass):
                # ── PostHog: signup event ─────────────────────────────────
                ph.identify(new_user, {"username": new_user})
                ph.track('user_signed_up', new_user, {
                    "signup_time": datetime.now().isoformat(),
                    "platform": "streamlit",
                })
                # ─────────────────────────────────────────────────────────
                st.success("Account created! Please log in.")
            else:
                st.error("Username already exists")

def main_app():
    """Main app after login."""
    st.sidebar.title(f"Welcome, {st.session_state.username}!")
    if st.sidebar.button("Logout"):
        username = st.session_state.username
        login_time_str = st.session_state.login_time

        # ── PostHog: logout event with session duration ───────────────────
        session_duration = None
        if login_time_str:
            login_dt = datetime.fromisoformat(login_time_str)
            session_duration = round((datetime.now() - login_dt).total_seconds())

        ph.track('user_logged_out', username, {
            "session_duration_seconds": session_duration,
            "logout_time": datetime.now().isoformat(),
            "platform": "streamlit",
        })
        # ─────────────────────────────────────────────────────────────────

        st.session_state.username = None
        st.session_state.login_time = None
        st.rerun()
    
    page = st.sidebar.radio("Select Page", 
                            ["Dashboard", "Create Account", "View Accounts", 
                             "Check Balance", "Deposit", "Withdraw", "Modify Account", "Delete Account"])

    # ── PostHog: track page navigation ───────────────────────────────────
    ph.track('page_visited', st.session_state.username, {
        "page_name": page,
        "platform": "streamlit",
    })
    # ─────────────────────────────────────────────────────────────────────
    
    if page == "Dashboard":
        dashboard_page()
    elif page == "Create Account":
        create_page()
    elif page == "View Accounts":
        accounts_page()
    elif page == "Check Balance":
        balance_page()
    elif page == "Deposit":
        deposit_page()
    elif page == "Withdraw":
        withdraw_page()
    elif page == "Modify Account":
        modify_page()
    elif page == "Delete Account":
        delete_page()

def dashboard_page():
    st.title("Dashboard")
    total_accounts, total_balance, saving_count, current_count = db.get_dashboard_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Accounts", total_accounts)
    col2.metric("Total Balance", f"₹{total_balance}")
    col3.metric("Savings Accounts", saving_count)
    col4.metric("Current Accounts", current_count)

def create_page():
    st.title("Create Account")
    with st.form("create_form"):
        accNo = st.number_input("Account Number", min_value=1)
        name = st.text_input("Account Holder Name")
        acc_type = st.selectbox("Account Type", ["Savings", "Current"])
        deposit = st.number_input("Initial Deposit", min_value=0)
        
        if st.form_submit_button("Create Account"):
            try:
                db.create_account(int(accNo), name, acc_type[0].upper(), int(deposit))

                # ── PostHog ───────────────────────────────────────────────
                ph.track('account_created', st.session_state.username, {
                    "accNo": int(accNo),
                    "acc_type": acc_type,
                    "initial_deposit": int(deposit),
                    "platform": "streamlit",
                })
                # ─────────────────────────────────────────────────────────

                st.success("Account created successfully!")
            except Exception as e:
                st.error(f"Error: {str(e)}")

def accounts_page():
    st.title("View All Accounts")
    rows = db.get_all_accounts()
    
    if rows:
        data = []
        for r in rows:
            data.append({
                "Account No": r[0],
                "Name": r[1],
                "Type": "Savings" if r[2] == "S" else "Current",
                "Balance": f"₹{r[3]}"
            })
        st.dataframe(data, use_container_width=True)
    else:
        st.info("No accounts found")

def balance_page():
    st.title("Check Balance")
    accNo = st.number_input("Enter Account Number", min_value=1, key="balance_accno")
    
    if st.button("Check Balance"):
        bal = db.get_balance(int(accNo))
        if bal is not None:
            # ── PostHog ───────────────────────────────────────────────────
            ph.track('balance_checked', st.session_state.username, {
                "accNo": int(accNo),
                "platform": "streamlit",
            })
            # ─────────────────────────────────────────────────────────────
            st.success(f"Balance: ₹{bal}")
        else:
            st.error("Account not found")

def deposit_page():
    st.title("Deposit Amount")
    with st.form("deposit_form"):
        accNo = st.number_input("Account Number", min_value=1, key="dep_accno")
        amount = st.number_input("Deposit Amount", min_value=1)
        
        if st.form_submit_button("Deposit"):
            try:
                db.update_balance(int(accNo), int(amount), mode=1)

                # ── PostHog ───────────────────────────────────────────────
                ph.track('deposit_made', st.session_state.username, {
                    "accNo": int(accNo),
                    "amount": int(amount),
                    "platform": "streamlit",
                })
                # ─────────────────────────────────────────────────────────

                st.success(f"Deposited ₹{amount} successfully!")
            except Exception as e:
                st.error(f"Error: {str(e)}")

def withdraw_page():
    st.title("Withdraw Amount")
    with st.form("withdraw_form"):
        accNo = st.number_input("Account Number", min_value=1, key="wd_accno")
        amount = st.number_input("Withdraw Amount", min_value=1)
        
        if st.form_submit_button("Withdraw"):
            try:
                db.update_balance(int(accNo), int(amount), mode=2)

                # ── PostHog ───────────────────────────────────────────────
                ph.track('withdrawal_made', st.session_state.username, {
                    "accNo": int(accNo),
                    "amount": int(amount),
                    "platform": "streamlit",
                })
                # ─────────────────────────────────────────────────────────

                st.success(f"Withdrawn ₹{amount} successfully!")
            except Exception as e:
                st.error(f"Error: {str(e)}")

def modify_page():
    st.title("Modify Account")
    accNo_lookup = st.number_input("Enter Account Number to Modify", min_value=1, key="mod_lookup")
    
    if st.button("Find Account"):
        row = db.get_account(int(accNo_lookup))
        if row:
            st.session_state.modify_account = SimpleNamespace(accNo=row[0], name=row[1], type=row[2], deposit=row[3])
    
    if 'modify_account' in st.session_state:
        acc = st.session_state.modify_account
        with st.form("modify_form"):
            new_name = st.text_input("Name", value=acc.name)
            new_type = st.selectbox("Account Type", ["Savings", "Current"], 
                                    index=0 if acc.type == "S" else 1)
            new_deposit = st.number_input("Balance", value=int(acc.deposit))
            
            if st.form_submit_button("Update Account"):
                try:
                    db.modify_account(int(acc.accNo), new_name, new_type[0].upper(), int(new_deposit))

                    # ── PostHog ───────────────────────────────────────────
                    ph.track('account_modified', st.session_state.username, {
                        "accNo": int(acc.accNo),
                        "new_type": new_type,
                        "platform": "streamlit",
                    })
                    # ─────────────────────────────────────────────────────

                    st.success("Account updated successfully!")
                    del st.session_state.modify_account
                except Exception as e:
                    st.error(f"Error: {str(e)}")

def delete_page():
    st.title("Delete Account")
    accNo = st.number_input("Enter Account Number to Delete", min_value=1, key="del_accno")
    
    if st.button("Delete Account", type="secondary"):
        try:
            db.delete_account(int(accNo))

            # ── PostHog ───────────────────────────────────────────────────
            ph.track('account_deleted', st.session_state.username, {
                "accNo": int(accNo),
                "platform": "streamlit",
            })
            # ─────────────────────────────────────────────────────────────

            st.success("Account deleted successfully!")
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Main logic
if st.session_state.username:
    main_app()
else:
    login_page()
