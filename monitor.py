import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SOURCE_URL = (
    "https://sede.inap.gob.es/es/procedimientos-y-servicios/seleccion/"
    "procesos-selectivos-de-cuerpos-y-escalas-generales/"
    "cuerpo-general-administrativo-de-la-administracion-del-estado-"
    "ingreso-libre-convocatoria-2025"
)

STATE_FILE = Path("state.json")
MONITOR_SCOPE = "all-documents-v1"

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ods",
    ".odt",
    ".rtf",
    ".csv",
    ".zip",
    ".7z",
}

DOWNLOAD_MARKERS = (
    "/documents/",
    "/document_library/",
    "/download/",
    "/downloads/",
    "/descarga/",
    "/descargas/",
    "/dam/",
    "/sites/default/files/",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AGE-Documentos/4.0)",
    "Accept-Language": "es-ES,es;q=0.9",
}


def normalize(value):
    return str(value).translate(
        str.maketrans(
            "áéíóúüñÁÉÍÓÚÜÑ",
            "aeiouunAEIOUUN",
        )
    ).lower()


def is_document_link(link, href):
    parsed = urlparse(href)

    if parsed.scheme not in {"http", "https"}:
        return False

    path = unquote(parsed.path).lower()
    query = unquote(parsed.query).lower()
    extension = Path(path).suffix

    if extension in DOCUMENT_EXTENSIONS:
        return True

    if any(
        f"{candidate}" in query
        for candidate in DOCUMENT_EXTENSIONS
    ):
        return True

    if link.has_attr("download"):
        return True

    link_type = link.get("type", "").lower()

    if (
        link_type.startswith("application/")
        and "html" not in link_type
    ):
        return True

    return any(marker in path for marker in DOWNLOAD_MARKERS)


def get_category(value):
    value = normalize(value)
    general = bool(
        re.search(r"turno general|acceso general", value)
    )
    disability = "discapacidad" in value

    if general and disability:
        return "Turno general y discapacidad"

    if disability:
        return "Cupo de discapacidad"

    if general:
        return "Turno general"

    return "Documento publicado en la página del INAP"


def document_id(url):
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:20]


def scrape_inap():
    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.find("main") or soup
    documents = {}

    for link in content.find_all("a", href=True):
        href = urljoin(
            SOURCE_URL,
            link["href"],
        ).split("#")[0]

        if not is_document_link(link, href):
            continue

        title = (
            link.get_text(" ", strip=True)
            or link.get("aria-label", "").strip()
            or link.get("title", "").strip()
            or unquote(Path(urlparse(href).path).name)
            or "Documento del INAP"
        )

        container = link.find_parent(
            ["li", "p", "tr", "article", "section"]
        )
        context = (
            container.get_text(" ", strip=True)
            if container
            else title
        )
        combined = f"{title} {context} {href}"
        identifier = document_id(href)

        documents[identifier] = {
            "id": identifier,
            "title": title,
            "url": href,
            "category": get_category(combined),
        }

    return list(documents.values())


def fetch_documents():
    documents = scrape_inap()
    print("Consulta directa al INAP completada.")
    return documents


def load_state():
    if not STATE_FILE.exists():
        return {
            "processed": [],
            "heartbeat_week": "",
        }

    return json.loads(
        STATE_FILE.read_text(encoding="utf-8")
    )


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def safe_filename(document, response):
    parsed = urlparse(document["url"])
    original = unquote(
        Path(parsed.path).name
    )

    if not original:
        original = document["title"]

    original = re.sub(
        r'[\\/:*?"<>|]+',
        "-",
        original,
    ).strip()

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if "." not in Path(original).name:
        original += (
            ".pdf"
            if "pdf" in content_type
            else ".bin"
        )

    return original[:180]


def telegram_request(files, caption):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendDocument",
        data={
            "chat_id": chat_id,
            "caption": caption[:1000],
        },
        files=files,
        timeout=120,
    )

    if not response.ok:
        raise RuntimeError(
            f"Telegram HTTP {response.status_code}: "
            + response.text[:500]
        )

    payload = response.json()

    if not payload.get("ok"):
        raise RuntimeError(
            "Telegram rechazó el documento: "
            + response.text[:500]
        )


def send_test():
    telegram_request(
        files={
            "document": (
                "prueba-age-documentos.txt",
                (
                    b"El monitor de GitHub Actions "
                    b"funciona correctamente."
                ),
                "text/plain",
            )
        },
        caption="Prueba del monitor AGE",
    )

    print(
        "Archivo de prueba enviado "
        "correctamente a Telegram."
    )


def send_document(document):
    response = requests.get(
        document["url"],
        headers=HEADERS,
        timeout=60,
    )
    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if "text/html" in content_type:
        raise RuntimeError(
            "El enlace detectado no devolvió un archivo: "
            + document["url"]
        )

    filename = safe_filename(
        document,
        response,
    )

    caption = (
        "Nuevo documento AGE\n"
        f"{document['category']}\n"
        f"{document['title']}\n"
        f"{document['url']}"
    )

    telegram_request(
        files={
            "document": (
                filename,
                response.content,
                content_type
                or "application/octet-stream",
            )
        },
        caption=caption,
    )

    print(
        f"Enviado correctamente: {filename}"
    )


def update_heartbeat(state):
    current_week = datetime.now(
        timezone.utc
    ).strftime("%G-W%V")

    if (
        state.get("heartbeat_week")
        != current_week
    ):
        state["heartbeat_week"] = current_week
        return True

    return False


def main():
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        sys.exit("Falta TELEGRAM_BOT_TOKEN")

    if not os.getenv("TELEGRAM_CHAT_ID"):
        sys.exit("Falta TELEGRAM_CHAT_ID")

    if (
        os.getenv("SEND_TEST", "false").lower()
        == "true"
    ):
        send_test()

    state = load_state()
    processed = set(
        state.get("processed", [])
    )
    documents = fetch_documents()

    print(
        "Documentos descargables encontrados: "
        f"{len(documents)}"
    )

    if state.get("scope") != MONITOR_SCOPE:
        processed.update(
            document["id"]
            for document in documents
        )
        state["processed"] = sorted(processed)
        state["scope"] = MONITOR_SCOPE
        update_heartbeat(state)
        save_state(state)
        print(
            "Inventario inicial guardado; "
            "no se enviarán documentos antiguos."
        )
        return

    for document in documents:
        if document["id"] in processed:
            continue

        send_document(document)
        processed.add(document["id"])

        state["processed"] = sorted(
            processed
        )
        save_state(state)

    if update_heartbeat(state):
        save_state(state)


if __name__ == "__main__":
    main()
