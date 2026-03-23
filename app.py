"""
Flask Todo App
==============
A minimal todo application with priority, due date, and flash message support.
"""

from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'dev-secret-key-change-in-production'

db = SQLAlchemy(app)

# Priority sort order: lower number = higher priority
PRIORITY_ORDER = {'高': 1, '中': 2, '低': 3}
VALID_PRIORITIES = set(PRIORITY_ORDER.keys())


class Todo(db.Model):
    """Represents a single todo task."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    complete = db.Column(db.Boolean, default=False)
    # New fields
    priority = db.Column(db.String(10), default='中')          # 高 / 中 / 低
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.Date, nullable=True)

    def is_overdue(self):
        """Return True if the task is past its due date and not yet completed."""
        return bool(self.due_date and not self.complete and self.due_date < date.today())


@app.route("/")
def home():
    """Display all todos sorted by priority (高 → 中 → 低)."""
    todo_list = Todo.query.all()
    todo_list.sort(key=lambda t: PRIORITY_ORDER.get(t.priority, 2))
    return render_template("base.html", todo_list=todo_list, today=date.today())


@app.route("/add", methods=["POST"])
def add():
    """Create a new todo task.

    Validates:
    - Title must not be blank.
    - Priority must be one of 高/中/低 (defaults to 中 if invalid).
    - Due date must be a valid YYYY-MM-DD string if provided.
    """
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

    new_todo = Todo(title=title, complete=False, priority=priority, due_date=due_date)
    db.session.add(new_todo)
    db.session.commit()
    flash(f"任务「{title}」已添加！", "success")
    return redirect(url_for("home"))


@app.route("/update/<int:todo_id>")
def update(todo_id):
    """Toggle the completion state of a todo task."""
    todo = Todo.query.filter_by(id=todo_id).first()
    if todo is None:
        flash(f"未找到 ID 为 {todo_id} 的任务。", "error")
        return redirect(url_for("home"))

    todo.complete = not todo.complete
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/delete/<int:todo_id>")
def delete(todo_id):
    """Permanently delete a todo task."""
    todo = Todo.query.filter_by(id=todo_id).first()
    if todo is None:
        flash(f"未找到 ID 为 {todo_id} 的任务。", "error")
        return redirect(url_for("home"))

    title = todo.title  # capture before deletion
    db.session.delete(todo)
    db.session.commit()
    flash(f"任务「{title}」已删除。", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
