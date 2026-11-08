# Datenschutz in der Praxis: RAG Knowledge Assistant

Stand: 5. November 2026. Implementierter lokaler Pilot mit fiktiven Daten, keine Freigabe für echte Unternehmens- oder Personaldaten.

## Konzept und Umsetzung

Der [ursprüngliche Portfolio-Entwurf](Datenschutzkonzept_Entwurf_2026-11-05.md) beschreibt die Anforderungen. Die folgende Tabelle ordnet ihnen die umgesetzten Kontrollen und Tests zu.

| Anforderung aus dem Konzept | Technische Maßnahme | Nachweis / Status |
|---|---|---|
| Konto A darf keine Informationen von B erhalten | Passwortanmeldung, serverseitige Kontozuordnung und verpflichtender Owner-Filter bei Liste, Suche, direktem Chunk-Abruf, Freigabe und Löschung | Umgesetzt und automatisiert mit identischen Testvektoren sowie manipulierten Dokument-IDs getestet |
| Nur erforderliche, freigegebene Inhalte extern übermitteln | Lokale Embeddings, NVIDIA standardmäßig serverseitig gesperrt; zusätzliche Dokumentfreigabe und Einzelfallbestätigung nach vollständiger Anfragevorschau | Umgesetzt; ausgehende Nutzlast mit Test-Sender geprüft. Kein echter NVIDIA-Aufruf für diese Prüfung |
| Vorschau darf keine überholte Berechtigung ersetzen | Kontozuordnung, aktuelle Freigabe und Quellen werden unmittelbar vor dem Senden erneut geprüft | Widerruf, Löschung, fremdes Konto und manipulierte Vorschau automatisiert getestet |
| Gelöschte Dokumente dürfen nicht mehr im aktiven Suchbestand liegen | Zufällige Dokument-ID verbindet alle Chunks und Vektoren; Löschung entfernt die Chroma-Einträge und prüft das Ergebnis | Suche und direkter Abruf alter IDs sowie erneutes Öffnen des Stores getestet; fremdes Dokument bleibt erhalten |
| Datenminimierung | Keine Originaldatei auf Festplatte; Text vor Speicherung manuell bearbeitbar; neutraler Titel; keine Frage-/Antwortspeicherung in Chroma; keine Inhaltslogs im Anwendungscode | Implementiert. Keine automatische zuverlässige Erkennung oder Anonymisierung personenbezogener Daten behauptet |
| Nachvollziehbare Quellen | Lokale Quellenansicht mit Titel und Abschnittsnummer; nummerierte Quellen im LLM-Prompt | Quellenansicht im Streamlit-Test geprüft; tatsächliche Quellenstützung einer NVIDIA-Antwort nicht getestet |
| Begrenzter Pilot und nachvollziehbare Speicherung | Upload max. 5 MB, PDF max. 100 Seiten, extrahierter Text max. 200.000 Zeichen; Sitzungen 30 Minuten; manuelles Löschen | Implementiert; kein automatisches Ablaufdatum für Dokumente |

## Selbst ausprobieren: etwa fünf Minuten

1. **Starten:** Im Projektordner `venv/bin/streamlit run frontend.py --server.address 127.0.0.1` ausführen. Konten einmalig mit `venv/bin/python scripts/setup_demo.py` anlegen, falls noch keine existieren. Das Skript überschreibt bestehende Konten nicht. Die lokal erzeugten Kennwörter stehen in `.rag-demo-access.md`; Passwort-Hashes in `.rag-users.json`. Beide Dateien sind nur für den lokalen Benutzer lesbar und von Git und Docker ausgeschlossen.
2. **Als alice anmelden.** Im Tab „Datenschutz-Demo“ ein fiktives Dokument anlegen. In „Private Suche“ nach Fortbildungstagen fragen. Die Quelle nennt 17 Tage und ALICE-KIESEL-731.
3. **Vorschau öffnen:** Den Bereich „Genau diese Anfrage würde NVIDIA erhalten“ aufklappen. Die Vorschau zeigt die konkrete Frage und die gefundenen Textstellen. API-Schlüssel, Kontoname, Dokument-ID, Dateiname und Chatverlauf gehören nicht zur Nutzlast. Namen oder andere sensible Informationen innerhalb des Texts wären trotzdem enthalten; diese vorher manuell entfernen.
4. **Als bob anmelden:** Abmelden und mit bob einloggen, alternativ einen zweiten Browser verwenden. Alice-Dokumente fehlen. Bob kann ein eigenes Testdokument mit BOB-LINDE-942 und 29 Tagen anlegen.
5. **Löschung zeigen.** Wieder als alice anmelden, das eigene Dokument unter „Private Uploads“ auswählen und löschen. Es verschwindet aus dem Suchbestand und der Auswahl. Bobs Dokument bleibt erhalten. Die Tests prüfen zusätzlich den direkten Abruf einer alten Chunk-ID.

