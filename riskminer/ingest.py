"""Normalize project spreadsheets and turn text documents into citable passages."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from datetime import date, datetime
from pathlib import Path

MAX_FILE = 20 * 1024 * 1024
MAX_UNPACKED = 100 * 1024 * 1024
MAX_ROWS = 15000
MAX_COLUMNS = 250
MAX_PASSAGES = 2500
MAX_TEXT = 3_000_000
NON_PROJECT_SHEETS = {"opis kolumn", "slownik", "legenda", "instrukcja"}


def fold(value) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold().replace("ł", "l"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", text))


_COLUMNS = {
    "project_id": ["Identyfikator rekordu", "project_id", "ID projektu"],
    "title": [
        "Nazwa przedsięwzięcia",
        "Tytuł projektu",
        "Nazwa projektu",
        "Nazwa zamówienia",
        "Tytuł",
        "Projekt",
    ],
    "description": ["Opis projektu", "Opis", "Adnotacja instytucji"],
    "buyer": ["Nazwa odbiorcy", "Zamawiający", "Beneficjent", "Nazwa beneficjenta", "Nazwa zamawiającego"],
    "location": ["Siedziba odbiorcy", "Lokalizacja", "Miejscowość", "Gmina"],
    "region": ["Województwo"],
    "scope": ["Zakres rekordu", "Część zamówienia"],
    "nip": ["NIP", "NIP beneficjenta", "NIP zamawiającego"],
    "regon": ["REGON"],
    "cst": ["CST", "Numer projektu", "Nr projektu", "Numer projektu CST"],
    "ocid": ["OCID", "OCDS", "Identyfikator postępowania"],
    "bzp": ["BZP", "Numer ogłoszenia BZP", "Nr BZP"],
    "ted": ["TED", "Numer ogłoszenia TED", "Nr TED"],
    "cpv": ["CPV", "Kod CPV", "Główny kod CPV"],
    "public_id": ["Identyfikator publiczny"],
    "public_id_type": ["Rodzaj identyfikatora publicznego"],
    "buyer_id": ["Identyfikator odbiorcy"],
    "buyer_id_type": ["Rodzaj identyfikatora odbiorcy"],
    "project_value": ["Wartość projektu", "Wartość przedsięwzięcia"],
    "planned_cost": ["Planowany koszt", "Budżet planowany"],
    "actual_cost": ["Koszt rzeczywisty", "Koszt końcowy"],
    "planned_days": ["Planowany czas w dniach", "Planowane dni"],
    "actual_days": ["Rzeczywisty czas w dniach", "Rzeczywiste dni"],
    "cost_basis": ["Podstawa kosztów", "Netto lub brutto"],
    "currency": ["Waluta", "Waluta rozliczeń"],
    "type": ["Typ inwestycji"],
    "live_operation": ["Ciągłość pracy"],
    "completed_at": ["Data faktycznego zakończenia"],
    "value": ["Wartość kontraktu", "Wartość umowy"],
    "status": ["Status przedsięwzięcia", "Status projektu", "Status"],
    "start_date": ["Data rozpoczęcia", "Początek"],
    "end_date": ["Data zakończenia", "Koniec"],
    "as_of": ["Data sporządzenia rekordu"],
    "sector": ["Obszar tematyczny", "Sektor"],
}
_HEADERS = {fold(alias): key for key, aliases in _COLUMNS.items() for alias in [key, *aliases]}


def _string(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == datetime.min.time() else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return str(value).strip() if value is not None else ""


def _projects(rows, sheet, source):
    recognized = False
    for index, row in enumerate(rows, 1):
        if index > MAX_ROWS or len(row) > MAX_COLUMNS:
            raise ValueError("Arkusz przekracza limit wierszy lub kolumn.")
        if not recognized:
            headers = [_string(v) for v in row]
            keys = [_HEADERS.get(fold(header)) for header in headers]
            if "title" not in keys or (
                len([h for h in headers if h]) > 1 and sum(k is not None for k in keys) < 2 and index > 1
            ):
                if index >= 24:
                    return
                continue
            fields = [f for f in keys if f]
            if len(set(fields)) != len(fields):
                raise ValueError(f"Powielona kolumna projektu w arkuszu {sheet}.")
            recognized = True
            continue
        values = [_string(value) for value in row]
        if not any(values):
            continue
        if any(values[len(headers):]):
            raise ValueError(f"Dane wykraczają poza nagłówek: {sheet}, wiersz {index}. Sprawdź separator kolumn.")
        data = {key: value for key, value in zip(keys, values) if key and value}
        if not data.get("title"):
            raise ValueError(f"Brak nazwy projektu: {sheet}, wiersz {index}.")
        for metric in ("planned_cost", "actual_cost", "planned_days", "actual_days"):
            if metric in data:
                try:
                    amount = float(re.sub(r"\s", "", data[metric]).replace(",", "."))
                    if amount < 0 or not math.isfinite(amount):
                        raise ValueError
                    data[metric] = amount
                except ValueError as exc:
                    raise ValueError(f"Niepoprawna wartość {metric}, {sheet}, wiersz {index}.") from exc
        if "live_operation" in data:
            boolean = fold(data["live_operation"])
            if boolean not in {"tak", "nie", "true", "false", "1", "0"}:
                raise ValueError(f"Podaj tak lub nie dla ciągłości pracy, wiersz {index}.")
            data["live_operation"] = boolean in {"tak", "true", "1"}
        if data.get("buyer_id_type", "").upper() in ("NIP", "REGON") and data.get("buyer_id"):
            data[data["buyer_id_type"].lower()] = data["buyer_id"]
        id_type = fold(data.get("public_id_type", ""))
        id_value = data.get("public_id", "")
        if id_value:
            for token, key in (
                ("bzp", "bzp"),
                ("ted", "ted"),
                ("ocid", "ocid"),
                ("kpo", "cst"),
                ("cst", "cst"),
            ):
                if token in id_type:
                    data[key] = id_value
                    break
        data["source"] = {**source, "locator": f"{sheet}, wiersz {index}"}
        data["raw"] = {h: v for h, v in zip(headers, values) if h and v}
        yield data


def _check_office_archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 7000 or sum(i.file_size for i in members) > MAX_UNPACKED:
            raise ValueError("Rozpakowana zawartość dokumentu przekracza limit.")


def _decoded(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Nieobsługiwane kodowanie pliku tekstowego.")


def _text_passages(name, data):
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        pdf = PdfReader(io.BytesIO(data))
        if pdf.is_encrypted:
            raise ValueError("Dokument PDF wymaga hasła.")
        if len(pdf.pages) > 500:
            raise ValueError("Dokument PDF przekracza limit 500 stron.")
        pages = [(page.extract_text() or "").strip() for page in pdf.pages]
        # Blank pages need no OCR. Render only pages with embedded image content.
        scans = [i for i, text in enumerate(pages) if not text and len(pdf.pages[i].images)]
        recognized = {}
        if scans:
            from .ocr import ocr_pages

            recognized = ocr_pages(data, scans)
        for i, text in enumerate(pages):
            yield f"strona {i + 1}" + (" (OCR)" if i in recognized else ""), text or recognized.get(i, "")
    elif ext == ".docx":
        from docx import Document
        from docx.table import Table

        _check_office_archive(data)
        document = Document(io.BytesIO(data))
        para, table = 0, 0
        for element in document.iter_inner_content():
            if isinstance(element, Table):
                table += 1
                for index, row in enumerate(element.rows, 1):
                    yield f"tabela {table}, wiersz {index}", " | ".join(cell.text for cell in row.cells)
            else:
                para += 1
                yield f"akapit {para}", element.text
    elif ext == ".doc":
        executable = shutil.which("antiword")
        if not executable:
            raise ValueError("Plik DOC wymaga zainstalowanego antiword albo zapisu do DOCX.")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "dokument.doc")
            path.write_bytes(data)
            child = subprocess.run(
                [executable, "-m", "UTF-8.txt", str(path)], capture_output=True, timeout=15
            )
        if child.returncode:
            raise ValueError("Nie można odczytać treści dokumentu DOC.")
        yield "treść dokumentu", child.stdout.decode("utf-8", errors="replace")
    else:
        yield "treść dokumentu", _decoded(data)


def load_file(name: str, data: bytes) -> list[dict]:
    if not data or len(data) > MAX_FILE:
        raise ValueError("Plik jest pusty albo przekracza 20 MiB.")
    name = Path(str(name).replace("\\", "/")).name
    ext = Path(name).suffix.lower()
    source = {"name": name, "sha256": hashlib.sha256(data).hexdigest()}
    records = []
    try:
        if ext in (".csv", ".tsv"):
            content = _decoded(data)
            try:
                delimiter = csv.Sniffer().sniff(content[:12000], delimiters=",;\t").delimiter
            except csv.Error:
                delimiter = "\t" if ext == ".tsv" else ";"
            records.extend(_projects(csv.reader(io.StringIO(content), delimiter=delimiter), name, source))
        elif ext == ".xlsx":
            from openpyxl import load_workbook

            _check_office_archive(data)
            workbook = load_workbook(io.BytesIO(data), data_only=True, read_only=True, keep_links=False)
            try:
                for sheet in workbook:
                    if fold(sheet.title) in NON_PROJECT_SHEETS:
                        continue
                    if (sheet.max_row or 0) > MAX_ROWS or (sheet.max_column or 0) > MAX_COLUMNS:
                        raise ValueError("Arkusz przekracza limit wierszy lub kolumn.")
                    records.extend(_projects(sheet.values, sheet.title, source))
            finally:
                workbook.close()
        elif ext == ".xls":
            import xlrd

            workbook = xlrd.open_workbook(file_contents=data, on_demand=True)
            try:
                for sheet in workbook.sheets():
                    if fold(sheet.name) in NON_PROJECT_SHEETS:
                        continue
                    rows = (
                        [
                            xlrd.xldate_as_datetime(c.value, workbook.datemode)
                            if c.ctype == xlrd.XL_CELL_DATE
                            else c.value
                            for c in sheet.row(i)
                        ]
                        for i in range(sheet.nrows)
                    )
                    records.extend(_projects(rows, sheet.name, source))
            finally:
                workbook.release_resources()
        elif ext in (".pdf", ".docx", ".doc", ".txt"):
            size = 0
            for locator, text in _text_passages(name, data):
                text = text.strip()
                if not text:
                    continue
                size += len(text)
                if size > MAX_TEXT or len(records) >= MAX_PASSAGES:
                    raise ValueError("Treść dokumentu przekracza limit analizy.")
                records.append(
                    {
                        "kind": "document",
                        "title": Path(name).stem,
                        "text": text,
                        "source": {**source, "locator": locator},
                    }
                )
            if not records:
                raise ValueError("Nie znaleziono czytelnej treści dokumentu.")
        else:
            raise ValueError("Obsługiwane formaty: XLSX, XLS, CSV, TSV, DOCX, DOC, PDF, TXT.")
    except (ValueError, ImportError):
        raise
    except Exception as exc:
        # Implementation-specific parser errors must surface as invalid input, not HTTP 500.
        raise ValueError(f"Nie można odczytać pliku {name}. Sprawdź jego format i zawartość.") from exc
    if not records:
        raise ValueError("Brak danych projektowych. Wymagana kolumna z nazwą projektu.")
    if len(records) > MAX_ROWS:
        raise ValueError("Plik przekracza limit liczby rekordów.")
    return records
