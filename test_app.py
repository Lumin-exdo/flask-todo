"""
Unit tests for the Flask Todo App (with authentication).
Uses an in-memory SQLite database; all todo routes require login.
"""

import pytest
from datetime import date, timedelta

from app import app, db, Todo, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Fresh in-memory DB + test client."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def auth_client(client):
    """Test client already logged in as 'testuser'."""
    _register(client, 'testuser', 'testpass123')
    _login(client, 'testuser', 'testpass123')
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(client, username, password):
    return client.post('/register', data={
        'username': username, 'password': password, 'confirm': password,
    }, follow_redirects=True)


def _login(client, username, password):
    return client.post('/login', data={
        'username': username, 'password': password,
    }, follow_redirects=True)


def _add(client, title, priority='中', due_date=''):
    return client.post('/add', data={
        'title': title, 'priority': priority, 'due_date': due_date,
    }, follow_redirects=True)


def _first_todo_id():
    """Return id of first Todo row (call inside app context)."""
    todo = Todo.query.first()
    return todo.id if todo else None


# ---------------------------------------------------------------------------
# Authentication — register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_page_loads(self, client):
        assert client.get('/register').status_code == 200

    def test_register_success_redirects_to_login(self, client):
        resp = _register(client, 'alice', 'secret123')
        assert '登录'.encode('utf-8') in resp.data

    def test_register_creates_user(self, client):
        _register(client, 'bob', 'pass1234')
        with app.app_context():
            assert User.query.filter_by(username='bob').first() is not None

    def test_register_empty_username(self, client):
        resp = _register(client, '', 'pass1234')
        assert '不能为空'.encode('utf-8') in resp.data

    def test_register_short_username(self, client):
        resp = _register(client, 'ab', 'pass1234')
        assert '3 个字符'.encode('utf-8') in resp.data

    def test_register_short_password(self, client):
        resp = _register(client, 'charlie', '123')
        assert '6 个字符'.encode('utf-8') in resp.data

    def test_register_password_mismatch(self, client):
        resp = client.post('/register', data={
            'username': 'dave', 'password': 'aaa111', 'confirm': 'bbb222',
        }, follow_redirects=True)
        assert '不一致'.encode('utf-8') in resp.data

    def test_register_duplicate_username(self, client):
        _register(client, 'eve', 'pass1234')
        resp = _register(client, 'eve', 'other456')
        assert '已被占用'.encode('utf-8') in resp.data

    def test_authenticated_user_redirected_from_register(self, auth_client):
        resp = auth_client.get('/register')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Authentication — login / logout
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_page_loads(self, client):
        assert client.get('/login').status_code == 200

    def test_login_success(self, client):
        _register(client, 'frank', 'pass1234')
        resp = _login(client, 'frank', 'pass1234')
        assert '欢迎'.encode('utf-8') in resp.data

    def test_login_wrong_password(self, client):
        _register(client, 'grace', 'correct1')
        resp = _login(client, 'grace', 'wrong')
        assert '错误'.encode('utf-8') in resp.data

    def test_login_nonexistent_user(self, client):
        resp = _login(client, 'nobody', 'pass1234')
        assert '错误'.encode('utf-8') in resp.data

    def test_authenticated_user_redirected_from_login(self, auth_client):
        resp = auth_client.get('/login')
        assert resp.status_code == 302

    def test_logout_redirects_to_login(self, auth_client):
        resp = auth_client.get('/logout', follow_redirects=True)
        assert '登录'.encode('utf-8') in resp.data

    def test_logout_requires_login(self, client):
        resp = client.get('/logout')
        assert resp.status_code == 302   # redirect to /login


# ---------------------------------------------------------------------------
# Access control — unauthenticated users get redirected
# ---------------------------------------------------------------------------

class TestAccessControl:
    def test_home_requires_login(self, client):
        resp = client.get('/')
        assert resp.status_code == 302

    def test_add_requires_login(self, client):
        resp = client.post('/add', data={'title': 'x', 'priority': '中', 'due_date': ''})
        assert resp.status_code == 302

    def test_update_requires_login(self, client):
        resp = client.get('/update/1')
        assert resp.status_code == 302

    def test_delete_requires_login(self, client):
        resp = client.get('/delete/1')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Home route
