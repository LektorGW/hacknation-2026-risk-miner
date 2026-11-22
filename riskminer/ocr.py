"""Local OCR for scanned pages. No document leaves the host."""

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import pypdfium2 as pdfium


_pdf_lock = threading.Lock()


def ocr_pages(data: bytes, pages: list[int]) -> dict[int, str]:
    if len(pages) > 30:
        raise ValueError("Jednorazowo można rozpoznać do 30 stron skanu.")
    tool = shutil.which("tesseract")
    if not tool and os.name != "nt":
        raise ValueError("Skan wymaga lokalnego Tesseract z pakietem języka polskiego.")
    results = {}
    with tempfile.TemporaryDirectory() as folder:
        for idx in pages:
            file = Path(folder) / f"page-{idx}.png"
            with _pdf_lock, pdfium.PdfDocument(data) as doc:
                page = doc[idx]
                width, height = page.get_size()
                scale = min(3, 2800 / max(width, height))
                page.render(scale=scale).to_pil().convert("L").save(file)
                page.close()
            if tool:
                cmd = [tool, str(file), "stdout", "-l", "pol+eng"]
            else:
                script = Path(__file__).with_name("windows-ocr.ps1")
                cmd = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    str(file),
                ]
            proc = subprocess.run(cmd, capture_output=True, timeout=35)
            if proc.returncode or not proc.stdout.strip():
                raise ValueError(f"Nie udało się odczytać skanu na stronie {idx + 1}. Sprawdź pakiet OCR.")
            results[idx] = proc.stdout.decode("utf-8-sig").strip()
    return results
