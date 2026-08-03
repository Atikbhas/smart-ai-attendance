from datetime import datetime, time, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.admin.forms import (
    ClassCreateForm,
    CourseCreateForm,
    DepartmentCreateForm,
    ProfessorCreateForm,
    ProfessorEditForm,
    StudentCreateForm,
    StudentEditForm,
    SubjectCreateForm,
)
from app.models import Attendance, AttendanceSession, ClassRoom, Course, Department, LeaveRequest, Professor, Role, Student, Subject, User
from app.security import roles_required
from app.services.face_service import (
    clear_known_encodings,
    clear_per_session_cache,
    face_training_status,
    get_known_encodings_cache_info,
)
from app.services.face_service import finalize_student_dataset
from app.services.qr_service import generate_student_qr_data_uri
from app.models import FaceEncoding, Student

_last_cache_clear_at = None

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@login_required
@roles_required("admin")
def dashboard():
    stats = {
        "departments": Department.query.count(),
        "courses": Course.query.count(),
        "subjects": Subject.query.count(),
        "professors": Professor.query.count(),
        "students": Student.query.count(),
        "leave_requests": LeaveRequest.query.count(),
        "users": User.query.count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/profile")
@login_required
@roles_required("admin")
def profile():
    profile_stats = {
        "role": current_user.role_name.title(),
        "email": current_user.email,
        "name": current_user.full_name,
        "last_login": current_user.last_login_at,
    }
    return render_template("admin/profile.html", profile_stats=profile_stats)


def _department_choices():
    return [(department.id, f"{department.code} - {department.name}") for department in Department.query.order_by(Department.name.asc()).all()]


def _course_choices():
    return [(course.id, f"{course.code} - {course.name}") for course in Course.query.order_by(Course.name.asc()).all()]


@admin_bp.route("/departments")
@login_required
@roles_required("admin")
def departments():
    records = Department.query.order_by(Department.name.asc()).all()
    return render_template("admin/departments.html", departments=records)


@admin_bp.route("/departments/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_department():
    form = DepartmentCreateForm()
    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        if Department.query.filter_by(code=code).first():
            flash("A department with this code already exists.", "danger")
            return render_template("admin/create_department.html", form=form)
        department = Department(name=form.name.data.strip(), code=code)
        db.session.add(department)
        db.session.commit()
        flash("Department created successfully.", "success")
        return redirect(url_for("admin.departments"))
    return render_template("admin/create_department.html", form=form)


@admin_bp.route("/courses")
@login_required
@roles_required("admin")
def courses():
    records = Course.query.join(Department).order_by(Course.name.asc()).all()
    return render_template("admin/courses.html", courses=records)


@admin_bp.route("/courses/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_course():
    form = CourseCreateForm()
    form.department_id.choices = _department_choices()
    if not form.department_id.choices:
        flash("Create a department before adding courses.", "warning")
        return redirect(url_for("admin.create_department"))
    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        if Course.query.filter_by(code=code).first():
            flash("A course with this code already exists.", "danger")
            return render_template("admin/create_course.html", form=form)
        course = Course(name=form.name.data.strip(), code=code, department_id=form.department_id.data)
        db.session.add(course)
        db.session.commit()
        flash("Course created successfully.", "success")
        return redirect(url_for("admin.courses"))
    return render_template("admin/create_course.html", form=form)


@admin_bp.route("/subjects")
@login_required
@roles_required("admin")
def subjects():
    records = Subject.query.join(Course).order_by(Subject.name.asc()).all()
    return render_template("admin/subjects.html", subjects=records)


@admin_bp.route("/subjects/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_subject():
    form = SubjectCreateForm()
    form.course_id.choices = _course_choices()
    if not form.course_id.choices:
        flash("Create a course before adding subjects.", "warning")
        return redirect(url_for("admin.create_course"))
    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        if Subject.query.filter_by(code=code).first():
            flash("A subject with this code already exists.", "danger")
            return render_template("admin/create_subject.html", form=form)
        subject = Subject(name=form.name.data.strip(), code=code, course_id=form.course_id.data)
        db.session.add(subject)
        db.session.commit()
        flash("Subject created successfully.", "success")
        return redirect(url_for("admin.subjects"))
    return render_template("admin/create_subject.html", form=form)


@admin_bp.route("/classes")
@login_required
@roles_required("admin")
def classes():
    records = ClassRoom.query.join(Course).order_by(ClassRoom.name.asc()).all()
    return render_template("admin/classes.html", classes=records)


@admin_bp.route("/leaves")
@login_required
@roles_required("admin")
def leave_requests():
    records = (
        LeaveRequest.query.join(Student)
        .join(User)
        .order_by(LeaveRequest.created_at.desc())
        .all()
    )
    stats = {
        "pending": LeaveRequest.query.filter_by(decision="pending").count(),
        "approved": LeaveRequest.query.filter_by(decision="approved").count(),
        "rejected": LeaveRequest.query.filter_by(decision="rejected").count(),
    }
    return render_template("admin/leaves.html", leaves=records, stats=stats)


@admin_bp.route("/leaves/<int:leave_id>/<decision>", methods=["POST"])
@login_required
@roles_required("admin")
def decide_leave(leave_id, decision):
    if decision not in {"approved", "rejected"}:
        flash("Invalid leave decision.", "danger")
        return redirect(url_for("admin.leave_requests"))

    leave = db.session.get(LeaveRequest, leave_id)
    if not leave:
        flash("Leave request not found.", "danger")
        return redirect(url_for("admin.leave_requests"))

    leave.decision = decision
    if decision == "approved" and leave.starts_on and leave.ends_on:
        # 1. Student leave sync
        if leave.student:
            start_dt = datetime.combine(leave.starts_on, time.min)
            end_dt = datetime.combine(leave.ends_on, time.max)
            sessions = AttendanceSession.query.filter(
                AttendanceSession.starts_at >= start_dt,
                AttendanceSession.starts_at <= end_dt
            ).all()
            for sess in sessions:
                att = Attendance.query.filter_by(session_id=sess.id, student_id=leave.student.id).first()
                if att:
                    att.attendance_status = "leave"
                else:
                    db.session.add(Attendance(
                        student_id=leave.student.id,
                        session_id=sess.id,
                        marked_at=start_dt,
                        attendance_status="leave"
                    ))

        # 2. Professor leave sync (Check if student's user or prof user submitted leave)
        prof = None
        if hasattr(leave, "student") and leave.student and hasattr(leave.student, "user"):
            prof = Professor.query.filter_by(user_id=leave.student.user_id).first()

        if prof:
            from datetime import timedelta
            from app.models import TimetableEntry, TimetableOverride, Notification
            curr_date = leave.starts_on
            while curr_date <= leave.ends_on:
                dow = curr_date.strftime("%a").upper()
                entries = TimetableEntry.query.filter_by(day_of_week=dow, professor_id=prof.id).all()
                for entry in entries:
                    ov = TimetableOverride.query.filter_by(
                        override_date=curr_date, class_id=entry.class_id, time_slot_id=entry.time_slot_id
                    ).first()
                    if not ov:
                        ov = TimetableOverride(
                            override_date=curr_date,
                            class_id=entry.class_id,
                            time_slot_id=entry.time_slot_id,
                            timetable_entry_id=entry.id,
                            status="cancelled",
                            note=f"Prof. {prof.user.full_name if prof.user else 'Faculty'} on approved leave"
                        )
                        db.session.add(ov)

                    # Notify students
                    if entry.classroom and entry.classroom.course_id:
                        students = Student.query.filter_by(course_id=entry.classroom.course_id).all()
                        for s in students:
                            db.session.add(Notification(
                                user_id=s.user_id,
                                title=f"Lecture Notice: {entry.classroom.name}",
                                body=f"Notice: Lecture on {curr_date} (Slot #{entry.time_slot_id}) is cancelled due to faculty leave."
                            ))
                curr_date += timedelta(days=1)

    db.session.commit()
    flash(f"Leave request {decision}.", "success")
    return redirect(url_for("admin.leave_requests"))


@admin_bp.route("/face-recognition")
@login_required
@roles_required("admin")
def face_recognition():
    stats = face_training_status()
    students = Student.query.join(User).order_by(User.first_name.asc()).all()
    cache_info = get_known_encodings_cache_info()
    return render_template("admin/face_recognition.html", stats=stats, students=students, cache_info=cache_info)


@admin_bp.route('/face-recognition/delete/<int:student_id>', methods=['POST'])
@login_required
@roles_required('admin')
def delete_face_data(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('admin.face_recognition'))

    # delete encoding records and files
    records = FaceEncoding.query.filter_by(student_id=student.id).all()
    removed = 0
    for r in records:
        try:
            from pathlib import Path
            Path(r.encoding_path).unlink(missing_ok=True)
            if r.image_path:
                Path(r.image_path).unlink(missing_ok=True)
        except Exception:
            pass
        db.session.delete(r)
        removed += 1
    db.session.commit()
    clear_known_encodings()
    clear_per_session_cache()
    flash(f'Removed {removed} face encodings for {student.user.full_name}.', 'success')
    return redirect(url_for('admin.face_recognition'))


@admin_bp.route('/face-recognition/retrain/<int:student_id>', methods=['POST'])
@login_required
@roles_required('admin')
def retrain_face_data(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('admin.face_recognition'))

    try:
        result = finalize_student_dataset(student)
    except Exception as exc:
        current_app.logger.exception('Retrain failed')
        flash('Retrain failed: ' + str(exc), 'danger')
        return redirect(url_for('admin.face_recognition'))

    clear_known_encodings()
    clear_per_session_cache()
    if result.get('trained'):
        flash(f"Retrain completed: {result.get('trained_count',0)} encodings created.", 'success')
    else:
        flash('Retrain did not complete: ' + (result.get('reason') or 'unknown'), 'warning')
    return redirect(url_for('admin.face_recognition'))


@admin_bp.route('/face-recognition/clear-cache', methods=['POST'])
@login_required
@roles_required('admin')
def clear_face_cache():
    global _last_cache_clear_at
    now = datetime.now(timezone.utc)
    rate_limit = int(current_app.config.get('FACE_CACHE_CLEAR_RATE_LIMIT_SECONDS', 60))
    if _last_cache_clear_at and (now - _last_cache_clear_at).total_seconds() < rate_limit:
        current_app.logger.warning('Admin attempted to clear face cache too frequently.')
        flash(f'Cache clearing is rate-limited. Try again later.', 'warning')
        return redirect(url_for('admin.face_recognition'))

    clear_known_encodings()
    _last_cache_clear_at = now
    current_app.logger.info('Face encodings cache cleared by admin.')
    flash('Face encodings cache cleared.', 'success')
    return redirect(url_for('admin.face_recognition'))


@admin_bp.route("/classes/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_class():
    form = ClassCreateForm()
    form.course_id.choices = _course_choices()
    if not form.course_id.choices:
        flash("Create a course before adding classes.", "warning")
        return redirect(url_for("admin.create_course"))
    if form.validate_on_submit():
        class_room = ClassRoom(
            name=form.name.data.strip(),
            course_id=form.course_id.data,
            semester=form.semester.data,
            section=form.section.data.strip() or None,
        )
        db.session.add(class_room)
        db.session.commit()
        flash("Class created successfully.", "success")
        return redirect(url_for("admin.classes"))
    return render_template("admin/create_class.html", form=form)


@admin_bp.route("/students")
@login_required
@roles_required("admin")
def students():
    student_records = Student.query.join(User).order_by(User.first_name.asc()).all()
    return render_template("admin/students.html", students=student_records)


@admin_bp.route("/students/<int:student_id>/id-card")
@login_required
@roles_required("admin")
def student_id_card(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.students"))
    qr_uri = generate_student_qr_data_uri(student)
    return render_template("student/id_card.html", student=student, qr_uri=qr_uri)


@admin_bp.route("/students/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_student():
    form = StudentCreateForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        roll_number = form.roll_number.data.strip()

        if User.query.filter_by(email=email).first():
            flash("A user with this email already exists.", "danger")
            return render_template("admin/create_student.html", form=form)

        if Student.query.filter_by(roll_number=roll_number).first():
            flash("A student with this roll number already exists.", "danger")
            return render_template("admin/create_student.html", form=form)

        student_role = Role.query.filter_by(name="student").first()
        if not student_role:
            flash("Student role is missing. Run the seed command first.", "danger")
            return render_template("admin/create_student.html", form=form)

        user = User(
            email=email,
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            role=student_role,
        )
        user.set_password(form.password.data)
        student = Student(
            user=user,
            roll_number=roll_number,
            gender=form.gender.data or None,
        )
        db.session.add(student)
        db.session.commit()

        flash("Student account created successfully.", "success")
        return redirect(url_for("admin.students"))

    return render_template("admin/create_student.html", form=form)


@admin_bp.route("/professors")
@login_required
@roles_required("admin")
def professors():
    professor_records = Professor.query.join(User).order_by(User.first_name.asc()).all()
    return render_template("admin/professors.html", professors=professor_records)


@admin_bp.route("/professors/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_professor():
    form = ProfessorCreateForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        employee_code = form.employee_code.data.strip()

        if User.query.filter_by(email=email).first():
            flash("A user with this email already exists.", "danger")
            return render_template("admin/create_professor.html", form=form)

        if Professor.query.filter_by(employee_code=employee_code).first():
            flash("A professor with this employee code already exists.", "danger")
            return render_template("admin/create_professor.html", form=form)

        professor_role = Role.query.filter_by(name="professor").first()
        if not professor_role:
            flash("Professor role is missing. Run the seed command first.", "danger")
            return render_template("admin/create_professor.html", form=form)

        user = User(
            email=email,
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            role=professor_role,
        )
        user.set_password(form.password.data)
        professor = Professor(user=user, employee_code=employee_code)
        db.session.add(professor)
        db.session.commit()

        flash("Professor account created successfully.", "success")
        return redirect(url_for("admin.professors"))

    return render_template("admin/create_professor.html", form=form)


@admin_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.students"))

    user = student.user
    form = StudentEditForm()
    form.course_id.choices = [(0, "No Course")] + _course_choices()

    if form.validate_on_submit():
        user.first_name = form.first_name.data.strip()
        user.last_name = form.last_name.data.strip()
        user.email = form.email.data.strip().lower()
        student.roll_number = form.roll_number.data.strip()
        student.barcode_id = form.barcode_id.data.strip() or None
        student.gender = form.gender.data or None
        student.course_id = form.course_id.data if form.course_id.data != 0 else None

        if form.new_password.data and form.new_password.data.strip():
            user.set_password(form.new_password.data.strip())

        db.session.commit()
        flash("Student profile updated successfully.", "success")
        return redirect(url_for("admin.students"))

    if request.method == "GET":
        form.first_name.data = user.first_name
        form.last_name.data = user.last_name
        form.email.data = user.email
        form.roll_number.data = student.roll_number
        form.barcode_id.data = student.barcode_id or ""
        form.gender.data = student.gender or ""
        form.course_id.data = student.course_id or 0

    return render_template("admin/edit_student.html", form=form, student=student)


@admin_bp.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.students"))

    Attendance.query.filter_by(student_id=student.id).delete()
    FaceEncoding.query.filter_by(student_id=student.id).delete()
    LeaveRequest.query.filter_by(student_id=student.id).delete()
    user = student.user
    db.session.delete(student)
    if user:
        db.session.delete(user)
    db.session.commit()
    flash("Student record deleted successfully.", "success")
    return redirect(url_for("admin.students"))


@admin_bp.route("/professors/<int:professor_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_professor(professor_id):
    prof = db.session.get(Professor, professor_id)
    if not prof:
        flash("Professor not found.", "danger")
        return redirect(url_for("admin.professors"))

    user = prof.user
    form = ProfessorEditForm()
    form.department_id.choices = [(0, "No Department")] + _department_choices()

    if form.validate_on_submit():
        user.first_name = form.first_name.data.strip()
        user.last_name = form.last_name.data.strip()
        user.email = form.email.data.strip().lower()
        prof.employee_code = form.employee_code.data.strip()
        prof.department_id = form.department_id.data if form.department_id.data != 0 else None

        if form.new_password.data and form.new_password.data.strip():
            user.set_password(form.new_password.data.strip())

        db.session.commit()
        flash("Professor profile updated successfully.", "success")
        return redirect(url_for("admin.professors"))

    if request.method == "GET":
        form.first_name.data = user.first_name
        form.last_name.data = user.last_name
        form.email.data = user.email
        form.employee_code.data = prof.employee_code
        form.department_id.data = prof.department_id or 0

    return render_template("admin/edit_professor.html", form=form, professor=prof)


@admin_bp.route("/professors/<int:professor_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_professor(professor_id):
    prof = db.session.get(Professor, professor_id)
    if not prof:
        flash("Professor not found.", "danger")
        return redirect(url_for("admin.professors"))
    user = prof.user
    db.session.delete(prof)
    if user:
        db.session.delete(user)
    db.session.commit()
    flash("Professor record deleted successfully.", "success")
    return redirect(url_for("admin.professors"))


@admin_bp.route("/attendance")
@login_required
@roles_required("admin")
def master_attendance():
    records = Attendance.query.order_by(Attendance.marked_at.desc()).limit(200).all()
    return render_template("admin/master_attendance.html", attendances=records)


# --- DEPARTMENT EDIT & DELETE ---
@admin_bp.route("/departments/<int:department_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_department(department_id):
    dep = db.session.get(Department, department_id)
    if not dep:
        flash("Department not found.", "danger")
        return redirect(url_for("admin.departments"))

    form = DepartmentCreateForm(obj=dep)
    if form.validate_on_submit():
        dep.name = form.name.data.strip()
        dep.code = form.code.data.strip().upper()
        db.session.commit()
        flash("Department updated successfully.", "success")
        return redirect(url_for("admin.departments"))

    return render_template("admin/create_department.html", form=form, edit_mode=True, department=dep)


@admin_bp.route("/departments/<int:department_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_department(department_id):
    dep = db.session.get(Department, department_id)
    if not dep:
        flash("Department not found.", "danger")
        return redirect(url_for("admin.departments"))

    db.session.delete(dep)
    db.session.commit()
    flash("Department deleted successfully.", "success")
    return redirect(url_for("admin.departments"))


# --- COURSE EDIT & DELETE ---
@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("admin.courses"))

    form = CourseCreateForm(obj=course)
    form.department_id.choices = _department_choices()
    if form.validate_on_submit():
        course.name = form.name.data.strip()
        course.code = form.code.data.strip().upper()
        course.department_id = form.department_id.data
        db.session.commit()
        flash("Course updated successfully.", "success")
        return redirect(url_for("admin.courses"))

    return render_template("admin/create_course.html", form=form, edit_mode=True, course=course)


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("admin.courses"))

    db.session.delete(course)
    db.session.commit()
    flash("Course deleted successfully.", "success")
    return redirect(url_for("admin.courses"))


# --- SUBJECT EDIT & DELETE ---
@admin_bp.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_subject(subject_id):
    subject = db.session.get(Subject, subject_id)
    if not subject:
        flash("Subject not found.", "danger")
        return redirect(url_for("admin.subjects"))

    form = SubjectCreateForm(obj=subject)
    form.course_id.choices = _course_choices()
    if form.validate_on_submit():
        subject.name = form.name.data.strip()
        subject.code = form.code.data.strip().upper()
        subject.course_id = form.course_id.data
        db.session.commit()
        flash("Subject updated successfully.", "success")
        return redirect(url_for("admin.subjects"))

    return render_template("admin/create_subject.html", form=form, edit_mode=True, subject=subject)


@admin_bp.route("/subjects/<int:subject_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_subject(subject_id):
    subject = db.session.get(Subject, subject_id)
    if not subject:
        flash("Subject not found.", "danger")
        return redirect(url_for("admin.subjects"))

    db.session.delete(subject)
    db.session.commit()
    flash("Subject deleted successfully.", "success")
    return redirect(url_for("admin.subjects"))


# --- CLASS EDIT & DELETE ---
@admin_bp.route("/classes/<int:class_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_class(class_id):
    class_room = db.session.get(ClassRoom, class_id)
    if not class_room:
        flash("Class not found.", "danger")
        return redirect(url_for("admin.classes"))

    form = ClassCreateForm(obj=class_room)
    form.course_id.choices = _course_choices()
    if form.validate_on_submit():
        class_room.name = form.name.data.strip()
        class_room.course_id = form.course_id.data
        class_room.semester = form.semester.data
        class_room.section = form.section.data.strip() or None
        db.session.commit()
        flash("Class updated successfully.", "success")
        return redirect(url_for("admin.classes"))

    return render_template("admin/create_class.html", form=form, edit_mode=True, class_room=class_room)


@admin_bp.route("/classes/<int:class_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_class(class_id):
    class_room = db.session.get(ClassRoom, class_id)
    if not class_room:
        flash("Class not found.", "danger")
        return redirect(url_for("admin.classes"))

    # Safely delete dependent child records
    from app.models import TimetableOverride, TimetableEntry, AttendanceSession, Attendance

    TimetableOverride.query.filter_by(class_id=class_id).delete(synchronize_session=False)
    TimetableEntry.query.filter_by(class_id=class_id).delete(synchronize_session=False)

    sessions = AttendanceSession.query.filter_by(class_id=class_id).all()
    session_ids = [s.id for s in sessions]
    if session_ids:
        Attendance.query.filter(Attendance.session_id.in_(session_ids)).delete(synchronize_session=False)
        AttendanceSession.query.filter(AttendanceSession.id.in_(session_ids)).delete(synchronize_session=False)

    db.session.delete(class_room)
    db.session.commit()
    flash("Class deleted successfully.", "success")
    return redirect(url_for("admin.classes"))
