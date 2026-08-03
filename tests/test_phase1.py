from datetime import datetime, timezone

from app import create_app, db
from app.models import Attendance, AttendanceSession, ClassRoom, Course, Department, LeaveRequest, Professor, Role, Student, Subject, TimeSlot, TimetableEntry, User


def build_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        admin_role = Role(name="admin", description="Admin")
        professor_role = Role(name="professor", description="Professor")
        student_role = Role(name="student", description="Student")
        db.session.add_all([admin_role, professor_role, student_role])
        user = User(
            email="admin@example.com",
            first_name="System",
            last_name="Admin",
            role=admin_role,
        )
        user.set_password("Admin@12345")
        db.session.add(user)
        db.session.commit()
    return app


def test_index_loads():
    app = build_app()
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"AI Attendance Management System" in response.data


def test_non_localhost_requests_return_forbidden():
    app = build_app()
    client = app.test_client()
    response = client.get("/", headers={"Host": "example.com"})
    assert response.status_code == 403


def test_localhost_host_is_allowed():
    app = build_app()
    client = app.test_client()
    response = client.get("/", headers={"Host": "localhost:5005"})
    assert response.status_code == 200


def test_admin_login_redirects_to_dashboard():
    app = build_app()
    client = app.test_client()
    response = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "Admin@12345"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Institution dashboard" in response.data


def test_admin_can_create_student():
    app = build_app()
    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "Admin@12345"},
        follow_redirects=True,
    )
    response = client.post(
        "/admin/students/new",
        data={
            "first_name": "Demo",
            "last_name": "Student",
            "email": "student@example.com",
            "roll_number": "STU001",
            "gender": "female",
            "password": "Student@12345",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="student@example.com").first() is not None
        assert Student.query.filter_by(roll_number="STU001").first() is not None


def test_student_can_open_face_profile():
    app = build_app()
    with app.app_context():
        student_role = Role.query.filter_by(name="student").first()
        user = User(
            email="student@example.com",
            first_name="Demo",
            last_name="Student",
            role=student_role,
        )
        user.set_password("Student@12345")
        db.session.add(Student(user=user, roll_number="STU001"))
        db.session.commit()

    client = app.test_client()
    response = client.post(
        "/login",
        data={"email": "student@example.com", "password": "Student@12345"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Student Dashboard" in response.data

    face_response = client.get("/student/face")
    assert face_response.status_code == 200
    assert b"Face profile" in face_response.data


def test_admin_can_create_professor():
    app = build_app()
    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "Admin@12345"},
        follow_redirects=True,
    )
    response = client.post(
        "/admin/professors/new",
        data={
            "first_name": "Demo",
            "last_name": "Professor",
            "email": "professor@example.com",
            "employee_code": "FAC001",
            "password": "Professor@12345",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="professor@example.com").first() is not None
        assert Professor.query.filter_by(employee_code="FAC001").first() is not None


def test_admin_can_create_academic_setup_chain():
    app = build_app()
    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "Admin@12345"},
        follow_redirects=True,
    )

    department_response = client.post(
        "/admin/departments/new",
        data={"name": "Computer Science", "code": "CS"},
        follow_redirects=True,
    )
    assert department_response.status_code == 200

    with app.app_context():
        department = Department.query.filter_by(code="CS").first()
        assert department is not None
        department_id = department.id

    course_response = client.post(
        "/admin/courses/new",
        data={"name": "BSc Computer Science", "code": "BSC-CS", "department_id": department_id},
        follow_redirects=True,
    )
    assert course_response.status_code == 200

    with app.app_context():
        course = Course.query.filter_by(code="BSC-CS").first()
        assert course is not None
        course_id = course.id

    subject_response = client.post(
        "/admin/subjects/new",
        data={"name": "Machine Learning", "code": "ML101", "course_id": course_id},
        follow_redirects=True,
    )
    assert subject_response.status_code == 200

    class_response = client.post(
        "/admin/classes/new",
        data={"name": "BSc CS Semester 1 A", "course_id": course_id, "semester": 1, "section": "A"},
        follow_redirects=True,
    )
    assert class_response.status_code == 200

    with app.app_context():
        assert Subject.query.filter_by(code="ML101").first() is not None
        assert ClassRoom.query.filter_by(name="BSc CS Semester 1 A").first() is not None


