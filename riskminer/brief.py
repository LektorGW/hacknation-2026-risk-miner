"""Create an editable, source-linked preparatory note for the investment file."""

import re
from datetime import date
from io import BytesIO
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Cm, Pt, RGBColor


def _word_text(value):
    # Form feeds separate pages in extracted text but are invalid inside Office XML.
    text = str(value).replace("\f", "\n").replace("\v", "\n")
    return re.sub(r"[\x00-\x08\x0e-\x1f\ud800-\udfff\ufffe\uffff]", " ", text)


def _external(paragraph, url, label):
    label = _word_text(label)
    if not isinstance(url, str) or url != _word_text(url) or not url.startswith(("https://", "http://")):
        paragraph.add_run(label)
        return
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True))
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "006952")
    props.append(color)
    run.append(props)
    text = OxmlElement("w:t")
    text.text = label
    run.append(text)
    link.append(run)
    paragraph._p.append(link)


def _interval_text(interval):
    return f"{interval['low']:,.2f} – {interval['high']:,.2f}".replace(",", " ").replace(".", ",")


def create_brief(project, result, sensitivity_selection=None):
    doc = Document()
    def paragraph(text="", style=None):
        return doc.add_paragraph(_word_text(text), style)

    def heading(text, level):
        return doc.add_heading(_word_text(text), level)

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin = sec.bottom_margin = Cm(2)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(5)
    for name in ("Heading 1", "Heading 2"):
        doc.styles[name].font.color.rgb = RGBColor.from_string("08644F")
    doc.styles["Title"].font.color.rgb = RGBColor.from_string("151C1B")
    doc.styles["Title"].font.size = Pt(24)
    style_pr = doc.styles["Title"].element.get_or_add_pPr()
    border = style_pr.find(qn("w:pBdr"))
    if border is not None:
        style_pr.remove(border)
    sec.header.paragraphs[0].text = "RISK MINER     /     PRZYGOTOWANIE INWESTYCJI"
    sec.footer.paragraphs[0].text = "Risk Miner  ·  Karta robocza do weryfikacji przez eksperta"
    paragraph("Karta przygotowania inwestycji", "Title")
    heading(str(project.get("title") or "Planowane przedsięwzięcie"), 1)
    paragraph(
        f"Data opracowania {date.today():%d.%m.%Y}     •     Liczba podobnych projektów {result['sample_size']}"
    )
    approval = result.get("reviews", {}).get("all")
    if approval:
        status = "zatwierdzona" if approval["status"] == "accepted" else "odrzucona"
        paragraph(
            f"Ocena ekspercka: {status}. Osoba: {approval['actor']}. Data: {approval['at'][:10]}."
        )
        if approval.get("comment"):
            paragraph(approval["comment"])
    else:
        paragraph("Status: analiza robocza do oceny eksperta.")
    if project.get("description"):
        paragraph(str(project["description"])[:1400])
    refs = {}

    def cite(ref):
        if not isinstance(ref, dict):
            return ""
        k = tuple(str(ref.get(key) or "") for key in ("id", "url", "locator", "excerpt", "start", "end"))
        if k not in refs:
            refs[k] = (len(refs) + 1, ref)
        return f"[{refs[k][0]}]"

    def short_refs(sources):
        numbers = sorted({int(cite(s)[1:-1]) for s in sources if isinstance(s, dict)})
        groups = []
        for n in numbers:
            if groups and n == groups[-1][-1] + 1:
                groups[-1].append(n)
            else:
                groups.append([n])
        return " ".join(f"[{g[0]}–{g[-1]}]" if len(g) > 1 else f"[{g[0]}]" for g in groups)

    heading("Pytania do wyjaśnienia", 1)
    checklist = list(result.get("checklist") or [])
    selected = {f.get("id") for f in checklist}
    reviews = result.get("reviews") or {}
    checklist.extend(f for f in result.get("flags", []) if f.get("id") in reviews and f.get("id") not in selected)
    for f in checklist:
        heading(f.get("question") or f["title"], 2)
        review = reviews.get(f.get("id"))
        if review:
            status = "zatwierdzony" if review["status"] == "accepted" else "odrzucony"
            paragraph(f"Wniosek {status} przez eksperta. {review['actor']}, {review['at'][:10]}.")
            if review.get("comment"):
                paragraph(review["comment"])
            if status == "odrzucony":
                continue
        labels = short_refs([*(f.get("evidence") or [])[:2], f.get("expert_source")])
        paragraph(f"{f.get('action', '')} {labels}".strip())
        for precedent in f.get("precedents", [])[:2]:
            event = precedent.get("event") or {}
            paragraph(f"Podobny przypadek: {precedent.get('title') or precedent.get('id')}. "
                              f"{event.get('title') or ''} {short_refs((event.get('evidence') or [])[:2])}".strip())
        for check in f.get("checks") or []:
            status = "Znaleziono w dokumentacji" if check.get("found") else "Do uzupełnienia"
            paragraph(f"{status}: {check['label']}. {short_refs((check.get('evidence') or [])[:2])}".strip())
        if not f.get("checks") and f.get("answer_evidence"):
            paragraph("Odpowiedź w dokumentacji " + short_refs(f["answer_evidence"][:2]))
        clause = f.get("draft_clause")
        if isinstance(clause, dict) and clause.get("text"):
            paragraph(f"Propozycja zapisu do oceny eksperta: {clause['text']} {cite(clause.get('source'))}".strip())
        if f.get("status") != "documented":
            paragraph("Uzupełnienie osoby prowadzącej: ____________________________________")
    if not checklist:
        paragraph(
            "W analizowanym materiale nie znaleziono podstaw do sformułowania pytań według aktywnego katalogu."
        )
    heading("Porównanie kosztów i terminów", 1)
    for k, title in (
        ("days_change", "Zmiana czasu realizacji"),
        ("cost_change_pct", "Zmiana kosztu"),
        ("actual_days", "Rzeczywisty czas realizacji"),
    ):
        m = result["metrics"][k]
        if m["count"]:
            labels = short_refs(s for p in m["points"] for s in p["sources"])
            paragraph(
                f"{title} ({m.get('scope_label', '')}). Zakres obserwowany {m['min']:g}–{m['max']:g} {m['unit']}. Mediana {m['median']:g}. Liczba obserwacji {m['count']}. {labels}"
            )
        else:
            paragraph(f"{title}. Brak porównywalnych wartości ze wskazanym źródłem.")
    for w in result.get("warnings", []):
        paragraph(w)
    for k in ("cost", "duration"):
        scenario = result.get("scenario", {}).get(k)
        if scenario:
            paragraph(
                f"Scenariusz przy historycznych odchyleniach ({scenario['basis']}): "
                f"{scenario['low']:g}–{scenario['high']:g} {scenario['unit']}. "
                f"Liczba obserwacji {scenario['count']}."
            )
    scenario = result.get("scenario", {})
    available = [k for k in ("duration", "cost") if (scenario.get(k) or {}).get("without_one")]
    if sensitivity_selection is not None and (
        not isinstance(sensitivity_selection, dict) or sensitivity_selection.get("metric") not in available
    ):
        raise ValueError("Wybrana miara nie występuje w zapisanej analizie.")
    if available:
        key = sensitivity_selection["metric"] if sensitivity_selection else available[0]
        base = scenario[key]
        variants = base["without_one"]
        choice = variants[0] if sensitivity_selection is None else next(
            (v for v in variants if v["omitted_id"] == sensitivity_selection.get("omitted_id")), None
        )
        if choice is None:
            raise ValueError("Wybrany projekt nie występuje w tej grupie porównawczej.")
        point = next(p for p in result["metrics"][base["metric"]]["points"] if p["id"] == choice["omitted_id"])
        heading("Wpływ pominięcia jednego projektu", 1)
        unit = "zł" if key == "cost" else "dni"
        paragraph(f"Pełna grupa (n = {base['count']}): {_interval_text(base)} {unit}.")
        paragraph(f"Pominięty przypadek: {point['title']} ({point['id']}). " + short_refs(point["sources"]))
        if choice["low"] is None:
            paragraph(f"Po pominięciu pozostały {choice['count']} obserwacje. Wymagane są co najmniej trzy.")
        else:
            paragraph(f"Po pominięciu (n = {choice['count']}): {_interval_text(choice)} {unit}.")
        paragraph("Porównanie wykorzystuje ten sam plan i historyczne odchylenia z zapisanej analizy.")
    heading("Decyzja prowadzącego", 1)
    paragraph("Działanie i osoba odpowiedzialna: __________________________________")
    paragraph("Termin i podpis: ___________________________________________________")
    if refs:
        if len(refs) > 5:
            doc.add_page_break()
        heading("Dokumenty i fragmenty źródłowe", 1)
        for n, r in refs.values():
            p = paragraph()
            p.add_run(f"[{n}] ").bold = True
            label = str(r.get("source") or r.get("title") or r.get("id"))
            if r.get("source") in {"BZP", "TED"}:
                label += " · " + str(r.get("title") or r.get("external_id") or r["id"])
            _external(p, r.get("url"), label)
            p.add_run(" · " + _word_text(r.get("locator") or r.get("id") or ""))
            if r.get("excerpt"):
                p.add_run("\n" + _word_text(r["excerpt"]))
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()
