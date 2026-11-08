# LangChain Recovery Demo fürs Interview

Das Terminal-Beispiel greift die Retrieval-Recovery-Idee aus dem separaten Recovery-Projekt auf. Die Antwort-Chain verwendet denselben Systemprompt und dasselbe Quellenformat wie `answer_machine.py`. Die Demo arbeitet mit drei erfundenen Textstellen. Der Suchschritt ist ein kleiner Stichwort-Retriever mit Top 1, damit man beide Suchläufe direkt vergleichen kann.

## Ausführen

Aus dem Wurzelverzeichnis des RAG-Projekts mit der bestehenden Python-Umgebung:

```bash
venv/bin/python -m pip install -r examples/langchain_recovery/requirements.txt
venv/bin/python -m examples.langchain_recovery.langchain_recovery
```

Der Offline-Modus nutzt vorgegebene Modellantworten. Er zeigt die Verdrahtung, die Suchergebnisse und alle drei Ausgänge.

| Frage | Erste Suche | Zweite Suche | Ausgang |
| --- | --- | --- | --- |
| Wo schläft die Gartenkatze Momo? | Notiz über Momo | entfällt | Auf dem Kissen neben der Linde |
| Wo kann ich im Lesegarten Bücher ausleihen? | Notiz zur Leseecke | Notiz zur Buchausleihe | Im blauen Gartenhäuschen |
| Gibt es im Lesegarten ein Baumhaus? | Notiz zur Leseecke | Notiz zur Leseecke | Die Quellen geben keine Antwort |

## Menschliche Freigabe ausprobieren

```bash
venv/bin/python -m examples.langchain_recovery.langchain_recovery --review
```

Sobald das Modell einen Beleg für ausreichend hält, pausiert LangGraph. Im Terminal siehst du die Frage und den Zettel. Mit `j` gibst du die Antwort frei. Mit `n` endet der Durchlauf ohne Antwort des Modells. Probiere zum Beispiel `j` bei Momo und `n` bei der Buchausleihe. Die Baumhausfrage endet bereits bei der Belegprüfung.

`interrupt()` pausiert den Ablauf. `Command(resume=...)` gibt deine Entscheidung an denselben Lauf zurück. LangGraph hält den Zwischenstand dafür im Arbeitsspeicher. Die Option `--review` funktioniert auch mit `live-recovery`.

## Live über NVIDIA

Die folgenden Befehle benötigen den vorhandenen `NVIDIA_API_KEY` aus der Umgebung oder der Projektdatei `.env`. `RAG_ALLOW_EXTERNAL=true` gilt nur für den jeweiligen Aufruf. Gesendet werden die fest eingebauten Demo-Fragen und -Quellen. LangSmith-Tracing ist während der Demo deaktiviert.

```bash
RAG_ALLOW_EXTERNAL=true venv/bin/python -m examples.langchain_recovery.langchain_recovery compare
RAG_ALLOW_EXTERNAL=true venv/bin/python -m examples.langchain_recovery.langchain_recovery live-recovery
```

- **`compare`** schickt dieselbe Frage und Quelle zuerst über den bestehenden SDK-Aufruf an Nemotron, dann über `ChatNVIDIA` an Nemotron und schließlich über dieselbe Chain an Google Gemma 4. Die Demo vergleicht die formatierten Nachrichten vor dem Senden. In der Chain wechselt nur die Modell-ID. Mit `--second-model ANBIETER/MODELL` kannst du ein anderes Modell aus dem NVIDIA-Katalog einsetzen.
- **`live-recovery`** nutzt Nemotron für die Frage nach der Buchausleihe. Das Modell beurteilt die Fundstellen, formuliert bei Bedarf eine neue Suche und schreibt die Antwort. Die Ausgabe zeigt pro Versuch Suchanfrage, Quellen-ID und Urteil. Nach einer Antwort gibt das Programm die verwendeten Quellen separat und nummeriert aus.

## Was du im Gespräch zeigen kannst

1. **LangChain** verbindet das Prompt-Template, den Chat-Adapter und den Parser über `|`. Für die Evidenzprüfung begrenzt ein Pydantic-Schema die erlaubten Urteile. Das Schema prüft die Form der Ausgabe. Die Belegqualität prüfst du am konkreten Treffer.
2. **LangGraph** steuert den Ablauf. Die erste bedingte Kante führt zur Antwort oder zur erneuten Suche. Die zweite bedingte Kante führt zur Antwort oder zum Abbruch. Der State zeigt beide Suchversuche.
3. **Der Modellwechsel** testet die Austauschbarkeit des Antwortschritts für einen festen Input. Der separate Recovery-Lauf zeigt, wie ein Modellurteil den weiteren Ablauf beeinflusst. Die wenigen Demo-Fälle dienen der Erklärung im Interview.

## Reisekosten-Tool mit LangChain

Die separate Demo nutzt dieselbe Python-Berechnung und dasselbe Eingabeschema wie der Streamlit-Tab. Für den fiktiven Beleg ermittelt sie 275,40 € erstattungsfähige Kosten aus 307,70 €. Die Regel deckelt das Hotel auf 120 € pro Nacht und schließt die private Minibar-Ausgabe aus.

```bash
venv/bin/python -m pip install -r examples/langchain_recovery/requirements.txt
venv/bin/python -m examples.langchain_recovery.travel_tool
```

Im Offline-Lauf enthält eine vorbereitete `AIMessage` den Aufruf. `StructuredTool.invoke(call)` führt Python aus und liefert eine `ToolMessage` mit derselben ID. Der Live-Lauf bindet das Tool über `model.bind_tools([...])` und übergibt die `ToolMessage` an das Modell zurück. Der Schalter `--live` sendet die feste Testfrage und das Ergebnis an NVIDIA. `NVIDIA_API_KEY` kommt aus der Umgebung oder der lokalen `.env`.

```bash
RAG_ALLOW_EXTERNAL=true venv/bin/python -m examples.langchain_recovery.travel_tool --live
```

Der bestehende Retrieval-Recovery-Ablauf bleibt ein separates Beispiel. Die Implementierung steht in [travel_tool.py](travel_tool.py).

Der **LangChain**-Tab bietet zusätzlich die Suche in fiktiven Firmenrichtlinien und die Websuche an. `StructuredTool` beschreibt jede Python-Funktion für NVIDIA. Das Modell schlägt einen Funktionsnamen und Argumente vor. Die App prüft den Vorschlag und führt die Funktion aus. Für Websuche kommt `BRAVE_SEARCH_API_KEY` in die lokale `.env`; die App zeigt den Suchtext an, bevor sie ihn an Brave sendet. [Websuche in Python](web_search.py)
