"""Travel claim lookup shared by the local UI and HTTP API."""

from contextlib import closing
import re
import sqlite3

CLAIM_ID_PATTERN = r"^RK-[0-9]{4}$"


def lookup_demo_claim(owner: str, claim_id: str) -> tuple[str, str] | None:
    # Each request gets an isolated, in-memory fixture. No real records are persisted.
    with closing(sqlite3.connect(":memory:")) as database:
        database.execute(
            """CREATE TABLE claims (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                status TEXT NOT NULL, deduction_reason TEXT NOT NULL
            )"""
        )
        database.execute(
            "INSERT INTO claims VALUES (?, ?, ?, ?)",
            ("RK-1042", "gandalf", "Teilweise erstattet", "Minibar ist eine private Ausgabe."),
        )
        return database.execute(
            "SELECT status, deduction_reason FROM claims WHERE id = ? AND owner = ?",
            (claim_id, owner),
        ).fetchone()


def claim_with_policy(library, owner: str, claim_id: str) -> dict[str, str] | None:
    if not re.fullmatch(CLAIM_ID_PATTERN, claim_id):
        raise ValueError("Ungültige Vorgangsnummer. Beispiel: RK-1042.")
    row = lookup_demo_claim(owner, claim_id)
    if row is None:
        return None
    for source in library.search(owner, "Minibar private Ausgaben"):
        if source.title == "Private Ausgaben bei Dienstreisen":
            return {
                "status": row[0],
                "deduction_reason": row[1],
                "policy_title": source.title,
                "policy_excerpt": source.text,
            }
    raise LookupError("Richtlinie nicht verfügbar.")
