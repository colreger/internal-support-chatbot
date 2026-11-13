"""Privacy-first local pilot: no external LLM call without preview and explicit send."""
import hashlib
import io
import json
import os
from contextlib import nullcontext
from pathlib import Path
import time
from threading import Lock

import streamlit as st

from claims import claim_with_policy
from support_workflow import answer_travel_question
from company_library import CompanyLibrary
from auth import authenticate, load_users, valid_session
from answer_machine import NVIDIA_BASE_URL, external_enabled, request_message
from document_processor import (MAX_TEXT_CHARACTERS, MAX_UPLOAD_BYTES, chunk_text,
                                read_pdf_file, read_txt_file)
from embeddings import create_embeddings, create_query_embedding
from rag_logging import log_operation
from rag_service import RagService
from tool_calling import (CALC_QUESTION, CALCULATOR_NAME, DEMO_QUESTION,
                          build_tool_followup, build_tool_request, offline_message)
from vector_store import DocumentStore

st.set_page_config(page_title="RAG · Datenschutz-Pilot", page_icon="🔐")
st.title("Internal Support Chatbot")
st.caption("Datenschutz-Pilot · lokale Suche zuerst · externe Weitergabe nur nach Freigabe")


@st.cache_resource
def login_limits():
    return {}, Lock()


def clear_transient():
    for key in ("preview", "passages", "answer", "confirm_send"):
        st.session_state.pop(key, None)


def require_login():
    try:
        users, config_version = load_users()
    except (ValueError, OSError):
        st.error("Die Kontenkonfiguration ist nicht lesbar. Bitte lokal prüfen.")
        st.stop()
    if not users:
        st.info("Zuerst lokale Testkonten anlegen: `venv/bin/python scripts/setup_demo.py`.")
        st.caption("Es gibt kein Standardpasswort und keinen Zugriff ohne Anmeldung.")
        st.stop()
    if not valid_session(st.session_state.get("login"), users, config_version):
        if "login" in st.session_state:
            st.session_state.clear()
        st.info("Mit einem lokalen Pilotkonto anmelden. Die Sitzung gilt 30 Minuten.")
        login_area = st.empty()
        with login_area.form("login_form", clear_on_submit=True):
            username = st.text_input("Konto", max_chars=100)
            password = st.text_input("Passwort", type="password", max_chars=200)
            submitted = st.form_submit_button("Anmelden")
        if submitted:
            username = username.strip()
            attempts, lock = login_limits()
            # In-memory per-account limit; managed identity is still required for public deployment.
            bucket = hashlib.sha256(username.encode()).hexdigest()
            now = time.time()
            with lock:
                recent = [t for t in attempts.get(bucket, []) if now - t < 60]
                allowed = len(recent) < 5
                if allowed:
                    recent.append(now)
                if len(attempts) > 1000:
                    attempts.clear()
                attempts[bucket] = recent
            if not allowed:
                st.error("Zu viele Versuche. Bitte nach einer Minute erneut versuchen.")
            elif authenticate(username, password, users):
                login_area.empty()
                st.session_state.clear()
                st.session_state.login = {"owner": username, "config_version": config_version,
                                          "issued_at": time.time()}
                st.rerun()
            else:
                st.error("Anmeldung nicht möglich.")
        st.stop()
    return st.session_state.login["owner"]


preview_mode = os.environ.get("RAG_LOCAL_PREVIEW") == "true"
if preview_mode and st.get_option("server.address") not in ("127.0.0.1", "::1"):
    st.error("Die Vorschau ohne Anmeldung benötigt eine lokale Bindung an 127.0.0.1 oder ::1.")
    st.stop()
# The preview uses the employee fixture only; it never opens private storage.
owner = "gandalf" if preview_mode else require_login()


@st.cache_resource
def get_store():
    return DocumentStore()


def show_passages(passages):
    for i, passage in enumerate(passages, 1):
        with st.expander(f"[{i}] {passage.source} · Abschnitt {passage.index + 1}", expanded=True):
            st.text(passage.text)


