"""Generación del ranking combinado a partir de las publicaciones del INAP."""

import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from pypdf import PdfReader

PUBLISHED_DIR = Path("published")
RAW_BASE_URL = (
    "https://raw.githubusercontent.com/sergioopo/"
    "age-documentos-monitor/main/published"
)
NAME_NIF_SCORE = re.compile(
    r"([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ ,.'-]+?)\*{3}(\d{4})\*{2}\s+(\d{1,3},\d{2})"
)


def normalized(value):
    return re.sub(r"\s+", " ", value).strip()


def download_pdf(url, destination):
    response = requests.get(
        url,
        timeout=90,
        headers={"User-Agent": "AGE-ranking-generator/1.0"},
    )
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"La URL no devuelve un PDF: {url}")
    destination.write_bytes(response.content)
    return hashlib.sha256(response.content).hexdigest()


def read_pdf(path):
    return "\n".join(
        page.extract_text() or ""
        for page in PdfReader(str(path)).pages
    )


def parse_list(text, access_type, expected_header):
    if expected_header not in text.upper():
        raise ValueError(
            "El PDF no contiene el encabezado esperado: "
            f"{expected_header}"
        )

    candidates = []
    for name, visible_nif, score in NAME_NIF_SCORE.findall(text):
        candidates.append(
            {
                "name": normalized(name).rstrip(".,;:"),
                "nif": f"***{visible_nif}**",
                "score": float(score.replace(",", ".")),
                "accessType": access_type,
            }
        )

    if not candidates:
        raise ValueError(
            f"No se han encontrado aspirantes en {access_type}"
        )
    return candidates


def find_section_minimums(text, section):
    compact = normalized(text)
    pattern = re.compile(
        rf"{section}.*?PRIMERA PARTE.*?\(Calificación\)\s+"
        rf"(\d+(?:,\d+)?)\s+\d+(?:,\d+)?"
        rf".*?SEGUNDA PARTE.*?\(Calificación\)\s+"
        rf"(\d+(?:,\d+)?)\s+\d+(?:,\d+)?",
        re.IGNORECASE,
    )
    match = pattern.search(compact)
    if not match:
        raise ValueError(
            "No se han podido extraer los mínimos de "
            f"{section}"
        )
    return f"{match.group(1)} / {match.group(2)}"


def parse_cuts(text):
    upper = text.upper()
    if (
        "NOTA INFORMATIVA" not in upper
        or "PUNTUACIÓN DIRECTA MÍNIMA" not in upper
    ):
        raise ValueError(
            "El PDF no parece una nota informativa "
            "de puntuaciones mínimas"
        )
    return {
        "general": find_section_minimums(text, "PROMOCIÓN GENERAL"),
        "disability": find_section_minimums(
            text,
            "CUPO BASE ESPECÍFICA 5",
        ),
    }


def generate_published_ranking(sources, edition="2025"):
    """Descarga, valida y publica los datos consumidos por la web."""
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="age-ranking-") as temporary:
        temporary_dir = Path(temporary)
        downloads = {
            "general": (
                sources["general"]["url"],
                temporary_dir / "general.pdf",
            ),
            "disability": (
                sources["disability"]["url"],
                temporary_dir / "disability.pdf",
            ),
            "minimumScores": (
                sources["minimum_scores"]["url"],
                temporary_dir / "minimum-scores.pdf",
            ),
        }
        hashes = {
            name: download_pdf(url, path)
            for name, (url, path) in downloads.items()
        }
        candidates = parse_list(
            read_pdf(downloads["general"][1]),
            "Turno general",
            "SISTEMA DE ACCESO: GENERAL",
        )
        candidates += parse_list(
            read_pdf(downloads["disability"][1]),
            "Cupo de discapacidad",
            "CUPO BASE ESPECÍFICA 5",
        )
        cuts = parse_cuts(read_pdf(downloads["minimumScores"][1]))

    candidates.sort(key=lambda row: (-row["score"], row["name"]))
    fingerprint = hashlib.sha256(
        "|".join(hashes.values()).encode("utf-8")
    ).hexdigest()[:16]
    ranking_filename = f"ranking-{fingerprint}.json"
    (PUBLISHED_DIR / ranking_filename).write_text(
        json.dumps(candidates, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    manifest = {
        "edition": edition,
        "dataUrl": f"{RAW_BASE_URL}/{ranking_filename}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "cuts": cuts,
        "sources": {
            name: {"url": url, "sha256": hashes[name]}
            for name, (url, _) in downloads.items()
        },
        "counts": {
            "general": sum(
                row["accessType"] == "Turno general"
                for row in candidates
            ),
            "disability": sum(
                row["accessType"] == "Cupo de discapacidad"
                for row in candidates
            ),
            "total": len(candidates),
        },
    }
    (PUBLISHED_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
