"""Read-only adapters to the public Polish BZP and European TED notice registers."""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import re
import threading
import time
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .ingest import fold

BZP = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
MIRROR = "https://bzp.cytr.us/mo-board/api/v1/notice"
TED = "https://api.ted.europa.eu/v3/notices/search"
_TYPES = {
    "ContractNotice": "notice",
    "TenderResultNotice": "award",
    "AgreementUpdateNotice": "change",
    "ContractPerformingNotice": "completion",
    "NoticeUpdateNotice": "notice_update",
}
_lock = threading.Lock()
_last_bzp = 0.0
_MAX_RESPONSE = 14 * 1024 * 1024


class _SourceNotes(list):
    complete = True


def _incomplete(warnings, message):
    warnings.append(message)
    if isinstance(warnings, _SourceNotes):
        warnings.complete = False


def _page_failure(source, warnings, rows, exc):
    """A later page can fail after earlier notices were successfully read."""
    if not rows:
        raise exc
    issue = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
    _incomplete(warnings, f"{source}: nie odczytano kolejnej strony ({issue}). Zachowano pobrane ogłoszenia.")
    return rows


def _page_records(batch, parser, source, warnings, **kwargs):
    skipped = 0
    for raw in batch:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        try:
            yield parser(raw, **kwargs)
        except (KeyError, ValueError, TypeError, AttributeError):
            skipped += 1
    if skipped:
        _incomplete(warnings, f"{source}: pominięto nieczytelne ogłoszenia na stronie: {skipped}.")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _request(url, body=None):
    global _last_bzp
    if url.startswith(BZP):
        # The official API guarantees 30 reads per minute per public IP.
        with _lock:
            time.sleep(max(0, _last_bzp + 2.1 - time.monotonic()))
            _last_bzp = time.monotonic()
    request = Request(
        url,
        data=json.dumps(body).encode() if body else None,
        headers={
            "User-Agent": "RiskMiner/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=12) as response:
        raw = response.read(_MAX_RESPONSE + 1)
    if len(raw) > _MAX_RESPONSE:
        raise ValueError("Odpowiedź przekroczyła rozmiar pojedynczej strony.")
    return json.loads(raw)


class _NoticeText(HTMLParser):
    blocks = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.content = []
        self.hidden = False

    def handle_starttag(self, tag, attrs):
        if tag in ("head", "style", "script"):
            self.hidden = True
        elif tag in self.blocks and not self.hidden:
            self.content.append("\n")

    def handle_endtag(self, tag):
        if tag in ("head", "style", "script"):
            self.hidden = False
        elif tag in self.blocks:
            self.content.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.content.append(data)


def notice_text(html):
    parser = _NoticeText()
    parser.feed(html)
    text = "".join(parser.content)
    return "\n".join(line for line in (" ".join(s.split()) for s in text.splitlines()) if line)


def _procurement_excerpt(text):
    # The complete, unmodified source remains at the public notice URL.
    text = re.sub(r"(?ms)^SEKCJA I\s+[-–].*?(?=^SEKCJA II\b)", "", text)
    text = re.sub(r"(?ms)^SEKCJA VII\s+WYKONAWCA.*?(?=^SEKCJA VIII\b|\Z)", "", text)
    text = re.sub(r"(?ms)^4\.3\.\) Dane wykonawcy.*?(?=^4\.4\.\)|\Z)", "", text)
    return re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[adres e-mail pominięty]", text)


def _bzp_number(value):
    m = re.search(r"(20\d\d)\s*[/ -]?\s*BZP\s*0*(\d+)(?:\s*/\s*(\d+))?", str(value), re.I)
    return (f"{m[1]}/BZP {int(m[2]):08d}", m[3] or "") if m else ("", "")


def _ted_number(value):
    oj = re.fullmatch(r"\s*(20\d{2})\s*/\s*S\s*\d{1,3}[- ]+0*(\d{1,8})\s*", str(value), re.I)
    if oj:
        return f"{int(oj[2])}-{oj[1]}"
    m = re.fullmatch(r"\s*0*(\d{1,8})\s*[-/]\s*(20\d{2})\s*", str(value))
    return f"{int(m[1])}-{m[2]}" if m else ""


def _national_id(value):
    return (
        re.sub(r"^(?:PL|REGON|NIP)\s*:?\s*", "", str(value), flags=re.I).replace("-", "").replace(" ", "")
    )


def _similar(left, right):
    a, b = fold(left), fold(right)
    if not a or not b:
        return 0.0
    return max(
        SequenceMatcher(None, a, b, autojunk=False).ratio(),
        len(set(a.split()) & set(b.split())) / max(1, len(set(a.split()) | set(b.split()))),
    )


def match(project, record):
    """Return a reviewable candidate score, never independent expert approval."""
    source_id = record.get("external_id", "")
    proj_notice, proj_ver = _bzp_number(project.get("bzp", ""))
    notice, version = _bzp_number(source_id)
    ted = _ted_number(project.get("ted", ""))
    exact = bool(
        (proj_notice and proj_notice == notice and (not proj_ver or proj_ver == version))
        or (ted and ted == _ted_number(source_id))
    )
    same_procedure = bool(
        project.get("ocid") and str(project["ocid"]).lower() == str(record.get("ocid", "")).lower()
    )
    cited_notice = bool(proj_notice and _bzp_number(record.get("notice_reference", ""))[0] == proj_notice)
    buyer_ids = {_national_id(project[k]) for k in ("nip", "regon") if project.get(k)}
    record_ids = {_national_id(i) for i in str(record.get("buyer_identifier", "")).split(",") if i}
    same_buyer = bool(buyer_ids & record_ids)
    conflicting_id = bool(
        not same_buyer
        and any(a.isdigit() and b.isdigit() and len(a) == len(b) for a in buyer_ids for b in record_ids)
    )
    buyer_name = _similar(project.get("buyer", ""), record.get("buyer", ""))
    title = _similar(project.get("title", ""), record.get("title", ""))
    same_city = bool(
        project.get("location") and fold(project["location"]) == fold(record.get("location", ""))
    )
    cpv = re.findall(r"\d{8}", str(project.get("cpv", "")))
    same_cpv = bool(set(cpv) & set(re.findall(r"\d{8}", str(record.get("cpv", "")))))
    reasons = []
    if exact:
        reasons.append("Zgodny numer ogłoszenia.")
    if same_procedure:
        reasons.append("Zgodny identyfikator postępowania OCID.")
    if cited_notice:
        reasons.append("Ogłoszenie przywołuje numer ogłoszenia podany w projekcie.")
    if same_buyer:
        reasons.append("Zgodny identyfikator zamawiającego.")
    elif buyer_name >= 0.78:
        reasons.append("Zbliżona nazwa zamawiającego.")
    if title >= 0.45:
        reasons.append(f"Podobieństwo tytułu {title:.0%}.")
    if same_city:
        reasons.append("Zgodna miejscowość zamawiającego.")
    if same_cpv:
        reasons.append("Wspólny kod CPV.")
    score = min(
        0.94, 0.55 * title + 0.28 * max(float(same_buyer), buyer_name) + 0.08 * same_city + 0.05 * same_cpv
    )
    if exact or same_procedure or cited_notice:
        score = 0.99
        if (
            (project.get("title") and title < 0.33)
            or conflicting_id
            or (buyer_ids and record_ids and not same_buyer and buyer_name < 0.70)
        ):
            reasons.append("Rozbieżność nazwy lub podmiotu mimo zgodności identyfikatora.")
            score = 0.56
    else:
        if title < 0.45:
            return 0, reasons
        if conflicting_id:
            reasons.append("Rozbieżne identyfikatory zamawiającego mimo podobieństwa nazw.")
            score = min(score, 0.56)
    proj_lot = re.search(r"czesc\s+(?:nr\s+)?(\d+)", fold(project.get("scope", "")))
    if proj_lot and record.get("lot") and str(record["lot"]) != proj_lot[1]:
        reasons.append(f"Dokument dotyczy innej części ({record['lot']}).")
        return 0, reasons
    if proj_lot and not record.get("lot"):
        reasons.append("Ogłoszenie obejmuje postępowanie. Przypisanie do części wymaga potwierdzenia.")
    return round(score, 3), reasons


def _field(text, pattern):
    match_ = re.search(pattern, text, re.I)
    return match_[1].strip() if match_ else ""


def _money(text):
    return float(text.replace(" ", "").replace("\xa0", "").replace(",", ".")) if text else None


def _contract_days(signed, period):
    if not signed or not period:
        return None
    try:
        start = date.fromisoformat(signed)
    except ValueError:
        return None
    deadline = _field(period, r"(?:do\s+dnia\s+|do\s+)?(\d{4}-\d\d-\d\d)")
    months = re.fullmatch(r"(\d+)\s+mies\w+", period, re.I)
    days = re.fullmatch(r"(\d+)\s+dn\w*", period, re.I)
    if months:
        idx = start.month - 1 + int(months[1])
        year, month = start.year + idx // 12, idx % 12 + 1
        if 1 <= year <= 9999:
            deadline = date(year, month, min(start.day, calendar.monthrange(year, month)[1])).isoformat()
    if days:
        return int(days[1])
    try:
        return (date.fromisoformat(deadline) - start).days if deadline else None
    except ValueError:
        return None


def _award_facts(text, ocid, number):
    sections = re.split(r"(?im)^SEKCJA VIII\s+UMOWA(?:\s+\(dla części\s+(\d+)\))?\s*\n", text)
    awards = []
    for index in range(1, len(sections), 2):
        lot = sections[index] or ""
        body = re.split(r"(?im)^SEKCJA [IVX]+ |^Część \d+\s*$", sections[index + 1], maxsplit=1)[0]
        signed = _field(body, r"8\.1\.\)\s*Data zawarcia umowy:\s*(\d{4}-\d\d-\d\d)")
        period = _field(body, r"8\.3\.\)\s*Okres realizacji zamówienia albo umowy ramowej:\s*([^\n]+)")
        value = _money(
            _field(body, r"8\.2\.\)\s*Wartość umowy/umowy ramowej:\s*([0-9 \xa0]+(?:[.,]\d{1,2})?)\s*PLN")
        )
        if signed and value is not None:
            awards.append(
                {
                    "lot": lot,
                    "signed_on": signed,
                    "agreed_period": period,
                    "contract_value_pln": value,
                    "planned_days": _contract_days(signed, period),
                    "award_id": number,
                    "contract_key": ":".join((ocid, number, lot or "bez-czesci", signed)),
                }
            )
    return awards


def completion_facts(text):
    signed = _field(text, r"4\.1\.\)\s*Data zawarcia umowy:\s*(\d{4}-\d\d-\d\d)")
    finished = _field(text, r"5\.2\.\)\s*Termin wykonania umowy:\s*(\d{4}-\d\d-\d\d)")
    period = _field(text, r"4\.2\.\)\s*Okres realizacji zamówienia:\s*([^\n]+)")
    agreed = _money(_field(text, r"4\.4\.\)\s*Wartość umowy:\s*([0-9 \xa0]+(?:[.,]\d{1,2})?)\s*PLN"))
    paid = _money(
        _field(
            text,
            r"5\.5\.\)\s*Łączna wartość wynagrodzenia wypłacona z tytułu zrealizowanej umowy:\s*([0-9 \xa0]+(?:[.,]\d{1,2})?)\s*PLN",
        )
    )
    facts = {
        "signed_on": signed,
        "finished_on": finished,
        "agreed_period": period,
        "contract_value_pln": agreed,
        "paid_pln": paid,
        "on_time": _field(text, r"5\.3\.\).*?terminie:\s*(Tak|Nie)"),
        "number_changes": _field(text, r"5\.4\.1\.\)\s*Liczba zmian:\s*(\d+)"),
    }
    if signed:
        facts["planned_days"] = _contract_days(signed, period)
        if finished:
            try:
                facts["actual_days"] = (date.fromisoformat(finished) - date.fromisoformat(signed)).days
            except ValueError:
                pass
    return {key: value for key, value in facts.items() if value is not None and value != ""}


def bzp_record(raw, retrieved_at=None, via=BZP):
    number = raw.get("noticeNumber") or raw.get("bzpNumber")
    if not number:
        raise ValueError("Ogłoszenie BZP bez numeru.")
    kind = _TYPES.get(raw.get("noticeType"), "notice")
    text = notice_text(raw.get("htmlBody") or "")
    excerpt = _procurement_excerpt(text)
    lot = _field(text, r"Umowa dla części nr\s*(\d+)") if kind in ("completion", "change") else ""
    ocid = raw.get("tenderId") or ""
    object_id = str(raw.get("objectId") or "")
    published = str(raw.get("publicationDate") or "")
    if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", object_id):
        url = "https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?" + urlencode(
            {"noticeId": object_id}
        )
    else:
        year = _bzp_number(number)[0][:4] or str(date.today().year)
        url = (
            BZP
            + "?"
            + urlencode(
                {
                    "NoticeNumber": number,
                    "NoticeType": raw.get("noticeType") or "ContractNotice",
                    "PublicationDateFrom": year + "-01-01T00:00:00",
                    "PublicationDateTo": year + "-12-31T23:59:59",
                    "PageSize": 1,
                }
            )
        )
    result = {
        "source": "BZP",
        "external_id": number,
        "title": raw.get("orderObject") or number,
        "buyer": raw.get("organizationName") or "",
        "buyer_identifier": raw.get("organizationNationalId") or "",
        "location": raw.get("organizationCity") or "",
        "cpv": raw.get("cpvCode") or "",
        "ocid": ocid,
        "procedure_key": ocid,
        "lot": lot,
        "kind": kind,
        "notice_type": raw.get("noticeType") or "",
        "published_at": published,
        "object_id": object_id,
        "retrieved_at": retrieved_at or _now(),
        "locator": "treść ogłoszenia BZP",
        "url": url,
        "retrieved_from": via,
        "text": excerpt,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
    }
    if kind == "completion":
        result["facts"] = facts = completion_facts(text)
        result["notice_reference"] = _field(
            text, r"3\.2\.1\.\)\s*Numer ogłoszenia[^:]{0,270}:\s*(20\d\d/BZP\s+\d+(?:/\d+)?)"
        )
        if ocid and facts.get("signed_on"):
            result["contract_key"] = ":".join([ocid, lot or "bez-czesci", facts["signed_on"], number])
        if facts.get("finished_on", "") > result["published_at"][:10] and result["published_at"]:
            result["quality_flags"] = [
                "Data wykonania późniejsza niż data publikacji ogłoszenia o wykonaniu."
            ]
    elif kind == "award":
        result["awards"] = _award_facts(text, ocid, number)
    elif kind == "notice":
        result["planned_periods"] = re.findall(
            r"4\.2\.10\.\)\s*Okres realizacji zamówienia albo umowy ramowej:\s*([^\n]+)", text, re.I
        )
    elif kind == "change":
        value = _field(
            text, r"4\.4\.\)\s*Wartość umowy(?:/umowy ramowej)?:\s*([0-9 \xa0]+(?:[.,]\d{1,2})?)\s*PLN"
        )
        signed = _field(text, r"4\.1\.\)\s*Data zawarcia umowy(?:/umowy ramowej)?:\s*(\d{4}-\d\d-\d\d)")
        result["facts"] = {"signed_on": signed, "contract_value_pln": _money(value)}
    if kind in ("change", "completion"):
        result["award_reference"] = _field(
            text, r"4\.5\.\)\s*Numer ogłoszenia o wyniku[^:]{0,270}:\s*(20\d\d/BZP\s+\d+(?:/\d+)?)"
        )
    return result


def link_contracts(records):
    """Connect outcome to exactly one award/lot using independently agreeing evidence."""
    awards = [a | {"ocid": r["ocid"]} for r in records for a in r.get("awards", [])]
    for r in records:
        if r["kind"] not in ("completion", "change"):
            continue
        facts = r.get("facts", {})
        reference = _bzp_number(r.get("award_reference", ""))[0]
        matches = [
            a
            for a in awards
            if a["ocid"] == r["ocid"]
            and reference
            and reference == _bzp_number(a["award_id"])[0]
            and a["signed_on"] == facts.get("signed_on")
            and a["contract_value_pln"] == facts.get("contract_value_pln")
            and (not r.get("lot") or a["lot"] == r["lot"])
        ]
        if len(matches) == 1:
            r["contract_key"] = matches[0]["contract_key"]
            r["lot"] = matches[0]["lot"]
            r["contract_basis"] = "Numer ogłoszenia o wyniku, OCID, data zawarcia i wartość umowy."
        elif (
            not matches
            and reference
            and r.get("lot")
            and facts.get("signed_on")
            and facts.get("contract_value_pln") is not None
        ):
            # An award may be missing from the available register. Other notices
            # can still name its number, the lot and the same signed contract.
            r["contract_key"] = ":".join(
                (r["ocid"], reference, r["lot"], facts["signed_on"], str(facts["contract_value_pln"]))
            )
            r["contract_basis"] = (
                "Źródło wskazuje numer wyniku, część, datę i wartość umowy. Brak potwierdzonego wpisu o udzieleniu."
            )
    return records


def scope_records(records, project):
    lot = re.search(r"czesc\s+(?:nr\s+)?(\d+)", fold(project.get("scope", "")))
    if not lot:
        return list(records)
    scoped = []
    for r in records:
        if r.get("lot") and r["lot"] != lot[1]:
            continue
        if "awards" in r:
            r = {**r, "awards": [a for a in r["awards"] if a["lot"] == lot[1]]}
        scoped.append(r)
    return scoped


def _polish(value):
    if isinstance(value, dict):
        value = value.get("pol") or value.get("eng") or next(iter(value.values()), "")
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value or "")


def ted_record(raw, retrieved_at=None):
    number = raw["publication-number"]
    if not _ted_number(number):
        raise ValueError("Nieprawidłowy numer publikacji TED.")
    title = _polish(raw.get("title-proc") or raw.get("title-lot") or raw.get("notice-title"))
    desc = _polish(raw.get("description-proc") or raw.get("description-lot"))
    category = _polish(raw.get("notice-type"))
    kind = (
        "change"
        if category.startswith("can-modif")
        else "award"
        if category.startswith("can")
        else "notice"
    )
    text = f"{title}\n{desc}".strip()
    identifier = _polish(raw.get("procedure-identifier"))
    pdf_links = (raw.get("links") or {}).get("pdf") or {}
    pdf = pdf_links.get("POL") or pdf_links.get("ENG") or next(iter(pdf_links.values()), "")
    if not re.fullmatch(r"https://ted\.europa\.eu/[a-z]{2}/notice/[0-9-]+/pdf", str(pdf)):
        pdf = f"https://ted.europa.eu/pl/notice/{quote(number, safe='-')}/pdf"
    return {
        "source": "TED",
        "external_id": number,
        "title": title or number,
        "text": text,
        "url": pdf,
        "buyer": _polish(raw.get("buyer-name")),
        "buyer_identifier": _polish(raw.get("organisation-identifier-buyer")),
        "procedure_key": identifier,
        "published_at": str(raw.get("publication-date") or "")[:10],
        "retrieved_at": retrieved_at or _now(),
        "locator": "tytuł i opis procedury TED",
        "kind": kind,
        "notice_type": category,
        "cpv": _polish(raw.get("classification-cpv")),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "retrieved_from": TED,
    }


def _bzp_query(endpoint, query, warnings):
    rows = []
    seen = set()
    for _ in range(3):
        url = endpoint + "?" + urlencode({**query, "PageSize": 30})
        try:
            batch = _request(url)
            if not isinstance(batch, list):
                raise ValueError("Nieznana struktura odpowiedzi BZP.")
            rows.extend(_page_records(batch, bzp_record, "BZP", warnings, via=url))
        except (ValueError, OSError, URLError, TimeoutError) as exc:
            return _page_failure("BZP", warnings, rows, exc)
        if len(batch) < 30:
            return rows
        cursor = batch[-1].get("objectId") if isinstance(batch[-1], dict) else None
        if not cursor or cursor in seen:
            break
        seen.add(cursor)
        query = {**query, "SearchAfter": cursor}
    _incomplete(warnings, "Wyszukiwanie BZP osiągnęło limit stron. Uzupełnij dane identyfikacyjne.")
    return rows


def _search_bzp(project, warnings):
    endpoint = MIRROR if os.getenv("RISKMINER_BZP_MIRROR", "").lower() in ("1", "true") else BZP
    if endpoint == MIRROR:
        warnings.append("Źródłem odczytu jest kopia BZP HackNation. Linki prowadzą do urzędowych ogłoszeń.")
    number, version = _bzp_number(project.get("bzp", ""))
    by_id = []
    if number:
        query = {
            "PublicationDateFrom": number[:4] + "-01-01T00:00:00",
            "PublicationDateTo": number[:4] + "-12-31T23:59:59",
            "NoticeNumber": number + ("/" + version if version else ""),
        }
        for notice_type in _TYPES:
            if endpoint == MIRROR and notice_type == "NoticeUpdateNotice":
                continue
            by_id = _bzp_query(endpoint, {**query, "NoticeType": notice_type}, warnings)
            if by_id:
                break
        if not by_id:
            warnings.append(
                f"BZP: nie znaleziono podanego numeru {number}. Pozostałe powiązania wymagają weryfikacji."
            )
    anchor = next((r for r in by_id if match(project, r)[0] >= 0.95), {})
    criteria = {**project, **({"ocid": anchor["ocid"]} if anchor.get("ocid") else {})}
    city = anchor.get("location") or project.get("location")
    title = anchor.get("title") or project.get("title") or ""
    has_id = any(project.get(k) for k in ("nip", "regon", "ocid", "cst")) or number
    if not title or (not city and not project.get("buyer") and not has_id):
        _incomplete(
            warnings,
            "Wyszukanie powiązanych ogłoszeń BZP wymaga tytułu oraz identyfikatora, miejscowości lub zamawiającego.",
        )
        return by_id
    # The API offers a substring filter on orderObject, but no OCID filter.
    # Combine a broad technical term with city; rank independently by full title and IDs.
    phrase = next(
        (
            word
            for word in ("kanaliz", "oczyszczal", "wodoci", "uzdatnian", "ruroci")
            if word in title.casefold()
        ),
        max(re.findall(r"\w+", title), key=len, default=title),
    )
    query = {
        "OrderObject": phrase,
        "PublicationDateFrom": "2021-01-01T00:00:00",
        "PublicationDateTo": date.today().isoformat() + "T23:59:59",
    }
    if city:
        query["OrganizationCity"] = city
    elif anchor.get("buyer") or project.get("buyer"):
        query["OrganizationName"] = anchor.get("buyer") or project["buyer"]
    else:
        query["OrderObject"] = " ".join(title.split())[:240]
    results = list(by_id)
    for notice_type in _TYPES:
        if endpoint == MIRROR and notice_type == "NoticeUpdateNotice":
            continue
        try:
            batch = _bzp_query(endpoint, {**query, "NoticeType": notice_type}, warnings)
        except (ValueError, OSError, URLError, TimeoutError) as exc:
            if not results:
                raise
            issue = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
            _incomplete(
                warnings,
                f"BZP: odczyt przerwano przy {notice_type} ({issue}). Wynik częściowy, można ponowić pobranie.",
            )
            break
        for item in batch:
            score, reasons = match(criteria, item)
            if criteria.get("ocid") and item.get("ocid") != criteria["ocid"]:
                continue
            if score >= 0.74:
                results.append({**item, "confidence": score, "reasons": reasons})
    unique = {r["external_id"]: r for r in results}
    linked = link_contracts(unique.values())
    if not criteria.get("ocid"):
        by_title = {}
        for r in linked:
            if r.get("ocid"):
                by_title.setdefault(fold(r["title"]), set()).add(r["ocid"])
        ambiguous = {k for k, ids in by_title.items() if len(ids) > 1}
        if ambiguous:
            warnings.append(
                "Podobny tytuł dotyczy kilku odrębnych postępowań BZP. Sprawdź identyfikatory i wynik każdego postępowania."
            )
            for r in linked:
                if fold(r["title"]) in ambiguous:
                    r["confidence"] = min(0.74, r.get("confidence", 0.74))
                    r["reasons"] = [
                        *r.get("reasons", []),
                        "Inne postępowanie ma identyczny znormalizowany tytuł.",
                    ]
    return scope_records([r for r in linked if match(criteria, r)[0] > 0], project)


def _search_ted(project, warnings):
    number = _ted_number(project.get("ted", ""))
    if number:
        query = f"publication-number = {number}"
    else:
        terms = re.findall(r"[\w]+", str(project.get("title") or ""), re.UNICODE)
        if not terms:
            return []
        words = sorted(dict.fromkeys(terms), key=len, reverse=True)
        generic = {"miejscowości", "miejscowościach", "przedsięwzięcia", "zaprojektuj", "wybuduj"}
        words = [w for w in words if w.casefold() not in generic][:3] or words[:1]
        query = "buyer-country = POL AND " + " AND ".join(f'title-proc ~ "{w[:80]}"' for w in words)
    fields = [
        "publication-number",
        "publication-date",
        "title-proc",
        "title-lot",
        "buyer-name",
        "organisation-identifier-buyer",
        "description-proc",
        "procedure-identifier",
        "notice-type",
        "classification-cpv",
    ]
    rows = []
    for page in (1, 2, 3):
        try:
            data = _request(TED, {"query": query, "fields": fields, "page": page, "limit": 20, "scope": "ALL"})
            if not isinstance(data, dict) or not isinstance(data.get("notices"), list):
                raise ValueError("Nieznana struktura odpowiedzi TED.")
            batch = data["notices"]
            rows.extend(_page_records(batch, ted_record, "TED", warnings))
            total = data.get("totalNoticeCount")
            if len(batch) < 20 or (total is not None and page * 20 >= int(total)):
                return rows
        except (ValueError, OSError, URLError, TimeoutError) as exc:
            return _page_failure("TED", warnings, rows, exc)
    _incomplete(warnings, "Osiągnięto limit stron TED. Podaj numer ogłoszenia, aby zawęzić wyniki.")
    return rows


def enrich(project: dict) -> dict:
    records = {}
    warnings = []
    source_status = {}
    adapters = [("BZP", _search_bzp), ("TED", _search_ted)]
    if str(project.get("cst", "")).upper().startswith("KPOD.03.15-IW.13-"):
        from .kpo import find

        adapters.append(("KPO / UMWD", lambda row, _: find(row, _now())))
    for label, run in adapters:
        notes = _SourceNotes()
        state = "ok"
        try:
            found = run(project, notes)
            for item in found:
                if "confidence" not in item:
                    item["confidence"], item["reasons"] = match(project, item)
                if item["confidence"] >= 0.55:
                    key = (label, item["external_id"])
                    if key not in records or records[key]["confidence"] <= item["confidence"]:
                        records[key] = item
            if not any(key[0] == label for key in records):
                notes.append(f"{label}: brak wystarczająco podobnych ogłoszeń.")
                state = "empty"
            if not notes.complete:
                state = "partial"
        except HTTPError as exc:
            notes.append(f"{label}: serwis zwrócił HTTP {exc.code}. Ponów odczyt później.")
            state = "failed"
        except (ValueError, OSError, URLError, TimeoutError) as exc:
            notes.append(f"{label}: nie udało się ukończyć odczytu ({type(exc).__name__}).")
            state = "failed"
        warnings.extend(notes)
        source_status[label] = {"status": state, "matched": sum(key[0] == label for key in records)}
    return {
        "records": sorted(records.values(), key=lambda r: (r["published_at"], r["external_id"])),
        "warnings": list(dict.fromkeys(warnings)),
        "source_status": source_status,
        "complete": all(s["status"] in ("ok", "empty") for s in source_status.values()),
    }
