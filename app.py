import os
from flask import Flask, render_template, request, url_for, make_response, flash, redirect, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import inspect, text
from datetime import date, datetime, date as dt_date
from sqlalchemy import func
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'my-secret-key')
db = SQLAlchemy(app)

# ---------- Flask-Login setup ----------
login_manager = LoginManager(app)
login_manager.login_view = "login"          # redirect target when @login_required blocks access
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.Date, nullable=False, default=date.today)
    security_question = db.Column(db.String(120), nullable=True)
    security_answer_hash = db.Column(db.String(255), nullable=True)


    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def set_security_answer(self, raw_answer):
        self.security_answer_hash = generate_password_hash(raw_answer.strip().lower())

    def check_security_answer(self, raw_answer):
        if not self.security_answer_hash:
            return False
        return check_password_hash(self.security_answer_hash, (raw_answer or "").strip().lower())


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)



class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # 'YYYY-MM'
    amount = db.Column(db.Float, nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'month', name='uq_budget_user_month'),)


class RecurringExpense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    day_of_month = db.Column(db.Integer, nullable=False, default=1)
    last_added_month = db.Column(db.String(7), nullable=True)  # 'YYYY-MM'


class SavingsGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    saved_amount = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.Date, nullable=False, default=date.today)


CATEGORIES = [
    "Food",
    "Transport",
    "Shopping",
    "Bills",
    "Health",
    "Utilities",
    "Education",
    "Other"
]


with app.app_context():
    db.create_all()

    # --- simple migration: add new User columns if they don't exist yet ---
    inspector = inspect(db.engine)
    existing_columns = [col["name"] for col in inspector.get_columns("user")]
    with db.engine.connect() as conn:
        if "email" not in existing_columns:
            conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
        if "security_question" not in existing_columns:
            conn.execute(text("ALTER TABLE user ADD COLUMN security_question VARCHAR(120)"))
        if "security_answer_hash" not in existing_columns:
            conn.execute(text("ALTER TABLE user ADD COLUMN security_answer_hash VARCHAR(255)"))
        conn.commit()

reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
RESET_TOKEN_MAX_AGE = 600  # seconds (10 minutes)

SECURITY_QUESTIONS = [
    "What is your favorite color?",
    "What was the name of your first school?",
    "What is your pet's name?",
    "What city were you born in?",
]


@app.context_processor
def inject_globals():
    today_str = date.today().isoformat()
    return {
        'today': today_str,
        'current_month': today_str[:7]
    }


def parse_date_or_none(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None
    

def month_bounds(month_str: str):
    """Given 'YYYY-MM', return (start_date, end_date_exclusive)."""
    year, mon = map(int, month_str.split("-"))
    start = date(year, mon, 1)
    if mon == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, mon + 1, 1)
    return start, end
    

def process_recurring_expenses(user_id):
    """Auto-add each recurring expense to the current month if not already added."""
    current_month = date.today().strftime("%Y-%m")
    recs = RecurringExpense.query.filter_by(user_id=user_id).all()
    added_any = False
    for r in recs:
        if r.last_added_month != current_month:
            e = Expense(
                description=r.name,
                amount=r.amount,
                category=r.category,
                date=date.today(),
                user_id=user_id,
            )
            db.session.add(e)
            r.last_added_month = current_month
            added_any = True
    if added_any:
        db.session.commit()


