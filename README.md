# Flask Todo App

A multi-user todo application built with Flask, SQLAlchemy, and Flask-Login.

## Features

| Feature | Original | This version |
|---|---|---|
| 用户系统 | 无，所有人共用 | 注册 / 登录 / 登出，数据按用户隔离 |
| 任务优先级 | 无 | 高 / 中 / 低，列表按优先级排序 |
| 截止日期 | 无 | 可选截止日期，过期任务自动标红 |
| 创建时间 | 无 | 自动记录 |
| 错误处理 | 无（空标题直接崩溃） | Flash 提示：空标题、非法日期、ID 不存在 |
| 测试 | 无 | 49 个 pytest 单元测试，覆盖所有路由和边界情况 |
| 依赖管理 | 无 requirements.txt | `requirements.txt` |

## Quick Start

```bash
# 1. 克隆 / 进入项目目录
cd flask-todo

# 2. 创建并激活虚拟环境（推荐）
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动
python app.py
```

打开浏览器访问 http://127.0.0.1:5000

首次访问会跳转到登录页，先点「立即注册」创建账号。

## Routes

| 路由 | 方法 | 说明 |
|---|---|---|
| `/` | GET | 任务列表（需登录） |
| `/add` | POST | 新建任务（需登录） |
| `/update/<id>` | GET | 切换完成状态（需登录，仅限本人任务） |
| `/delete/<id>` | GET | 删除任务（需登录，仅限本人任务） |
| `/register` | GET / POST | 注册 |
| `/login` | GET / POST | 登录 |
| `/logout` | GET | 退出登录 |

## Running Tests

```bash
python -m pytest test_app.py -v
```

```
49 passed in ~14s
```

测试覆盖：注册验证、登录鉴权、访问控制、用户数据隔离、优先级排序、过期判断、所有 CRUD 边界情况。

## Tech Stack

- [Flask](https://flask.palletsprojects.com/) — web framework
- [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) — ORM，SQLite 存储
- [Flask-Login](https://flask-login.readthedocs.io/) — 会话管理与路由保护
- [Werkzeug](https://werkzeug.palletsprojects.com/) — 密码哈希（`generate_password_hash` / `check_password_hash`）
- [Semantic UI](https://semantic-ui.com/) — 前端样式
- [pytest](https://pytest.org/) — 单元测试
