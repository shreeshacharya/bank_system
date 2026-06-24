from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import os
from types import SimpleNamespace
from datetime import datetime
import bank_database as db
import posthog_client as ph

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# ── PostHog Template Variables ─────────────────────────────────────────────
@app.context_processor
def inject_posthog():
    return {
        'posthog_api_key': os.environ.get('POSTHOG_API_KEY'),
        'posthog_host': os.environ.get('POSTHOG_HOST', 'https://eu.i.posthog.com')
    }


# -------------------- Login Auth -------------------- #
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if db.validate_user(username, password):
            session['username'] = username
            session['login_time'] = datetime.now().isoformat()

            # ── PostHog: identify + login event ──────────────────────────
            ph.identify(username, {"username": username})
            ph.track('user_logged_in', username, {
                "login_time": session['login_time'],
                "ip_address": request.remote_addr,
            })
            # ─────────────────────────────────────────────────────────────

            return redirect(url_for('index'))

        # ── PostHog: failed login ────────────────────────────────────────
        ph.track('login_failed', request.form.get('username', 'unknown'), {
            "ip_address": request.remote_addr,
        })
        # ─────────────────────────────────────────────────────────────────

        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    login_time_str = session.get('login_time')

    # ── PostHog: logout event with session duration ──────────────────────
    session_duration = None
    if login_time_str:
        login_dt = datetime.fromisoformat(login_time_str)
        session_duration = round((datetime.now() - login_dt).total_seconds())

    ph.track('user_logged_out', username, {
        "session_duration_seconds": session_duration,
        "logout_time": datetime.now().isoformat(),
    })
    # ────────────────────────────────────────────────────────────────────

    session.pop('username', None)
    session.pop('login_time', None)
    return redirect(url_for('login'))

# -------------------- Account Operations -------------------- #
@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        accNo = int(request.form['accNo'])
        name = request.form['name']
        acc_type = request.form['type'].upper()
        deposit = int(request.form['deposit'])
        try:
            db.create_account(accNo, name, acc_type, deposit)
            flash('Account created successfully')

            # ── PostHog ──────────────────────────────────────────────────
            ph.track('account_created', session['username'], {
                "accNo": accNo,
                "acc_type": acc_type,
                "initial_deposit": deposit,
            })
            # ─────────────────────────────────────────────────────────────

        except Exception as e:
            flash(str(e))
        return redirect(url_for('create'))
    return render_template('create.html')

@app.route('/delete', methods=['GET', 'POST'])
@login_required
def delete():
    if request.method == 'POST':
        accNo = int(request.form['accNo'])
        db.delete_account(accNo)
        flash('Account deleted')

        # ── PostHog ──────────────────────────────────────────────────────
        ph.track('account_deleted', session['username'], {"accNo": accNo})
        # ─────────────────────────────────────────────────────────────────

        return redirect(url_for('delete'))
    return render_template('delete.html')

@app.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    if request.method == 'POST':
        accNo = int(request.form['accNo'])
        amount = int(request.form['amount'])
        try:
            db.update_balance(accNo, amount, mode=1)
            flash('Deposited successfully')

            # ── PostHog ──────────────────────────────────────────────────
            ph.track('deposit_made', session['username'], {
                "accNo": accNo,
                "amount": amount,
            })
            # ─────────────────────────────────────────────────────────────

        except Exception as e:
            flash(str(e))
        return redirect(url_for('deposit'))
    return render_template('deposit.html')

@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    if request.method == 'POST':
        accNo = int(request.form['accNo'])
        amount = int(request.form['amount'])
        try:
            db.update_balance(accNo, amount, mode=2)
            flash('Withdrawn successfully')

            # ── PostHog ──────────────────────────────────────────────────
            ph.track('withdrawal_made', session['username'], {
                "accNo": accNo,
                "amount": amount,
            })
            # ─────────────────────────────────────────────────────────────

        except Exception as e:
            flash(str(e))
        return redirect(url_for('withdraw'))
    return render_template('withdraw.html')

@app.route('/balance', methods=['GET', 'POST'])
@login_required
def balance():
    result = None
    if request.method == 'POST':
        accNo = int(request.form['accNo'])
        result = db.get_balance(accNo)
        if result is None:
            flash('Account not found')
        else:
            # ── PostHog ──────────────────────────────────────────────────
            ph.track('balance_checked', session['username'], {"accNo": accNo})
            # ─────────────────────────────────────────────────────────────

    return render_template('balance.html', result=result)

@app.route('/modify', methods=['GET', 'POST'])
@login_required
def modify():
    account = None
    if request.method == 'POST':
        if request.form.get('update'):
            accNo = int(request.form['accNo'])
            name = request.form['name']
            acc_type = request.form['type'].upper()
            deposit = int(request.form['deposit'])
            db.modify_account(accNo, name, acc_type, deposit)
            flash('Account modified')

            # ── PostHog ──────────────────────────────────────────────────
            ph.track('account_modified', session['username'], {
                "accNo": accNo,
                "new_type": acc_type,
            })
            # ─────────────────────────────────────────────────────────────

            return redirect(url_for('modify'))
        else:
            accNo = int(request.form['accNo'])
            row = db.get_account(accNo)
            if row:
                account = SimpleNamespace(accNo=row[0], name=row[1], type=row[2], deposit=row[3])
            else:
                flash('Account not found')
    return render_template('modify.html', account=account)


@app.route('/accounts')
@login_required
def accounts():
    rows = db.get_all_accounts()
    accounts = []
    for r in rows:
        accounts.append(SimpleNamespace(accNo=r[0], name=r[1], type=r[2], deposit=r[3]))

    # ── PostHog ──────────────────────────────────────────────────────────
    ph.track('page_visited', session['username'], {"page_name": "all_accounts"})
    # ─────────────────────────────────────────────────────────────────────

    return render_template('accounts.html', accounts=accounts)

# -------------------- Dashboard -------------------- #
@app.route('/dashboard')
@login_required
def dashboard():
    total_accounts, total_balance, saving_count, current_count = db.get_dashboard_stats()

    # ── PostHog ──────────────────────────────────────────────────────────
    ph.track('page_visited', session['username'], {"page_name": "dashboard"})
    # ─────────────────────────────────────────────────────────────────────

    return render_template('dashboard.html',
                           total_accounts=total_accounts,
                           total_balance=total_balance,
                           saving_count=saving_count,
                           current_count=current_count)

# -------------------- Forgot Password -------------------- #
@app.route('/forgot_password')
def forgot_password():
    flash('This is a placeholder. Implement password reset logic.')
    return redirect(url_for('login'))

# -------------------- Signup -------------------- #
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if db.register_user(username, password):
            flash('Account created successfully. Please log in.')

            # ── PostHog ──────────────────────────────────────────────────
            ph.identify(username, {"username": username})
            ph.track('user_signed_up', username, {"signup_time": datetime.now().isoformat()})
            # ─────────────────────────────────────────────────────────────

            return redirect(url_for('login'))
        else:
            flash('Username already exists. Choose another.')
    return render_template('signup.html')


if __name__ == "__main__":
    app.secret_key = os.environ.get('SECRET_KEY', app.secret_key)
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
        use_reloader=True   # Auto-restart when any .py file changes
    )
