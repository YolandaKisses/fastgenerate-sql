from sqlmodel import SQLModel, Session, create_engine

from app.models.datasource import DataSource, DataSourceCreate, DataSourceUpdate
from app.services.datasource_service import (
    build_database_url,
    create_datasource,
    encrypt_existing_datasource_passwords,
    update_datasource,
)
from app.core.security import decrypt_datasource_password, is_encrypted_datasource_password


def test_create_datasource_encrypts_database_password_at_rest():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        ds = create_datasource(
            session,
            DataSourceCreate(
                name="demo",
                db_type="mysql",
                host="localhost",
                port=3306,
                database="demo",
                username="root",
                password="plain-secret",
            ),
        )

        assert ds.password != "plain-secret"
        assert is_encrypted_datasource_password(ds.password)
        assert decrypt_datasource_password(ds.password) == "plain-secret"
        assert "plain-secret" in build_database_url(ds)


def test_update_datasource_encrypts_new_database_password():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        ds = create_datasource(
            session,
            DataSourceCreate(
                name="demo",
                db_type="mysql",
                host="localhost",
                port=3306,
                database="demo",
                username="root",
                password="old-secret",
            ),
        )

        updated = update_datasource(
            session,
            ds.id,
            DataSourceUpdate(password="new-secret"),
        )

        assert updated.password != "new-secret"
        assert is_encrypted_datasource_password(updated.password)
        assert decrypt_datasource_password(updated.password) == "new-secret"
        assert "new-secret" in build_database_url(updated)


def test_update_datasource_ignores_explicit_null_password():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        ds = create_datasource(
            session,
            DataSourceCreate(
                name="demo",
                db_type="mysql",
                host="localhost",
                port=3306,
                database="demo",
                username="root",
                password="old-secret",
            ),
        )
        stored_password = ds.password

        updated = update_datasource(
            session,
            ds.id,
            DataSourceUpdate(name="renamed", password=None),
        )

        assert updated.name == "renamed"
        assert updated.password == stored_password
        assert decrypt_datasource_password(updated.password) == "old-secret"


def test_plaintext_legacy_datasource_password_still_builds_connection_url():
    ds = DataSource(
        name="legacy",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database="demo",
        username="admin",
        password="legacy-secret",
    )

    assert not is_encrypted_datasource_password(ds.password)
    assert "legacy-secret" in build_database_url(ds)


def test_encrypt_existing_datasource_passwords_migrates_legacy_plaintext_values():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        ds = DataSource(
            name="legacy",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="legacy-secret",
        )
        session.add(ds)
        session.commit()

        migrated_count = encrypt_existing_datasource_passwords(session)

        assert migrated_count == 1
        session.refresh(ds)
        assert ds.password != "legacy-secret"
        assert is_encrypted_datasource_password(ds.password)
        assert decrypt_datasource_password(ds.password) == "legacy-secret"
