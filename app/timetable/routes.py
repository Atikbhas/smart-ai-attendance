from datetime import datetime, date as date_cls, timezone
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import csrf, db
from app.models import ClassRoom, Course, Department, Notification, Professor, Student, Subject, TimeSlot, TimetableEntry, TimetableOverride, User
from app.security import roles_required
from app.timetable import timetable_bp


DAYS_OF_WEEK = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]


def _safe_int(val):
    try:
        return int(val) if val is not None and str(val).strip() != "" else None
    except (ValueError, TypeError):
        return None


@timetable_bp.route("/timetable", methods=["GET"])
@login_required
def view():
    selected_class_id = request.args.get("class_id", type=int)
    selected_prof_id = request.args.get("prof_id", type=int)
    selected_date_str = request.args.get("date", "").strip()
    view_mode = request.args.get("mode", "my" if current_user.role_name == "professor" else "all").strip().lower()

    classes = ClassRoom.query.order_by(ClassRoom.name.asc()).all()
    professors = Professor.query.join(User).order_by(User.first_name.asc()).all()
    time_slots = TimeSlot.query.order_by(TimeSlot.id.asc()).all()

    # Parse date
    if selected_date_str:
        try:
            target_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.now().date()
    else:
        target_date = datetime.now().date()

    # Role-based profile detection
    user_role = current_user.role_name
    student_profile = getattr(current_user, "student_profile", None)
    prof_profile = getattr(current_user, "professor_profile", None)
    my_prof_id = prof_profile.id if prof_profile else None

    if user_role == "student" and student_profile and student_profile.course_id:
        if not selected_class_id:
            matching_class = ClassRoom.query.filter_by(course_id=student_profile.course_id).first()
            if matching_class:
                selected_class_id = matching_class.id

    # View Mode handling
    if view_mode == "my" and prof_profile:
        selected_prof_id = prof_profile.id
        selected_class_id = None
    elif not selected_class_id and not selected_prof_id and classes:
        selected_class_id = classes[0].id

    # Build timetable matrix data: { (day, slot_id): [entry, ...] }
    query = TimetableEntry.query
    if selected_class_id:
        query = query.filter_by(class_id=selected_class_id)
    elif selected_prof_id:
        query = query.filter_by(professor_id=selected_prof_id)

    entries = query.all()
    grid = {}
    for entry in entries:
        key = (entry.day_of_week, entry.time_slot_id)
        if key not in grid:
            grid[key] = []
        grid[key].append(entry)

    # Calculate Monday of the target_date's week (weekday: 0=Mon, 6=Sun)
    from datetime import timedelta
    monday_date = target_date - timedelta(days=target_date.weekday())
    saturday_date = monday_date + timedelta(days=5)

    today_date = datetime.now().date()
    week_days_data = []
    day_abbrs = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for idx, day_code in enumerate(day_abbrs):
        d_date = monday_date + timedelta(days=idx)
        week_days_data.append({
            "code": day_code,
            "date": d_date,
            "date_str": d_date.strftime("%d %b"),
            "iso_date": d_date.strftime("%Y-%m-%d"),
            "is_today": (d_date == today_date)
        })

    prev_week_date_str = (monday_date - timedelta(days=7)).strftime("%Y-%m-%d")
    next_week_date_str = (monday_date + timedelta(days=7)).strftime("%Y-%m-%d")
    week_range_str = f"{monday_date.strftime('%b %d')} - {saturday_date.strftime('%b %d, %Y')}"

    # Fetch Date Overrides for target_date
    override_query = TimetableOverride.query.filter(
        TimetableOverride.override_date >= monday_date,
        TimetableOverride.override_date <= saturday_date
    )
    if selected_class_id:
        override_query = override_query.filter_by(class_id=selected_class_id)
    overrides_list = override_query.all()

    overrides_grid = {}
    for ov in overrides_list:
        overrides_grid[(ov.override_date.strftime("%Y-%m-%d"), ov.time_slot_id, ov.class_id)] = ov

    # Highlight active current time slot & day
    now = datetime.now()
    current_day = now.strftime("%a").upper()
    current_time_str = now.strftime("%H:%M")

    current_slot_id = None
    for ts in time_slots:
        if ts.start_time <= current_time_str <= ts.end_time:
            current_slot_id = ts.id
            break

    selected_class = db.session.get(ClassRoom, selected_class_id) if selected_class_id else None
    selected_prof = db.session.get(Professor, selected_prof_id) if selected_prof_id else None

    return render_template(
        "timetable/view.html",
        classes=classes,
        professors=professors,
        time_slots=time_slots,
        days=DAYS_OF_WEEK,
        week_days_data=week_days_data,
        week_range_str=week_range_str,
        prev_week_date_str=prev_week_date_str,
        next_week_date_str=next_week_date_str,
        grid=grid,
        overrides_grid=overrides_grid,
        target_date=target_date,
        target_date_str=target_date.strftime("%Y-%m-%d"),
        selected_class_id=selected_class_id,
        selected_prof_id=selected_prof_id,
        selected_class=selected_class,
        selected_prof=selected_prof,
        current_day=current_day,
        current_slot_id=current_slot_id,
        view_mode=view_mode,
        my_prof_id=my_prof_id,
    )