def test_professor_dashboard_shows_face_attendance_link():
    app = build_app()
    with app.app_context():
        professor_role = Role.query.filter_by(name="professor").first()
        professor_user = User(
            email="professor_nav@example.com",
            first_name="Nav",
            last_name="Professor",
            role=professor_role,
        )
        professor_user.set_password("Professor@12345")
        professor = Professor(user=professor_user, employee_code="FAC_NAV")
        db.session.add_all([professor_user, professor])
        db.session.commit()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "professor_nav@example.com", "password": "Professor@12345"},
        follow_redirects=True,
    )
    response = client.get("/professor/dashboard")
    assert response.status_code == 200
    assert b"Face Attendance" in response.data


def test_professor_face_attendance_marks_student(monkeypatch):
    app = build_app()
    with app.app_context():
        department = Department(name="Computer Science", code="CS")
        course = Course(name="BSc Computer Science", code="BSC-CS", department=department)
        subject = Subject(name="Machine Learning", code="ML101", course=course)
        class_room = ClassRoom(name="BSc CS Semester 1 A", course=course, semester=1, section="A")
        professor_role = Role.query.filter_by(name="professor").first()
        student_role = Role.query.filter_by(name="student").first()
        professor_user = User(
            email="professor@example.com",
            first_name="Demo",
            last_name="Professor",
            role=professor_role,
        )
        professor_user.set_password("Professor@12345")
        student_user = User(
            email="student@example.com",
            first_name="Demo",
            last_name="Student",
            role=student_role,
        )
        student_user.set_password("Student@12345")
        professor = Professor(user=professor_user, employee_code="FAC001")
        student = Student(user=student_user, roll_number="STU001", course=course)
        db.session.add_all([department, course, subject, class_room, professor, student])
        db.session.commit()
        subject_id = subject.id
        class_id = class_room.id
        student_id = student.id

    def fake_recognize(image_bytes, tolerance=0.6, known=None):
        return {"student_id": student_id, "confidence": 0.92, "encoding_path": "fake.npy"}

    monkeypatch.setattr("app.professor.routes.recognize_face_from_image_bytes", fake_recognize)
    monkeypatch.setattr("app.professor.routes.preload_known_encodings_for_session", lambda *args, **kwargs: [])

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "professor@example.com", "password": "Professor@12345"},
        follow_redirects=True,
    )
    start_response = client.post(
        "/professor/session/start",
        json={"method": "face", "class_id": class_id, "subject_id": subject_id},
    )
    assert start_response.status_code == 200
    session_id = start_response.get_json()["session_id"]

    face_response = client.post(
        "/professor/attendance/face",
        json={"image": "data:image/jpeg;base64,ZmFrZQ==", "session_id": session_id},
    )
    assert face_response.status_code == 200
    payload = face_response.get_json()
    assert payload["recognized"] is True
    assert payload["persisted"] is True
    assert payload["attendance_status"] == "present"

    duplicate_response = client.post(
        "/professor/attendance/face",
        json={"image": "data:image/jpeg;base64,ZmFrZQ==", "session_id": session_id},
    )
    assert duplicate_response.get_json()["duplicate"] is True

    with app.app_context():
        assert Attendance.query.filter_by(session_id=session_id, student_id=student_id).count() == 1


