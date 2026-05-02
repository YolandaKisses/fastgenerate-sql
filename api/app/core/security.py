from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.config import settings

PBKDF2_ITERATIONS = 210000
DATASOURCE_PASSWORD_PREFIX = "fgenc:v1:"


def _auth_dir() -> Path:
    path = Path(settings.DATA_DIR) / "auth"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _datasource_secret_path() -> Path:
    return _auth_dir() / "datasource_secret"


def _datasource_secret() -> bytes:
    secret_path = _datasource_secret_path()
    if secret_path.exists():
        return base64.urlsafe_b64decode(secret_path.read_text(encoding="utf-8"))

    secret = AESGCM.generate_key(bit_length=256)
    secret_path.write_text(base64.urlsafe_b64encode(secret).decode("ascii"), encoding="utf-8")
    return secret


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return password_hash, salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return hmac.compare_digest(password_hash, expected_hash)


def is_encrypted_datasource_password(value: str | None) -> bool:
    return bool(value and value.startswith(DATASOURCE_PASSWORD_PREFIX))


def encrypt_datasource_password(password: str | None) -> str:
    if not password:
        return ""
    aesgcm = AESGCM(_datasource_secret())
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, password.encode("utf-8"), None)
    payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{DATASOURCE_PASSWORD_PREFIX}{payload}"


def decrypt_datasource_password(value: str | None) -> str:
    if not value:
        return ""
    if not is_encrypted_datasource_password(value):
        return value

    payload = value.removeprefix(DATASOURCE_PASSWORD_PREFIX)
    raw = base64.urlsafe_b64decode(payload.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(_datasource_secret())
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def _private_key_path() -> Path:
    return _auth_dir() / "rsa_private.pem"


def _public_key_path() -> Path:
    return _auth_dir() / "rsa_public.pem"


def get_or_create_rsa_key_pair() -> tuple[bytes, bytes]:
    private_path = _private_key_path()
    public_path = _public_key_path()
    if private_path.exists() and public_path.exists():
        return private_path.read_bytes(), public_path.read_bytes()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    return private_pem, public_pem


def get_public_key_pem() -> str:
    _, public_pem = get_or_create_rsa_key_pair()
    return public_pem.decode("utf-8")


def decrypt_password(encrypted_password: str) -> str:
    private_pem, _ = get_or_create_rsa_key_pair()
    private_key = serialization.load_pem_private_key(private_pem, password=None)
    plaintext = private_key.decrypt(
        base64.b64decode(encrypted_password),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return plaintext.decode("utf-8")


def encrypt_password_for_test(password: str) -> str:
    _, public_pem = get_or_create_rsa_key_pair()
    public_key = serialization.load_pem_public_key(public_pem)
    encrypted = public_key.encrypt(
        password.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(encrypted).decode("ascii")


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    padding_len = (4 - len(data) % 4) % 4
    return base64.urlsafe_b64decode(data + ("=" * padding_len))


def _token_secret() -> str:
    if settings.AUTH_TOKEN_SECRET:
        return settings.AUTH_TOKEN_SECRET
    secret_path = _auth_dir() / "token_secret"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8")
    secret = secrets.token_urlsafe(48)
    secret_path.write_text(secret, encoding="utf-8")
    return secret


def create_access_token(user: Any, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES))
    header = {"alg": "HS256", "typ": "FGSQL"}
    payload = {
        "sub": user.user_id,
        "account": user.account,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(_token_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_base64url_encode(signature)}"


def verify_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Token 格式无效")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected_signature = hmac.new(_token_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual_signature = _base64url_decode(parts[2])
        payload = json.loads(_base64url_decode(parts[1]))
    except Exception as exc:
        raise ValueError("Token 格式无效") from exc
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise ValueError("Token 签名无效")
    if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("Token 已过期")
    return payload
