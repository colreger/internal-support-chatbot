"""Small local pilot login. Replace with managed OIDC before public deployment."""
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

ITERATIONS = 600_000
SESSION_SECONDS = 30 * 60


def hash_password(password, *, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 100_000 <= int(iterations) <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def load_users():
    """Read hashes only. No default password and no public self-registration."""
    path = Path(os.environ.get("RAG_USERS_FILE", ".rag-users.json"))
    if not path.exists():
        return {}, ""
    raw = path.read_bytes()
    users = json.loads(raw)
    if not isinstance(users, dict) or any(not isinstance(v, str) for v in users.values()):
        raise ValueError("Ungültige Kontenkonfiguration.")
    return users, hashlib.sha256(raw).hexdigest()


def authenticate(username, password, users):
    stored = users.get(username)
    # Unknown accounts still perform the expensive hash operation.
    dummy = f"pbkdf2_sha256${ITERATIONS}${'00' * 16}${'00' * 32}"
    return verify_password(password, stored or dummy) and stored is not None


def valid_session(session, users, config_version, now=None):
    now = time.time() if now is None else now
    return bool(session and session.get("owner") in users
                and session.get("config_version") == config_version
                and 0 <= now - session.get("issued_at", 0) < SESSION_SECONDS)