with st.sidebar:
    st.header("Dein Bereich")
    if preview_mode:
        st.info("Lokale Gastvorschau · fiktives Firmenwissen und Websuche")
    else:
        st.write(f"Angemeldet: **{owner}**")
        st.caption("Die Firmenbibliothek ist gemeinsam. Deine eigenen Uploads bleiben privat.")
        if st.button("Abmelden und Sitzung leeren"):
            st.session_state.clear()
            st.rerun()
        if st.button("Fragen, Antwort und Upload-Puffer leeren"):
            login = st.session_state.login
            st.session_state.clear()
            st.session_state.login = login
            st.rerun()
        st.caption("Sitzung leeren löscht keine gespeicherten Dokumente. Dafür unten die Dokumentlöschung nutzen.")
    st.divider()
    st.subheader("Externe KI")
    if external_enabled():
        st.warning("NVIDIA ist serverseitig erlaubt. Jede Anfrage braucht einen Sende-Klick. "
                   "Private Dokumente brauchen zusätzlich eine Freigabe.")
    else:
        st.success("Gesperrt: Es werden keine Fragen oder Quellen an NVIDIA geschickt.")
    st.caption("Embeddings werden lokal aus bereits heruntergeladenen Modellgewichten berechnet.")

if preview_mode:
    langchain_tab, tool_tab = st.tabs(["LangChain", "Tool Calling"])
else:
    langchain_tab, company_tab, claims_tab, tool_tab, upload_tab, query_tab, privacy_tab = st.tabs(
        ["LangChain", "Firmenwissen (Testdaten)", "Reisekostenstatus", "Tool Calling", "Private Uploads",
         "Private Suche", "Datenschutz-Demo"]
    )

with langchain_tab:
    st.subheader("LangChain-Chat mit NVIDIA")
    st.caption("Wähle ein Beispiel für Firmenwissen, Reisekosten oder Websuche.")
    example = st.radio("LangChain-Beispiel", ["Firmenwissen", "Reisekosten", "Websuche"], horizontal=True)
    default_question = {
        "Firmenwissen": DEMO_QUESTION,
        "Reisekosten": CALC_QUESTION,
        "Websuche": "Suche im Web nach der offiziellen Python-Dokumentation zu virtuellen Umgebungen.",
    }[example]
    langchain_question = st.text_area("Frage für NVIDIA", value=default_question, max_chars=2000,
                                      key=f"langchain_question_{example}")
    if not external_enabled():
        st.info("Für diesen Chat die App mit RAG_ALLOW_EXTERNAL=true und NVIDIA_API_KEY starten.")
    if st.button("Frage an NVIDIA senden", key="langchain_send", type="primary",
                 disabled=not external_enabled() or not langchain_question.strip()):
        st.session_state.pop("langchain_demo_chat", None)
        try:
            from examples.langchain_recovery.travel_tool import (
                WEB_SEARCH, chat_messages, get_tool_call, run_tool_call, send_chat,
            )

            messages = chat_messages(langchain_question)
            response = send_chat(messages, offer_tool=True)
            chat = {"question": langchain_question}
            if response.tool_calls or response.invalid_tool_calls:
                call = get_tool_call(response)
                chat["call"] = call
                chat["followup"] = [*messages, response]
                if call["name"] != WEB_SEARCH.name:
                    chat["followup"].append(run_tool_call(response))
            else:
                chat["answer"] = response.text or "Keine Antwort erhalten."
            st.session_state.langchain_demo_chat = chat
        except ModuleNotFoundError:
            st.error("LangChain fehlt. Installiere examples/langchain_recovery/requirements.txt.")
        except Exception:
            st.error("Der LangChain-Aufruf konnte nicht abgeschlossen werden. Prüfe den NVIDIA-Schlüssel und den Tool-Aufruf.")

    langchain_chat = st.session_state.get("langchain_demo_chat")
    if langchain_chat and langchain_chat["question"] == langchain_question:
        if "call" in langchain_chat:
            st.markdown("**Vom Modell vorgeschlagener Tool-Aufruf**")
            st.json(langchain_chat["call"])
            followup = langchain_chat["followup"]
            if len(followup) == 3:
                st.caption("Bei der Websuche gehen die oben angezeigten Suchbegriffe an Brave Search.")
                if st.button("Suchbegriffe an Brave senden", key="langchain_send_web"):
                    try:
                        from examples.langchain_recovery.travel_tool import run_tool_call

                        followup.append(run_tool_call(followup[-1], allow_web=True))
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception:
                        st.error("Die Websuche konnte nicht ausgeführt werden.")
        if "call" in langchain_chat and len(followup) == 4:
            st.markdown("**Tool-Ergebnis**")
            st.json(json.loads(followup[-1].content))
            if st.button("Tool-Ergebnis an NVIDIA senden", key="langchain_send_result",
                         disabled=not external_enabled()):
                try:
                    from examples.langchain_recovery.travel_tool import send_chat

                    response = send_chat(followup, offer_tool=False)
                    langchain_chat["answer"] = response.text or "Keine Antwort erhalten."
                except Exception:
                    st.error("NVIDIA konnte das Tool-Ergebnis nicht formulieren.")
        if "answer" in langchain_chat:
            st.markdown("**Antwort von NVIDIA**")
            st.text(langchain_chat["answer"])



