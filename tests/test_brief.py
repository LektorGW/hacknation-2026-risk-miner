from io import BytesIO

from docx import Document

from riskminer.brief import create_brief


def test_brief_preserves_answer_spans_clause_and_individual_review():
    def source(text):
        return {"id": "annex-1", "title": "Aneks 1", "locator": "strona 2", "excerpt": text}

    answer = "X" * 320 + " Operator zatwierdził wariant B."
    checklist = [{
        "id": "R1", "question": "Czy operator zatwierdził wariant?", "action": "Sprawdź pisemne potwierdzenie.",
        "evidence": [source("Pierwsza wzmianka o sprawie.")], "expert_source": source("Zalecenie eksperta."),
        "status": "documented", "checks": [{"label": "Stanowisko operatora", "found": True, "evidence": [source(answer)]}],
        "draft_clause": {"text": "Zamawiający wskazuje datę odbioru.", "source": source("Wzór zapisu umownego.")},
    }]
    result = {"sample_size": 0, "checklist": checklist, "flags": [*checklist, {"id": "R2", "question": "Drugi wniosek?"}],
              "reviews": {"R2": {"status": "rejected", "actor": "Anna", "at": "2025-01-10", "comment": "Zakres wyłączono."}},
              "metrics": {k: {"count": 0} for k in ("days_change", "cost_change_pct", "actual_days")}}
    document = Document(BytesIO(create_brief({"title": "Test"}, result)))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Znaleziono w dokumentacji: Stanowisko operatora. [3]" in text
    assert "[3] Aneks 1 · strona 2\n" + answer in text
    assert "Zamawiający wskazuje datę odbioru. [4]" in text
    assert "Wniosek odrzucony przez eksperta. Anna" in text and "Zakres wyłączono." in text
    assert "Uzupełnienie osoby prowadzącej" not in text


def test_brief_accepts_page_breaks_and_control_characters_from_imported_text():
    project = {"title": "Pompownia\fA", "description": "Strona pierwsza\fStrona druga\x01 – Łódź"}
    ref = {"id": "source", "title": "Załącznik\x01", "locator": "str. 2", "excerpt": "Wynik\fpróby."}
    result = {"sample_size": 0, "checklist": [{"title": "Odbiór", "evidence": [ref]}],
              "metrics": {k: {"count": 0} for k in ("days_change", "cost_change_pct", "actual_days")}}
    text = "\n".join(p.text for p in Document(BytesIO(create_brief(project, result))).paragraphs)
    assert "Pompownia\nA" in text and "Strona druga  – Łódź" in text and "Wynik\npróby." in text