# ---------------- AUTH ROUTES ----------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        confirm = (request.form.get("confirm_password") or "").strip()
        security_question = (request.form.get("security_question") or "").strip()
        security_answer = (request.form.get("security_answer") or "").strip()

        if not username or not email or not password:
            flash("Username, email, and password are required", "error")
            return redirect(url_for("signup"))

        if "@" not in email or "." not in email:
            flash("Please enter a valid email address", "error")
            return redirect(url_for("signup"))

        if len(password) < 6:
            flash("Password must be at least 6 characters long", "error")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for("signup"))

        if User.query.filter(func.lower(User.username) == username.lower()).first():
            flash("That username is already taken. Please choose another.", "error")
            return redirect(url_for("signup"))

        if User.query.filter(func.lower(User.email) == email.lower()).first():
            flash("An account with that email already exists. Please log in.", "error")
            return redirect(url_for("signup"))

        user = User(username=username, email=email)
        user.set_password(password)
        if security_question and security_answer:
            user.security_question = security_question
            user.set_security_answer(security_answer)

        db.session.add(user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html", security_questions=SECURITY_QUESTIONS)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        login_id = (request.form.get("login_id") or request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not login_id or not password:
            flash("Please enter your email or username, and password", "error")
            return redirect(url_for("login"))

        user = User.query.filter(
            (func.lower(User.username) == login_id.lower()) |
            (func.lower(User.email) == login_id.lower())
        ).first()

        if user is None or not user.check_password(password):
            flash("Invalid email/username or password", "error")
            return redirect(url_for("login"))

        login_user(user)
        flash(f"Welcome back, {user.username}!", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        login_id = (request.form.get("login_id") or request.form.get("username") or request.form.get("email") or "").strip()

        # Step 2: if an answer was submitted to security question
        if "security_answer" in request.form:
            username = (request.form.get("verified_username") or "").strip()
            user = User.query.filter_by(username=username).first()
            if not user:
                flash("Session expired. Please search for your account again.", "error")
                return redirect(url_for("forgot_password"))

            answer = request.form.get("security_answer") or ""
            if not user.check_security_answer(answer):
                flash("That security answer does not match our records.", "error")
                token = reset_serializer.dumps(user.username, salt="password-reset")
                reset_link = url_for("reset_password", token=token)
                return render_template("forgot_password.html", user=user, token=token, reset_link=reset_link)

            token = reset_serializer.dumps(user.username, salt="password-reset")
            return redirect(url_for("reset_password", token=token))

        # Step 1: User submitted email or username
        if not login_id:
            flash("Please enter your email or username", "error")
            return redirect(url_for("forgot_password"))

        user = User.query.filter(
            (func.lower(User.username) == login_id.lower()) |
            (func.lower(User.email) == login_id.lower())
        ).first()

        if user is None:
            flash("No account found with that email or username", "error")
            return redirect(url_for("forgot_password"))

        token = reset_serializer.dumps(user.username, salt="password-reset")
        reset_link = url_for("reset_password", token=token)
        return render_template("forgot_password.html", user=user, token=token, reset_link=reset_link)

    return render_template("forgot_password.html", user=None)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    try:
        username = reset_serializer.loads(token, salt="password-reset", max_age=RESET_TOKEN_MAX_AGE)
    except SignatureExpired:
        flash("This password reset link has expired. Please try again.", "error")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("Invalid password reset link.", "error")
        return redirect(url_for("forgot_password"))

    user = User.query.filter_by(username=username).first()
    if user is None:
        flash("Invalid password reset link.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = (request.form.get("password") or "").strip()
        confirm = (request.form.get("confirm_password") or "").strip()

        if not password:
            flash("Please enter a new password", "error")
            return redirect(url_for("reset_password", token=token))

        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for("reset_password", token=token))

        user.set_password(password)
        db.session.commit()
        flash("Password reset successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out", "success")
    return redirect(url_for("login"))



def serialize_expense(e):
    return {
        "id": e.id,
        "description": e.description,
        "amount": round(float(e.amount), 2),
        "category": e.category,
        "date": e.date.strftime("%Y-%m-%d") if e.date else ""
    }


def get_dashboard_stats(user_id, start_str=None, end_str=None, category_str=None, search_str=None, sort_by=None, order='desc'):
    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)

    if start_date and end_date and end_date < start_date:
        start_date = end_date = None
        start_str = end_str = ""

    q = Expense.query.filter_by(user_id=user_id)
    if start_date:
        q = q.filter(Expense.date >= start_date)
    if end_date:
        q = q.filter(Expense.date <= end_date)
    if category_str:
        q = q.filter(Expense.category == category_str)
    if search_str:
        q = q.filter(Expense.description.ilike(f"%{search_str}%"))

    # Sorting
    if sort_by == 'amount':
        q = q.order_by(Expense.amount.asc() if order == 'asc' else Expense.amount.desc(), Expense.id.desc())
    elif sort_by == 'description':
        q = q.order_by(Expense.description.asc() if order == 'asc' else Expense.description.desc(), Expense.id.desc())
    elif sort_by == 'category':
        q = q.order_by(Expense.category.asc() if order == 'asc' else Expense.category.desc(), Expense.id.desc())
    elif sort_by == 'date':
        q = q.order_by(Expense.date.asc() if order == 'asc' else Expense.date.desc(), Expense.id.desc())
    else:
        q = q.order_by(Expense.date.desc(), Expense.id.desc())

    expenses = q.all()
    total = round(sum(e.amount for e in expenses), 2)
    count = len(expenses)

    # Average per day
    unique_dates = set(e.date for e in expenses if e.date)
    avg_per_day = round(total / len(unique_dates), 2) if unique_dates else 0.0

    # Category breakdown
    cat_q = db.session.query(Expense.category, func.sum(Expense.amount)).filter(Expense.user_id == user_id)
    if start_date:
        cat_q = cat_q.filter(Expense.date >= start_date)
    if end_date:
        cat_q = cat_q.filter(Expense.date <= end_date)
    if category_str:
        cat_q = cat_q.filter(Expense.category == category_str)
    if search_str:
        cat_q = cat_q.filter(Expense.description.ilike(f"%{search_str}%"))
    cat_rows = cat_q.group_by(Expense.category).all()
    cat_labels = [c for c, _ in cat_rows]
    cat_values = [round(float(s or 0), 2) for _, s in cat_rows]

    top_category = "None"
    top_category_amount = 0.0
    if cat_rows:
        top_cat_pair = max(cat_rows, key=lambda r: float(r[1] or 0))
        top_category = top_cat_pair[0]
        top_category_amount = round(float(top_cat_pair[1] or 0), 2)

    # Daily breakdown
    day_q = db.session.query(Expense.date, func.sum(Expense.amount)).filter(Expense.user_id == user_id)
    if start_date:
        day_q = day_q.filter(Expense.date >= start_date)
    if end_date:
        day_q = day_q.filter(Expense.date <= end_date)
    if category_str:
        day_q = day_q.filter(Expense.category == category_str)
    if search_str:
        day_q = day_q.filter(Expense.description.ilike(f"%{search_str}%"))
    day_rows = day_q.group_by(Expense.date).order_by(Expense.date).all()
    day_labels = [d.isoformat() for d, _ in day_rows if d]
    day_values = [round(float(s or 0), 2) for _, s in day_rows]

    # Current month budget status
    current_month = date.today().strftime("%Y-%m")
    cur_budget = Budget.query.filter_by(user_id=user_id, month=current_month).first()
    budget_amount = cur_budget.amount if cur_budget else 0.0

    m_start, m_end = month_bounds(current_month)
    month_spent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= m_start,
        Expense.date < m_end,
    ).scalar() or 0.0
    month_spent = round(float(month_spent), 2)

    budget_percent = round((month_spent / budget_amount * 100), 1) if budget_amount > 0 else 0.0
    budget_status = None
    if budget_amount > 0:
        if budget_percent >= 100:
            budget_status = "exceeded"
        elif budget_percent >= 80:
            budget_status = "warning"
        else:
            budget_status = "ok"

    return {
        "expenses": expenses,
        "total": total,
        "count": count,
        "avg_per_day": avg_per_day,
        "top_category": top_category,
        "top_category_amount": top_category_amount,
        "cat_labels": cat_labels,
        "cat_values": cat_values,
        "day_labels": day_labels,
        "day_values": day_values,
        "budget_amount": budget_amount,
        "month_spent": month_spent,
        "budget_remaining": round(budget_amount - month_spent, 2),
        "budget_percent": budget_percent,
        "budget_status": budget_status,
        "start_str": start_str,
        "end_str": end_str,
        "category_str": category_str,
        "search_str": search_str or ""
    }


