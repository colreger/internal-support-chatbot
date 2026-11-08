"""Generate two local demo accounts. Refuses to overwrite existing accounts."""
import json
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from auth import hash_password

root = Path(__file__).resolve().parents[1]
users_path = root / ".rag-users.json"
access_path = root / ".rag-demo-access.md"
passwords = {name: secrets.token_urlsafe(18) for name in ("alice", "bob")}
# Exclusive create prevents silently replacing an existing account configuration.
fd = os.open(users_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as out:
    json.dump({name: hash_password(pw) for name, pw in passwords.items()}, out, indent=2)
fd = os.open(access_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as out:
    out.write("# Lokale Demo-Zugänge\n\nNur für die lokale Demo. Nicht veröffentlichen oder committen.\n\n")
    for name, password in passwords.items():
        out.write(f"- **{name}**: `{password}`\n")
    out.write("\nStart: `venv/bin/streamlit run frontend.py --server.address 127.0.0.1`\n")
print("Zwei Konten angelegt. Zugangsdaten stehen lokal in .rag-demo-access.md (nicht im Git).")