def test_professor_face_attendance_requires_active_session(monkeypatch):
    app = build_app()
    with app.app_context():
        professor_role = Role.query.filter_by(name="professor").first()
        professor_user = User(
            email="professor_required@example.com",
            first_name="Demo",
            last_name="Professor",
            role=professor_role,
        )
        professor_user.set_password("Professor@12345")
        professor = Professor(user=professor_user, employee_code="FAC_REQUIRED")
        db.session.add(professor)
        db.session.commit()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "professor_required@example.com", "password": "Professor@12345"},
        follow_redirects=True,
    )

    response = client.post(
        "/professor/attendance/face",
        json={"image": "data:image/jpeg;base64,ZmFrZQ=="},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Start a session before marking attendance."


def test_qr_attendance_session_marks_student_once():
    app = build_app()
    with app.app_context():
        department = Department(name="Computer Science", code="CS")
        course = Course(name="BSc Computer Science", code="BSC-CS", department=department)
        subject = Subject(name="Machine Learning", code="ML101", course=course)
        class_room = ClassRoom(name="BSc CS Semester 1 A", course=course, semester=1, section="A")
        professor_role = Role.query.filter_by(name="professor").first()
        student_role = Role.query.filter_by(name="student").first()
        professor_user = User(
            email="qr_professor@example.com",
            first_name="QR",
            last_name="Professor",
            role=professor_role,
        )
        professor_user.set_password("Professor@12345")
        student_user = User(
            email="qr_student@example.com",
            first_name="QR",
            last_name="Student",
            role=student_role,
        )
        student_user.set_password("Student@12345")
        professor = Professor(user=professor_user, employee_code="FAC_QR")
        student = Student(user=student_user, roll_number="QR001", course=course)
        db.session.add_all([department, course, subject, class_room, professor, student])
        db.session.commit()
        subject_id = subject.id
        class_id = class_room.id
        student_id = student.id

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "qr_professor@example.com", "password": "Professor@12345"},
        follow_redirects=True,
    )
    start_response = client.post(
        "/professor/session/start",
        json={"method": "qr", "class_id": class_id, "subject_id": subject_id},
    )
    assert start_response.status_code == 200
    payload = start_response.get_json()
    assert payload["session_id"]
    assert payload["qr_url"]
    assert payload["qr_image"].startswith("data:image/png;base64,")

    client.get("/logout", follow_redirects=True)
    client.post(
        "/login",
        data={"email": "qr_student@example.com", "password": "Student@12345"},
        follow_redirects=True,
    )
    mark_response = client.get(payload["qr_url"], follow_redirects=True)
    assert mark_response.status_code == 200
    assert b"attendance successfully mark" in mark_response.data

    duplicate_response = client.get(payload["qr_url"], follow_redirects=True)
    assert duplicate_response.status_code == 200
    assert b"pehlethi mark" in duplicate_response.data

    with app.app_context():
        assert Attendance.query.filter_by(session_id=payload["session_id"], student_id=student_id).count() == 1


def test_professor_analytics_shows_real_attendance_data():
    app = build_app()
    with app.app_context():
        department = Department(name="Computer Science", code="CS")
        course = Course(name="BSc Computer Science", code="BSC-CS", department=department)
        subject = Subject(name="Machine Learning", code="ML101", course=course)
        class_room = ClassRoom(name="BSc CS Semester 1 A", course=course, semester=1, section="A")
        professor_role = Role.query.filter_by(name="professor").first()
        student_role = Role.query.filter_by(name="student").first()
        professor_user = User(
            email="analytics_professor@example.com",
            first_name="Analytics",
            last_name="Professor",
            role=professor_role,
        )
        professor_user.set_password("Professor@12345")
        student_user = User(
            email="analytics_student@example.com",
            first_name="Analytics",
            last_name="Student",
            role=student_role,
        )
        student_user.set_password("Student@12345")
        professor = Professor(user=professor_user, employee_code="FAC_ANALYTICS")
        student = Student(user=student_user, roll_number="AN001", course=course)
        session = AttendanceSession(
            method="qr",
            starts_at=datetime(2026, 8, 10, 9, 0),
            subject=subject,
            professor=professor,
            classroom=class_room,
        )
        db.session.add_all([department, course, subject, class_room, professor, student, session])
        db.session.commit()
        db.session.add(
            Attendance(
                student_id=student.id,
                session_id=session.id,
                marked_at=datetime(2026, 8, 10, 9, 2),
                attendance_status="present",
            )
        )
        db.session.commit()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "analytics_professor@example.com", "password": "Professor@12345"},
        follow_redirects=True,
    )
    page_response = client.get("/professor/analytics?start_date=2026-08-01&end_date=2026-08-31")
    assert page_response.status_code == 200
    assert b"Automated summary" in page_response.data
    assert b"Attendance rate" in page_response.data
    assert b"Analytics Student" in page_response.data

    pdf_response = client.get("/professor/analytics/export.pdf?start_date=2026-08-01&end_date=2026-08-31")
    assert pdf_response.status_code == 200
    assert pdf_response.content_type == "application/pdf"