@app.route("/")
@login_required
def index():
    # auto-add this month's recurring expenses (Netflix, Rent, etc.)
    process_recurring_expenses(current_user.id)

    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    category_str = (request.args.get("category") or "").strip()
    search_str = (request.args.get("search") or "").strip()
    sort_by = (request.args.get("sort_by") or "").strip()
    order = (request.args.get("order") or "desc").strip()

    data = get_dashboard_stats(
        current_user.id,
        start_str=start_str,
        end_str=end_str,
        category_str=category_str,
        search_str=search_str,
        sort_by=sort_by,
        order=order
    )

    return render_template(
        "index.html",
        categories=CATEGORIES,
        today=date.today().isoformat(),
        expenses=data["expenses"],
        total=data["total"],
        count=data["count"],
        avg_per_day=data["avg_per_day"],
        top_category=data["top_category"],
        top_category_amount=data["top_category_amount"],
        start_str=data["start_str"],
        end_str=data["end_str"],
        category_str=data["category_str"],
        search_str=data["search_str"],
        cat_labels=data["cat_labels"],
        cat_values=data["cat_values"],
        day_labels=data["day_labels"],
        day_values=data["day_values"],
        budget_amount=data["budget_amount"],
        month_spent=data["month_spent"],
        budget_remaining=data["budget_remaining"],
        budget_percent=data["budget_percent"],
        budget_status=data["budget_status"],
    )


