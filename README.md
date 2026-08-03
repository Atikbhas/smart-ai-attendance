# AI Attendance Management System

Production-shaped Flask application for an AI-based attendance platform with Admin, Professor, and Student portals.

## Phase 1 Included

- Flask app factory with Blueprint architecture
- MySQL-ready SQLAlchemy models
- Flask-Login authentication
- bcrypt password hashing
- CSRF-protected forms
- Role-based dashboard routing
- Admin student and professor creation
- Admin student and professor list pages
- Admin academic setup for departments, courses, subjects, and classes
- Student face image upload and encoding workflow
- Admin face recognition training status page
- Admin, Professor, and Student portal shells
- Bootstrap 5 responsive UI with light/dark mode
- Chart.js dashboard widgets
- CLI seed command for default roles and admin login

Later phases will add CRUD management, face recognition, QR attendance sessions, analytics, exports, notifications, and deployment hardening.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a MySQL database:

```sql
CREATE DATABASE ai_attendance CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'attendance_user'@'localhost' IDENTIFIED BY 'attendance_password';
GRANT ALL PRIVILEGES ON ai_attendance.* TO 'attendance_user'@'localhost';
FLUSH PRIVILEGES;
```

Copy `.env.example` to `.env` and adjust values as needed.

Generate the first migration and apply the database schema:

```powershell
flask db migrate -m "phase 1 core schema"
flask db upgrade
flask seed
```

Run the app:

```powershell
flask run
```

Default admin:

- Email: `admin@example.com`
- Password: `Admin@12345`

## Project Structure

```text
app/
  admin/
  analytics/
  attendance/
  auth/
  main/
  models/
  professor/
  reports/
  repositories/
  services/
  static/
  student/
  templates/
  utils/
```

## Test

```powershell
pytest
```

## Deployment Target

The app is structured for Linux deployment with Gunicorn and Nginx. Production should set a strong `SECRET_KEY`, secure cookies, a non-root MySQL user, HTTPS, log rotation, backups, and environment-managed secrets.