@st.cache_resource
def get_company_library():
    return CompanyLibrary.load_demo()


library = get_company_library()


with tool_tab:
    st.subheader("Tool Calling für fiktive Reisekosten")
    scenario = st.radio("Beispiel", ["Abrechnung prüfen", "Richtlinie suchen"], horizontal=True)
    tool_question = CALC_QUESTION if scenario == "Abrechnung prüfen" else DEMO_QUESTION
    st.write(tool_question)
    st.caption("Das Modell wählt zwischen Rechner und Suche. Python prüft den Aufruf und führt das Tool lokal aus.")
    if tool_question == CALC_QUESTION:
        st.caption("Fiktive Demo-Regel · 120 € pro Hotelnacht · genehmigtes Taxi voll · private Ausgaben ausgeschlossen")
    live = external_enabled() and st.toggle("Live-Modus mit NVIDIA", key="tool_demo_live")
    if not live:
        st.caption("Offline-Demo mit vorbereitetem Tool-Aufruf. Das Ergebnis wird lokal ermittelt.")

    tool_request = build_tool_request(tool_question)
    with st.expander("1 · Frage und Tool-Schema prüfen"):
        st.json(tool_request)
    if st.button("Anfrage an NVIDIA senden" if live else "Offline-Beispiel ausführen", key="tool_demo_run"):
        st.session_state.pop("tool_demo_result", None)
        try:
            if live:
                reply = request_message(tool_request)
                if reply.invalid_tool_calls:
                    raise ValueError("Das Modell hat ungültige Tool-Argumente geliefert.")
                message = {"tool_calls": [
                    {
                        "id": call.get("id"),
                        "type": "function",
                        "function": {"name": call["name"], "arguments": json.dumps(call["args"])},
                    }
                    for call in reply.tool_calls
                ]}
            else:
                message = offline_message(tool_question)
            followup = build_tool_followup(tool_request, message, library, owner)
        except ValueError as exc:
            st.error(f"Tool-Demo abgebrochen: {exc}" if not live else "Die Tool-Demo konnte nicht ausgeführt werden.")
        except Exception:
            st.error("NVIDIA-Anfrage fehlgeschlagen. Du kannst die Offline-Demo verwenden.")
        else:
            if followup is None:
                st.info("Das Modell hat keinen Tool-Aufruf geliefert.")
            else:
                st.session_state.tool_demo_result = {"live": live, "question": tool_question, "followup": followup}

    tool_result = st.session_state.get("tool_demo_result")
    if tool_result and tool_result.get("question") == tool_question and tool_result["live"] == live:
        followup = tool_result["followup"]
        tool_call = followup["messages"][-2]["tool_calls"][0]
        tool_content = followup["messages"][-1]["content"]
        st.markdown("**2 · Tool-Aufruf**")
        st.json(tool_call)
        st.markdown("**3 · Lokales Tool-Ergebnis**")
        if tool_call["function"]["name"] == CALCULATOR_NAME:
            calculation = json.loads(tool_content)
            st.metric("Erstattungsfähig nach Demo-Regel", calculation["reimbursable_eur"])
            st.json(calculation)
        else:
            st.text(tool_content)
        with st.expander("4 · Zweite Anfrage mit Tool-Ergebnis prüfen"):
            st.json(followup)
        if live and st.button("Tool-Ergebnis an NVIDIA senden", key="tool_demo_send_result"):
            tool_result.pop("answer", None)
            try:
                tool_result["answer"] = request_message(followup).content or "Keine Antwort erhalten."
            except Exception:
                st.error("Die externe Antwort konnte nicht erstellt werden.")
        if live and "answer" in tool_result:
            st.markdown("**Antwort von NVIDIA**")
            st.text(tool_result["answer"])


