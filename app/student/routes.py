from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, url_for, request, jsonify, current_app
from flask_login import current_user, login_required

from app import db
from app.models import Attendance, AttendanceSession, LeaveRequest
from app.models import Attendance, AttendanceSession, LeaveRequest, FaceEncoding
from app.services.face_service import (
    FaceRecognitionUnavailable,
    upload_and_train_student_face,
    save_dataset_image_bytes,
    finalize_student_dataset,
)
from app import csrf
from pathlib import Path
import base64
from app.services.qr_service import generate_student_qr_data_uri, verify_qr_session_token
from app.security import roles_required
from app.student.forms import FaceUploadForm, LeaveRequestForm

student_bp = Blueprint("student", __name__)


@student_bp.route("/id-card")
@login_required
@roles_required("student", "admin")
def id_card():
    student = current_user.student_profile
    if not student:
        flash("Student profile is missing. Contact admin.", "danger")
        return redirect(url_for("student.dashboard"))
    qr_uri = generate_student_qr_data_uri(student)
    return render_template("student/id_card.html", student=student, qr_uri=qr_uri)


@student_bp.route("/dashboard")
@login_required
@roles_required("student", "admin")
def dashboard():
    student = current_user.student_profile
    leave_count = LeaveRequest.query.filter_by(student_id=student.id).count() if student else 0
    enc_count = 0
    last_registered = None
    show_onboarding_modal = False
    qr_uri = None
    if student:
        from app.services.qr_service import generate_student_qr_data_uri
        qr_uri = generate_student_qr_data_uri(student)
        enc_count = student.face_encodings.count()
        last = student.face_encodings.order_by(FaceEncoding.created_at.desc()).first()
        if last:
            last_registered = last.created_at
        if not student.is_profile_completed:
            show_onboarding_modal = True

    return render_template(
        "student/dashboard.html",
        leave_count=leave_count,
        face_count=enc_count,
        last_registered=last_registered,
        show_onboarding_modal=show_onboarding_modal,
        student=student,
        qr_uri=qr_uri,
    )