# ---------------- REST / JSON API ENDPOINTS ----------------

@app.route("/api/expenses", methods=["GET"])
@login_required
def api_get_expenses():
    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    category_str = (request.args.get("category") or "").strip()
    search_str = (request.args.get("search") or "").strip()
    sort_by = (request.args.get("sort_by") or "").strip()
    order = (request.args.get("order") or "desc").strip()

    data = get_dashboard_stats(
        current_user.id,
        start_str=start_str,
        end_str=end_str,
        category_str=category_str,
        search_str=search_str,
        sort_by=sort_by,
        order=order
    )

    return jsonify({
        "success": True,
        "expenses": [serialize_expense(e) for e in data["expenses"]],
        "total": data["total"],
        "count": data["count"],
        "avg_per_day": data["avg_per_day"],
        "top_category": data["top_category"],
        "top_category_amount": data["top_category_amount"],
        "cat_labels": data["cat_labels"],
        "cat_values": data["cat_values"],
        "day_labels": data["day_labels"],
        "day_values": data["day_values"],
        "budget": {
            "amount": data["budget_amount"],
            "spent": data["month_spent"],
            "remaining": data["budget_remaining"],
            "percent": data["budget_percent"],
            "status": data["budget_status"]
        },
        "categories": CATEGORIES
    })