def test_student_can_submit_leave_and_professor_can_approve():
    app = build_app()
    with app.app_context():
        professor_role = Role.query.filter_by(name="professor").first()
        student_role = Role.query.filter_by(name="student").first()
        professor_user = User(
            email="leave_professor@example.com",
            first_name="Leave",
            last_name="Professor",
            role=professor_role,
        )
        professor_user.set_password("Professor@12345")
        student_user = User(
            email="leave_student@example.com",
            first_name="Leave",
            last_name="Student",
            role=student_role,
        )
        student_user.set_password("Student@12345")
        professor = Professor(user=professor_user, employee_code="FAC_LEAVE")
        student = Student(user=student_user, roll_number="LEAVE001")
        db.session.add_all([professor, student])
        db.session.commit()
        student_id = student.id

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "leave_student@example.com", "password": "Student@12345"},
        follow_redirects=True,
    )
    submit_response = client.post(
        "/student/leaves",
        data={"starts_on": "2026-08-01", "ends_on": "2026-08-02", "reason": "Medical appointment"},
        follow_redirects=True,
    )
    assert submit_response.status_code == 200
    assert b"Leave request submit" in submit_response.data

    with app.app_context():
        leave = LeaveRequest.query.filter_by(student_id=student_id).first()
        assert leave is not None
        assert leave.decision == "pending"
        leave_id = leave.id

    client.get("/logout", follow_redirects=True)
    client.post(
        "/login",
        data={"email": "leave_professor@example.com", "password": "Professor@12345"},
        follow_redirects=True,
    )
    approve_response = client.post(f"/professor/leaves/{leave_id}/approved", follow_redirects=True)
    assert approve_response.status_code == 200
    assert b"Leave request approved" in approve_response.data

    with app.app_context():
        assert db.session.get(LeaveRequest, leave_id).decision == "approved"


def test_admin_can_view_leave_records():
    app = build_app()
    with app.app_context():
        student_role = Role.query.filter_by(name="student").first()
        student_user = User(
            email="admin_leave_student@example.com",
            first_name="Admin",
            last_name="LeaveStudent",
            role=student_role,
        )
        student_user.set_password("Student@12345")
        student = Student(user=student_user, roll_number="ADMINLEAVE001")
        db.session.add(student)
        db.session.commit()
        db.session.add(
            LeaveRequest(
                student_id=student.id,
                starts_on=datetime(2026, 8, 5).date(),
                ends_on=datetime(2026, 8, 6).date(),
                reason="Family function",
            )
        )
        db.session.commit()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "Admin@12345"},
        follow_redirects=True,
    )
    response = client.get("/admin/leaves")
    assert response.status_code == 200
    assert b"Leave management" in response.data
    assert b"Family function" in response.data