@student_bp.route("/profile", methods=["GET", "POST"])
@login_required
@roles_required("student", "admin")
def profile():
    student = current_user.student_profile
    if not student:
        flash("Student profile is missing. Contact admin.", "danger")
        return redirect(url_for("student.dashboard"))

    from app.services.barcode_service import generate_code128_data_uri
    from app.models import Subject, TimetableEntry, ClassRoom

    # Handle Profile Update (Idea 4 + Photo Upload)
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", current_user.first_name).strip()
        current_user.last_name = request.form.get("last_name", current_user.last_name).strip()
        student.phone_number = request.form.get("phone_number", "").strip() or None
        student.blood_group = request.form.get("blood_group", "").strip() or None
        student.address = request.form.get("address", "").strip() or None
        student.guardian_name = request.form.get("guardian_name", "").strip() or None
        student.guardian_phone = request.form.get("guardian_phone", "").strip() or None
        student.emergency_contact = request.form.get("emergency_contact", "").strip() or None

        # Process Photo File Upload
        photo_file = request.files.get("profile_photo")
        if photo_file and photo_file.filename:
            from pathlib import Path
            upload_dir = Path(current_app.root_path) / "static" / "uploads" / "profile_photos"
            upload_dir.mkdir(parents=True, exist_ok=True)
            ext = photo_file.filename.rsplit(".", 1)[-1].lower() if "." in photo_file.filename else "jpg"
            filename = f"student_{student.id}.{ext}"
            filepath = upload_dir / filename
            photo_file.save(str(filepath))
            student.profile_photo = f"uploads/profile_photos/{filename}"

        student.is_profile_completed = True
        db.session.commit()
        flash("Profile information saved successfully!", "success")
        return redirect(url_for("student.profile"))

    # 1. Digital ID Card Data (Idea 1)
    qr_uri = generate_student_qr_data_uri(student)
    barcode_uri = generate_code128_data_uri(student.roll_number or f"STU-{student.id}")

    # 2. Academic Attendance Meter & Subject Breakdown (Idea 3)
    attendances = Attendance.query.filter_by(student_id=student.id).all()
    total_attended = len([a for a in attendances if a.attendance_status == 'present'])
    
    student_class_id = getattr(student, "class_id", None)
    if not student_class_id and student.course_id:
        c_cls = ClassRoom.query.filter_by(course_id=student.course_id).first()
        if c_cls:
            student_class_id = c_cls.id

    total_sessions = 0
    if student_class_id:
        total_sessions = AttendanceSession.query.filter_by(class_id=student_class_id).count()
    if total_sessions == 0:
        total_sessions = max(total_attended, 1)

    overall_pct = round((total_attended / total_sessions) * 100, 1)

    # Subject-wise attendance calculation
    subjects_list = []
    if student.course_id:
        course_subjects = Subject.query.filter_by(course_id=student.course_id).all()
        for sb in course_subjects:
            sb_sessions = AttendanceSession.query.filter_by(class_id=student_class_id, subject_id=sb.id).count() if student_class_id else 0
            sb_attended = len([a for a in attendances if a.session and a.session.subject_id == sb.id and a.attendance_status == 'present'])
            sb_pct = round((sb_attended / sb_sessions * 100), 1) if sb_sessions > 0 else 100.0
            subjects_list.append({
                "name": sb.name,
                "code": sb.code,
                "attended": sb_attended,
                "total": sb_sessions,
                "pct": sb_pct,
                "is_low": (sb_pct < 75.0)
            })

    # 3. Leave Requests & Recent Activity Timeline (Idea 5)
    recent_leaves = LeaveRequest.query.filter_by(student_id=student.id).order_by(LeaveRequest.created_at.desc()).limit(5).all()
    recent_attendances = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.marked_at.desc()).limit(5).all()

    return render_template(
        "student/profile.html",
        student=student,
        qr_uri=qr_uri,
        barcode_uri=barcode_uri,
        total_attended=total_attended,
        total_sessions=total_sessions,
        overall_pct=overall_pct,
        subjects_list=subjects_list,
        recent_leaves=recent_leaves,
        recent_attendances=recent_attendances,
    )


@student_bp.route("/face", methods=["GET", "POST"])
@login_required
@roles_required("student", "admin")
def face_profile():
    form = FaceUploadForm()
    student = current_user.student_profile
    if not student:
        flash("Student profile is missing. Contact admin.", "danger")
        return redirect(url_for("student.dashboard"))

    if form.validate_on_submit():
        try:
            upload_and_train_student_face(student, form.face_image.data)
            flash("Face image trained successfully.", "success")
            return redirect(url_for("student.face_profile"))
        except FaceRecognitionUnavailable as exc:
            flash(str(exc), "warning")
        except ValueError as exc:
            flash(str(exc), "danger")

    encodings = student.face_encodings.order_by().all()
    return render_template("student/face_profile.html", form=form, encodings=encodings)