@timetable_bp.route("/admin/timetable/free-professors", methods=["GET"])
@login_required
@roles_required("admin")
def free_professors():
    day = request.args.get("day_of_week")
    slot_id = request.args.get("time_slot_id", type=int)

    if not day or not slot_id:
        return jsonify({"error": "day_of_week and time_slot_id required"}), 400

    # Find professors busy in regular timetable
    busy_prof_ids = [
        e.professor_id
        for e in TimetableEntry.query.filter_by(day_of_week=day, time_slot_id=slot_id).all()
        if e.professor_id
    ]

    # Available professors
    available_profs = Professor.query.filter(~Professor.id.in_(busy_prof_ids)).all() if busy_prof_ids else Professor.query.all()
    result = [
        {"id": p.id, "name": p.user.full_name if p.user else f"Prof #{p.id}", "code": p.employee_code}
        for p in available_profs
    ]
    return jsonify({"free_professors": result})


@timetable_bp.route("/admin/timetable/override/save", methods=["POST"])
@login_required
@roles_required("admin")
@csrf.exempt
def save_override():
    data = request.get_json() or request.form.to_dict() or {}
    class_id = _safe_int(data.get("class_id"))
    slot_id = _safe_int(data.get("time_slot_id"))
    date_str = data.get("override_date", "").strip()
    status = data.get("status", "normal").strip().lower() # "substitute", "cancelled", "holiday"
    sub_prof_id = _safe_int(data.get("substitute_professor_id"))
    note = str(data.get("note", "")).strip()

    if not class_id or not slot_id or not date_str:
        return jsonify({"error": "class_id, time_slot_id, and override_date are required"}), 400

    try:
        ov_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Conflict check for substitute professor
    if status == "substitute" and sub_prof_id:
        day_of_week = ov_date.strftime("%a").upper()
        busy = TimetableEntry.query.filter(
            TimetableEntry.day_of_week == day_of_week,
            TimetableEntry.time_slot_id == slot_id,
            TimetableEntry.professor_id == sub_prof_id,
            TimetableEntry.class_id != class_id,
        ).first()
        if busy:
            prof_obj = db.session.get(Professor, sub_prof_id)
            prof_name = prof_obj.user.full_name if prof_obj and prof_obj.user else f"Prof #{sub_prof_id}"
            return jsonify({"error": f"Collision! {prof_name} already teaches another class at this time slot."}), 409

    entry = TimetableEntry.query.filter_by(class_id=class_id, time_slot_id=slot_id).first()

    override = TimetableOverride.query.filter_by(
        override_date=ov_date, class_id=class_id, time_slot_id=slot_id
    ).first()
    if not override:
        override = TimetableOverride(
            override_date=ov_date, class_id=class_id, time_slot_id=slot_id, timetable_entry_id=entry.id if entry else None
        )
        db.session.add(override)

    override.status = status
    override.substitute_professor_id = sub_prof_id if status == "substitute" else None
    override.note = note
    db.session.commit()

    # Send Notification to Students in this Class
    cls_obj = db.session.get(ClassRoom, class_id)
    class_name = cls_obj.name if cls_obj else "your class"

    if cls_obj and cls_obj.course_id:
        students = Student.query.filter_by(course_id=cls_obj.course_id).all()
        sub_prof_obj = db.session.get(Professor, sub_prof_id) if sub_prof_id else None
        sub_name = sub_prof_obj.user.full_name if sub_prof_obj and sub_prof_obj.user else "Substitute Faculty"

        title = f"Timetable Update for {class_name}"
        if status == "cancelled":
            body = f"Notice: Lecture on {date_str} (Slot #{slot_id}) has been CANCELLED. Note: {note}"
        elif status == "holiday":
            body = f"Notice: {date_str} is marked as a HOLIDAY for {class_name}. Note: {note}"
        elif status == "substitute":
            body = f"Notice: Lecture on {date_str} (Slot #{slot_id}) will be conducted by {sub_name}. Note: {note}"
        else:
            body = f"Notice: Lecture update for {date_str}. Note: {note}"

        for std in students:
            notif = Notification(user_id=std.user_id, title=title, body=body)
            db.session.add(notif)
        db.session.commit()

    return jsonify({"success": True, "override_id": override.id})