@app.route("/api/expenses", methods=["POST"])
@login_required
def api_add_expense():
    req_data = request.get_json(silent=True) or request.form
    description = (req_data.get("description") or "").strip()
    amount_val = req_data.get("amount")
    category = (req_data.get("category") or "").strip()
    date_str = (req_data.get("date") or "").strip()

    if not description or not amount_val or not category:
        return jsonify({"success": False, "message": "Description, amount, and category are required"}), 400

    try:
        amount = float(amount_val)
        if amount <= 0:
            return jsonify({"success": False, "message": "Amount must be a positive number"}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid amount number"}), 400

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        d = date.today()

    e = Expense(description=description, amount=amount, category=category, date=d, user_id=current_user.id)
    db.session.add(e)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Expense added successfully",
        "expense": serialize_expense(e)
    }), 201


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
@login_required
def api_update_expense(expense_id):
    e = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not e:
        return jsonify({"success": False, "message": "Expense not found"}), 404

    req_data = request.get_json(silent=True) or request.form
    description = (req_data.get("description") or "").strip()
    amount_val = req_data.get("amount")
    category = (req_data.get("category") or "").strip()
    date_str = (req_data.get("date") or "").strip()

    if not description or not amount_val or not category:
        return jsonify({"success": False, "message": "Description, amount, and category are required"}), 400

    try:
        amount = float(amount_val)
        if amount <= 0:
            return jsonify({"success": False, "message": "Amount must be a positive number"}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid amount number"}), 400

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else dt_date.today()
    except ValueError:
        d = dt_date.today()

    e.description = description
    e.amount = amount
    e.category = category
    e.date = d
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Expense updated successfully",
        "expense": serialize_expense(e)
    })


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
@login_required
def api_delete_expense(expense_id):
    e = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not e:
        return jsonify({"success": False, "message": "Expense not found"}), 404
    db.session.delete(e)
    db.session.commit()
    return jsonify({"success": True, "message": "Expense deleted successfully", "id": expense_id})


@app.route("/add", methods=['POST'])
@login_required
def add():
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")
    req_data = request.get_json(silent=True) or request.form

    description = (req_data.get("description") or "").strip()
    amount_str = (req_data.get("amount") or "").strip() if isinstance(req_data.get("amount"), str) else str(req_data.get("amount") or "")
    category = (req_data.get("category") or "").strip()
    date_str = (req_data.get("date") or "").strip()

    if not description or not amount_str or not category:
        if is_ajax:
            return jsonify({"success": False, "message": "Please fill description, amount, and category"}), 400
        flash("Please fill description, amount, and category", "error")
        return redirect(url_for("index"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        if is_ajax:
            return jsonify({"success": False, "message": "Amount must be a positive number"}), 400
        flash("Amount must be a positive number", "error")
        return redirect(url_for("index"))

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        d = date.today()

    e = Expense(description=description, amount=amount, category=category, date=d, user_id=current_user.id)
    db.session.add(e)
    db.session.commit()

    if is_ajax:
        return jsonify({"success": True, "message": "Expense added", "expense": serialize_expense(e)}), 201

    flash("Expense added", "success")
    return redirect(url_for("index"))


@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete(expense_id):
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")
    e = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not e:
        if is_ajax:
            return jsonify({"success": False, "message": "Expense not found"}), 404
        flash("Expense not found", "error")
        return redirect(url_for("index"))

    db.session.delete(e)
    db.session.commit()

    if is_ajax:
        return jsonify({"success": True, "message": "Expense deleted", "id": expense_id})

    flash("Expense deleted", "success")
    return redirect(url_for("index"))


@app.route("/edit/<int:expense_id>", methods=["GET"])
@login_required
def edit(expense_id):
    e = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "expense": serialize_expense(e)})
    return render_template("edit.html", expense=e, categories=CATEGORIES, today=dt_date.today().isoformat())


@app.route("/edit/<int:expense_id>", methods=["POST"])
@login_required
def edit_post(expense_id):
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")
    e = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()

    req_data = request.get_json(silent=True) or request.form
    description = (req_data.get("description") or "").strip()
    amount_str = (req_data.get("amount") or "").strip() if isinstance(req_data.get("amount"), str) else str(req_data.get("amount") or "")
    category = (req_data.get("category") or "").strip()
    date_str = (req_data.get("date") or "").strip()

    if not description or not amount_str or not category:
        if is_ajax:
            return jsonify({"success": False, "message": "Please fill description, amount, and category"}), 400
        flash("Please fill description, amount, and category", "error")
        return redirect(url_for("edit", expense_id=expense_id))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        if is_ajax:
            return jsonify({"success": False, "message": "Amount must be a positive number"}), 400
        flash("Amount must be a positive number", "error")
        return redirect(url_for("edit", expense_id=expense_id))

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else dt_date.today()
    except ValueError:
        d = dt_date.today()

    e.description = description
    e.amount = amount
    e.category = category
    e.date = d

    db.session.commit()

    if is_ajax:
        return jsonify({"success": True, "message": "Expense updated", "expense": serialize_expense(e)})

    flash("Expense updated", "success")
    return redirect(url_for("index"))    
    
    



