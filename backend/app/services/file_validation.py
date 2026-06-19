from __future__ import annotations

import csv
import io
import json
import zipfile


OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
PDF_SIGNATURE = b"%PDF-"


def _decode_text_sample(contents: bytes) -> str | None:
    sample = contents[:65536]
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return sample.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _looks_like_xlsx(contents: bytes) -> bool:
    if not zipfile.is_zipfile(io.BytesIO(contents)):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            names = set(archive.namelist())
        return "[Content_Types].xml" in names and any(name.startswith("xl/") for name in names)
    except zipfile.BadZipFile:
        return False


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped or stripped[0] not in "{[":
        return False
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


def _looks_like_delimited_text(text: str, delimiter: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    sample = "\n".join(lines[:10])
    try:
        rows = list(csv.reader(io.StringIO(sample), delimiter=delimiter))
    except Exception:
        return False
    if len(rows) < 2:
        return False
    widths = [len(row) for row in rows if row]
    if not widths or max(widths) < 2:
        return False
    return len(set(widths)) == 1


def detect_file_signature(contents: bytes) -> set[str]:
    detected: set[str] = set()
    if contents.startswith(PDF_SIGNATURE):
        detected.add(".pdf")
    if contents.startswith(PNG_SIGNATURE):
        detected.add(".png")
    if contents.startswith(JPEG_SIGNATURE):
        detected.update({".jpg", ".jpeg"})
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        detected.add(".webp")
    if contents.startswith(OLE_SIGNATURE):
        detected.add(".xls")
    if _looks_like_xlsx(contents):
        detected.add(".xlsx")

    text = _decode_text_sample(contents)
    if text is not None:
        if _looks_like_json(text):
            detected.add(".json")
        if _looks_like_delimited_text(text, ","):
            detected.add(".csv")
        if _looks_like_delimited_text(text, "\t"):
            detected.add(".tsv")
        if all(character == "\n" or character == "\r" or character == "\t" or character.isprintable() for character in text[:4096]):
            detected.add(".txt")
    return detected


def validate_file_signature(*, extension: str, contents: bytes) -> None:
    detected = detect_file_signature(contents)
    if extension in detected:
        return
    if extension == ".jpg" and ".jpeg" in detected:
        return
    if extension == ".jpeg" and ".jpg" in detected:
        return
    raise ValueError("Uploaded file contents do not match the selected file type")
