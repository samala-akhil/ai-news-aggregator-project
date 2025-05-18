from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email, Length
from wtforms.validators import DataRequired, Email
import requests
import os
from gtts import gTTS
import io
import telegram
from flask_wtf.csrf import CSRFProtect

# ------------------------
# App Configuration
# ------------------------
app = Flask(__name__)
app.secret_key = 'b7f1c973af204efba894d2ab2433ee7a'  # Secret key for CSRF protection and sessions
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ------------------------
# Extensions Setup
# ------------------------
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)  # Enable CSRF protection

# ------------------------
# Telegram Setup
# ------------------------
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or '8173091809:AAEpRD1-MypO5h0VPG9_YfqsB0P9FDT_mq0'
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID') or '8173091809'
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# ------------------------
# Models
# ------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    profile_image = db.Column(db.String(150), default='default.png')

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(300))
    url = db.Column(db.String(300))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------------
# Utility Functions
# ------------------------
def get_news(query, page=1):
    api_key = os.getenv('NEWS_API_KEY') or 'df47efb7b3bc49aba14a7c87da87c972'
    url = f'https://newsapi.org/v2/everything?q={query}&page={page}&pageSize=10&apiKey={api_key}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('articles', []), data.get('totalResults', 0)
    else:
        print(f"News API error: {response.status_code} - {response.text}")
        return [], 0

def get_weather(city='New York'):
    api_key = os.getenv('WEATHER_API_KEY') or '7895b25915c4f06ae846ff57d526fab'
    url = f'https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def send_telegram_alert(message):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"Telegram error: {e}")

# ------------------------
# Forms
# ------------------------
class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=3, max=150)])
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=6, max=256)])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# ------------------------
# Routes
# ------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.')
        send_telegram_alert(f"New user registered: {username}")
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return f"Hello, {current_user.username}! Welcome to your dashboard."

@app.route("/", methods=["GET", "POST"])
def home():
    query = request.form.get("query") or request.args.get("query")
    page = int(request.args.get("page", 1))
    if not query:
        query = "latest"
    articles, total_results = get_news(query, page)
    results_per_page = 10
    total_pages = (total_results // results_per_page) + (1 if total_results % results_per_page else 0)

    search_history = session.get("search_history", [])
    if query not in search_history:
        search_history.append(query)
        session["search_history"] = search_history

    weather = get_weather()
    bookmarks = []
    if current_user.is_authenticated:
        bookmarks = Bookmark.query.filter_by(user_id=current_user.id).all()

    return render_template(
        "index.html",
        articles=articles,
        query=query,
        page=page,
        total_pages=total_pages,
        search_history=search_history,
        weather=weather,
        bookmarks=bookmarks
    )

@app.route("/audio/<int:article_id>")
def audio(article_id):
    articles, _ = get_news('latest')
    if 0 <= article_id < len(articles):
        article = articles[article_id]
        tts = gTTS(text=article.get('description', 'No description available'), lang='en')
        audio_file = io.BytesIO()
        tts.save(audio_file)
        audio_file.seek(0)
        return send_file(audio_file, mimetype="audio/mp3")
    else:
        return "Invalid article ID", 404

@app.route('/bookmark', methods=['POST'])
@login_required
def bookmark():
    title = request.form['title']
    url = request.form['url']
    bookmark = Bookmark(user_id=current_user.id, title=title, url=url)
    db.session.add(bookmark)
    db.session.commit()
    flash('Article bookmarked successfully!')
    return redirect(url_for('home'))

@app.route('/bookmarks')
@login_required
def bookmarks():
    user_bookmarks = Bookmark.query.filter_by(user_id=current_user.id).all()
    return render_template('bookmarks.html', bookmarks=user_bookmarks)

# ------------------------
# Run the App
# ------------------------
if __name__ == '__main__':
    app.run(debug=True)