@timetable_bp.route("/admin/timetable/override/delete", methods=["POST"])
@login_required
@roles_required("admin")
@csrf.exempt
def delete_override():
    data = request.get_json() or request.form.to_dict() or {}
    override_id = _safe_int(data.get("override_id"))
    class_id = _safe_int(data.get("class_id"))
    slot_id = _safe_int(data.get("time_slot_id"))
    date_str = data.get("override_date", "").strip()

    if override_id:
        override = db.session.get(TimetableOverride, override_id)
    else:
        try:
            ov_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            override = TimetableOverride.query.filter_by(override_date=ov_date, class_id=class_id, time_slot_id=slot_id).first()
        except ValueError:
            override = None

    if override:
        db.session.delete(override)
        db.session.commit()
        return jsonify({"success": True, "deleted": True})

    return jsonify({"error": "Override not found"}), 404


@timetable_bp.route("/admin/timetable/builder", methods=["GET"])
@login_required
@roles_required("admin")
def admin_builder():
    selected_class_id = request.args.get("class_id", type=int)
    classes = ClassRoom.query.order_by(ClassRoom.name.asc()).all()
    subjects = Subject.query.order_by(Subject.name.asc()).all()
    professors = Professor.query.join(User).order_by(User.first_name.asc()).all()
    time_slots = TimeSlot.query.order_by(TimeSlot.id.asc()).all()

    if not selected_class_id and classes:
        selected_class_id = classes[0].id

    selected_class = db.session.get(ClassRoom, selected_class_id) if selected_class_id else None

    entries = TimetableEntry.query.filter_by(class_id=selected_class_id).all() if selected_class_id else []
    grid = {}
    for entry in entries:
        grid[(entry.day_of_week, entry.time_slot_id)] = entry

    return render_template(
        "admin/timetable_builder.html",
        classes=classes,
        subjects=subjects,
        professors=professors,
        time_slots=time_slots,
        days=DAYS_OF_WEEK,
        grid=grid,
        selected_class_id=selected_class_id,
        selected_class=selected_class,
    )


@timetable_bp.route("/admin/timetable/entry/save", methods=["POST"])
@login_required
@roles_required("admin")
@csrf.exempt
def save_entry():
    data = request.get_json() or request.form.to_dict() or {}
    class_id = _safe_int(data.get("class_id"))
    day = data.get("day_of_week")
    slot_id = _safe_int(data.get("time_slot_id"))
    subject_id = _safe_int(data.get("subject_id"))
    prof_id = _safe_int(data.get("professor_id"))
    room = str(data.get("room_number", "")).strip()
    is_lab = bool(data.get("is_lab"))

    if not class_id or not day or not slot_id:
        return jsonify({"error": "class_id, day_of_week, and time_slot_id are required"}), 400

    if prof_id:
        conflict = TimetableEntry.query.filter(
            TimetableEntry.day_of_week == day,
            TimetableEntry.time_slot_id == slot_id,
            TimetableEntry.professor_id == prof_id,
            TimetableEntry.class_id != class_id,
        ).first()
        if conflict:
            prof_name = conflict.professor.user.full_name if conflict.professor and conflict.professor.user else f"Prof #{prof_id}"
            other_cls = conflict.classroom.name if conflict.classroom else f"Class #{conflict.class_id}"
            return jsonify({"error": f"Conflict! {prof_name} is already assigned to {other_cls} at this time."}), 409

    entry = TimetableEntry.query.filter_by(class_id=class_id, day_of_week=day, time_slot_id=slot_id).first()
    if not entry:
        entry = TimetableEntry(class_id=class_id, day_of_week=day, time_slot_id=slot_id)
        db.session.add(entry)

    entry.subject_id = subject_id
    entry.professor_id = prof_id
    entry.room_number = room if room else None
    entry.is_lab = is_lab

    db.session.commit()
    return jsonify({"success": True, "entry_id": entry.id})


