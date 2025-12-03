# app.py (fixed)
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, DateField
from wtforms.validators import DataRequired, Length, Email
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import pandas as pd
import json

# Load .env if present
load_dotenv()

app = Flask(__name__)   # fixed: use __name_

# ---------------- Configuration ----------------
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URI") or "sqlite:///collegefinder.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY") or "dev-secret-key"
app.config["SESSION_TYPE"] = "filesystem"

db = SQLAlchemy(app)
Session(app)

# ---------------- Helpers ----------------
def validate_input(data, required_fields):
    """Validate form input; returns list of error messages."""
    errors = []
    for field in required_fields:
        if not data.get(field):
            errors.append(f"{field.replace('_',' ').title()} is required")
    return errors

# ---------------- Forms ----------------
class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=1, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(min=7, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Note: percentile is stored as float in DB, but use StringField to accept decimals in input and parse safely
class ProfileForm(FlaskForm):
    name = StringField('Fullname', validators=[DataRequired()])
    phone_number = StringField('Phone number', validators=[DataRequired(), Length(min=7, max=20)])
    dob = DateField('Date Of Birth', validators=[DataRequired()], format='%Y-%m-%d')
    gender = StringField('Gender', validators=[DataRequired()])
    category = StringField('Category', validators=[DataRequired()])
    home_state = StringField('Home State', validators=[DataRequired()])
    district = StringField('District', validators=[DataRequired()])
    percentile = StringField('Percentile', validators=[DataRequired()])  # accept decimals as string
    submit = SubmitField('Profile')

# ---------------- Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    dob = db.Column(db.Date, nullable=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    gender = db.Column(db.String(10), nullable=True)
    category = db.Column(db.String(15), nullable=True)
    home_state = db.Column(db.String(25), nullable=True)
    district = db.Column(db.String(25), nullable=True)
    percentile = db.Column(db.Float, nullable=True)   # store as float
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

class College(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    cutoff = db.Column(db.Float, nullable=True)

class Branch(db.Model):
    id =  db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20))
    name = db.Column(db.String(200), nullable=False)

class Cutoff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round = db.Column(db.Integer, nullable=False)
    allocation_type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    merit_number = db.Column(db.Integer, nullable=True)
    percentile = db.Column(db.Float, nullable=True)

    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)

    college = db.relationship("College", backref="cutoffs")
    branch = db.relationship("Branch", backref="cutoffs")

