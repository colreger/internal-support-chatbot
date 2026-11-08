# Beispiel einer Datenschutz-Folgenabschätzung für den RAG-Assistenten

Stand 8. November 2026 · Portfolio-Entwurf für einen fiktiven betrieblichen Einsatz · Entscheidung für einen konkreten Betrieb offen

## 1. Vorprüfung nach Art. 35 DSGVO

Die DSFA-Schwelle ist ein **voraussichtlich hohes Risiko für die Rechte und Freiheiten natürlicher Personen**. Entscheidend sind Art, Umfang, Umstände und Zweck der konkreten Verarbeitung. Art. 35 Abs. 3 nennt insbesondere systematische, umfassende automatisierte Bewertungen als Grundlage für Entscheidungen mit erheblicher Wirkung, umfangreiche Verarbeitung von Daten nach Art. 9 oder 10 und systematische umfangreiche Überwachung öffentlich zugänglicher Bereiche. Zusätzlich ist die Muss-Liste der zuständigen Aufsicht zu prüfen. In der DSK-Liste für den nichtöffentlichen Bereich erfasst Nr. 11 unter anderem KI, die personenbezogene Daten nutzt, um die Interaktion mit Betroffenen zu steuern oder persönliche Aspekte zu bewerten. [Art. 35 DSGVO](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32016R0679#art_35) · [DSK-Muss-Liste](https://www.datenschutzkonferenz-online.de/media/ah/20181017_ah_DSK_DSFA_Muss-Liste_Version_1.1_Deutsch.pdf)

| Einsatz | Vorläufige Entscheidung |
| --- | --- |
| Lokale Demo mit fiktiven Dokumenten und Testfragen, kleinem Nutzerkreis, ohne externe KI und ohne Personenbewertung | Eine Pflicht zur vollständigen DSFA ist unter diesen Annahmen derzeit nicht erkennbar. Konten, Sitzungen, Betriebsdaten und versehentliche Eingaben separat berücksichtigen. Die Anwendung erlaubt freie Uploads und Fragen. Die Annahme fiktiver Inhalte hängt daher von der tatsächlichen Nutzung ab. |
| Interne Suche über freigegebene Unternehmensrichtlinien mit echten Nutzerkonten | Vor Beginn eine eigene Vorprüfung dokumentieren. Datenumfang, personenbezogene Freitexte, Empfänger, Zugriffsmöglichkeiten und die anwendbare Muss-Liste prüfen. Der DSFA-Entwurf unten geht von einer begrenzten internen Suche aus. |
| Echte Personalakten, Gesundheitsdaten, personenbezogene Beratung oder Bewerberbewertung | Eigenen Einsatzfall vorab prüfen. Umfangreiche Verarbeitung besonderer Kategorien fällt unter Art. 35 Abs. 3 Buchst. b. Personenbezogene KI-Beratung oder Bewertung kann unter Nr. 11 der Muss-Liste fallen. KI zur Bewerberauswahl oder Leistungsbewertung kann zusätzlich Hochrisiko-KI nach Art. 6 und Anhang III Nr. 4 des AI Act sein. |

**Separater AI-Act-Check.** Der beabsichtigte Zweck ist die interne Suche nach Richtlinien und Arbeitsanweisungen mit Quellen. Dafür ist nach aktuellem Stand kein Hochrisiko-Tatbestand ersichtlich. Bei generierten Antworten die Transparenzpflichten nach Art. 50 gesondert prüfen. Art. 27 sieht für bestimmte Betreiber und Hochrisiko-Einsätze eine eigene Grundrechte-Folgenabschätzung vor. Einschlägige Teile einer DSFA können dort wiederverwendet oder referenziert werden. [AI Act, Art. 2 Abs. 7, Art. 6, 26 Abs. 9, 27, 50 und Anhang III](https://eur-lex.europa.eu/eli/reg/2024/1689/2026-07-27/deu/pdf)

## 2. Verarbeitung und Zweck · Art. 35 Abs. 7 Buchst. a

- **Geplanter Zweck.** Mitarbeitende finden gültige interne Richtlinien und Arbeitsanweisungen und können die Fundstelle prüfen. Personalentscheidungen, individuelle Leistungsüberwachung und personenbezogene Fallberatung liegen außerhalb dieses Einsatzfalls.
- **Betroffene und Daten.** Mitarbeitende mit Zugang sowie gegebenenfalls Personen, die in freigegebenen Dokumenten oder Fragen vorkommen. Erfasst werden Kontokennungen, Fragen, Textabschnitte, Embeddings, Zugriffsmetadaten, Ausgaben und Betriebsereignisse. Vor der Bewertung tatsächliche Datenquellen, Personengruppen, Umfang und Nutzungshäufigkeit eintragen.
- **Datenfluss des Piloten.** Private Uploads werden eingelesen, lokal eingebettet und als Textabschnitte und Vektoren mit Kontozuordnung in Chroma abgelegt. Die fiktive Firmenbibliothek ist davon getrennt und filtert nach Zugriffsberechtigung. Sitzungsdaten liegen vorübergehend im Serverspeicher. [Umsetzung und Speicherorte](datenschutz-praxis.md) · [Firmenbibliothek](firmenwissen.md)
- **Empfänger und Speicherfristen.** Im Pilot ist externe Generierung standardmäßig aus. Der optionale NVIDIA-Pfad übermittelt nach technischer Freigabe und explizitem Senden die Frage und ausgewählte Textstellen. Die separate optionale Websuche sendet nach Bestätigung öffentliche Suchbegriffe an Brave Search. Dokumente im aktiven privaten Index bleiben bis zur manuellen Löschung. Für den Zielbetrieb Verantwortlichen, Administratoren, Hosting, gegebenenfalls Auftragsverarbeiter, Datenstandorte, Drittlandzugriffe, Speicherfristen und Backup-Löschung eintragen.
- **Tool-Calling-Demos.** Die direkte Demo verwendet feste Testfragen. Der LangChain-Tab erlaubt Freitext und sendet die Frage samt Tool-Beschreibungen auf Klick an NVIDIA. Nach der Ausführung eines Tools kann ein weiterer Klick das angezeigte Ergebnis zur Antwortformulierung an NVIDIA senden. Für Websuche wird die angezeigte Suchanfrage separat an Brave gesendet. Die Firmenwissenssuche im LangChain-Tab verwendet freigegebene fiktive Richtlinien. Für den betrieblichen Einsatz sind Freitexte und alle Übermittlungen gesondert zu bewerten. [Tool-Calling-Demos](../README.md#tool-calling-demo)

## 3. Erforderlichkeit und Verhältnismäßigkeit · Art. 35 Abs. 7 Buchst. b

Mit kuratierten, freigegebenen Richtlinien und lokaler Quellensuche beginnen. Für jeden zusätzlichen Datenbestand begründen, warum der Zweck ihn erfordert und welche Felder entfernt werden können. Vor optionaler Generierung dokumentieren, welchen Zusatznutzen sie gegenüber der Quellensuche bringt und ob externe Verarbeitung dafür erforderlich ist. Im Zielbetrieb Rechtsgrundlage je Verarbeitung, Datenschutzhinweise, Fristen und Ablauf für Auskunft, Berichtigung und Löschung festlegen. Bei externen Diensten Anbieterrolle, gegebenenfalls Auftragsverarbeitungsvertrag, Unterauftragnehmer, Aufbewahrung, Trainingsnutzung und Übermittlungsgrundlage prüfen. Die Bestätigung im UI dient der technischen Kontrolle der Übermittlung. Die Rechtsgrundlage ist separat zu bestimmen.

## 4. Risiken, Maßnahmen und Nachweise · Art. 35 Abs. 7 Buchst. c und d

Die Einschätzung der Schwere bezieht sich auf mögliche Folgen für Personen im Zielbetrieb. Eintrittswahrscheinlichkeit und Restrisiko bleiben bis zur Prüfung der tatsächlichen Daten und Betriebsumgebung offen. Pro Zeile im Zielbetrieb Schwere, Wahrscheinlichkeit, Begründung, verantwortliche Rolle, Termin und Nachweis für das verbleibende Risiko ergänzen.

| Ereignis und mögliche Folge | Maßnahmen und Pilotnachweis | Prüfung vor dem Zielbetrieb |
| --- | --- | --- |
| Fremde Inhalte erscheinen in Treffern, Quellen oder Modellanfragen. Offenlegung vertraulicher Angaben kann Beschäftigten erheblich schaden. | Serverseitiger Kontofilter bei privaten Uploads, Rollenfilter in der Firmenbibliothek und erneute Prüfung vor dem Senden. Tests mit fremden IDs, gesperrter HR-Testquelle und Widerruf. | Abgleich mit den tatsächlichen Dokumentrechten, einschließlich direktem Abruf, Rechteentzug, aktiven Sitzungen und mehreren Instanzen. |
| Personenangaben gelangen aus Frage oder Quelle zum Modellanbieter. Je nach Inhalt kann die Offenlegung schwer wiegen. | Externe Generierung standardmäßig gesperrt. Freigabe, Vorschau und kontrollierte Nutzlast sind im Pilot mit Test-Sender geprüft. | Anbieterprüfung und technische Freigabe nur für zulässige Datenkategorien. Freitext und Quellen mit synthetischen Prüfdaten testen. |
| Gelöschte oder korrigierte Angaben bleiben in Index, Sitzung oder Backup auffindbar. Falsche Angaben können weiterverwendet werden. | Tests prüfen die Löschung aus dem aktiven Chroma-Index und den direkten Abruf alter IDs. | Löschfristen und Löschkette für Index, Sitzung, Protokolle, Backups und gegebenenfalls Dienstleister testen. Wiederherstellung mit bereits gelöschten Testdaten prüfen. |
| Eine falsche oder aus dem Kontext gelöste Antwort wird auf eine Person angewandt. Das kann zu einer ungerechtfertigten Entscheidung führen. | Lokale Originalstellen und Quellenangaben sind im Pilot vorgesehen. | Aktuelle und widersprüchliche Quellen, unbeantwortbare Fragen und Prompt-Injection testen. Personalsachverhalte an den vorgesehenen menschlichen Prozess verweisen. |

Nachweise im Repository: [Tests zur privaten Suche und externen Freigabe](../tests/test_privacy.py) · [Tests zur Firmenbibliothek](../tests/test_company_library.py).

## 5. Entscheidung und Aktualisierung

1. Der Verantwortliche hält Zweck, Datenquellen, Rollen, Hosting, Modellpfad, Rechtsgrundlagen und Umfang fest. Er dokumentiert das Ergebnis der Vorprüfung und zieht den Datenschutzbeauftragten hinzu, sofern benannt. Gegebenenfalls sind die Betroffenen oder ihre Vertretung einzubeziehen.
2. Bei DSFA-Pflicht vor Beginn der Verarbeitung die offenen Maßnahmen und Restrisiken bewerten und die Entscheidung dokumentieren. Bleibt ein hohes Risiko bestehen, vor der Verarbeitung die Aufsichtsbehörde nach Art. 36 DSGVO konsultieren.
3. Bei Änderungen mit Auswirkung auf das Risiko erneut prüfen. Beispiele sind neue Datenquellen, echte Personaldaten, weitere Nutzergruppen, Modell- oder Hostingwechsel, externe Übermittlung und eine neue Nutzung für Entscheidungen über Menschen.

[Bestehendes Datenschutzkonzept](Datenschutzkonzept_Entwurf_2026-11-05.md) · [DSGVO, Art. 35 und 36](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32016R0679#art_35) · [DSK-Orientierungshilfe für RAG](https://www.datenschutzkonferenz-online.de/media/oh/DSK_OH_RAG.pdf)