if preview_mode:
    st.stop()


with claims_tab:
    st.subheader("Reisekostenstatus")
    st.caption("Fiktive Kommunalverwaltung · Die Abfrage verwendet dein angemeldetes Konto.")
    with st.form("claim_status"):
        claim_id = st.text_input("Vorgangsnummer", value="RK-1042", max_chars=20)
        submitted = st.form_submit_button("Status abrufen")
    if submitted:
        try:
            claim = claim_with_policy(library, owner, claim_id.strip())
        except (ValueError, LookupError) as exc:
            st.error(str(exc))
        else:
            if claim is None:
                st.info("Kein sichtbarer Vorgang gefunden.")
            else:
                st.write(claim["status"])
                st.write(claim["deduction_reason"])
                st.caption(claim["policy_title"])
                st.text(claim["policy_excerpt"])


    st.subheader("Frage zu Reisekosten")
    with st.form("travel_question"):
        question = st.text_input(
            "Reisekostenfrage", placeholder="Wie ist der Stand von RK-1042?", max_chars=2000
        )
        asked = st.form_submit_button("Frage stellen")
    if asked:
        try:
            result = answer_travel_question(library, owner, question)
        except (ValueError, LookupError) as exc:
            st.error(str(exc))
        else:
            st.write(result["answer"])
            for source in result["sources"]:
                st.caption(f"Quelle: {source['title']}")
                if source["excerpt"] != result["answer"]:
                    st.text(source["excerpt"])


store = get_store()
service = RagService(store, create_query_embedding)

def clear_company_answer():
    st.session_state.pop("company_answer", None)
    st.session_state.pop("company_confirm_send", None)


with company_tab:
    st.subheader("Frag die Firmenbibliothek")
    st.caption("Fiktive Firmenbibliothek auf diesem Rechner. Die Dokumente sind bereits eingebunden.")
    hr_revoked = False
    if owner == "galadriel":
        with st.expander("Testlabor: HR-Zugriff entziehen"):
            st.caption("Nur für diese Demo-Sitzung. Das Testdokument bleibt in derselben Bibliothek.")
            hr_revoked = st.toggle("HR-Zugriff in dieser Sitzung entziehen", key="demo_hr_revoked",
                                   on_change=clear_company_answer)
            st.write("HR-Zugriff entzogen" if hr_revoked else "HR-Zugriff aktiv")
    with st.expander("Dokumente, die mein Konto lesen darf"):
        for title in library.titles(owner, hr_revoked=hr_revoked):
            st.text(title)
    with st.form("company_search"):
        company_question = st.text_input("Frage zum Firmenwissen", max_chars=2000,
                                         placeholder="Darf ich bei einer Dienstreise ein Taxi zum Flughafen nehmen?")
        company_search = st.form_submit_button("Firmenwissen durchsuchen", type="primary")
    if company_search:
        clear_company_answer()
        st.session_state.company_question = company_question.strip()
    if question := st.session_state.get("company_question"):
        # Streamlit reruns the view on other interactions; measure only a search click.
        with log_operation("company_search") if company_search else nullcontext() as event:
            hits = library.search(owner, question, hr_revoked=hr_revoked)
            if event is not None and not hits:
                event["status"] = "no_match"
        if not hits:
            st.info("Zu dieser Frage wurde keine passende, für dein Konto verfügbare Quelle gefunden.")
        else:
            st.markdown("**Passende Textstelle**")
            st.text(hits[0].text)
            st.caption(f"Quelle: {hits[0].title} · Originalauszug, keine KI-generierte Antwort")
            if len(hits) > 1:
                with st.expander("Weitere passende Quellen"):
                    for hit in hits[1:]:
                        st.markdown(f"**{hit.title}**")
                        st.text(hit.text)
            request = library.preview(owner, question, hr_revoked=hr_revoked)
            if request is None:
                st.caption("Diese Treffer sind nur für die lokale Suche freigegeben.")
            elif external_enabled():
                with st.expander("Anfrage an NVIDIA vorab prüfen"):
                    st.json(request)
                confirmed = st.checkbox("Ich möchte diese Frage und die angezeigten Textstellen an NVIDIA senden.",
                                        key="company_confirm_send")
                if st.button("Antwort mit NVIDIA formulieren", disabled=not confirmed):
                    try:
                        with log_operation("company_model_call"):
                            st.session_state.company_answer = library.send(
                                owner, question, request, hr_revoked=hr_revoked
                            )
                    except Exception:
                        st.error("Die externe Antwort konnte nicht erstellt werden.")
                if answer := st.session_state.get("company_answer"):
                    st.markdown("**Antwort von NVIDIA**")
                    st.text(answer)
            else:
                st.caption("Die Suche bleibt lokal. Externe KI ist derzeit ausgeschaltet.")


