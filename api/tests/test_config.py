from app.core.config import Settings


def test_default_cors_origins_do_not_allow_wildcard():
    settings = Settings()

    assert "*" not in settings.cors_allowed_origins
    assert "http://127.0.0.1:5173" in settings.cors_allowed_origins


def test_cors_origins_are_parsed_from_comma_separated_setting():
    settings = Settings(ALLOWED_ORIGINS="https://app.example.com, http://localhost:4173")

    assert settings.cors_allowed_origins == [
        "https://app.example.com",
        "http://localhost:4173",
    ]


def test_rag_backend_defaults_to_local_with_remote_rebuild_disabled():
    settings = Settings()

    assert settings.RAG_RETRIEVAL_BACKEND == "local"
    assert settings.LIGHTRAG_ENABLE_REMOTE_REBUILD is False
