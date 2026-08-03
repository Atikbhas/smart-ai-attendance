from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import DateField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class FaceUploadForm(FlaskForm):
    face_image = FileField(
        "Face image",
        validators=[
            FileRequired(),
            FileAllowed(["jpg", "jpeg", "png"], "Only JPG, JPEG, and PNG images are allowed."),
        ],
    )
    submit = SubmitField("Upload and train")


class LeaveRequestForm(FlaskForm):
    starts_on = DateField("Start date", validators=[DataRequired()])
    ends_on = DateField("End date", validators=[DataRequired()])
    reason = TextAreaField("Reason", validators=[DataRequired(), Length(min=5, max=1000)])
    submit = SubmitField("Submit leave request")
