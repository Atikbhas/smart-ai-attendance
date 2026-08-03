import io
from PIL import Image

import pytest


def _make_jpeg_bytes(color=(255, 255, 255), size=(200, 200)):
    from PIL import ImageDraw
    img = Image.new('RGB', size, color)
    draw = ImageDraw.Draw(img)
    for i in range(0, size[0], 10):
        draw.line([(i, 0), (i, size[1])], fill=(0, 0, 0), width=2)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


def test_save_and_finalize_dataset(monkeypatch):
    from app import create_app, db
    from app.models import Role, User, Student
    import app.services.face_service as fs
    import numpy as np

    app = create_app('testing')
    with app.app_context():
        # create role, user, student
        role = Role(name='student')
        db.session.add(role)
        db.session.commit()

        user = User(email='t@example.com', first_name='T', last_name='User', role=role)
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()

        student = Student(user=user, roll_number='R1')
        db.session.add(student)
        db.session.commit()

        # point dataset folder to a test subfolder in project parent
        app.config['FACE_DATASET_FOLDER'] = 'tests_run_faces'
        app.config['FACE_MIN_LAPLACIAN_VARIANCE'] = 0
        app.config['FACE_MIN_BRIGHTNESS'] = 0

        # Disable InsightFace (use DeepFace fallback path)
        monkeypatch.setattr(fs, '_get_insightface', lambda: None)

        # Monkeypatch DeepFace fallback for face presence check
        class FakeDeepFace:
            @staticmethod
            def extract_faces(image_array, detector_backend=None, enforce_detection=True):
                return [{'facial_area': {'x': 0, 'y': 0, 'w': 10, 'h': 10}}]

            @staticmethod
            def represent(image_array, model_name=None, detector_backend=None, enforce_detection=False, **kw):
                return [{'embedding': [0.1] * 128}]

        monkeypatch.setattr(fs, '_face_recognition', lambda: (FakeDeepFace, np))
        monkeypatch.setattr(fs, '_deepface_backend', lambda: 'opencv')

        # save a few images via save_dataset_image_bytes
        b = _make_jpeg_bytes()
        p1 = fs.save_dataset_image_bytes(student, b)
        p2 = fs.save_dataset_image_bytes(student, b)

        assert p1.exists()
        assert p2.exists()

        # monkeypatch train_student_face to avoid heavy model calls
        class FakeResult:
            def __init__(self, image_path, encoding_path):
                self.image_path = image_path
                self.encoding_path = encoding_path

        def fake_train(student_obj, img_path):
            return FakeResult(str(img_path), str(img_path) + '.npy')

        monkeypatch.setattr(fs, 'train_student_face', fake_train)

        res = fs.finalize_student_dataset(student, min_images=1, max_images=5)
        assert res.get('trained') is True
        assert res.get('trained_count', 0) >= 1