@timetable_bp.route("/admin/timetable/entry/delete", methods=["POST"])
@login_required
@roles_required("admin")
@csrf.exempt
def delete_entry():
    data = request.get_json() or request.form.to_dict() or {}
    entry_id = _safe_int(data.get("entry_id"))
    class_id = _safe_int(data.get("class_id"))
    day = data.get("day_of_week")
    slot_id = _safe_int(data.get("time_slot_id"))

    if entry_id:
        entry = db.session.get(TimetableEntry, entry_id)
    else:
        entry = TimetableEntry.query.filter_by(class_id=class_id, day_of_week=day, time_slot_id=slot_id).first()

    if entry:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({"success": True, "deleted": True})

    return jsonify({"error": "Timetable entry not found"}), 404


@timetable_bp.route("/admin/timetable/generate", methods=["POST"])
@login_required
@roles_required("admin")
@csrf.exempt
def auto_generate():
    """Smart AI Timetable Generator with Staggered Lab Shift Rotation & Lab Room Capacity Checker"""
    data = request.get_json() or {}
    class_id = _safe_int(data.get("class_id"))

    if not class_id:
        return jsonify({"error": "class_id required"}), 400

    cls = db.session.get(ClassRoom, class_id)
    if not cls:
        return jsonify({"error": "Class not found"}), 404

    subjects = Subject.query.all()
    professors = Professor.query.all()
    non_recess_slots = TimeSlot.query.filter_by(is_recess=False).order_by(TimeSlot.id.asc()).all()

    if not subjects or not professors or not non_recess_slots:
        return jsonify({"error": "Subjects, Professors, and Time Slots must exist before generating."}), 400

    lab_subject = Subject.query.filter((Subject.code == "LAB") | (Subject.name.ilike("%lab%"))).first()
    if not lab_subject:
        lab_subject = subjects[0]

    theory_subjects = [s for s in subjects if s.id != lab_subject.id]
    if not theory_subjects:
        theory_subjects = subjects

    # Clear existing entries for this class
    TimetableEntry.query.filter_by(class_id=class_id).delete()
    db.session.commit()

    # Total physical computer labs in institution (Exactly 2 Labs: Lab 1 & Lab 2)
    physical_labs = ["Lab 1", "Lab 2"]

    count = 0
    theory_index = 0
    prof_index = 0
    assigned_shifts = []

    for day in DAYS_OF_WEEK:
        # Check Physical Lab Availability for Shift A (Slot 1 + Slot 2)
        shift_a_available_lab = None
        shift_a_prof = None

        for plab in physical_labs:
            # Is plab occupied at Slot 1 or Slot 2 on this day by another class?
            occ1 = TimetableEntry.query.filter(TimetableEntry.day_of_week == day, TimetableEntry.time_slot_id == 1, TimetableEntry.room_number == plab, TimetableEntry.class_id != class_id).first()
            occ2 = TimetableEntry.query.filter(TimetableEntry.day_of_week == day, TimetableEntry.time_slot_id == 2, TimetableEntry.room_number == plab, TimetableEntry.class_id != class_id).first()
            if not occ1 and not occ2:
                # Find a professor free for Shift A
                for p_try in range(len(professors)):
                    p_candidate = professors[(prof_index + p_try) % len(professors)]
                    c1 = TimetableEntry.query.filter_by(day_of_week=day, time_slot_id=1, professor_id=p_candidate.id).first()
                    c2 = TimetableEntry.query.filter_by(day_of_week=day, time_slot_id=2, professor_id=p_candidate.id).first()
                    if not c1 and not c2:
                        shift_a_available_lab = plab
                        shift_a_prof = p_candidate
                        prof_index = (prof_index + p_try + 1) % len(professors)
                        break
                if shift_a_available_lab:
                    break

        if shift_a_available_lab and shift_a_prof:
            # Assign Shift A: LAB at Slot 1 & 2, Theory at Slot 3 & 5
            assigned_shifts.append("Shift A")
            e1 = TimetableEntry(day_of_week=day, time_slot_id=1, class_id=class_id, subject_id=lab_subject.id, professor_id=shift_a_prof.id, room_number=shift_a_available_lab, is_lab=True)
            e2 = TimetableEntry(day_of_week=day, time_slot_id=2, class_id=class_id, subject_id=lab_subject.id, professor_id=shift_a_prof.id, room_number=shift_a_available_lab, is_lab=True)
            db.session.add(e1)
            db.session.add(e2)
            count += 2
            theory_slots = [3, 5]
        else:
            # Shift A labs are full! Stagger to Shift B: LAB at Slot 3 & 5, Theory at Slot 1 & 2
            assigned_shifts.append("Shift B")
            shift_b_lab = physical_labs[class_id % len(physical_labs)]
            # Find prof free for Shift B
            shift_b_prof = None
            for p_try in range(len(professors)):
                p_candidate = professors[(prof_index + p_try) % len(professors)]
                c3 = TimetableEntry.query.filter_by(day_of_week=day, time_slot_id=3, professor_id=p_candidate.id).first()
                c5 = TimetableEntry.query.filter_by(day_of_week=day, time_slot_id=5, professor_id=p_candidate.id).first()
                if not c3 and not c5:
                    shift_b_prof = p_candidate
                    prof_index = (prof_index + p_try + 1) % len(professors)
                    break
            if not shift_b_prof:
                shift_b_prof = professors[0]

            e3 = TimetableEntry(day_of_week=day, time_slot_id=3, class_id=class_id, subject_id=lab_subject.id, professor_id=shift_b_prof.id, room_number=shift_b_lab, is_lab=True)
            e5 = TimetableEntry(day_of_week=day, time_slot_id=5, class_id=class_id, subject_id=lab_subject.id, professor_id=shift_b_prof.id, room_number=shift_b_lab, is_lab=True)
            db.session.add(e3)
            db.session.add(e5)
            count += 2
            theory_slots = [1, 2]

        # Schedule Theory Slots for this day
        for tsid in theory_slots:
            tsub = theory_subjects[theory_index % len(theory_subjects)]
            tprof = None
            for p_try in range(len(professors)):
                p_candidate = professors[(prof_index + p_try) % len(professors)]
                conflict = TimetableEntry.query.filter_by(day_of_week=day, time_slot_id=tsid, professor_id=p_candidate.id).first()
                if not conflict:
                    tprof = p_candidate
                    prof_index = (prof_index + p_try + 1) % len(professors)
                    break
            if not tprof:
                # Find any professor free at tsid
                for p_candidate in professors:
                    c = TimetableEntry.query.filter_by(day_of_week=day, time_slot_id=tsid, professor_id=p_candidate.id).first()
                    if not c:
                        tprof = p_candidate
                        break
            if not tprof:
                tprof = professors[0]

            e_theory = TimetableEntry(
                day_of_week=day,
                time_slot_id=tsid,
                class_id=class_id,
                subject_id=tsub.id,
                professor_id=tprof.id,
                room_number=f"Room {100 + class_id}",
                is_lab=False
            )
            db.session.add(e_theory)
            count += 1
            theory_index += 1

    db.session.commit()
    shift_summary = f"{assigned_shifts.count('Shift A')} days Shift A (08:00 AM Lab), {assigned_shifts.count('Shift B')} days Shift B (09:35 AM Lab)"
    return jsonify({
        "success": True,
        "generated_entries": count,
        "message": f"Generated timetable for {cls.name} with Staggered Lab Shift & Room Capacity Check ({shift_summary})!"
    })
