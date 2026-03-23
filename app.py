"""
Flask Todo App
==============
Multi-user todo application with Flask-Login authentication.
Each user can only see and manage their own tasks.
"""

from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, login_required, current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'dev-secret-key-change-in-production'

db = SQLAlchemy(app)

# Configure Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'          # redirect here when @login_required fails
login_manager.login_message = '请先登录后再访问该页面。'
login_manager.login_message_category = 'error'

# Priority sort order: lower number = higher priority
PRIORITY_ORDER = {'高': 1, '中': 2, '低': 3}
VALID_PRIORITIES = set(PRIORITY_ORDER.keys())


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    """Registered user account."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    todos = db.relationship('Todo', backref='owner', lazy=True,
                            cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    """Reload user from session on every request."""
    return db.session.get(User, int(user_id))


class Todo(db.Model):
    """A single todo task belonging to one user."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    complete = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(10), default='中')       # 高 / 中 / 低
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def is_overdue(self):
        """Return True if past due date and not completed."""
        return bool(self.due_date and not self.complete and self.due_date < date.today())


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    """Show registration form / create new user account."""
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        if not username:
            flash("用户名不能为空。", "error")
        elif len(username) < 3:
            flash("用户名至少需要 3 个字符。", "error")
        elif not password:
            flash("密码不能为空。", "error")
        elif len(password) < 6:
            flash("密码至少需要 6 个字符。", "error")
        elif password != confirm:
            flash("两次输入的密码不一致。", "error")
        elif User.query.filter_by(username=username).first():
            flash(f"用户名「{username}」已被占用，请换一个。", "error")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("注册成功！请登录。", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Show login form / authenticate user."""
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("用户名或密码错误。", "error")
        else:
            login_user(user)
            next_page = request.args.get("next")
            flash(f"欢迎回来，{user.username}！", "success")
            return redirect(next_page or url_for("home"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash("已退出登录。", "success")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Todo routes  (all require login; queries scoped to current_user)
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def home():
    """Display current user's todos sorted by priority (高 → 中 → 低)."""
    todo_list = Todo.query.filter_by(user_id=current_user.id).all()
    todo_list.sort(key=lambda t: PRIORITY_ORDER.get(t.priority, 2))
    return render_template("base.html", todo_list=todo_list, today=date.today())


@app.route("/add", methods=["POST"])
@login_required
def add():
    """Create a new todo task for the logged-in user."""
    title = request.form.get("title", "").strip()
    if not title:
        flash("任务标题不能为空！", "error")
        return redirect(url_for("home"))

    priority = request.form.get("priority", "中")
    if priority not in VALID_PRIORITIES:
        priority = "中"

    due_date = None
    due_date_str = request.form.get("due_date", "").strip()
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("截止日期格式无效，请使用 YYYY-MM-DD 格式。", "error")
            return redirect(url_for("home"))

    new_todo = Todo(title=title, complete=False, priority=priority,
                    due_date=due_date, user_id=current_user.id)
    db.session.add(new_todo)
    db.session.commit()
    flash(f"任务「{title}」已添加！", "success")
    return redirect(url_for("home"))


@app.route("/update/<int:todo_id>")
@login_required
def update(todo_id):
    """Toggle completion state — only the owning user may update."""
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first()
    if todo is None:
        flash(f"未找到 ID 为 {todo_id} 的任务。", "error")
        return redirect(url_for("home"))

    todo.complete = not todo.complete
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/delete/<int:todo_id>")
@login_required
def delete(todo_id):
    """Permanently delete a todo — only the owning user may delete."""
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first()
    if todo is None:
        flash(f"未找到 ID 为 {todo_id} 的任务。", "error")
        return redirect(url_for("home"))

    title = todo.title
    db.session.delete(todo)
    db.session.commit()
    flash(f"任务「{title}」已删除。", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
