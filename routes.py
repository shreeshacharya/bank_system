from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Transaction

bp = Blueprint('routes', __name__)

@bp.route('/')
@login_required
def index():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.timestamp.desc()).limit(10).all()
    total_users = User.query.count()
    savings_count = User.query.filter_by(account_type='savings').count()
    current_count = User.query.filter_by(account_type='current').count()
    return render_template('index.html', transactions=transactions, total_users=total_users, savings_count=savings_count, current_count=current_count)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        account_type = request.form.get('account_type', 'savings')
        
        user_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()
        
        if user_exists:
            flash('Username already exists.', 'danger')
        elif email_exists:
            flash('Email already registered.', 'danger')
        else:
            new_user = User(
                username=username, 
                email=email, 
                password_hash=generate_password_hash(password),
                account_type=account_type
            )
            db.session.add(new_user)
            db.session.commit()
            
            # ── PostHog ──────────────────────────────────────────────────
            import posthog_client as ph
            ph.identify(username, {"username": username, "email": email, "account_type": account_type})
            ph.track('user_signed_up', username, {
                "account_type": account_type,
            })
            # ─────────────────────────────────────────────────────────────
            
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('routes.login'))
            
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            
            # ── PostHog: identify + login event ──────────────────────────
            from flask import session
            from datetime import datetime
            import posthog_client as ph
            session['login_time'] = datetime.now().isoformat()
            ph.identify(user.username, {"username": user.username, "email": user.email})
            ph.track('user_logged_in', user.username, {
                "login_time": session['login_time'],
                "ip_address": request.remote_addr,
            })
            # ─────────────────────────────────────────────────────────────
            
            return redirect(url_for('routes.index'))
        else:
            # ── PostHog: failed login ────────────────────────────────────
            import posthog_client as ph
            ph.track('login_failed', username or 'unknown', {
                "ip_address": request.remote_addr,
            })
            # ─────────────────────────────────────────────────────────────
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    # ── PostHog: logout event with session duration ──────────────────────
    from flask import session
    from datetime import datetime
    import posthog_client as ph
    username = current_user.username
    login_time_str = session.get('login_time')
    session_duration = None
    if login_time_str:
        try:
            login_dt = datetime.fromisoformat(login_time_str)
            session_duration = round((datetime.now() - login_dt).total_seconds())
        except Exception:
            pass

    ph.track('user_logged_out', username, {
        "session_duration_seconds": session_duration,
        "logout_time": datetime.now().isoformat(),
    })
    # ────────────────────────────────────────────────────────────────────
    logout_user()
    return redirect(url_for('routes.login'))

@bp.route('/transaction', methods=['GET', 'POST'])
@login_required
def transaction():
    if request.method == 'POST':
        action = request.form.get('action')
        amount = float(request.form.get('amount', 0))
        description = request.form.get('description', '')
        
        if amount <= 0:
            flash('Amount must be greater than zero.', 'danger')
            return redirect(url_for('routes.transaction'))
            
        if action == 'deposit':
            current_user.balance += amount
            tx = Transaction(user_id=current_user.id, type='deposit', amount=amount, description=description)
            db.session.add(tx)
            db.session.commit()
            
            # ── PostHog ──────────────────────────────────────────────────
            import posthog_client as ph
            ph.track('deposit_made', current_user.username, {
                "amount": amount,
                "description": description,
            })
            # ─────────────────────────────────────────────────────────────
            
            flash('Deposit successful.', 'success')
            return redirect(url_for('routes.index'))
            
        elif action == 'withdraw':
            if current_user.balance < amount:
                flash('Insufficient balance.', 'danger')
            else:
                current_user.balance -= amount
                tx = Transaction(user_id=current_user.id, type='withdraw', amount=amount, description=description)
                db.session.add(tx)
                db.session.commit()
                
                # ── PostHog ──────────────────────────────────────────────
                import posthog_client as ph
                ph.track('withdrawal_made', current_user.username, {
                    "amount": amount,
                    "description": description,
                })
                # ─────────────────────────────────────────────────────────
                
                flash('Withdrawal successful.', 'success')
                return redirect(url_for('routes.index'))
                
        elif action == 'transfer':
            target_username = request.form.get('target_username')
            target_user = User.query.filter_by(username=target_username).first()
            
            if not target_user:
                flash('Target user not found.', 'danger')
            elif target_user.id == current_user.id:
                flash('Cannot transfer to yourself.', 'danger')
            elif current_user.balance < amount:
                flash('Insufficient balance for transfer.', 'danger')
            else:
                current_user.balance -= amount
                target_user.balance += amount
                
                tx_out = Transaction(user_id=current_user.id, type='transfer_out', amount=amount, description=f'Transfer to {target_user.username}: {description}')
                tx_in = Transaction(user_id=target_user.id, type='transfer_in', amount=amount, description=f'Transfer from {current_user.username}: {description}')
                
                db.session.add(tx_out)
                db.session.add(tx_in)
                db.session.commit()
                
                # ── PostHog ──────────────────────────────────────────────
                import posthog_client as ph
                ph.track('transfer_made', current_user.username, {
                    "amount": amount,
                    "recipient": target_username,
                    "description": description,
                })
                # ─────────────────────────────────────────────────────────
                
                flash('Transfer successful.', 'success')
                return redirect(url_for('routes.index'))
                
    return render_template('transaction.html')


@bp.route('/debug-db')
def debug_db():
    try:
        from flask import current_app
        uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
        if not uri:
            return "Active Database URI: Not Set"
            
        uri_str = str(uri)
        masked_uri = uri_str
        if "@" in uri_str:
            parts = uri_str.split("@")
            prefix = parts[0]
            host = parts[1]
            if "://" in prefix:
                db_type, creds = prefix.split("://", 1)
                if ":" in creds:
                    username = creds.split(":")[0]
                    masked_uri = f"{db_type}://{username}:****@{host}"
                else:
                    masked_uri = f"{db_type}://{creds}:****@{host}"
        return f"Active Database URI: {masked_uri}"
    except Exception as e:
        return f"Error parsing DB URI: {str(e)}"


