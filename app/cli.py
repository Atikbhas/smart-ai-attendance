import click
from flask import Flask

from app import db
from app.models import Role, User


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    def seed() -> None:
        roles = {
            "admin": "Institution administrator",
            "professor": "Faculty attendance manager",
            "student": "Student portal user",
        }
        for name, description in roles.items():
            role = Role.query.filter_by(name=name).first()
            if not role:
                db.session.add(Role(name=name, description=description))
        db.session.commit()

        admin_role = Role.query.filter_by(name="admin").first()
        admin = User.query.filter_by(email="admin@example.com").first()
        if not admin:
            admin = User(
                email="admin@example.com",
                first_name="System",
                last_name="Admin",
                role=admin_role,
            )
            admin.set_password("Admin@12345")
            db.session.add(admin)
            db.session.commit()
            click.echo("Created admin@example.com with password Admin@12345")
        else:
            click.echo("Seed data already exists.")
