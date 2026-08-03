from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional


class StudentCreateForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    roll_number = StringField("Roll number", validators=[DataRequired(), Length(max=50)])
    barcode_id = StringField("College ID Barcode (Optional)", validators=[Optional(), Length(max=100)])
    gender = SelectField(
        "Gender",
        choices=[
            ("", "Prefer not to say"),
            ("female", "Female"),
            ("male", "Male"),
            ("non_binary", "Non-binary"),
        ],
        validators=[Optional()],
    )
    password = PasswordField("Temporary password", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("Create student")


class StudentEditForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    roll_number = StringField("Roll number", validators=[DataRequired(), Length(max=50)])
    barcode_id = StringField("College ID Barcode (Optional)", validators=[Optional(), Length(max=100)])
    gender = SelectField(
        "Gender",
        choices=[
            ("", "Prefer not to say"),
            ("female", "Female"),
            ("male", "Male"),
            ("non_binary", "Non-binary"),
        ],
        validators=[Optional()],
    )
    course_id = SelectField("Course", coerce=int, validators=[Optional()])
    new_password = PasswordField("New Password (optional)", validators=[Optional(), Length(min=8, max=128)])
    submit = SubmitField("Update student")


class ProfessorCreateForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    employee_code = StringField("Employee code", validators=[DataRequired(), Length(max=50)])
    password = PasswordField("Temporary password", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("Create professor")


class ProfessorEditForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    employee_code = StringField("Employee code", validators=[DataRequired(), Length(max=50)])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    new_password = PasswordField("New Password (optional)", validators=[Optional(), Length(min=8, max=128)])
    submit = SubmitField("Update professor")


class DepartmentCreateForm(FlaskForm):
    name = StringField("Department name", validators=[DataRequired(), Length(max=150)])
    code = StringField("Department code", validators=[DataRequired(), Length(max=20)])
    submit = SubmitField("Create department")


class CourseCreateForm(FlaskForm):
    name = StringField("Course name", validators=[DataRequired(), Length(max=150)])
    code = StringField("Course code", validators=[DataRequired(), Length(max=20)])
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Create course")


class SubjectCreateForm(FlaskForm):
    name = StringField("Subject name", validators=[DataRequired(), Length(max=150)])
    code = StringField("Subject code", validators=[DataRequired(), Length(max=20)])
    course_id = SelectField("Course", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Create subject")


class ClassCreateForm(FlaskForm):
    name = StringField("Class name", validators=[DataRequired(), Length(max=100)])
    course_id = SelectField("Course", coerce=int, validators=[DataRequired()])
    semester = SelectField(
        "Semester",
        coerce=int,
        choices=[(number, str(number)) for number in range(1, 9)],
        validators=[DataRequired()],
    )
    section = StringField("Section", validators=[Optional(), Length(max=20)])
    submit = SubmitField("Create class")
