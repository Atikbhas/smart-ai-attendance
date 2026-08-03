# AI Attendance Management System - Project Details

## Overview

This is a Flask-based attendance management system built for an AI-enabled attendance workflow with Admin, Professor, and Student portals.

The project supports:
- Role-based authentication and dashboards
- Department, course, subject, class, professor, and student management
- Face recognition training and cached face encoding handling
- Attendance sessions and records
- Password reset and email support
- CLI seeding for default roles and admin

## Project Layout

- `run.py` - application entry point
- `app/__init__.py` - Flask app factory, database initialization, blueprint registration, startup seeding, and host enforcement
- `app/config.py` - application configuration with environment variables and default SQLite fallback
- `app/models/__init__.py` - SQLAlchemy models for users, roles, students, professors, attendance, face encodings, QR codes, notifications, reports, and settings
- `app/auth/` - authentication forms and routes
- `app/admin/` - admin forms and routes for managing academic data and face recognition
- `app/main/` - public landing page route
- `app/services/face_service.py` - face image upload, training, encoding cache management, and DeepFace integration
- `app/cli.py` - Flask CLI seed command
- `app/templates/` - HTML templates for auth, admin, professor, student, and main UI
- `app/static/` - CSS and JavaScript assets
- `requirements.txt` - Python dependencies
- `README.md` - setup and usage instructions

## Key Files

- `app/__init__.py`
  - Initializes Flask extensions: SQLAlchemy, Migrate, LoginManager, Bcrypt, CSRF
  - Registers blueprints: `auth`, `main`, `admin`, `professor`, `student`
  - Creates database tables on startup and seeds roles/users
  - Sets allowed localhost host headers for security

- `app/config.py`
  - Defines `BaseConfig`, `DevelopmentConfig`, `ProductionConfig`, `TestingConfig`
  - Loads `.env` values with `python-dotenv`
  - Configures database URI, uploads, face cache TTL, email settings, and session cookie security

- `app/models/__init__.py`
  - Defines main entities and relationships:
    - `User`, `Role`
    - `Department`, `Course`, `Subject`, `ClassRoom`
    - `Professor`, `Student`, `AttendanceSession`, `Attendance`
    - `FaceEncoding`, `QRCode`, `LeaveRequest`, `Notification`, `Report`, `ActivityLog`, `Setting`

- `app/auth/routes.py`
  - Handles login, logout, change password, forgot password, and reset password flows

- `app/admin/routes.py`
  - Admin dashboard and CRUD routes for departments, courses, subjects, classes, professors, and students
  - Face recognition status, cache info, and cache clearing

- `app/services/face_service.py`
  - Handles allowed image formats, image saving, training with DeepFace, encoding persistence, and caching

- `app/cli.py`
  - Provides `flask seed` to create default roles and admin user

## Dependencies

Major dependencies in `requirements.txt`:
- `Flask` and Flask extensions: `Flask-SQLAlchemy`, `Flask-Migrate`, `Flask-Login`, `Flask-WTF`, `Flask-Bcrypt`, `Flask-Limiter`
- `PyMySQL` for MySQL support
- AI/vision libraries: `opencv-python`, `deepface`, `numpy`
- Data and reporting: `pandas`, `matplotlib`, `seaborn`, `qrcode`, `Pillow`, `reportlab`, `openpyxl`
- Testing: `pytest`

## Setup Instructions

1. Create/activate the virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Create `.env` from `.env.example` and set values.
4. Create the database and apply migrations or rely on default SQLite if no database URL is provided.
5. Run the app:
   ```powershell
   python run.py
   ```

## How to Use the Project

### Admin portal
- Login as admin at `/login` using `admin@example.com / Admin@12345`.
- Access the admin dashboard at `/admin/dashboard`.
- Manage academic entities:
  - Departments at `/admin/departments`
  - Courses at `/admin/courses`
  - Subjects at `/admin/subjects`
  - Classes at `/admin/classes`
- Create and manage users:
  - Professors at `/admin/professors`
  - Students at `/admin/students`
- Use face recognition tools at `/admin/face-recognition` to view training status and clear the face encoding cache.

### Professor portal
- Professors login at `/login` and are redirected to `/professor/dashboard`.
- Start attendance sessions via face recognition or QR code in the Professor portal.
- Face attendance page is available at `/professor/attendance/face`.
- QR attendance page is available at `/professor/attendance/qr`.
- Start a session with a class and subject selection, then scan or upload student images to mark attendance.
- Stop the session via `/professor/session/stop` when attendance is complete.
- View session history at `/professor/sessions` and export records as CSV or PDF.
- Access analytics at `/professor/analytics` for attendance trends and reporting.

### Student portal
- Students login at `/login` and are redirected to `/student/dashboard`.
- Upload their face image and train the system at `/student/face`.
- For QR attendance, scan the QR code provided by the professor and visit the generated URL.
- The student QR attendance endpoint is `/student/attendance/qr/<token>` and marks attendance when valid.

## Default Login Credentials

- Admin portal:
  - Email: `admin@example.com`
  - Password: `Admin@12345`
- Professor portal demo users (when seeded):
  - Email: `professor1@example.com` to `professor10@example.com`
  - Password: `Professor@1 23` to `Professor@10 23` (pattern: `Professor@<index>123`)
- Student portal demo users (when seeded):
  - Email: `student1@example.com` to `student10@example.com`
  - Password: `Student@1 23` to `Student@10 23` (pattern: `Student@<index>123`)

The app also writes demo credentials to `demo_accounts.txt` during startup.

## Notes

- `app/config.py` uses an SQLite fallback database in `instance/app.db` when no database settings are present.
- Face recognition requires `deepface`, `opencv-python`, and `numpy`.

---

File created as `PROJECT_DETAILS.md` with the project summary and structure.