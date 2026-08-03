from datetime import datetime, timezone
from enum import Enum

from flask_login import UserMixin

from app import bcrypt, db


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class TimestampStatusMixin:
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    status = db.Column(db.Enum(Status), default=Status.ACTIVE, nullable=False)


class Role(db.Model, TimestampStatusMixin):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    users = db.relationship("User", back_populates="role", lazy="dynamic")


class User(UserMixin, db.Model, TimestampStatusMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    role = db.relationship("Role", back_populates="users")
    professor_profile = db.relationship("Professor", back_populates="user", uselist=False)
    student_profile = db.relationship("Student", back_populates="user", uselist=False)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else ""

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)


class Department(db.Model, TimestampStatusMixin):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    courses = db.relationship("Course", back_populates="department", lazy="dynamic")


class Course(db.Model, TimestampStatusMixin):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    department = db.relationship("Department", back_populates="courses")
    subjects = db.relationship("Subject", back_populates="course", lazy="dynamic")


class Subject(db.Model, TimestampStatusMixin):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    course = db.relationship("Course", back_populates="subjects")


class Professor(db.Model, TimestampStatusMixin):
    __tablename__ = "professors"

    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    user = db.relationship("User", back_populates="professor_profile")
    department = db.relationship("Department")


class Student(db.Model, TimestampStatusMixin):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=False)
    barcode_id = db.Column(db.String(100), unique=True, nullable=True, index=True)  # Real college ID card barcode
    gender = db.Column(db.String(30), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)
    address = db.Column(db.Text, nullable=True)
    guardian_name = db.Column(db.String(100), nullable=True)
    guardian_phone = db.Column(db.String(30), nullable=True)
    emergency_contact = db.Column(db.String(30), nullable=True)
    profile_photo = db.Column(db.String(500), nullable=True)
    is_profile_completed = db.Column(db.Boolean, default=False, nullable=False)
    user = db.relationship("User", back_populates="student_profile")
    course = db.relationship("Course")
    face_encodings = db.relationship("FaceEncoding", back_populates="student", lazy="dynamic")
    leave_requests = db.relationship("LeaveRequest", back_populates="student", lazy="dynamic")


class ClassRoom(db.Model, TimestampStatusMixin):
    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(20), nullable=True)
    course = db.relationship("Course")
    attendance_sessions = db.relationship("AttendanceSession", back_populates="classroom", lazy="dynamic")


class AttendanceSession(db.Model, TimestampStatusMixin):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    method = db.Column(db.String(30), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey("professors.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject = db.relationship("Subject")
    professor = db.relationship("Professor")
    classroom = db.relationship("ClassRoom", back_populates="attendance_sessions")
    attendance_records = db.relationship("Attendance", back_populates="session", lazy="dynamic")


class Attendance(db.Model, TimestampStatusMixin):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False)
    marked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    attendance_status = db.Column(db.String(30), nullable=False)
    confidence_score = db.Column(db.Float, nullable=True)
    student = db.relationship("Student")
    session = db.relationship("AttendanceSession", back_populates="attendance_records")
    __table_args__ = (db.UniqueConstraint("student_id", "session_id", name="uq_student_session"),)


class FaceEncoding(db.Model, TimestampStatusMixin):
    __tablename__ = "face_encodings"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    encoding_path = db.Column(db.String(500), nullable=False)
    image_path = db.Column(db.String(500), nullable=True)
    confidence_threshold = db.Column(db.Float, default=0.6, nullable=False)
    student = db.relationship("Student", back_populates="face_encodings")


class QRCode(db.Model, TimestampStatusMixin):
    __tablename__ = "qr_codes"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)


class LeaveRequest(db.Model, TimestampStatusMixin):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    decision = db.Column(db.String(30), default="pending", nullable=False)
    document_path = db.Column(db.String(500), nullable=True)
    student = db.relationship("Student", back_populates="leave_requests")


class Notification(db.Model, TimestampStatusMixin):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)


class Report(db.Model, TimestampStatusMixin):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    generated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    report_type = db.Column(db.String(80), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)


class ActivityLog(db.Model, TimestampStatusMixin):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(150), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(80), nullable=True)


class Setting(db.Model, TimestampStatusMixin):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)


class TimeSlot(db.Model, TimestampStatusMixin):
    __tablename__ = "time_slots"

    id = db.Column(db.Integer, primary_key=True)
    slot_name = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    is_recess = db.Column(db.Boolean, default=False, nullable=False)


class TimetableEntry(db.Model, TimestampStatusMixin):
    __tablename__ = "timetable_entries"

    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.String(15), nullable=False)
    time_slot_id = db.Column(db.Integer, db.ForeignKey("time_slots.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True)
    professor_id = db.Column(db.Integer, db.ForeignKey("professors.id"), nullable=True)
    room_number = db.Column(db.String(50), nullable=True)
    is_lab = db.Column(db.Boolean, default=False, nullable=False)

    time_slot = db.relationship("TimeSlot")
    classroom = db.relationship("ClassRoom")
    subject = db.relationship("Subject")
    professor = db.relationship("Professor")


class TimetableOverride(db.Model, TimestampStatusMixin):
    __tablename__ = "timetable_overrides"

    id = db.Column(db.Integer, primary_key=True)
    override_date = db.Column(db.Date, nullable=False)
    timetable_entry_id = db.Column(db.Integer, db.ForeignKey("timetable_entries.id"), nullable=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    time_slot_id = db.Column(db.Integer, db.ForeignKey("time_slots.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="normal")
    substitute_professor_id = db.Column(db.Integer, db.ForeignKey("professors.id"), nullable=True)
    note = db.Column(db.Text, nullable=True)

    timetable_entry = db.relationship("TimetableEntry")
    classroom = db.relationship("ClassRoom")
    time_slot = db.relationship("TimeSlot")
    substitute_professor = db.relationship("Professor", foreign_keys=[substitute_professor_id])

