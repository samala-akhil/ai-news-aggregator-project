from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from flask import jsonify
from wtforms import StringField, PasswordField, SubmitField, FileField
from wtforms.validators import InputRequired, Email, Length, EqualTo, DataRequired
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename

import os
import requests
import telegram
from gtts import gTTS
import io

# ------------------------
# App Configuration
# ------------------------
app = Flask(__name__)
app.secret_key = 'df47efb7b3bc49aba14a7c87da87c972'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# ------------------------
# Extensions Setup
# ------------------------
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)

# ------------------------
# Telegram Setup
# ------------------------
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or 'your_fallback_bot_token'
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID') or 'your_chat_id'
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
# Forms
# ------------------------
class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Login')

class SettingsForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    profile_image = FileField('Profile Image')
    submit = SubmitField('Update Settings')

# ------------------------
# Utility Functions
# ------------------------
def get_news(query, page=1):
    api_key = 'df47efb7b3bc49aba14a7c87da87c972'
    url = f'https://newsapi.org/v2/everything?q={query}&page={page}&pageSize=10&apiKey={api_key}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('articles', []), data.get('totalResults', 0)
    return [], 0

def get_weather(city):
    api_key = '7895b25915c4f06ae846ff57d526fab'
    url = f'https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return {
                'description': data['weather'][0]['description'].capitalize(),
                'temperature': data['main']['temp'],
                'icon': data['weather'][0]['icon']
            }
    except Exception as e:
        print("Weather API error:", e)
    return None

def send_telegram_alert(message):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"Telegram error: {e}")

# ------------------------
# Routes
# ------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first():
            flash('Username or email already exists')
            return redirect(url_for('register'))
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data)
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful!')
        send_telegram_alert(f"New user registered: {form.username.data}")
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    city = request.form.get('city', 'London')
    weather = get_weather(city)
    articles, _ = get_news("Latest")
    return render_template('dashboard.html', weather=weather, articles=articles)

@app.route('/check_weather', methods=['POST'])
def check_weather():
    city = request.form.get('city')
    weather = get_weather(city)
    if weather:
        return render_template('dashboard.html', weather=weather)
    flash("Weather unavailable. Please try again.", "danger")
    return redirect(url_for('dashboard'))

@app.route("/search", methods=["GET", "POST"])
def search():
    query = request.args.get('query', '')
    page = int(request.args.get('page', 1))
    articles, total_results = get_news(query, page)
    total_pages = (total_results // 10) + (1 if total_results % 10 else 0)
    return render_template("dashboard.html", articles=articles, query=query, page=page, total_pages=total_pages)

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
    return "Invalid article ID", 404

@app.route('/bookmark', methods=['POST'])
@login_required
def bookmark():
    bookmark = Bookmark(user_id=current_user.id, title=request.form['title'], url=request.form['url'])
    db.session.add(bookmark)
    db.session.commit()
    flash('Article bookmarked successfully!')
    return redirect(url_for('home'))

@app.route('/bookmarks')
@login_required
def bookmarks():
    user_bookmarks = Bookmark.query.filter_by(user_id=current_user.id).all()
    return render_template('bookmarks.html', bookmarks=user_bookmarks)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    form = SettingsForm()
    user = current_user

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        profile_pic = request.files.get("profile_pic")

        # Check for username/email duplicates (excluding current user)
        if User.query.filter(User.username == username, User.id != user.id).first():
            flash("Username already taken", "danger")
            return redirect(url_for("settings"))

        if User.query.filter(User.email == email, User.id != user.id).first():
            flash("Email already taken", "danger")
            return redirect(url_for("settings"))

        # Update username and email
        user.username = username
        user.email = email

        # Handle profile picture upload
        if profile_pic and profile_pic.filename != '':
            filename = secure_filename(profile_pic.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_pic.save(filepath)
            user.profile_image = filename

        db.session.commit()
        flash("Settings updated successfully", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html", user=user)



@app.route("/")
def home():
    query = request.args.get("query", "latest")
    page = int(request.args.get("page", 1))
    articles, total_results = get_news(query, page)
    total_pages = (total_results // 10) + (1 if total_results % 10 else 0)
    search_history = session.get("search_history", [])
    if query not in search_history:
        search_history.append(query)
        session["search_history"] = search_history
    weather = get_weather("London")
    bookmarks = Bookmark.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    return render_template("index.html", articles=articles, query=query, page=page,
                           total_pages=total_pages, search_history=search_history,
                           weather=weather, bookmarks=bookmarks)

# ------------------------
# Run the App
# ------------------------
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
