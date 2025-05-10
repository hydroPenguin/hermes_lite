# web_api/database.py

from flask_sqlalchemy import SQLAlchemy
from extensions import db

def init_db(app):
    print(f"[init_db] Using DB URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    with app.app_context():
        db.create_all()
        print("[init_db] create_all() called")
