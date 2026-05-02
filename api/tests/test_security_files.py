import os
import stat

from app.core import security


def test_generated_secret_files_are_private_even_with_permissive_umask(tmp_path, monkeypatch):
    monkeypatch.setattr(security.settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(security.settings, "AUTH_TOKEN_SECRET", "")

    old_umask = os.umask(0)
    try:
        security._datasource_secret()
        security.get_or_create_rsa_key_pair()
        security._token_secret()
    finally:
        os.umask(old_umask)

    for path in [
        tmp_path / "auth" / "datasource_secret",
        tmp_path / "auth" / "rsa_private.pem",
        tmp_path / "auth" / "token_secret",
    ]:
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600
