import os
from pathlib import Path

from flask import Flask, abort, request
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from app.config import config_by_name

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "static", "uploads", "profile_photos"), exist_ok=True)
    
    cfg_key = config_name or os.getenv("FLASK_ENV", "development")
    cfg_cls = config_by_name.get(cfg_key, config_by_name["development"])
    app.config.from_object(cfg_cls)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    from app.models import (
        ActivityLog,
        Attendance,
        AttendanceSession,
        ClassRoom,
        Course,
        Department,
        FaceEncoding,
        LeaveRequest,
        Notification,
        QRCode,
        Report,
        Role,
        Setting,
        Student,
        Subject,
        User,
        Professor,
        TimeSlot,
        TimetableEntry,
        TimetableOverride,
    )

    with app.app_context():
        db.create_all()

        if not app.testing:
            if not Role.query.first():
                db.session.add_all(
                    [
                        Role(name="admin", description="Institution administrator"),
                        Role(name="professor", description="Faculty attendance manager"),
                        Role(name="student", description="Student portal user"),
                    ]
                )
                db.session.commit()

            admin_role = Role.query.filter_by(name="admin").first()
            professor_role = Role.query.filter_by(name="professor").first()
            student_role = Role.query.filter_by(name="student").first()

            if not User.query.first():
                admin = User(
                    email="admin@example.com",
                    first_name="System",
                    last_name="Admin",
                    role=admin_role,
                )
                admin.set_password("Admin@12345")
                db.session.add(admin)

                for index in range(1, 11):
                    student_email = f"student{index}@example.com"
                    student = User(
                        email=student_email,
                        first_name="Demo",
                        last_name=f"Student{index}",
                        role=student_role,
                    )
                    student.set_password(f"Student@{index}123")
                    db.session.add(student)

                    professor_email = f"professor{index}@example.com"
                    professor = User(
                        email=professor_email,
                        first_name="Demo",
                        last_name=f"Professor{index}",
                        role=professor_role,
                    )
                    professor.set_password(f"Professor@{index}123")
                    db.session.add(professor)

                db.session.commit()

                for index in range(1, 11):
                    professor_user = User.query.filter_by(email=f"professor{index}@example.com").first()
                    if professor_user and not professor_user.professor_profile:
                        db.session.add(Professor(user=professor_user, employee_code=f"FAC-{index:02d}"))

                    student_user = User.query.filter_by(email=f"student{index}@example.com").first()
                    if student_user and not student_user.student_profile:
                        db.session.add(Student(user=student_user, roll_number=f"STU-{index:02d}"))

                db.session.commit()

                demo_credentials = [
                    "Demo Accounts",
                    "==============",
                    "Admin: admin@example.com / Admin@12345",
                ]
                for index in range(1, 11):
                    demo_credentials.append(f"Professor{index}: professor{index}@example.com / Professor@{index}123")
                    demo_credentials.append(f"Student{index}: student{index}@example.com / Student@{index}123")

                credentials_path = Path(app.root_path).parent / "demo_accounts.txt"
                credentials_path.write_text("\n".join(demo_credentials) + "\n", encoding="utf-8")

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.admin.routes import admin_bp
    from app.professor.routes import professor_bp
    from app.student.routes import student_bp
    from app.timetable import timetable_bp
    from app.cli import register_cli

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(professor_bp, url_prefix="/professor")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(timetable_bp)
    register_cli(app)

    # ── Custom Jinja2 filters ─────────────────────────────────────────────────
    import os as _os

    @app.template_filter('basename')
    def _basename_filter(path):
        """Return the filename portion of a path string."""
        return _os.path.basename(str(path)) if path else ''

    @app.before_request
    def enforce_localhost_access():
        # Skip the localhost-only check entirely when running on Render (or any host
        # that sets RENDER env var) — this restriction is for local dev safety only.
        if os.environ.get("RENDER"):
            return None

        host_header = (request.headers.get("Host", request.host) or request.host).strip().lower()
        port = os.environ.get("PORT", "5000")
        allowed_hosts = {
            f"localhost:{port}",
            "localhost",
            f"127.0.0.1:{port}",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            f"[::1]:{port}",
            f"127.0.0.1:{int(port) + 1}",
        }

        if host_header in allowed_hosts:
            return None

        if host_header.startswith("localhost") or host_header.startswith("127.0.0.1") or host_header.startswith("::1") or host_header.startswith("test_client"):
            return None

        if host_header.endswith(":5000") or host_header.endswith(":5001"):
            return None
        
        print(f"DEBUG host_header={host_header!r} RENDER_env={os.environ.get('RENDER')!r}", flush=True)
        abort(403)
        
        @app.route('/healthz')
        def health_check():
            return 'OK', 200
        
        print("ROUTES:", app.url_map, flush=True)
        return app