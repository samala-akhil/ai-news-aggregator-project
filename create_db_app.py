from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db, User  # assuming you already have models.py with User model

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///news.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database with app
db.init_app(app)

# Create database
with app.app_context():
    db.create_all()
    print("✅ Database and tables created successfully!")
