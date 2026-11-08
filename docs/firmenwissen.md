# Firmenwissen: vom Datei-Upload zur gemeinsamen Bibliothek

Der erste Tab durchsucht bereits eingebundene, erfundene Firmendokumente. Kein manuelles Hochladen und keine Auswahl einer einzelnen Datei nötig.

| Frage | Alice (Mitarbeiterin) | Bob (Mitarbeiter und HR) |
|---|---|---|
| „Darf ich bei einer Dienstreise ein Taxi zum Flughafen nehmen?“ | Reisekostenrichtlinie | Dieselbe Reisekostenrichtlinie |
| „Was steht zu Nordstern 482?“ | Kein Treffer | Interne HR-Quelle, nur lokal |
| „Quantencomputer?“ | Kein Treffer | Kein Treffer |

Die Rollen werden serverseitig aus der angemeldeten Demo-Identität abgeleitet. Der Suchindex filtert vor der Rangbildung. Ohne externe KI wird ein gekennzeichneter Originalauszug angezeigt. Mit aktivierter NVIDIA-Option kann eine Antwort für freigegebene Treffer nach Prüfung der Anfrage formuliert werden; ein nicht freigegebener Treffer sperrt den gesamten Versand. Privater Upload, Vektorsuche und Löschung bleiben in separaten Tabs verfügbar.

Die Bibliothek ist **eine lokale SharePoint-Simulation**. Dokumente und Zugriffsregeln stehen in `demo/company_library.json` und `company_library.py`; der Stichwortindex wird beim ersten Zugriff aufgebaut und pro Prozess zwischengespeichert. Änderungen an der Beispieldatei erfordern einen Neustart. Der Pilot verbindet sich nicht mit Microsoft 365 und synchronisiert keine Rechte oder Dokumente.

## Wie der Index funktioniert

Ein Index ist eine vorbereitete Suchstruktur. Hier zeigt er von einem Wort auf Dokumente, etwa „Flughafen“ → „Reisekostenrichtlinie“. Die private Chroma-Suche nutzt dagegen Embeddings als Suchrepräsentation. Ein Index und ein Embedding sind unterschiedliche Dinge: Das eine organisiert die Suche, das andere repräsentiert einen Text als Zahlenvektor.

In einem echten Firmenprojekt zuerst eine freigegebene SharePoint-Bibliothek und die Identität des angemeldeten Nutzers anbinden. Microsoft Search kann passende Treffer im vorhandenen Microsoft-Index suchen. Die Anwendung müsste autorisierte Inhalte abrufen, daraus eine Antwort mit Links erzeugen und prüfen, dass widerrufene Rechte wirksam werden. Für diesen Ansatz muss man keinen eigenen Embedding-Index aufbauen. [Microsoft Search API](https://learn.microsoft.com/en-us/graph/api/resources/search-api-overview?view=graph-rest-1.0)

## Router und Agenten: mögliche Erweiterungen

Ein Router entscheidet, welchen Weg eine Anfrage nimmt. Bei Fragen zu Reisekosten, IT und Personal könnte er zwischen drei Suchquellen wählen. Ein **gelernter** Router kann wie die Stressklassifikation trainiert werden: Frage als Eingabe, richtige Route als Label. Als erster Versuch reichen gelabelte Fragen, TF-IDF und logistische Regression; auf separaten Fragen die Fehler je Kategorie prüfen. Unklare oder gemischte Fragen brauchen eine Rückfrage oder einen breiteren Suchpfad. Zugriffsrechte werden unabhängig vom Routing geprüft.

Ein Multi-Agent-System hat mehrere ausführende Agenten. Beispiel: Ein Reise-Agent prüft die Richtlinie, ein Abrechnungs-Agent prüft Beleganforderungen. Ein koordinierender Ablauf sammelt ihre Quellen und meldet Widersprüche. Das Entwicklungsteam legt Werkzeuge, Zugriff, Übergaben und Tests fest; Fachverantwortliche definieren und prüfen den Prozess. Für diesen Piloten reichen eine Suche und ein optionales Antwortmodell. Router und Agenten wurden hier nicht implementiert.

## Testlabor: Rechteentzug auf derselben Suche

1. Als Bob anmelden und nach **Nordstern 482** suchen. Die HR-Quelle erscheint.
2. Unter **Testlabor: HR-Zugriff entziehen** den Schalter aktivieren. Dieselbe Frage wird mit den neuen Rechten erneut ausgewertet. Titel und Text verschwinden.
3. Nach **Taxi Flughafen** suchen: Die gemeinsame Richtlinie bleibt sichtbar.
4. Den Schalter zurückstellen und erneut nach **Nordstern 482** suchen. Die HR-Quelle ist wieder sichtbar.

Der Schalter gilt nur für diese Demo-Sitzung. Er ändert keine echten Berechtigungen und entfernt kein Dokument aus dem Index. Er zeigt, warum Rechte zur Anfragezeit geprüft werden müssen und eine alte Trefferliste nicht als Berechtigungsnachweis genügt.

## Echter SharePoint-Test: vorbereitet, noch nicht ausgeführt

In einer freigegebenen Testbibliothek zwei fiktive Dateien anlegen: eine für den Testnutzer weiterhin lesbare Kontrolldatei und eine Zieldatei mit eindeutiger Testkennung. Der Testnutzer darf zuerst beide lesen. Nach dem ersten Lauf die Leseberechtigung der Zieldatei entziehen (auch geerbte Rechte und Freigabelinks berücksichtigen). Dasselbe Nutzerkonto und dieselbe Suche erneut prüfen.

Der Lesetest ruft Microsoft Graph im Namen dieses Nutzers auf. Er braucht die Bibliotheks-ID (Drive-ID), beide Datei-IDs und ein kurzlebiges delegiertes Graph-Token mit den nötigen Leserechten für `/me` und die Bibliothek. Das Token nur in die verdeckte Terminalabfrage eingeben. Keine Schreibrechte und kein Dienstkonto verwenden.

```bash
venv/bin/python scripts/check_sharepoint_access.py \
  --drive DRIVE_ID --control KONTROLLDATEI_ID --target ZIELDATEI_ID \
  --term Nordstern482 --expect visible
```

Nach dem Rechteentzug mit `--expect hidden` wiederholen. Erfolg vorher bedeutet: Treffer vorhanden und Metadaten direkt abrufbar. Erfolg nachher bedeutet: Kontrolldatei weiterhin lesbar, direkter Abruf der Zieldatei verweigert oder nicht gefunden. Ein eventuell noch vorhandener Suchtreffer wird getrennt ausgewiesen und wäre ohne erneute Prüfung kein zulässiger Beleg. Login- oder Verbindungsfehler sind kein bestandener Test.

Das Skript prüft Suchtreffer und Dateimetadaten, lädt keine Dateiinhalte herunter und übermittelt nichts an ein LLM. Es ist ein separater Graph-Lesetest, keine Live-SharePoint-Anbindung der Web-App. Für einen echten Lauf fehlt noch die freigegebene Testbibliothek mit Nutzerzugang.

[Microsoft Graph: Dateien in einer Bibliothek suchen](https://learn.microsoft.com/en-us/graph/api/driveitem-search?view=graph-rest-1.0)