# ---------------------------------------------------------------------------

class TestHome:
    def test_home_returns_200(self, auth_client):
        assert auth_client.get('/').status_code == 200

    def test_home_shows_empty_message(self, auth_client):
        assert '暂无任务'.encode('utf-8') in auth_client.get('/').data

    def test_home_shows_added_task(self, auth_client):
        _add(auth_client, 'Buy milk')
        assert b'Buy milk' in auth_client.get('/').data


# ---------------------------------------------------------------------------
# Add route
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_valid_task(self, auth_client):
        resp = _add(auth_client, 'Walk the dog')
        assert b'Walk the dog' in resp.data

    def test_add_with_high_priority(self, auth_client):
        _add(auth_client, 'Urgent', priority='高')
        with app.app_context():
            assert Todo.query.first().priority == '高'

    def test_add_with_due_date(self, auth_client):
        future = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
        _add(auth_client, 'Future task', due_date=future)
        with app.app_context():
            assert Todo.query.first().due_date is not None

    def test_add_empty_title_shows_error(self, auth_client):
        assert '不能为空'.encode('utf-8') in _add(auth_client, '').data

    def test_add_whitespace_only_title_shows_error(self, auth_client):
        assert '不能为空'.encode('utf-8') in _add(auth_client, '   ').data

    def test_add_invalid_due_date_shows_error(self, auth_client):
        assert '格式无效'.encode('utf-8') in _add(auth_client, 'X', due_date='bad').data

    def test_add_invalid_priority_defaults_to_medium(self, auth_client):
        _add(auth_client, 'Sneaky', priority='超高')
        with app.app_context():
            assert Todo.query.first().priority == '中'

    def test_add_sets_created_at(self, auth_client):
        _add(auth_client, 'Timed')
        with app.app_context():
            assert Todo.query.first().created_at is not None

    def test_add_shows_success_flash(self, auth_client):
        assert '已添加'.encode('utf-8') in _add(auth_client, 'Flash me').data


# ---------------------------------------------------------------------------
# Update route
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_toggles_complete(self, auth_client):
        _add(auth_client, 'Toggle me')
        with app.app_context():
            todo_id = _first_todo_id()

        auth_client.get(f'/update/{todo_id}')
        with app.app_context():
            assert db.session.get(Todo, todo_id).complete is True

        auth_client.get(f'/update/{todo_id}')
        with app.app_context():
            assert db.session.get(Todo, todo_id).complete is False

    def test_update_nonexistent_shows_error(self, auth_client):
        resp = auth_client.get('/update/99999', follow_redirects=True)
        assert '未找到'.encode('utf-8') in resp.data

    def test_update_redirects_to_home(self, auth_client):
        _add(auth_client, 'Redirect me')
        with app.app_context():
            todo_id = _first_todo_id()
        assert auth_client.get(f'/update/{todo_id}').status_code == 302


# ---------------------------------------------------------------------------
# Delete route
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_removes_task(self, auth_client):
        _add(auth_client, 'Gone soon')
        with app.app_context():
            todo_id = _first_todo_id()

        auth_client.get(f'/delete/{todo_id}', follow_redirects=True)
        with app.app_context():
            assert db.session.get(Todo, todo_id) is None

    def test_delete_nonexistent_shows_error(self, auth_client):
        resp = auth_client.get('/delete/99999', follow_redirects=True)
        assert '未找到'.encode('utf-8') in resp.data

    def test_delete_shows_success_flash(self, auth_client):
        _add(auth_client, 'Delete flash')
        with app.app_context():
            todo_id = _first_todo_id()
        resp = auth_client.get(f'/delete/{todo_id}', follow_redirects=True)
        assert '已删除'.encode('utf-8') in resp.data

    def test_delete_redirects_to_home(self, auth_client):
        _add(auth_client, 'Quick delete')
        with app.app_context():
            todo_id = _first_todo_id()
        assert auth_client.get(f'/delete/{todo_id}').status_code == 302


