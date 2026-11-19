from sqlalchemy import Engine, create_engine, event

from config.settings import settings


def create_database_engine() -> Engine:
    database_path = settings.absolute_database_path

    if not database_path.exists():
        raise FileNotFoundError(
            f"Northwind database was not found at: {database_path}"
        )

    database_url = f"sqlite:///{database_path.as_posix()}"

    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
        },
        future=True,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(
        dbapi_connection,
        connection_record,
    ) -> None:
        del connection_record

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


engine = create_database_engine()


def get_engine() -> Engine:
    return engine