@student_bp.route('/face/capture', methods=['POST'])
@login_required
@roles_required('student')
@csrf.exempt
def face_capture():
    data = {}
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict() if request.form else {}

    img_data = data.get('image') or data.get('img') or data.get('imageData') or data.get('file')
    file_obj = request.files.get('image') or request.files.get('file') or request.files.get('photo')

    image_bytes = None
    if file_obj:
        image_bytes = file_obj.read()
    elif img_data and isinstance(img_data, str) and img_data.strip():
        img_b64 = img_data.split(',', 1)[1] if ',' in img_data else img_data
        try:
            image_bytes = base64.b64decode(img_b64)
        except Exception:
            return jsonify({'error': 'Invalid image data.'}), 400
    elif isinstance(data.get('images'), list) and data['images']:
        first = data['images'][0]
        if isinstance(first, str):
            img_b64 = first.split(',', 1)[1] if ',' in first else first
            try:
                image_bytes = base64.b64decode(img_b64)
            except Exception:
                return jsonify({'error': 'Invalid image data.'}), 400

    if not image_bytes:
        return jsonify({'error': 'No image provided.'}), 400

    student = current_user.student_profile
    if not student:
        return jsonify({'error': 'Student profile missing.'}), 400

    try:
        path = save_dataset_image_bytes(student, image_bytes)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception('Failed saving dataset image')
        return jsonify({'error': 'Failed to save image.'}), 500

    # count images remaining
    base_dir = Path(current_app.root_path).parent / current_app.config['FACE_DATASET_FOLDER']
    student_dir = base_dir / f"student_{student.id}"
    count = 0
    if student_dir.exists():
        count = len([p for p in student_dir.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png')])

    return jsonify({'saved': True, 'path': str(path), 'count': count})


@student_bp.route('/face/finalize', methods=['POST'])
@login_required
@roles_required('student')
@csrf.exempt
def face_finalize():
    student = current_user.student_profile
    if not student:
        return jsonify({'error': 'Student profile missing.'}), 400
    try:
        result = finalize_student_dataset(student)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception('Finalize dataset failed')
        return jsonify({'error': 'Finalize failed.'}), 500
    return jsonify(result)


@student_bp.route("/leaves", methods=["GET", "POST"])
@login_required
@roles_required("student", "admin")
def leave_requests():
    student = current_user.student_profile
    if not student:
        flash("Student profile is missing. Contact admin.", "danger")
        return redirect(url_for("student.dashboard"))

    form = LeaveRequestForm()
    if form.validate_on_submit():
        if form.ends_on.data < form.starts_on.data:
            flash("End date start date karta pehla nathi hoi shakti.", "danger")
        else:
            leave = LeaveRequest(
                student_id=student.id,
                starts_on=form.starts_on.data,
                ends_on=form.ends_on.data,
                reason=form.reason.data.strip(),
                decision="pending",
            )
            db.session.add(leave)
            db.session.commit()
            flash("Leave request submit thai gai.", "success")
            return redirect(url_for("student.leave_requests"))

    records = LeaveRequest.query.filter_by(student_id=student.id).order_by(LeaveRequest.created_at.desc()).all()
    recent_attendances = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.marked_at.desc()).limit(5).all()
    return render_template("student/leaves.html", form=form, leaves=records, recent_attendances=recent_attendances)


def _now_utc_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@student_bp.route("/attendance/qr/<token>")
@login_required
@roles_required("student")
def mark_qr_attendance(token):
    student = current_user.student_profile
    if not student:
        flash("Student profile missing chhe. Admin ne contact karo.", "danger")
        return redirect(url_for("student.dashboard"))

    session_id = verify_qr_session_token(token)
    if not session_id:
        flash("QR code invalid athva expire thai gayo chhe.", "danger")
        return redirect(url_for("student.dashboard"))

    session = db.session.get(AttendanceSession, session_id)
    if not session or session.method != "qr":
        flash("Aa QR attendance session valid nathi.", "danger")
        return redirect(url_for("student.dashboard"))

    now = _now_utc_naive()
    starts_at = session.starts_at.replace(tzinfo=None) if session.starts_at and session.starts_at.tzinfo else session.starts_at
    ends_at = session.ends_at.replace(tzinfo=None) if session.ends_at and session.ends_at.tzinfo else session.ends_at
    if starts_at and starts_at > now:
        flash("QR attendance session haju start nathi thayu.", "warning")
        return redirect(url_for("student.dashboard"))
    if ends_at and ends_at < now:
        flash("QR attendance session stop thai gayu chhe.", "warning")
        return redirect(url_for("student.dashboard"))

    if student.course_id and session.classroom and student.course_id != session.classroom.course_id:
        flash("Aa QR tamara class/course mate nathi.", "danger")
        return redirect(url_for("student.dashboard"))

    existing = Attendance.query.filter_by(session_id=session.id, student_id=student.id).first()
    if existing:
        flash("Tamari attendance pehlethi mark thai gai chhe.", "info")
        return redirect(url_for("student.dashboard"))

    attendance = Attendance(
        student_id=student.id,
        session_id=session.id,
        marked_at=now,
        attendance_status="present",
        confidence_score=None,
    )
    db.session.add(attendance)
    db.session.commit()
    flash("QR scan thi attendance successfully mark thai gai.", "success")
    return redirect(url_for("student.dashboard"))