class Placement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    percentage = db.Column(db.Float, nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    college =  db.relationship("College", backref="placement")

class CollegeBranch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round = db.Column(db.Integer, nullable=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    college = db.relationship("College", backref="college_branches")
    branch = db.relationship("Branch", backref="college_branches")

# Create tables
with app.app_context():
    db.create_all()

# ---------------- Routes ----------------
@app.route('/')
def index():
    return render_template("index.html")

# --------- Auth: Login / Logout / Register ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    session.permanent = True
    if session.get('user_id'):
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data

        errors = validate_input({'email': email, 'password': password}, ['email', 'password'])
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("login.html", form=form)

        try:
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                session["user_id"] = user.id
                session["email"] = user.email
                session["username"] = user.name
                flash(f"Welcome back, {user.name}", "success")
                return redirect(url_for("profile"))
            else:
                flash("Invalid username or password", "danger")
        except OperationalError:
            flash("Our database is temporarily unavailable. Please try again.", "warning")
            return redirect(url_for('login'))
    return render_template("login.html", form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        email = form.email.data.strip()
        phone_number = form.phone_number.data.strip()
        password = form.password.data

        errors = validate_input({'email': email, 'phone_number': phone_number, 'password': password},
                                ['email', 'phone_number', 'password'])

        try:
            if User.query.filter_by(email=email).first():
                errors.append("Email already used")
            if User.query.filter_by(phone_number=phone_number).first():
                errors.append("Phone number already used")
        except OperationalError:
            flash("Our database is temporarily unavailable. Please try again.", "warning")
            return redirect(url_for('register'))

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("register.html", form=form)

        try:
            hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
            new_user = User(name=name, email=email, phone_number=phone_number, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            session["user_id"] = new_user.id
            session["email"] = new_user.email
            session["username"] = new_user.name
            flash("Registered successfully", "success")
            return redirect(url_for('profile'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
            return render_template("register.html", form=form)
    return render_template("register.html", form=form)

# --------- Profile (Step 1) ----------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user = User.query.get(session.get('user_id'))
    form = ProfileForm(obj=user)
    if form.validate_on_submit():
        try:
            user.name = form.name.data.strip()
            user.phone_number = form.phone_number.data.strip()
            user.dob = form.dob.data
            user.gender = form.gender.data.strip()
            user.category = form.category.data.strip()
            user.home_state = form.home_state.data.strip()
            user.district = form.district.data.strip()
            # parse percentile safely
            try:
                user.percentile = float(form.percentile.data)
            except Exception:
                user.percentile = None
            db.session.commit()
            flash("Profile updated", "success")

            # Check which button the user clicked: 'save' or 'next'
            action = request.form.get('action', 'save')
            if action == 'next':
                return redirect(url_for('preferences'))
            else:
                return redirect(url_for('profile'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating profile: {e}", "danger")
    return render_template("profile.html", form=form, user=user)

# --------- API endpoints for search used by preferences ----------
@app.route('/api/colleges')
def api_colleges():
    q = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 10))
    try:
        if not q:
            cols = College.query.order_by(College.name.asc()).limit(limit).all()
        else:
            pattern = f"%{q}%"
            cols = College.query.filter(College.name.ilike(pattern)).order_by(College.name.asc()).limit(limit).all()
    except Exception:
        cols = []
    results = [{"id": c.id, "name": c.name} for c in cols]
    return jsonify(results)

@app.route('/api/branches')
def api_branches():
    q = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 10))
    try:
        if not q:
            brs = Branch.query.order_by(Branch.name.asc()).limit(limit).all()
        else:
            pattern = f"%{q}%"
            brs = Branch.query.filter(Branch.name.ilike(pattern)).order_by(Branch.name.asc()).limit(limit).all()
    except Exception:
        brs = []
    results = [{"id": b.id, "name": b.name} for b in brs]
    return jsonify(results)

# --------- Preferences (Step 2) ----------
@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    if not session.get('user_id'):
        flash("Please login to set preferences.", "info")
        return redirect(url_for('login'))

    if request.method == 'POST':
        pc = request.form.get('preferred_colleges', '').strip()
        pb = request.form.get('preferred_branches', '').strip()

        preferred_colleges = [s.strip() for s in pc.split(',') if s.strip()] if pc else []
        preferred_branches = [s.strip() for s in pb.split(',') if s.strip()] if pb else []

        preferred_colleges = preferred_colleges[:10]
        preferred_branches = preferred_branches[:10]

        # persist in session for now (you can persist in DB later)
        session['preferred_colleges'] = preferred_colleges
        session['preferred_branches'] = preferred_branches

        flash("Preferences saved. Generating recommendations...", "success")
        return redirect(url_for('recommend'))

    existing_colleges = session.get('preferred_colleges', [])
    existing_branches = session.get('preferred_branches', [])
    return render_template('preferences.html',
                           preferred_colleges=existing_colleges,
                           preferred_branches=existing_branches)

# --------- Recommendation (Step 3 / final list) ----------
@app.route('/recommend', methods=['GET'])
def recommend():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please login to view recommendations.", "info")
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('login'))

    preferred_colleges = session.get('preferred_colleges', [])
    preferred_branches = session.get('preferred_branches', [])

    # Load pivot CSVs (ensure these exist in 'data/')
    try:
        all_rounds = []
        for r in [1, 2, 3]:
            path = f"data/pivot_gopens_cap{r}.csv"
            if os.path.exists(path):
                df = pd.read_csv(path)
                df['round'] = r
                all_rounds.append(df)
        if not all_rounds:
            flash("Cutoff data files not found. Please upload CSVs in data/ directory.", "warning")
            return redirect(url_for('index'))
        cap_data = pd.concat(all_rounds, ignore_index=True)
    except Exception as e:
        flash(f"Error loading cutoff data: {e}", "danger")
        return redirect(url_for('index'))

    # Prepare user inputs
    try:
        user_percentile = float(user.percentile or 0)
    except Exception:
        user_percentile = 0.0
    user_category = (user.category or "OPEN").strip().upper()

    # Check expected columns
    expected_cols = {'College', 'Branch', 'Category', 'Cutoff'}
    if not expected_cols.issubset(set(cap_data.columns)):
        flash("Cutoff CSV headers must include: 'College', 'Branch', 'Category', 'Cutoff'.", "danger")
        return redirect(url_for('index'))

    # Filter by category
    df_filtered = cap_data[cap_data['Category'].astype(str).str.contains(user_category, case=False, na=False)].copy()

    # Status calculation
    def compute_status(cutoff_val, user_pct):
        try:
            cutoff_val = float(cutoff_val)
        except Exception:
            return 'Unlikely'
        if user_pct >= cutoff_val + 2:
            return 'Safe'
        if cutoff_val - 2 <= user_pct < cutoff_val + 2:
            return 'Reach'
        return 'Unlikely'

    df_filtered['status'] = df_filtered['Cutoff'].apply(lambda x: compute_status(x, user_percentile))

    # Apply optional filters
    if preferred_colleges:
        df_filtered = df_filtered[df_filtered['College'].isin(preferred_colleges)]
    if preferred_branches:
        df_filtered = df_filtered[df_filtered['Branch'].isin(preferred_branches)]

    # Sorting: status priority then cutoff descending
    status_order = {'Safe': 0, 'Reach': 1, 'Unlikely': 2}
    df_filtered['status_rank'] = df_filtered['status'].map(status_order).fillna(3)
    recommendation_df = df_filtered.sort_values(by=['status_rank', 'Cutoff'], ascending=[True, False]).head(200)

    # Build list for template
    recs = []
    for _, row in recommendation_df.iterrows():
        recs.append({
            "college_name": row.get('College'),
            "branch_name": row.get('Branch'),
            "round": int(row.get('round')) if 'round' in row and not pd.isna(row.get('round')) else None,
            "cutoff": float(row.get('Cutoff')) if not pd.isna(row.get('Cutoff')) else None,
            "status": row.get('status')
        })

    return render_template('recommendation.html', recommendation=recs, user=user)

# ---------------- Run ----------------
if __name__ == '__main__':   # fixed run guard
    app.run(debug=True)