with upload_tab:
    st.subheader("Dokument lokal vorbereiten")
    st.info("Nur erfundene oder ausdrücklich freigegebene, nicht vertrauliche Pilotdaten verwenden.")
    st.caption("Originaldateien werden nicht auf Festplatte gespeichert. Vor dem Indexieren kannst du unnötige Angaben entfernen.")
    uploaded = st.file_uploader("PDF oder UTF-8-TXT (max. 5 MB)", type=["pdf", "txt"])
    if uploaded is not None and st.button("Text lokal auslesen"):
        try:
            with log_operation("document_extract"):
                if uploaded.size > MAX_UPLOAD_BYTES:
                    raise ValueError("Die Datei überschreitet 5 MB.")
                buffer = io.BytesIO(uploaded.getvalue())
                text = read_pdf_file(buffer) if uploaded.name.lower().endswith(".pdf") else read_txt_file(buffer)
                if not text.strip():
                    raise ValueError("Kein lesbarer Text. Scan-PDFs benötigen OCR.")
                if len(text) > MAX_TEXT_CHARACTERS:
                    raise ValueError("Für den Pilot sind maximal 200.000 Zeichen erlaubt.")
            st.session_state.draft_text = text
            st.session_state.draft_title = "Mein Testdokument"
            st.session_state.draft_external = False
            st.session_state.pilot_data = False
            st.rerun()
        except (ValueError, UnicodeError):
            st.error("Datei nicht lesbar oder zu groß. Bitte eine UTF-8-TXT-Datei oder ein textbasiertes PDF innerhalb der Grenzen verwenden.")
        except Exception:
            st.error("Dokument konnte nicht ausgelesen werden. Es wurde nicht indexiert.")
    if "draft_text" in st.session_state:
        with st.form("index_document"):
            title = st.text_input("Neutraler Dokumenttitel (keine Personenangaben)", key="draft_title", max_chars=120)
            edited_text = st.text_area("Text prüfen und unnötige Angaben vor dem Speichern entfernen",
                                      key="draft_text", height=230, max_chars=MAX_TEXT_CHARACTERS)
            pilot_data = st.checkbox("Das sind erfundene oder freigegebene, nicht vertrauliche Testdaten.", key="pilot_data")
            external_approved = st.checkbox("Dieses Dokument darf nach separater Vorschau an NVIDIA übermittelt werden.",
                                           key="draft_external")
            index_clicked = st.form_submit_button("Geprüften Text lokal indexieren")
        if index_clicked:
            if not pilot_data:
                st.error("Bitte zuerst die Eignung der Pilotdaten bestätigen.")
            else:
                try:
                    with log_operation("document_index"):
                        chunks = chunk_text(edited_text)
                        if not title.strip() or not chunks:
                            raise ValueError("Titel und lesbarer Text sind erforderlich.")
                        with st.spinner("Lokale Embeddings werden berechnet …"):
                            doc_id = store.add(owner, title, chunks, create_embeddings(chunks),
                                               external_approved=external_approved)
                    clear_transient()
                    # Clear upload/editor buffers on a fresh widget run.
                    login = st.session_state.login
                    st.session_state.clear()
                    st.session_state.login = login
                    st.session_state.notice = f"Dokument lokal gespeichert: {len(chunks)} Abschnitte."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("Indexierung fehlgeschlagen. Modellgewichte müssen lokal vorhanden sein. Bitte den Dokumentbestand prüfen, bevor du es erneut versuchst.")
    if notice := st.session_state.pop("notice", None):
        st.success(notice)

    st.divider()
    st.subheader("Deine gespeicherten Dokumente")
    documents = store.documents(owner)
    if not documents:
        st.caption("Noch keine Dokumente in diesem Konto.")
    for doc in documents:
        with st.expander(f"{doc['source']} · {doc['chunks']} Abschnitte"):
            st.caption(f"Dokument-ID: {doc['document_id']}")
            st.write("Externe Freigabe: " + ("erteilt" if doc["external_approved"] else "gesperrt"))
            if st.button("Externe Freigabe " + ("widerrufen" if doc["external_approved"] else "erteilen"),
                         key=f"approve_{doc['document_id']}"):
                store.approve_external(owner, doc["document_id"], not doc["external_approved"])
                clear_transient()
                st.rerun()
            confirm_delete = st.checkbox("Dieses Dokument mit allen Chunks und Vektoren löschen",
                                         key=f"delete_confirm_{doc['document_id']}")
            if st.button("Dokument endgültig aus aktivem Suchbestand löschen", disabled=not confirm_delete,
                         key=f"delete_{doc['document_id']}"):
                with log_operation("document_delete"):
                    removed = store.delete(owner, doc["document_id"])
                login = st.session_state.login
                st.session_state.clear()
                st.session_state.login = login
                st.session_state.notice = f"{removed} Chunks samt Vektoren entfernt. Direkter Dokumentabruf ist ebenfalls leer."
                st.rerun()

