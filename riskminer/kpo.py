"""Official regional KPO B3.1.1 application register (Lower Silesia)."""

import hashlib
import io
import re
from functools import lru_cache
from time import time
from urllib.request import Request, urlopen

from pypdf import PdfReader

from .ingest import fold

KPO_URL = (
    "https://umwd.dolnyslask.pl/fileadmin/user_upload/KPO/"
    "2025.12.18_Zalacznik_do_Uchwaly_zaktualizowana_lista_przedsiewziec.pdf"
)


@lru_cache(maxsize=1)
def _pages(cache_hour):
    req = Request(KPO_URL, headers={"User-Agent": "RiskMiner/1.0"})
    with urlopen(req, timeout=12) as r:
        data = r.read(3_000_001)
    if len(data) > 3_000_000:
        raise ValueError("Plik rejestru przekracza limit.")
    pdf = PdfReader(io.BytesIO(data))
    return [p.extract_text() or "" for p in pdf.pages]


def find(project, retrieved_at):
    number = str(project.get("cst") or "").strip().upper()
    if not re.fullmatch(r"KPOD\.03\.15-IW\.13-\d{4}/\d{2}", number):
        return []
    for page, text in enumerate(_pages(int(time() // 3600)), 1):
        row = re.search(rf"(?ms)^(\d+)\s+{re.escape(number)}\b.*?(?=^\d+\s+KPOD\.|\Z)", text)
        if not row:
            continue
        excerpt = " ".join(row[0].split())
        buyer_match = bool(project.get("buyer")) and fold(project["buyer"]) in fold(excerpt)
        title_match = bool(project.get("title")) and fold(project["title"]) in fold(excerpt)
        reasons = ["Zgodny numer przedsięwzięcia KPO."]
        if buyer_match:
            reasons.append("Zgodny wnioskodawca.")
        if title_match:
            reasons.append("Zgodny tytuł przedsięwzięcia.")
        value = re.search(r"\b(\d{1,3}(?: \d{3})+,\d{2})\b", excerpt)
        result = {
            "source": "KPO / UMWD",
            "external_id": number,
            "cst": number,
            "title": "B3.1.1 · " + number,
            "kind": "funding_application",
            "text": excerpt,
            "source_title": "Zaktualizowana lista przedsięwzięć KPO B3.1.1",
            "url": KPO_URL + f"#page={page}",
            "retrieved_from": KPO_URL,
            "locator": f"strona {page}, pozycja {row[1]}, kolumna wnioskowanej kwoty wsparcia",
            "published_at": "2025-12-18",
            "retrieved_at": retrieved_at,
            "confidence": 0.98 if buyer_match and title_match else 0.65,
            "reasons": reasons,
            "sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        }
        if value:
            result["requested_funding_pln"] = float(value[1].replace(" ", "").replace(",", "."))
        return [result]
    return []
