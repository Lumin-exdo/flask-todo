"""
Unit tests for the Flask Todo App.
Covers all routes and edge cases using an in-memory SQLite database.
"""

import pytest
from datetime import date, timedelta

from app import app, db, Todo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Provide a test client backed by a fresh in-memory database."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _add(client, title, priority='中', due_date=''):
    """POST to /add and follow redirect."""
    return client.post(
        '/add',
        data={'title': title, 'priority': priority, 'due_date': due_date},
        follow_redirects=True,
    )


def _first_id(client):
    """Return the id of the first Todo in the DB (within app context)."""
    with app.app_context():
        todo = Todo.query.first()
        return todo.id if todo else None


# ---------------------------------------------------------------------------
# Home route
# ---------------------------------------------------------------------------

class TestHome:
    def test_home_returns_200(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_home_shows_empty_message(self, client):
        resp = client.get('/')
        assert '暂无任务'.encode() in resp.data

    def test_home_shows_added_task(self, client):
        _add(client, 'Buy milk')
        resp = client.get('/')
        assert b'Buy milk' in resp.data


# ---------------------------------------------------------------------------
# Add route
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_valid_task(self, client):
        resp = _add(client, 'Walk the dog')
        assert resp.status_code == 200
        assert b'Walk the dog' in resp.data

    def test_add_with_high_priority(self, client):
        _add(client, 'Urgent', priority='高')
        with app.app_context():
            todo = Todo.query.first()
            assert todo.priority == '高'

    def test_add_with_due_date(self, client):
        future = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
        _add(client, 'Future task', due_date=future)
        with app.app_context():
            todo = Todo.query.first()
            assert todo.due_date is not None

    def test_add_empty_title_shows_error(self, client):
        resp = _add(client, '')
        assert '不能为空'.encode('utf-8') in resp.data

    def test_add_whitespace_only_title_shows_error(self, client):
        resp = _add(client, '   ')
        assert '不能为空'.encode('utf-8') in resp.data

    def test_add_invalid_due_date_shows_error(self, client):
        resp = _add(client, 'Bad date', due_date='not-a-date')
        assert '格式无效'.encode('utf-8') in resp.data

    def test_add_invalid_priority_defaults_to_medium(self, client):
        _add(client, 'Sneaky task', priority='超高')
        with app.app_context():
            todo = Todo.query.first()
            assert todo.priority == '中'

    def test_add_sets_created_at(self, client):
        _add(client, 'Timed task')
        with app.app_context():
            todo = Todo.query.first()
            assert todo.created_at is not None

    def test_add_defaults_complete_to_false(self, client):
        _add(client, 'Fresh task')
        with app.app_context():
            todo = Todo.query.first()
            assert todo.complete is False

    def test_add_shows_success_flash(self, client):
        resp = _add(client, 'Flash me')
        assert '已添加'.encode('utf-8') in resp.data


# ---------------------------------------------------------------------------
# Update route
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_toggles_complete(self, client):
        _add(client, 'Toggle me')
        todo_id = _first_id(client)

        client.get(f'/update/{todo_id}', follow_redirects=True)
        with app.app_context():
            assert db.session.get(Todo, todo_id).complete is True

        client.get(f'/update/{todo_id}', follow_redirects=True)
        with app.app_context():
            assert db.session.get(Todo, todo_id).complete is False

    def test_update_nonexistent_shows_error(self, client):
        resp = client.get('/update/99999', follow_redirects=True)
        assert resp.status_code == 200
        assert '未找到'.encode('utf-8') in resp.data

    def test_update_redirects_to_home(self, client):
        _add(client, 'Redirect me')
        todo_id = _first_id(client)
        resp = client.get(f'/update/{todo_id}')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Delete route
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_removes_task(self, client):
        _add(client, 'Gone soon')
        todo_id = _first_id(client)

        client.get(f'/delete/{todo_id}', follow_redirects=True)
        with app.app_context():
            assert db.session.get(Todo, todo_id) is None

    def test_delete_nonexistent_shows_error(self, client):
        resp = client.get('/delete/99999', follow_redirects=True)
        assert resp.status_code == 200
        assert '未找到'.encode('utf-8') in resp.data

    def test_delete_shows_success_flash(self, client):
        _add(client, 'Delete flash')
        todo_id = _first_id(client)
        resp = client.get(f'/delete/{todo_id}', follow_redirects=True)
        assert '已删除'.encode('utf-8') in resp.data

    def test_delete_redirects_to_home(self, client):
        _add(client, 'Quick delete')
        todo_id = _first_id(client)
        resp = client.get(f'/delete/{todo_id}')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Priority sorting
# ---------------------------------------------------------------------------

class TestPrioritySorting:
    def test_high_before_medium_before_low(self, client):
        _add(client, 'Low task', priority='低')
        _add(client, 'High task', priority='高')
        _add(client, 'Mid task', priority='中')

        resp = client.get('/')
        body = resp.data.decode('utf-8')
        high_pos = body.find('High task')
        mid_pos = body.find('Mid task')
        low_pos = body.find('Low task')
        assert high_pos < mid_pos < low_pos


# ---------------------------------------------------------------------------
# Overdue tasks
# ---------------------------------------------------------------------------

class TestOverdue:
    def test_overdue_task_shows_badge(self, client):
        past = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        _add(client, 'Late task', due_date=past)
        resp = client.get('/')
        assert '已过期'.encode('utf-8') in resp.data

    def test_future_task_not_overdue(self, client):
        future = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
        _add(client, 'Future task', due_date=future)
        with app.app_context():
            todo = Todo.query.first()
            assert todo.is_overdue() is False

    def test_completed_task_not_overdue_even_if_past_due(self, client):
        past = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
        _add(client, 'Done late', due_date=past)
        todo_id = _first_id(client)
        client.get(f'/update/{todo_id}')  # mark complete
        with app.app_context():
            todo = db.session.get(Todo, todo_id)
            assert todo.is_overdue() is False

    def test_no_due_date_never_overdue(self, client):
        _add(client, 'No deadline')
        with app.app_context():
            todo = Todo.query.first()
            assert todo.is_overdue() is False


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------

class TestModelDefaults:
    def test_default_priority_is_medium(self, client):
        with app.app_context():
            todo = Todo(title='Default', complete=False)
            db.session.add(todo)
            db.session.commit()
            assert todo.priority == '中'

    def test_default_complete_is_false(self, client):
        with app.app_context():
            todo = Todo(title='Fresh', complete=False)
            db.session.add(todo)
            db.session.commit()
            assert todo.complete is False