Die Demo legt Dokumente absichtlich erst durch einen Klick an; es werden keine echten Dokumente übernommen. Gleichnamige Uploads erhalten verschiedene IDs und überschreiben sich nicht. Eine Neufassung ersetzt die alte daher nicht automatisch: die alte bewusst löschen.

## Optional: externe Antwort praktisch ausprobieren

Der lokale Quellenabruf funktioniert ohne NVIDIA-Schlüssel und ohne LLM-Aufruf. Für eine tatsächlich formulierte Modellantwort muss der Betreiber den Prozess ausdrücklich so starten:

```bash
RAG_ALLOW_EXTERNAL=true venv/bin/streamlit run frontend.py --server.address 127.0.0.1
```

Zusätzlich muss `NVIDIA_API_KEY` in der Prozessumgebung oder lokal in `.env` vorhanden sein. Den Schlüssel nie in ein Dokument, Git oder die Anfragevorschau schreiben. Die serverseitige Erlaubnis wird absichtlich nicht aus `.env` geladen. Danach das fiktive Dokument für externe KI freigeben, lokal suchen, Vorschau prüfen, Einzelfall bestätigen und den Sende-Knopf betätigen. Erst dieser Klick löst die Anfrage aus. Bei Widerruf oder Löschung wird eine frühere Vorschau nicht akzeptiert.

Es wird weiterhin ausschließlich der fest konfigurierte NVIDIA-Endpunkt verwendet. Keine frei eingebbaren Endpunkte und kein externer Fallback für Embeddings. Eine Antwort wird als reiner Text dargestellt, damit vom Modell ausgegebene Bilder oder Links nicht automatisch externe Inhalte nachladen.

## Datenfluss und Speicherorte

```text
Anmeldung → geprüfte Kontoidentität im serverseitigen Sitzungszustand

Upload im Browser
  → temporärer Upload-Puffer auf dem Server
  → Textauslesen und manuelle Prüfung/Redaktion
  → 1.000-Zeichen-Chunks ohne Überlappung
  → lokales MiniLM (nur vorhandene Modellgewichte)
  → Chroma: Chunks + Vektoren + Dokument-ID + Kontozuordnung + Freigabe

Frage
  → lokale Frageeinbettung
  → Suche mit Konto- UND Dokumentfilter
  → Quellen und exakte NVIDIA-Anfragevorschau im Browser
  → optional: erneute Berechtigungsprüfung → explizit bestätigter NVIDIA-Aufruf
```

- **Aktiver Index:** `privacy_rag_db/`, alternativ `RAG_DATA_DIR`. Nur geprüfter Text und erforderliche Metadaten werden dort abgelegt. Embeddings sind nicht automatisch anonym.
- **Sitzung:** Upload-Puffer, bearbeiteter Entwurf, Frage, Vorschau und letzte Antwort liegen vorübergehend im Serverspeicher. Es gibt keine dauerhafte Chatdatenbank und keinen geteilten Cache für Dokumenttexte oder Suchergebnisse. Nur Modellgewichte und der Datenbankclient werden pro Prozess wiederverwendet.
- **Aufbewahrung:** Dokumente bis zur manuellen Löschung. Sitzungen sind 30 Minuten ab Anmeldung gültig. Fristablauf wird beim nächsten Zugriff geprüft; dies ist kein Hintergrundprozess, der RAM exakt nach 30 Minuten überschreibt. Abmelden und Sitzung-leeren entfernen den aktiven Anwendungszustand.
- **Alte Daten:** `chroma_db/` und die frühere Sammlung `document_chunks` werden nicht importiert, durchsucht oder automatisch gelöscht. Bereits vorhandene Altbestände müssen separat geprüft und gegebenenfalls kontrolliert entfernt werden. Die neue Anwendung behauptet nicht, diese Altbestände bereinigt zu haben.
- **Protokolle:** Die Anwendung schreibt keine Fragen, Quellen, Antworten oder Kennwörter in Inhaltslogs. Framework-, Infrastruktur- und vom Betreiber aktivierte Debuglogs sind separat zu konfigurieren. Streamlit-Nutzungsstatistik, Hugging-Face-Telemetrie und Chroma-Telemetrie sind in der Anwendung deaktiviert.
- **Modellinstallation:** Inferenz verwendet `local_files_only=True`. Falls MiniLM noch nicht vorhanden ist, werden Suchläufe nicht automatisch ins Netz ausweichen. Ein einmaliger Download öffentlicher Modellgewichte ist separat erforderlich; dabei werden keine Pilotdokumente benötigt.

## Durchgeführte Prüfungen