def test_professor_session_start_requires_class_and_subject(monkeypatch):
    app = build_app()
    with app.app_context():
        professor_role = Role.query.filter_by(name="professor").first()
        professor_user = User(
            email="professor2@example.com",
            first_name="Demo",
            last_name="Professor",
            role=professor_role,
        )
        professor_user.set_password("Professor@12345")
        professor = Professor(user=professor_user, employee_code="FAC002")
        db.session.add(professor)
        db.session.commit()

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "professor2@example.com", "password": "Professor@12345"},
        follow_redirects=True,
    )

    missing_class = client.post(
        "/professor/session/start",
        json={"method": "face", "subject_id": 1},
    )
    assert missing_class.status_code == 400
    assert missing_class.get_json()["error"] == "class_id required"

    missing_subject = client.post(
        "/professor/session/start",
        json={"method": "face", "class_id": 1},
    )
    assert missing_subject.status_code == 400
    assert missing_subject.get_json()["error"] == "subject_id required"


def test_professor_cannot_stop_other_professor_session(monkeypatch):
    app = build_app()
    with app.app_context():
        professor_role = Role.query.filter_by(name="professor").first()
        professor_user1 = User(
            email="prof1@example.com",
            first_name="Demo",
            last_name="Professor",
            role=professor_role,
        )
        professor_user1.set_password("Professor@12345")
        professor1 = Professor(user=professor_user1, employee_code="FAC003")

        professor_user2 = User(
            email="prof2@example.com",
            first_name="Demo",
            last_name="Professor",
            role=professor_role,
        )
        professor_user2.set_password("Professor@12345")
        professor2 = Professor(user=professor_user2, employee_code="FAC004")

        department = Department(name="Computer Science", code="CS")
        course = Course(name="BSc Computer Science", code="BSC-CS", department=department)
        subject = Subject(name="Machine Learning", code="ML101", course=course)
        class_room = ClassRoom(name="BSc CS Semester 1 A", course=course, semester=1, section="A")
        db.session.add_all([department, course, subject, class_room, professor1, professor2])
        db.session.commit()
        session = AttendanceSession(
            method="face",
            starts_at=datetime.now(timezone.utc),
            subject=subject,
            professor=professor1,
            class_id=class_room.id,
        )
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    client = app.test_client()
    client.post(
        "/login",
        data={"email": "prof2@example.com", "password": "Professor@12345"},
        follow_redirects=True,
    )

    stop_response = client.post(
        "/professor/session/stop",
        json={"session_id": session_id},
    )
    assert stop_response.status_code == 404
    assert stop_response.get_json()["error"] == "session not found or unauthorized"


def test_timetable_view_accessible_by_student():
    app = build_app()
    client = app.test_client()
    with app.app_context():
        s_role = Role.query.filter_by(name="student").first()
        u = User.query.filter_by(email="student_test@example.com").first()
        if not u:
            u = User(email="student_test@example.com", first_name="Stud", last_name="Test", role=s_role)
            u.set_password("Student@1123")
            db.session.add(u)
            db.session.commit()

    client.post("/login", data={"email": "student_test@example.com", "password": "Student@1123"}, follow_redirects=True)
    res = client.get("/timetable")
    assert res.status_code == 200
    assert b"Class Timetable Schedule" in res.data


def test_timetable_view_accessible_by_professor():
    app = build_app()
    client = app.test_client()
    with app.app_context():
        p_role = Role.query.filter_by(name="professor").first()
        u = User.query.filter_by(email="prof_test@example.com").first()
        if not u:
            u = User(email="prof_test@example.com", first_name="Prof", last_name="Test", role=p_role)
            u.set_password("Professor@1123")
            db.session.add(u)
            db.session.commit()

    client.post("/login", data={"email": "prof_test@example.com", "password": "Professor@1123"}, follow_redirects=True)
    res = client.get("/timetable")
    assert res.status_code == 200
    assert b"Class Timetable Schedule" in res.data


def test_timetable_view_accessible_by_admin():
    app = build_app()
    client = app.test_client()
    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    res = client.get("/timetable")
    assert res.status_code == 200
    assert b"Timetable Builder" in res.data


def test_admin_builder_view():
    app = build_app()
    client = app.test_client()
    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    res = client.get("/admin/timetable/builder")
    assert res.status_code == 200
    assert b"Timetable Builder & AI Auto-Scheduler" in res.data


