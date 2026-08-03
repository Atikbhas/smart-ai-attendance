from flask import Blueprint

timetable_bp = Blueprint("timetable", __name__)

from app.timetable import routes
