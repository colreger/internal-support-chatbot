from pypdf import PdfReader

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARACTERS = 200_000


def read_txt_file(uploaded_file):
    return uploaded_file.read().decode("utf-8-sig")


def read_pdf_file(uploaded_file):
    reader = PdfReader(uploaded_file)
    if len(reader.pages) > 100:
        raise ValueError("Für den Pilot sind maximal 100 PDF-Seiten erlaubt.")
    parts = []
    length = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        length += len(text)
        if length > MAX_TEXT_CHARACTERS:
            raise ValueError("Zu viel Text. Bitte ein kleineres Dokument verwenden.")
        parts.append(text)
    return "\n".join(parts)


def chunk_text(text, chunk_size=1000):
    if chunk_size <= 0:
        raise ValueError("Chunkgröße muss positiv sein.")
    return [part for start in range(0, len(text), chunk_size)
            if (part := text[start:start + chunk_size]).strip()]