with query_tab:
    st.subheader("Nur in deinem ausgewählten Dokument suchen")
    documents = store.documents(owner)
    if documents:
        options = {doc["document_id"]: doc for doc in documents}
        selected = st.selectbox("Dokument", list(options), format_func=lambda key: options[key]["source"])
        if st.session_state.get("selected_document") != selected:
            clear_transient()
            st.session_state.pop("question_input", None)
            st.session_state.selected_document = selected
        with st.form("search_form"):
            question = st.text_input("Deine Frage (keine unnötigen Personenangaben)", key="question_input", max_chars=2000)
            search_clicked = st.form_submit_button("Lokal suchen und Anfragevorschau erstellen")
        if search_clicked:
            clear_transient()
            try:
                with st.spinner("Suche nur in deinem Dokument …"):
                    with log_operation("private_retrieval"):
                        preview, passages = service.preview_with_passages(owner, selected, question)
                st.session_state.preview = preview
                st.session_state.passages = passages
            except (PermissionError, ValueError) as exc:
                st.error(str(exc))
            except Exception:
                st.error("Lokale Suche nicht möglich. Bitte lokale Modellinstallation und Dokumentbestand prüfen.")
        preview = st.session_state.get("preview")
        if preview and preview.document_id == selected:
            st.markdown("**Gefundene Quellen – noch nichts an NVIDIA gesendet**")
            st.caption("Ähnlichkeit ist kein Beweis, dass die Frage beantwortbar ist. Prüfe die Textstellen.")
            show_passages(st.session_state.passages)
            with st.expander("Genau diese Anfrage würde NVIDIA erhalten", expanded=False):
                st.caption(f"Empfänger: {NVIDIA_BASE_URL}. Kein API-Schlüssel, Kontoname, Dateiname oder Chatverlauf im Inhalt.")
                st.json(json.loads(preview.payload_json))
            doc = store.document(owner, selected)
            allowed = external_enabled() and doc is not None and doc["external_approved"]
            st.caption("Lokal suchen ist keine Modellantwort. Für eine formulierte Antwort wäre die sichtbare Anfrage an NVIDIA nötig.")
            confirmed = st.checkbox("Ich habe Frage und Quellen geprüft und möchte genau diese Inhalte an NVIDIA senden.",
                                    key="confirm_send", disabled=not allowed)
            if st.button("Geprüfte Anfrage jetzt an NVIDIA senden", disabled=not (allowed and confirmed)):
                try:
                    with st.spinner("NVIDIA antwortet …"):
                        with log_operation("private_model_call"):
                            st.session_state.answer = service.send(owner, preview)
                except (PermissionError, ValueError) as exc:
                    st.error(str(exc))
                except Exception:
                    # Never show provider exception bodies, which may contain request content.
                    st.error("Die externe Anfrage ist fehlgeschlagen. Es werden keine Anfrageinhalte protokolliert.")
            if answer := st.session_state.get("answer"):
                st.markdown("**Antwort von NVIDIA**")
                # Plain text avoids remote image fetching and executable/hidden markup.
                st.text(answer)
    else:
        st.info("Lade zuerst ein Dokument hoch oder verwende die fiktive Datenschutz-Demo.")

