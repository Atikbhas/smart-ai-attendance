from logging.config import fileConfig

from flask import current_app

from alembic import context

config = context.config
fileConfig(config.config_file_name)
target_db = current_app.extensions["migrate"].db


def get_engine():
    try:
        return target_db.get_engine()
    except TypeError:
        return target_db.engine


def get_metadata():
    return target_db.metadata


def run_migrations_offline():
    url = str(get_engine().url).replace("%", "%%")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            process_revision_directives=process_revision_directives,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
