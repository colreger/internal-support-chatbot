"""Local demo of a shared, permission-aware company document index."""
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import json
import math
import re

from answer_machine import build_request, external_enabled, send_request

_ROLES = {"gandalf": frozenset({"employee"}), "galadriel": frozenset({"employee", "hr"})}
_STOP = set("a am an auf aus bei bin bis das dass dem den der des die ein eine einem einer es für gibt ich im in ist kann man mit nach ob sich sind so und vom von vor wann was welche welcher wem wer wie wird wo zu zum zur darf dürfen muss soll viele".split())


def terms(text):
    return set(re.findall(r"[^\W_]+", text.casefold())) - _STOP


@dataclass(frozen=True)
class Source:
    title: str
    text: str
    role: str
    external: bool


class CompanyLibrary:
    def __init__(self, sources):
        self.sources = tuple(sources)
        postings = defaultdict(set)
        for i, source in enumerate(self.sources):
            for word in terms(f"{source.title} {source.text}"):
                postings[word].add(i)
        self.postings = dict(postings)

    @classmethod
    def load_demo(cls):
        path = Path(__file__).parent / "demo" / "company_library.json"
        return cls(Source(**row) for row in json.loads(path.read_text(encoding="utf-8")))

    def allowed(self, owner, *, hr_revoked=False):
        roles = _ROLES.get(owner, frozenset())
        if hr_revoked:
            roles = roles - {"hr"}
        return {i for i, source in enumerate(self.sources) if source.role in roles}

    def titles(self, owner, *, hr_revoked=False):
        return [self.sources[i].title for i in sorted(self.allowed(owner, hr_revoked=hr_revoked))]

    def search(self, owner, question, *, hr_revoked=False):
        question = question.strip()
        if not question or len(question) > 2000:
            raise ValueError("Bitte eine Frage mit 1 bis 2.000 Zeichen eingeben.")
        allowed = self.allowed(owner, hr_revoked=hr_revoked)
        scores = defaultdict(float)
        for word in sorted(terms(question)):
            matches = self.postings.get(word, set()) & allowed
            if matches:
                weight = 1 + math.log((1 + len(allowed)) / (1 + len(matches)))
                for i in matches:
                    scores[i] += weight
        return [self.sources[i] for i in sorted(scores, key=lambda i: (-scores[i], i))[:3]]

    def preview(self, owner, question, *, hr_revoked=False):
        hits = self.search(owner, question, hr_revoked=hr_revoked)
        if not hits or not all(hit.external for hit in hits):
            return None
        return build_request(question.strip(), hits)

    def send(self, owner, question, reviewed_payload, *, hr_revoked=False, sender=send_request):
        if not external_enabled():
            raise PermissionError("Externe KI ist serverseitig deaktiviert.")
        current = self.preview(owner, question, hr_revoked=hr_revoked)
        if current is None or current != reviewed_payload:
            raise PermissionError("Diese Quellen sind nicht freigegeben oder die Vorschau hat sich geändert.")
        return sender(current)