def test_admin_save_and_delete_entry():
    import json
    app = build_app()
    client = app.test_client()
    with app.app_context():
        cls = ClassRoom.query.first() or ClassRoom(name="BCA-5(A)", semester=5, section="A")
        if not cls.id:
            crs = Course.query.first() or Course(name="BCA", code="BCA", department_id=1)
            db.session.add(crs)
            db.session.commit()
            cls.course_id = crs.id
            db.session.add(cls)
            db.session.commit()

        sb = Subject.query.first() or Subject(name="J2EE", code="J2EE", course_id=cls.course_id)
        if not sb.id:
            db.session.add(sb)
            db.session.commit()

        pr = Professor.query.first()
        if not pr:
            p_role = Role.query.filter_by(name="professor").first()
            pu = User(email="prof_auto@example.com", first_name="Prof", last_name="Auto", role=p_role)
            pu.set_password("Professor@1123")
            db.session.add(pu)
            db.session.commit()
            pr = Professor(employee_code="FAC-AUTO", user_id=pu.id, department_id=1)
            db.session.add(pr)
            db.session.commit()

        ts = TimeSlot.query.first() or TimeSlot(id=1, slot_name="8:00 TO 8:45", start_time="08:00", end_time="08:45", is_recess=False)
        if not ts.id:
            db.session.add(ts)
            db.session.commit()

        cid = cls.id
        sid = sb.id
        pid = pr.id
        tid = ts.id

    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    r1 = client.post(
        "/admin/timetable/entry/save",
        data=json.dumps({
            "class_id": cid,
            "day_of_week": "TUE",
            "time_slot_id": tid,
            "subject_id": sid,
            "professor_id": pid,
            "room_number": "Room 999",
            "is_lab": False,
        }),
        content_type="application/json",
    )
    assert r1.status_code == 200
    assert r1.get_json().get("success") is True

    r2 = client.post(
        "/admin/timetable/entry/delete",
        data=json.dumps({"class_id": cid, "day_of_week": "TUE", "time_slot_id": tid}),
        content_type="application/json",
    )
    assert r2.status_code == 200
    assert r2.get_json().get("success") is True


def test_admin_auto_generate_timetable():
    import json
    app = build_app()
    client = app.test_client()
    with app.app_context():
        cls = ClassRoom.query.first() or ClassRoom(name="BCA-5(A)", semester=5, section="A")
        if not cls.id:
            crs = Course.query.first() or Course(name="BCA", code="BCA", department_id=1)
            db.session.add(crs)
            db.session.commit()
            cls.course_id = crs.id
            db.session.add(cls)
            db.session.commit()

        sb = Subject.query.first() or Subject(name="J2EE", code="J2EE", course_id=cls.course_id)
        if not sb.id:
            db.session.add(sb)
            db.session.commit()

        pr = Professor.query.first()
        if not pr:
            p_role = Role.query.filter_by(name="professor").first()
            pu = User(email="prof_auto@example.com", first_name="Prof", last_name="Auto", role=p_role)
            pu.set_password("Professor@1123")
            db.session.add(pu)
            db.session.commit()
            pr = Professor(employee_code="FAC-AUTO", user_id=pu.id, department_id=1)
            db.session.add(pr)
            db.session.commit()

        ts = TimeSlot.query.filter_by(is_recess=False).first()
        if not ts:
            ts = TimeSlot(slot_name="8:00 TO 8:45", start_time="08:00", end_time="08:45", is_recess=False)
            db.session.add(ts)
            db.session.commit()

        cid = cls.id

    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    r = client.post(
        "/admin/timetable/generate",
        data=json.dumps({"class_id": cid}),
        content_type="application/json",
    )
    assert r.status_code == 200
    res_data = r.get_json()
    assert res_data.get("success") is True
    assert res_data.get("generated_entries") > 0


def test_free_professors_endpoint():
    app = build_app()
    client = app.test_client()
    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    res = client.get("/admin/timetable/free-professors?day_of_week=MON&time_slot_id=1")
    assert res.status_code == 200
    data = res.get_json()
    assert "free_professors" in data