```bash
venv/bin/python -m unittest discover -s tests -v
```

Zwölf Tests in `tests/test_privacy.py` prüfen reale Chroma-Speicherung und Filterung, Passwortprüfung und Sitzungsablauf, kontrollierte externe Nutzlasten mit einem Test-Sender sowie den Streamlit-Ablauf mit Anmeldung, Demoanlage, Suche, Vorschau, Freigabeänderung, Löschung und Abmeldung. Der Streamlit-Test verwendet deterministische Testvektoren; die Backend-Tests sind keine Messung der Retrieval-Qualität.

Zusätzlich wurde ein separater Durchlauf mit dem echten lokal vorhandenen MiniLM-Modell und temporärer Chroma-Datenbank ausgeführt: beide fiktiven Dokumente einbetten, nur Alices Quelle abrufen, fremde ID abweisen, Anfragevorschau kontrollieren, Alice löschen, alte Chunk-ID prüfen und Bob erhalten. Kein externer LLM-Aufruf dabei.

Die laufende App wurde zusätzlich im Browser mit dem echten lokalen Modell geprüft: Anmeldung als alice, fiktives Dokument anlegen, Frage nach Fortbildungstagen stellen und die Quelle mit 17 Tagen anzeigen. Der NVIDIA-Sendeknopf blieb bei deaktivierter externer Verarbeitung gesperrt.

## Offene Punkte vor echtem Unternehmenseinsatz

- Die [DSFA-Vorprüfung und der Arbeitsentwurf für den Work-Assistenten](DSFA_Work_Assistent_Entwurf.md) trennen die lokale Demo vom Einsatz mit echten Unternehmensdaten und führen die dafür benötigten Nachweise auf.
- Zweck, Rechtsgrundlage, Verantwortlichkeiten, Informationspflichten und gegebenenfalls Datenschutz-Folgenabschätzung klären.
- Anbieterbedingungen, Speicherung, Trainingsnutzung, Auftragsverarbeitung und Datenstandorte prüfen. Ein technischer Freigabe-Klick ersetzt keine rechtliche Prüfung.
- Die lokale Passwortanmeldung ist eine Pilotlösung. Unternehmens-SSO/OIDC, Kontenverwaltung, zentrale Missbrauchserkennung, TLS und Administratorrechte sind gesonderte Aufgaben. Das eingebaute Anmeldelimit gilt nur pro Prozess und ersetzt keine vorgelagerte Absicherung.
- Datenbank und Konto-Hashes sind nicht anwendungsseitig verschlüsselt. Betriebssystem-/Volume-Verschlüsselung, Dateirechte und Backup-Zugriffe für den Zielbetrieb festlegen.
- Löschung bedeutet Entfernung aus dem aktiven Chroma-Bestand, keine garantierte physische Überschreibung auf Datenträgern. Backups und Wiederherstellungen benötigen ein eigenes Verfahren. Bereits übermittelte NVIDIA-Anfragen und bereits angezeigte oder kopierte Browserinhalte werden nicht zurückgeholt. Andere offene Sitzungen können bereits angezeigte Inhalte behalten.
- Der Lösch-/Sende-Lock gilt für einen Prozess. Mehrere Replikas erfordern gemeinsame Autorisierung und ein geeignetes Transaktions-/Sperrkonzept. Diesen Pilot nicht ungeprüft horizontal skalieren.
- Quellen können unzureichend sein und Prompt-Injection enthalten. Rollengetrennte Prompts und begrenzter Kontext sind keine Garantie gegen Halluzinationen oder Angriffe. Antwortqualität, Quellenstützung und unbeantwortbare Fragen separat testen.
- Tokenbasiertes Chunking bleibt eine unabhängige Qualitätsverbesserung. Die bisherige 1.000-Zeichen-Grenze garantiert nicht die Einhaltung des MiniLM-Tokenlimits.

## Für Portfolio und Interview

> „Ich habe einen Datenschutzentwurf in drei konkrete Kontrollen übersetzt: kontogetrennte Suche, kontrollierte externe Weitergabe mit Anfragevorschau und eine Löschung von Chunks samt Vektoren. Diese Kontrollen habe ich mit getrennten Testkonten und automatisierten Negativtests überprüft. Das ist ein lokaler Pilot mit Testdaten, keine pauschale DSGVO-Zertifizierung.“

Fachlicher Ausgangspunkt: [DSK-Orientierungshilfe zu RAG, Oktober 2025](https://www.datenschutzkonferenz-online.de/media/oh/DSK_OH_RAG.pdf). Technische Referenzen: [Chroma-Metadatenfilter](https://docs.trychroma.com/docs/querying-collections/metadata-filtering), [Chroma-Löschung](https://docs.trychroma.com/docs/collections/delete-data), [Streamlit-AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).
