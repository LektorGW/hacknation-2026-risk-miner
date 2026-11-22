"""Create an editable, source-linked preparatory note for the investment file."""

from datetime import date
from io import BytesIO
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Cm, Pt, RGBColor


def _external(paragraph, url, label):
    if not str(url or "").startswith(("https://", "http://")):
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
    doc.add_paragraph("Karta przygotowania inwestycji", "Title")
    doc.add_heading(str(project.get("title") or "Planowane przedsięwzięcie"), 1)
    doc.add_paragraph(
        f"Data opracowania {date.today():%d.%m.%Y}     •     Liczba podobnych projektów {result['sample_size']}"
    )
    approval = result.get("reviews", {}).get("all")
    if approval:
        status = "zatwierdzona" if approval["status"] == "accepted" else "odrzucona"
        doc.add_paragraph(
            f"Ocena ekspercka: {status}. Osoba: {approval['actor']}. Data: {approval['at'][:10]}."
        )
        if approval.get("comment"):
            doc.add_paragraph(approval["comment"])
    else:
        doc.add_paragraph("Status: analiza robocza do oceny eksperta.")
    if project.get("description"):
        doc.add_paragraph(str(project["description"])[:1400])
    refs = {}

    def cite(ref):
        if not isinstance(ref, dict):
            return ""
        k = (ref.get("id"), str(ref.get("locator") or ""))
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

    doc.add_heading("Pytania do wyjaśnienia", 1)
    for f in result.get("checklist", []):
        doc.add_heading(f.get("question") or f["title"], 2)
        evidence = list(f.get("evidence") or [])
        if f.get("expert_source"):
            evidence.append(f["expert_source"])
        for precedent in f.get("precedents", [])[:2]:
            evidence.extend(precedent.get("event", {}).get("evidence") or [])
        labels = " ".join(dict.fromkeys(cite(r) for r in evidence[:5]))
        doc.add_paragraph(f"{f.get('action', '')} {labels}".strip())
        doc.add_paragraph("Odpowiedź osoby prowadzącej: ____________________________________")
    if not result.get("checklist"):
        doc.add_paragraph(
            "W analizowanym materiale nie znaleziono podstaw do sformułowania pytań według aktywnego katalogu."
        )
    doc.add_heading("Porównanie kosztów i terminów", 1)
    for k, title in (
        ("days_change", "Zmiana czasu realizacji"),
        ("cost_change_pct", "Zmiana kosztu"),
        ("actual_days", "Rzeczywisty czas realizacji"),
    ):
        m = result["metrics"][k]
        if m["count"]:
            labels = short_refs(s for p in m["points"] for s in p["sources"])
            doc.add_paragraph(
                f"{title} ({m.get('scope_label', '')}). Zakres obserwowany {m['min']:g}–{m['max']:g} {m['unit']}. Mediana {m['median']:g}. Liczba obserwacji {m['count']}. {labels}"
            )
        else:
            doc.add_paragraph(f"{title}. Brak porównywalnych wartości ze wskazanym źródłem.")
    for w in result.get("warnings", []):
        doc.add_paragraph(w)
    for k in ("cost", "duration"):
        scenario = result.get("scenario", {}).get(k)
        if scenario:
            doc.add_paragraph(
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
        doc.add_heading("Wpływ pominięcia jednego projektu", 1)
        unit = "zł" if key == "cost" else "dni"
        doc.add_paragraph(f"Pełna grupa (n = {base['count']}): {_interval_text(base)} {unit}.")
        doc.add_paragraph(f"Pominięty przypadek: {point['title']} ({point['id']}). " + short_refs(point["sources"]))
        if choice["low"] is None:
            doc.add_paragraph(f"Po pominięciu pozostały {choice['count']} obserwacje. Wymagane są co najmniej trzy.")
        else:
            doc.add_paragraph(f"Po pominięciu (n = {choice['count']}): {_interval_text(choice)} {unit}.")
        doc.add_paragraph("Porównanie wykorzystuje ten sam plan i historyczne odchylenia z zapisanej analizy.")
    doc.add_heading("Decyzja prowadzącego", 1)
    doc.add_paragraph("Działanie i osoba odpowiedzialna: __________________________________")
    doc.add_paragraph("Termin i podpis: ___________________________________________________")
    if refs:
        if len(refs) > 5:
            doc.add_page_break()
        doc.add_heading("Dokumenty i fragmenty źródłowe", 1)
        for n, r in refs.values():
            p = doc.add_paragraph()
            p.add_run(f"[{n}] ").bold = True
            label = str(r.get("source") or r.get("title") or r.get("id"))
            if r.get("source") in {"BZP", "TED"}:
                label += " · " + str(r.get("title") or r.get("external_id") or r["id"])
            _external(p, r.get("url"), label)
            p.add_run(" · " + str(r.get("locator") or r.get("id") or ""))
            if r.get("excerpt"):
                p.add_run("\n" + str(r["excerpt"])[:310])
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()