def test_save_and_delete_timetable_override():
    import json
    from datetime import datetime
    app = build_app()
    client = app.test_client()
    with app.app_context():
        cls = ClassRoom.query.first() or ClassRoom(name="BCA-5(A)", semester=5, section="A")
        if not cls.id:
            crs = Course.query.first() or Course(name="BCA", code="BCA", department_id=1)
            db.session.add(crs)
            db.session.commit()
            cls.course_id = crs.id
            db.session.add(cls)
            db.session.commit()

        ts = TimeSlot.query.first() or TimeSlot(id=1, slot_name="8:00 TO 8:45", start_time="08:00", end_time="08:45", is_recess=False)
        if not ts.id:
            db.session.add(ts)
            db.session.commit()

        cid = cls.id
        tid = ts.id
        today_str = datetime.now().strftime("%Y-%m-%d")

    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    r1 = client.post(
        "/admin/timetable/override/save",
        data=json.dumps({
            "class_id": cid,
            "time_slot_id": tid,
            "override_date": today_str,
            "status": "cancelled",
            "note": "Faculty on sick leave"
        }),
        content_type="application/json"
    )
    assert r1.status_code == 200
    assert r1.get_json().get("success") is True

    r2 = client.post(
        "/admin/timetable/override/delete",
        data=json.dumps({
            "class_id": cid,
            "time_slot_id": tid,
            "override_date": today_str
        }),
        content_type="application/json"
    )
    assert r2.status_code == 200
    assert r2.get_json().get("success") is True


def test_leave_approval_auto_sync_timetable_override():
    from datetime import date
    app = build_app()
    client = app.test_client()
    with app.app_context():
        # Create student and leave request
        s_role = Role.query.filter_by(name="student").first()
        u = User(email="stud_leave_sync@example.com", first_name="Leave", last_name="Student", role=s_role)
        u.set_password("Student@1123")
        db.session.add(u)
        db.session.commit()

        crs = Course.query.first() or Course(name="BCA", code="BCA", department_id=1)
        if not crs.id:
            db.session.add(crs)
            db.session.commit()

        st = Student(roll_number="STU-LS", user_id=u.id, course_id=crs.id)
        db.session.add(st)
        db.session.commit()

        lr = LeaveRequest(
            student_id=st.id,
            reason="Medical Leave",
            starts_on=date.today(),
            ends_on=date.today(),
            decision="pending"
        )
        db.session.add(lr)
        db.session.commit()
        lrid = lr.id

    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    res = client.post(f"/admin/leaves/{lrid}/approved", follow_redirects=True)
    assert res.status_code == 200
    assert b"Leave request approved" in res.data


def test_dual_mode_and_personal_highlight():
    app = build_app()
    client = app.test_client()
    with app.app_context():
        p_role = Role.query.filter_by(name="professor").first()
        u = User.query.filter_by(email="prof_dual@example.com").first()
        if not u:
            u = User(email="prof_dual@example.com", first_name="DualProf", last_name="Test", role=p_role)
            u.set_password("Professor@1123")
            db.session.add(u)
            db.session.commit()
            p = Professor(employee_code="EMP-DUAL", user_id=u.id, department_id=1)
            db.session.add(p)
            db.session.commit()

    client.post("/login", data={"email": "prof_dual@example.com", "password": "Professor@1123"}, follow_redirects=True)
    res_my = client.get("/timetable?mode=my")
    assert res_my.status_code == 200
    assert b"My Schedule" in res_my.data

    res_all = client.get("/timetable?mode=all")
    assert res_all.status_code == 200
    assert b"Full College Schedule" in res_all.data


