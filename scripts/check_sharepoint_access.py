"""Read-only access probe for one real SharePoint test library."""
import argparse
from getpass import getpass
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def graph_reader(token):
    opener = build_opener(NoRedirect())

    def read(path, *, denied_ok=False):
        request = Request("https://graph.microsoft.com/v1.0" + path,
                          headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        try:
            with opener.open(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as exc:
            if denied_ok and exc.code in (403, 404):
                return None
            raise RuntimeError(f"Graph hat die Anfrage abgelehnt (HTTP {exc.code}).") from None
        except (URLError, TimeoutError, ValueError):
            raise RuntimeError("Graph ist nicht erreichbar oder hat keine gültige Antwort geliefert.") from None

    return read


def check(read, drive, control, target, term, expected):
    if control == target:
        raise ValueError("Kontroll- und Testdatei müssen verschieden sein.")
    identity = read("/me?" + urlencode({"$select": "id"}))
    if not identity.get("id"):
        raise RuntimeError("Die delegierte Nutzeridentität konnte nicht bestätigt werden.")
    base = f"/drives/{quote(drive, safe='')}"
    path = lambda item: f"{base}/items/{quote(item, safe='')}?$select=id"
    if read(path(control), denied_ok=True) is None:
        raise RuntimeError("Kontrolldokument ist nicht lesbar. Der Test ist nicht auswertbar.")
    query = quote(term.replace("'", "''"), safe="")
    hits = read(f"{base}/root/search(q='{query}')?" + urlencode({"$select": "id"}))
    if "@odata.nextLink" in hits:
        raise RuntimeError("Suchbegriff nicht eindeutig genug. Verwende eine eindeutige Testkennung.")
    if not isinstance(hits.get("value"), list):
        raise RuntimeError("Graph lieferte keine auswertbare Trefferliste.")
    indexed = any(item.get("id") == target for item in hits["value"])
    readable = read(path(target), denied_ok=True) is not None
    visible = indexed and readable
    passed = visible if expected == "visible" else not readable
    return passed, indexed, readable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("drive", "control", "target", "term"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--expect", choices=("visible", "hidden"), required=True)
    args = parser.parse_args()
    token = getpass("Delegiertes Microsoft-Graph-Token (wird nicht angezeigt oder gespeichert): ").strip()
    if not token:
        parser.exit(2, "Ein delegiertes Token ist erforderlich.\n")
    try:
        passed, indexed, readable = check(graph_reader(token), args.drive, args.control, args.target, args.term, args.expect)
    except (RuntimeError, ValueError) as exc:
        parser.exit(2, f"Nicht auswertbar: {exc}\n")
    print(f"Graph-Suchtreffer: {indexed}; direkter Zugriff: {readable}; Test bestanden: {passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
