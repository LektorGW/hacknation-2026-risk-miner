"""Public, read-only reconstruction from the archived BZP notices."""

import json
from datetime import date
from functools import lru_cache
from html import escape
from string import Template
from urllib.parse import quote

from .db import ROOT
from .projection import field_reference

CASES = {
    "zagrodno": "RM-2026-002",
    "zlawies-wielka": "RM-2026-005",
    "grodzisko-dolne": "RM-2026-010",
}


@lru_cache(maxsize=1)
def archive():
    rows = json.loads((ROOT / "fixtures/real/cases.json").read_text(encoding="utf-8"))
    by_id = {p["project"]["project_id"]: p for p in rows}
    result = {}
    for slug, pid in CASES.items():
        p = by_id[pid]
        (award,) = (r for r in p["records"] if r["kind"] == "award")
        (contract,) = award["awards"]
        entries = [(award, contract, "8.3")]
        entries.extend(
            (r, r["facts"], "4.2")
            for r in p["records"]
            if r["kind"] == "completion"
            and r.get("contract_key") == contract["contract_key"]
        )
        notices = []
        for r, facts, code in sorted(
            entries, key=lambda entry: entry[0]["published_at"]
        ):
            period = facts["agreed_period"]
            passage = field_reference({**r, "id": r["external_id"]}, code)["excerpt"]
            # End at the field value, before the printed notice footer.
            quote, match, _ = passage.partition(period)
            notices.append(
                dict(
                    number=r["external_id"],
                    day=r["published_at"][:10],
                    url=r["url"],
                    period=period,
                    quote=quote + match if match else passage,
                    code=code,
                    finished=facts.get("finished_on"),
                    signed=facts["signed_on"],
                )
            )
        result[slug] = (p["project"]["location"], p["project"]["title"], notices)
    return result


def date_label(value):
    return date.fromisoformat(value).strftime("%d.%m.%Y")


def evidence_note(title, place, visible, finding, detail):
    last_day = date_label(visible[-1]["day"])
    lines = [
        f"# {place} · Karta dowodowa umowy",
        title,
        f"Stan dokumentów na {last_day}.",
        "",
        f"## {finding}",
        detail,
    ]
    for item in visible:
        lines.extend([
            "",
            f"## {date_label(item['day'])} · {item['number']}",
            f"Okres umowny według pola {item['code']}: {item['period']}.",
            f"> {item['quote']}",
        ])
        if item["finished"]:
            lines.append(f"Data wykonania według pola 5.2: {date_label(item['finished'])}.")
        lines.append(f"Źródło BZP: {item['url']}")
    return "\n".join(lines) + "\n"


def dossier(slug, step, *, static_site=False):
    cases = archive()
    place, title, notices = cases[slug]
    if step is None:
        step = len(notices)
    if not 1 <= step <= len(notices):
        raise IndexError("Nieznany etap publikacji.")
    visible = notices[:step]
    periods = {item["period"] for item in visible}
    if step == 1:
        finding = "Znany jest pierwotny termin umowy."
        detail = "Na tym etapie w aktach jest ogłoszenie o wyniku. Dokument dotyczący wykonania pojawi się później."
    elif len(periods) > 1:
        finding = "Dokumenty podają różne okresy realizacji."
        detail = "Porównaj pole 8.3 ogłoszenia o wyniku z polem 4.2 ogłoszeń o wykonaniu. Rozstrzygnięcie wymaga sprawdzenia umowy i jej aneksów."
    else:
        finding = "Dokumenty podają ten sam termin umowy."
        detail = "Zgodność zapisów dotyczy okresu umownego. Faktyczną datę wykonania podano osobno w polu 5.2."
    def case_href(key, stage=None):
        if static_site:
            return f"{key}-{stage}.html" if stage else f"{key}.html"
        return f"?sprawa={key}" + (f"&amp;etap={stage}" if stage else "")

    choices = "".join(
        f'<a href="{case_href(key)}"'
        + (' aria-current="page"' if key == slug else "")
        + f">{escape(info[0])}</a>"
        for key, info in cases.items()
    )
    timeline = "".join(
        f'<a href="{case_href(slug, i)}#os-czasu"'
        + (' aria-current="step"' if i == step else "")
        + f"><b>{date_label(n['day'])}</b><span>{'Wynik postępowania' if i == 1 else 'Ogłoszenie o wykonaniu'}</span></a>"
        for i, n in enumerate(notices, 1)
    )
    cards = []
    for index, n in enumerate(visible, 1):
        finished = ""
        if n["finished"]:
            days = (
                date.fromisoformat(n["finished"]) - date.fromisoformat(n["signed"])
            ).days
            finished = (
                f'<p class="actual">Wykonanie według pola 5.2: <b>{date_label(n["finished"])}</b>. '
                f"Od zawarcia umowy upłynęło {days} dni.</p>"
            )
        cards.append(
            f'<article id="dowod-{index}" tabindex="-1"><small>{date_label(n["day"])} · pole {n["code"]}</small>'
            f"<h3>{escape(n['period'])}</h3><blockquote>{escape(n['quote'])}</blockquote>{finished}"
            f'<a href="{escape(n["url"])}">BZP · {escape(n["number"])}</a></article>'
        )
    readings = "".join(
        f'<li><a href="#dowod-{index}"><span>{date_label(item["day"])}</span>'
        f'<strong>{escape(item["period"])}</strong></a></li>'
        for index, item in enumerate(visible, 1)
    )
    note = evidence_note(title, place, visible, finding, detail)
    template = Template((ROOT / "riskminer/dossier.html").read_text(encoding="utf-8"))
    return template.substitute(
        assets="static" if static_site else "/static",
        readings=readings,
        note="data:text/markdown;charset=utf-8," + quote(note, safe=""),
        filename=f"Risk-Miner-{slug}-{visible[-1]['day']}.md",
        choices=choices,
        place=escape(place),
        title=escape(title),
        timeline=timeline,
        day=date_label(visible[-1]["day"]),
        finding=finding,
        detail=detail,
        cards="".join(cards),
    )