def test_delete_class_safely_deletes_dependent_records():
    app = build_app()
    client = app.test_client()
    with app.app_context():
        crs = Course.query.first() or Course(name="BCA", code="BCA", department_id=1)
        if not crs.id:
            db.session.add(crs)
            db.session.commit()

        cls = ClassRoom(name="Test Delete Class", course_id=crs.id, semester=1, section="Z")
        db.session.add(cls)
        db.session.commit()
        cid = cls.id

    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    res = client.post(f"/admin/classes/{cid}/delete", follow_redirects=True)
    assert res.status_code == 200
    assert b"Class deleted successfully." in res.data


def test_week_dates_in_timetable_view():
    app = build_app()
    client = app.test_client()
    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    res = client.get("/timetable")
    assert res.status_code == 200
    assert b"Week:" in res.data
    assert b"Previous Week" in res.data
    assert b"Next Week" in res.data


def test_auto_generate_consecutive_lab_rule():
    app = build_app()
    client = app.test_client()
    with app.app_context():
        dept = Department.query.first() or Department(name="CS", code="CS")
        if not dept.id:
            db.session.add(dept)
            db.session.commit()
        crs = Course.query.first() or Course(name="BCA", code="BCA", department_id=dept.id)
        if not crs.id:
            db.session.add(crs)
            db.session.commit()
        cls = ClassRoom.query.first()
        if not cls:
            cls = ClassRoom(name="BCA-5(A)", course_id=crs.id, semester=5, section="A")
            db.session.add(cls)
            db.session.commit()
        cid = cls.id

        if not Subject.query.first():
            db.session.add(Subject(name="Practical Lab", code="LAB", course_id=crs.id))
            db.session.add(Subject(name="J2EE", code="J2EE", course_id=crs.id))
            db.session.commit()

        if not Professor.query.first():
            p_role = Role.query.filter_by(name="professor").first()
            u = User(email="test_gen_prof@example.com", first_name="GenProf", last_name="Test", role=p_role)
            u.set_password("Professor@1123")
            db.session.add(u)
            db.session.commit()
            p = Professor(employee_code="FAC-GEN", user_id=u.id, department_id=dept.id)
            db.session.add(p)
            db.session.commit()

        if not TimeSlot.query.first():
            db.session.add(TimeSlot(id=1, slot_name="8:00 TO 8:45", start_time="08:00", end_time="08:45", is_recess=False))
            db.session.add(TimeSlot(id=2, slot_name="8:50 TO 9:35", start_time="08:50", end_time="09:35", is_recess=False))
            db.session.add(TimeSlot(id=3, slot_name="9:35 TO 10:25", start_time="09:35", end_time="10:25", is_recess=False))
            db.session.add(TimeSlot(id=4, slot_name="10:25 TO 10:55", start_time="10:25", end_time="10:55", is_recess=True))
            db.session.add(TimeSlot(id=5, slot_name="11:00 TO 11:45", start_time="11:00", end_time="11:45", is_recess=False))
            db.session.commit()

    client.post("/login", data={"email": "admin@example.com", "password": "Admin@12345"}, follow_redirects=True)
    res = client.post("/admin/timetable/generate", json={"class_id": cid})
    assert res.status_code == 200
    data = res.get_json()
    assert data.get("success") is True
    assert "Staggered Lab Shift" in data.get("message", "")


def test_student_profile_page():
    app = build_app()
    client = app.test_client()
    with app.app_context():
        s_role = Role.query.filter_by(name="student").first()
        u = User.query.filter_by(email="stu_profile_test@example.com").first()
        if not u:
            u = User(email="stu_profile_test@example.com", first_name="ProfileStu", last_name="Test", role=s_role)
            u.set_password("Student@1123")
            db.session.add(u)
            db.session.commit()
            st = Student(roll_number="STU-PROF1", user_id=u.id, course_id=1)
            db.session.add(st)
            db.session.commit()

    client.post("/login", data={"email": "stu_profile_test@example.com", "password": "Student@1123"}, follow_redirects=True)
    res = client.get("/student/profile")
    assert res.status_code == 200
    assert b"Student Official Digital Profile" in res.data
    assert b"Personal & Guardian Details" in res.data or b"Complete Personal & Guardian Information" in res.data











