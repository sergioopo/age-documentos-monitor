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

VERCEL_API = (
    "https://age-documentos-monitor-scaop.vercel.app/api/documents"
)

STATE_FILE = Path("state.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AGE-Documentos/3.0)",
    "Accept-Language": "es-ES,es;q=0.9",
}


def normalize(value):
    return str(value).translate(
        str.maketrans(
            "áéíóúüñÁÉÍÓÚÜÑ",
            "aeiouunAEIOUUN",
        )
    ).lower()


def is_relevant(value):
    value = normalize(value)

    return bool(
        re.search(r"listado|relacion", value)
        and "provisional" in value
        and re.search(r"aprobad|superad", value)
        and re.search(
            r"turno general|acceso general|discapacidad",
            value,
        )
    )


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

    return "Turno general"


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
    documents = {}

    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        href = urljoin(
            SOURCE_URL,
            link["href"],
        ).split("#")[0]

        container = link.find_parent(
            ["li", "p", "article", "div"]
        )

        context = (
            container.get_text(" ", strip=True)
            if container
            else title
        )

        combined = f"{title} {context} {href}"

        if not is_relevant(combined):
            continue

        identifier = document_id(href)

        documents[identifier] = {
            "id": identifier,
            "title": (
                title
                or "Listado provisional de aprobados"
            ),
            "url": href,
            "category": get_category(combined),
        }

    return list(documents.values())


def fetch_from_vercel():
    response = requests.get(
        VERCEL_API,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    return payload.get("documents", [])


def fetch_documents():
    try:
        documents = scrape_inap()
        print("Consulta directa al INAP completada.")
        return documents
    except Exception as error:
        print(
            "Acceso directo al INAP fallido: "
            f"{error}"
        )
        print(
            "Utilizando la API de Vercel "
            "como respaldo."
        )
        return fetch_from_vercel()


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

    response.raise_for_status()
    payload = response.json()

    if not payload.get("ok"):
        raise RuntimeError(
            "Telegram rechazó el documento: "
            + response.text[:300]
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
                response.headers.get(
                    "Content-Type",
                    "application/octet-stream",
                ),
            )
        },
        caption=caption,
    )

    print(
        f"Enviado correctamente: {filename}"
    )


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
        "Documentos relevantes encontrados: "
        f"{len(documents)}"
    )

    for document in documents:
        if document["id"] in processed:
            continue

        send_document(document)
        processed.add(document["id"])

        state["processed"] = sorted(
            processed
        )
        save_state(state)

    current_week = datetime.now(
        timezone.utc
    ).strftime("%G-W%V")

    if (
        state.get("heartbeat_week")
        != current_week
    ):
        state["heartbeat_week"] = (
            current_week
        )
        save_state(state)


if __name__ == "__main__":
    main()