with privacy_tab:
    st.subheader("Die drei Schutzmaßnahmen selbst ausprobieren")
    st.markdown("""
1. **Firmenbibliothek:** Gandalf und Galadriel können die Reisekostenrichtlinie suchen. Nur Galadriel findet die interne Gehaltsband-Prüfung.
2. **Private Uploads:** Lege unten ein fiktives Dokument an. Melde dich danach mit dem anderen Konto an: Titel, Quellen und Inhalte dürfen dort nicht erscheinen.
3. **Weitergabe kontrollieren:** Suche lokal nach Fortbildungstagen. Öffne die Anfragevorschau. Ohne serverseitige Erlaubnis und Dokumentfreigabe bleibt der Sende-Knopf gesperrt.
4. **Löschung:** Notiere die Dokument-ID, lösche das Dokument unter „Private Uploads“ und kontrolliere: Es fehlt in der Auswahl und kann nicht mehr durchsucht werden. Automatisierte Tests prüfen zusätzlich alte Chunk-IDs.
""")
    st.caption("Fiktive Kennungen: gandalf → Gandalf-KIESEL-731 / 17 Tage; galadriel → Galadriel-LINDE-942 / 29 Tage.")
    if st.button("Fiktives Testdokument für mein Konto anlegen"):
        sample = "gandalf" if owner == "gandalf" else "galadriel" if owner == "galadriel" else None
        text = ((Path(__file__).parent / "demo" / f"{sample}.txt").read_text()
                if sample else "Fiktive Richtlinie: 11 Fortbildungstage pro Jahr.")
        try:
            with st.spinner("Demo lokal indexieren …"):
                store.add(owner, "Fiktive Fortbildungsrichtlinie", chunk_text(text),
                          create_embeddings(chunk_text(text)))
            clear_transient()
            st.rerun()
        except Exception:
            st.error("Demo nicht indexiert. Bitte zuerst das Embedding-Modell lokal bereitstellen.")
    st.divider()
    st.markdown("""
**Was wird gespeichert?** Nur der geprüfte Text als Chunks, Vektoren, Kontozuordnung, neutraler Titel, Zeitstempel und externe Freigabe. Originaldateien und Fragen/Antworten werden nicht in die Datenbank geschrieben. Upload-Puffer, Vorschau und letzte Antwort liegen vorübergehend in der Serversitzung; der Button zum Leeren entfernt sie aus dem aktiven Sitzungszustand.

**Wie lange?** Indexierte Dokumente bleiben bis zur manuellen Löschung bestehen. Es gibt keine automatische Löschfrist. Eine Sitzung ist 30 Minuten gültig; Abmelden leert ihren aktiven Zustand. Das ist keine Zusicherung einer sofortigen forensischen Löschung aus RAM, Browser oder Streamlit-internen Puffern.

**Grenzen:** Nur lokaler Pilot mit Testdaten. Die Kontenanmeldung ersetzt kein Unternehmens-SSO. Löschung betrifft den aktiven Chroma-Bestand, keine garantierte physische Überschreibung von Datenträgern, Backups oder bereits an NVIDIA gesendeten Inhalten. Anbieterverträge, Rechtsgrundlage und produktiver Betrieb müssen gesondert geprüft werden.
""")
    st.caption("Alte Daten aus ./chroma_db werden nicht importiert oder durchsucht. Sie werden auch nicht automatisch gelöscht.")