# ---------------------------------------------------------------------------
# User isolation — user A cannot touch user B's todos
# ---------------------------------------------------------------------------

class TestUserIsolation:
    def test_user_cannot_see_other_users_todos(self, client):
        # User A adds a task
        _register(client, 'userA', 'passA123')
        _login(client, 'userA', 'passA123')
        _add(client, 'Private task of A')
        client.get('/logout')

        # User B logs in and should see empty list
        _register(client, 'userB', 'passB123')
        _login(client, 'userB', 'passB123')
        resp = client.get('/')
        assert b'Private task of A' not in resp.data
        assert '暂无任务'.encode('utf-8') in resp.data

    def test_user_cannot_delete_other_users_todo(self, client):
        # User A adds a task
        _register(client, 'userA', 'passA123')
        _login(client, 'userA', 'passA123')
        _add(client, 'A secret task')
        with app.app_context():
            todo_id = _first_todo_id()
        client.get('/logout')

        # User B tries to delete it — should get "not found"
        _register(client, 'userB', 'passB123')
        _login(client, 'userB', 'passB123')
        resp = client.get(f'/delete/{todo_id}', follow_redirects=True)
        assert '未找到'.encode('utf-8') in resp.data

        # Task must still exist in DB
        with app.app_context():
            assert db.session.get(Todo, todo_id) is not None

    def test_user_cannot_update_other_users_todo(self, client):
        _register(client, 'userA', 'passA123')
        _login(client, 'userA', 'passA123')
        _add(client, 'A task')
        with app.app_context():
            todo_id = _first_todo_id()
        client.get('/logout')

        _register(client, 'userB', 'passB123')
        _login(client, 'userB', 'passB123')
        resp = client.get(f'/update/{todo_id}', follow_redirects=True)
        assert '未找到'.encode('utf-8') in resp.data


# ---------------------------------------------------------------------------
# Priority sorting
# ---------------------------------------------------------------------------

class TestPrioritySorting:
    def test_high_before_medium_before_low(self, auth_client):
        _add(auth_client, 'Low task', priority='低')
        _add(auth_client, 'High task', priority='高')
        _add(auth_client, 'Mid task', priority='中')

        body = auth_client.get('/').data.decode('utf-8')
        assert body.find('High task') < body.find('Mid task') < body.find('Low task')


# ---------------------------------------------------------------------------
# Overdue tasks
# ---------------------------------------------------------------------------

class TestOverdue:
    def test_overdue_task_shows_badge(self, auth_client):
        past = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        _add(auth_client, 'Late task', due_date=past)
        assert '已过期'.encode('utf-8') in auth_client.get('/').data

    def test_future_task_not_overdue(self, auth_client):
        future = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
        _add(auth_client, 'Future task', due_date=future)
        with app.app_context():
            assert Todo.query.first().is_overdue() is False

    def test_completed_task_not_overdue_even_if_past_due(self, auth_client):
        past = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
        _add(auth_client, 'Done late', due_date=past)
        with app.app_context():
            todo_id = _first_todo_id()
        auth_client.get(f'/update/{todo_id}')
        with app.app_context():
            assert db.session.get(Todo, todo_id).is_overdue() is False

    def test_no_due_date_never_overdue(self, auth_client):
        _add(auth_client, 'No deadline')
        with app.app_context():
            assert Todo.query.first().is_overdue() is False


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------

class TestModelDefaults:
    def test_default_priority_is_medium(self, auth_client):
        with app.app_context():
            user = User.query.first()
            todo = Todo(title='Default', complete=False, user_id=user.id)
            db.session.add(todo)
            db.session.commit()
            assert todo.priority == '中'

    def test_password_is_hashed(self, client):
        _register(client, 'hashed', 'mypassword')
        with app.app_context():
            user = User.query.filter_by(username='hashed').first()
            assert user.password_hash != 'mypassword'
            assert user.check_password('mypassword') is True
            assert user.check_password('wrong') is False