@app.route("/export.csv")
@login_required
def export_csv():


    # 1 read query string

    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    category_str = (request.args.get("category") or "").strip()

    # 2 parsing

    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)

    q = Expense.query.filter_by(user_id=current_user.id)
    
    if start_date:
        q = q.filter(Expense.date >= start_date)
    
    if end_date:
        q = q.filter(Expense.date <= end_date)
    
    if category_str:
        q = q.filter(Expense.category == category_str)            

    expenses = q.order_by(Expense.date, Expense.id).all()

    lines = ["date, description, category, amount"]

    for e in expenses:
        lines.append(f"{e.date.isoformat()}, {e.description}, {e.category}, {e.amount:.2f}")
    csv_data = "\n".join(lines)


    fname_start = start_str or "all"
    fname_end = end_str or "all"
    filename = f"expenses_{fname_start}_to_{fname_end}.csv"


    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv",
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@app.route("/export.pdf")
@login_required
def export_pdf():

    # 1 read query string

    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    category_str = (request.args.get("category") or "").strip()
  
   # 2 parsing

    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)

    q = Expense.query.filter_by(user_id=current_user.id)

    if start_date:
        q = q.filter(Expense.date >= start_date)

    if end_date:
        q = q.filter(Expense.date <= end_date)

    if category_str:
        q = q.filter(Expense.category == category_str)

    expenses = q.order_by(Expense.date, Expense.id).all()
    total = round(sum(e.amount for e in expenses), 2)

    cat_totals = {}
    for e in expenses:
        cat_totals[e.category] = round(cat_totals.get(e.category, 0) + e.amount, 2)

    highest_category = max(cat_totals, key=cat_totals.get) if cat_totals else "N/A"
    lowest_category = min(cat_totals, key=cat_totals.get) if cat_totals else "N/A"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Expense Report",
                             leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Expense Report", styles['Title']))
    period_label = f"{start_str or 'All time'} &nbsp;to&nbsp; {end_str or 'Present'}"
    if category_str:
        period_label += f" &nbsp;|&nbsp; Category: {category_str}"
    elements.append(Paragraph(period_label, styles['Normal']))
    elements.append(Paragraph(f"Generated on {date.today().isoformat()}", styles['Normal']))
    elements.append(Spacer(1, 0.6*cm))
 
    summary_data = [
        ["Total Expense", f"Rs. {total:.2f}"],
        ["Highest Category", highest_category],
        ["Lowest Category", lowest_category],
    ]
    summary_table = Table(summary_data, colWidths=[6*cm, 8*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#1e293b")),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.8*cm))
    
    if cat_totals:
        elements.append(Paragraph("Spending by Category", styles['Heading2']))
        drawing = Drawing(420, 200)
        pie = Pie()
        pie.x = 130
        pie.y = 15
        pie.width = 160
        pie.height = 160
        pie.data = list(cat_totals.values())
        pie.labels = [f"{k} (Rs.{v:.0f})" for k, v in cat_totals.items()]
        pie.slices.strokeWidth = 0.5
        palette = [colors.HexColor(c) for c in
                   ["#38bdf8", "#f472b6", "#facc15", "#4ade80", "#a78bfa", "#fb923c", "#f87171", "#94a3b8"]]
        for i in range(len(pie.data)):
            pie.slices[i].fillColor = palette[i % len(palette)]
        drawing.add(pie)
        elements.append(drawing)
        elements.append(Spacer(1, 0.5*cm))
    
    elements.append(Paragraph("Expense Details", styles['Heading2']))
    table_data = [["Date", "Description", "Category", "Amount"]]
    for e in expenses:
        table_data.append([e.date.isoformat(), e.description, e.category, f"Rs. {e.amount:.2f}"])
    if len(table_data) == 1:
        table_data.append(["-", "No expenses in this range", "-", "-"])


    detail_table = Table(table_data, colWidths=[3*cm, 6.5*cm, 3.5*cm, 3*cm], repeatRows=1)
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    elements.append(detail_table)

    doc.build(elements)
    buffer.seek(0)

    fname_start = start_str or "all"
    fname_end = end_str or "all"
    filename = f"expense_report_{fname_start}_to_{fname_end}.pdf"

    return Response(
        buffer.getvalue(),
        headers={
            "Content-Type": "application/pdf",
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# ---------------- BUDGET ----------------

@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    month = (request.args.get("month") or date.today().strftime("%Y-%m")).strip()

    if request.method == "POST":
        month = (request.form.get("month") or date.today().strftime("%Y-%m")).strip()
        amount_str = (request.form.get("amount") or "").strip()

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Budget must be a positive number", "error")
            return redirect(url_for("budget", month=month))

        b = Budget.query.filter_by(user_id=current_user.id, month=month).first()
        if b:
            b.amount = amount
        else:
            b = Budget(user_id=current_user.id, month=month, amount=amount)
            db.session.add(b)
        db.session.commit()

        flash("Budget saved", "success")
        return redirect(url_for("budget", month=month))

    b = Budget.query.filter_by(user_id=current_user.id, month=month).first()
    budget_amount = b.amount if b else 0

    m_start, m_end = month_bounds(month)
    spent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.date >= m_start,
        Expense.date < m_end,
    ).scalar() or 0
    spent = round(float(spent), 2)

    remaining = round(budget_amount - spent, 2)
    percent = round((spent / budget_amount * 100), 1) if budget_amount > 0 else 0

    status = None
    if budget_amount > 0:
        if percent >= 100:
            status = "exceeded"
        elif percent >= 80:
            status = "warning"

    return render_template(
        "budget.html",
        month=month,
        budget_amount=budget_amount,
        spent=spent,
        remaining=remaining,
        percent=percent,
        status=status,
        today=date.today().isoformat(),
    )


# ---------------- RECURRING EXPENSES ----------------

@app.route("/recurring", methods=["GET", "POST"])
@login_required
def recurring():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        amount_str = (request.form.get("amount") or "").strip()
        category = (request.form.get("category") or "").strip()
        day_str = (request.form.get("day_of_month") or "1").strip()

        if not name or not amount_str or not category:
            flash("Please fill name, amount, and category", "error")
            return redirect(url_for("recurring"))

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number", "error")
            return redirect(url_for("recurring"))

        try:
            day_of_month = int(day_str)
            if not (1 <= day_of_month <= 28):
                raise ValueError
        except ValueError:
            day_of_month = 1

        r = RecurringExpense(
            name=name, amount=amount, category=category,
            day_of_month=day_of_month, user_id=current_user.id,
        )
        db.session.add(r)
        db.session.commit()

        flash("Recurring expense added — it will be auto-added every month", "success")
        return redirect(url_for("recurring"))

    recs = RecurringExpense.query.filter_by(user_id=current_user.id).order_by(RecurringExpense.day_of_month).all()
    return render_template("recurring.html", recurring_expenses=recs, categories=CATEGORIES)


@app.route("/recurring/delete/<int:rec_id>", methods=["POST"])
@login_required
def recurring_delete(rec_id):
    r = RecurringExpense.query.filter_by(id=rec_id, user_id=current_user.id).first_or_404()
    db.session.delete(r)
    db.session.commit()
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")
    if is_ajax:
        return jsonify({"success": True, "message": "Recurring expense removed", "id": rec_id})
    flash("Recurring expense removed", "success")
    return redirect(url_for("recurring"))


# ---------------- SAVINGS GOALS ----------------

@app.route("/savings", methods=["GET", "POST"])
@login_required
def savings():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        target_str = (request.form.get("target_amount") or "").strip()

        if not name or not target_str:
            flash("Please fill goal name and target amount", "error")
            return redirect(url_for("savings"))

        try:
            target_amount = float(target_str)
            if target_amount <= 0:
                raise ValueError
        except ValueError:
            flash("Target amount must be a positive number", "error")
            return redirect(url_for("savings"))

        g = SavingsGoal(name=name, target_amount=target_amount, saved_amount=0, user_id=current_user.id)
        db.session.add(g)
        db.session.commit()

        flash("Savings goal created", "success")
        return redirect(url_for("savings"))

    goals = SavingsGoal.query.filter_by(user_id=current_user.id).order_by(SavingsGoal.id.desc()).all()
    goals_view = []
    for g in goals:
        pct = round((g.saved_amount / g.target_amount * 100), 1) if g.target_amount > 0 else 0
        goals_view.append({"goal": g, "percent": min(pct, 100)})

    return render_template("savings.html", goals_view=goals_view)


@app.route("/savings/<int:goal_id>/add", methods=["POST"])
@login_required
def savings_add(goal_id):
    g = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    req_data = request.get_json(silent=True) or request.form
    amount_str = (req_data.get("amount") or "").strip() if isinstance(req_data.get("amount"), str) else str(req_data.get("amount") or "")

    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        if is_ajax:
            return jsonify({"success": False, "message": "Amount must be a positive number"}), 400
        flash("Amount must be a positive number", "error")
        return redirect(url_for("savings"))

    g.saved_amount = round(g.saved_amount + amount, 2)
    db.session.commit()

    pct = round((g.saved_amount / g.target_amount * 100), 1) if g.target_amount > 0 else 0
    if is_ajax:
        return jsonify({
            "success": True,
            "message": f"Added ₹{amount:.2f} to {g.name}!",
            "goal_id": g.id,
            "saved_amount": g.saved_amount,
            "target_amount": g.target_amount,
            "percent": min(pct, 100),
            "is_completed": g.saved_amount >= g.target_amount
        })

    flash("Savings updated", "success")
    return redirect(url_for("savings"))


@app.route("/savings/<int:goal_id>/delete", methods=["POST"])
@login_required
def savings_delete(goal_id):
    g = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    db.session.delete(g)
    db.session.commit()
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")
    if is_ajax:
        return jsonify({"success": True, "message": "Savings goal deleted", "id": goal_id})
    flash("Savings goal deleted", "success")
    return redirect(url_for("savings"))


# ---------------- PROFILE ----------------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_password = (request.form.get("current_password") or "").strip()
        new_password = (request.form.get("new_password") or "").strip()
        confirm_password = (request.form.get("confirm_password") or "").strip()

        if not current_user.check_password(current_password):
            flash("Current password is incorrect", "error")
            return redirect(url_for("profile"))

        if not new_password or new_password != confirm_password:
            flash("New passwords do not match", "error")
            return redirect(url_for("profile"))

        current_user.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully", "success")
        return redirect(url_for("profile"))

    total_expenses_count = Expense.query.filter_by(user_id=current_user.id).count()
    total_spent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id
    ).scalar() or 0
    total_spent = round(float(total_spent), 2)

    goals_count = SavingsGoal.query.filter_by(user_id=current_user.id).count()
    recurring_count = RecurringExpense.query.filter_by(user_id=current_user.id).count()

    current_month = date.today().strftime("%Y-%m")
    current_budget = Budget.query.filter_by(user_id=current_user.id, month=current_month).first()

    return render_template(
         "profile.html",
        total_expenses_count=total_expenses_count,
        total_spent=total_spent,
        goals_count=goals_count,
        recurring_count=recurring_count,
        current_budget=current_budget.amount if current_budget else None,
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
 