from flask import Flask
from models import db, User
from routes import bp as routes_bp
from flask_login import LoginManager
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Connect to Supabase/PostgreSQL if DATABASE_URL is set, otherwise use local SQLite
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # URL encode password to handle special characters (like '@') in the password
    if "://" in database_url:
        prefix, rest = database_url.split("://", 1)
        if "@" in rest:
            # The last '@' separates credentials from host
            creds, host_part = rest.rsplit("@", 1)
            if ":" in creds:
                user, password = creds.split(":", 1)
                import urllib.parse
                # quote_plus encodes special characters like '@' -> '%40'
                encoded_password = urllib.parse.quote_plus(password)
                database_url = f"{prefix}://{user}:{encoded_password}@{host_part}"

    # SQLAlchemy requires postgresql+pg8000 for pure-Python pg8000 driver
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+pg8000://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+pg8000://", 1)
    
    # Strip query parameters (like ?pgbouncer=true) which are not supported by pg8000 connect()
    if "?" in database_url:
        database_url = database_url.split("?")[0]
        
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Vercel's filesystem is read-only except for /tmp.
    # Data stored here will reset every time the serverless function sleeps.
    if os.environ.get('VERCEL') == '1':
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/bank.db'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bank.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Auto-create tables in Supabase (or SQLite) on boot
with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.login_view = 'routes.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(routes_bp)

if __name__ == '__main__':
    app.run(debug=True)
