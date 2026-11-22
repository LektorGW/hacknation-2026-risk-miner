import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from docx import Document
from openpyxl import Workbook
from pypdf import PdfWriter

from riskminer.ingest import fold, load_file
from riskminer.kpo import find
from riskminer.sources import BZP, _bzp_query, enrich, match, notice_text

ROOT = Path(__file__).resolve().parents[1]


class Ingestion(unittest.TestCase):
    def test_real_workbook_preserves_scope_and_does_not_import_dictionary(self):
        workbook = ROOT / "fixtures/starter/Risk_Miner_dane_projekty.xlsx"
        projects = load_file(workbook.name, workbook.read_bytes())
        self.assertEqual([r["project_id"] for r in projects], [f"RM-2026-{i:03}" for i in range(1, 23)])
        self.assertEqual(projects[1]["cst"], "KPOD.03.15-IW.13-0004/25")
        self.assertEqual(projects[8]["scope"], "część 2")
        self.assertEqual(projects[8]["source"]["locator"], "Projekty, wiersz 10")
        self.assertNotIn("value", projects[1])
        self.assertEqual(fold("Część II Łódź"), "czesc ii lodz")

    def test_semicolon_csv_and_sheet_header_after_preamble(self):
        rows = load_file("sample.csv", "Tytuł;NIP\r\nRury;0000000000".encode("cp1250"))
        self.assertEqual(rows[0]["nip"], "0000000000")
        wb = Workbook()
        wb.active.append(["Lista"])
        wb.active.append(["Nazwa projektu", "NIP"])
        wb.active.append(["Stacja prób", "0123"])
        wb.create_sheet("Legenda").append(["Tytuł projektu"])
        stream = io.BytesIO()
        wb.save(stream)
        self.assertEqual(
            load_file("sample.xlsx", stream.getvalue())[0]["source"]["locator"], "Sheet, wiersz 3"
        )

    def test_document_paragraphs_and_tables_have_locators(self):
        doc = Document()
        doc.add_paragraph("Aneks pierwszy")
        table = doc.add_table(1, 2)
        table.cell(0, 0).text, table.cell(0, 1).text = "Okres", "20 dni"
        out = io.BytesIO()
        doc.save(out)
        rows = load_file("sample.docx", out.getvalue())
        self.assertEqual([i["source"]["locator"] for i in rows], ["akapit 1", "tabela 1, wiersz 1"])
        self.assertIn("20 dni", rows[1]["text"])

    def test_malformed_input_blank_pdf_missing_columns_and_duplicates(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        out = io.BytesIO()
        writer.write(out)
        for name, value in [
            ("broken.xlsx", b"broken"),
            ("empty.pdf", out.getvalue()),
            ("a.csv", b"bad;fields\n1;2"),
            ("b.csv", b"title;title\nA;B"),
        ]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                load_file(name, value)


class Sources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((ROOT / "fixtures/real/cases.json").read_text("utf-8"))

    def test_authentic_history_and_verifiable_provenance(self):
        self.assertEqual(len(self.cases), 22)
        for case in self.cases:
            self.assertTrue(case["records"], case["project"]["project_id"])
            for item in case["records"]:
                for field in (
                    "source",
                    "external_id",
                    "published_at",
                    "retrieved_at",
                    "text",
                    "url",
                    "sha256",
                    "reasons",
                    "locator",
                ):
                    self.assertTrue(item.get(field), (field, item["external_id"]))
                if item["source"] == "BZP":
                    self.assertEqual(
                        item["url"],
                        "https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId="
                        + item["object_id"],
                    )
        credit = next(r for r in self.cases[1]["records"] if r["source"] == "KPO / UMWD")
        self.assertEqual(credit["requested_funding_pln"], 4770558.05)
        self.assertNotIn("contract_value_pln", credit)
        self.assertFalse(any(i.get("lot") == "1" for i in self.cases[8]["records"]))
        self.assertEqual(
            {r["lot"] for r in self.cases[-1]["records"] if r["kind"] == "completion"}, {"1", "2"}
        )

    def test_corner_cases_ocid_shared_across_lots_and_duplicate_completion(self):
        o = self.cases[0]
        awarded = next(r for r in o["records"] if r["kind"] == "award")["awards"][0]
        finished = next(r for r in o["records"] if r["kind"] == "completion")
        self.assertEqual(awarded["contract_key"], finished["contract_key"])
        self.assertEqual(awarded["planned_days"], 365)
        self.assertEqual(finished["facts"]["actual_days"], 442)
        self.assertEqual(finished["facts"]["paid_pln"], 2246177.66)
        duplicates = [r for r in self.cases[1]["records"] if r["kind"] == "completion"]
        self.assertEqual(len({r["contract_key"] for r in duplicates}), 1)
        self.assertEqual(len({r["facts"]["agreed_period"] for r in duplicates}), 2)
        bad = {**finished, "lot": "2"}
        self.assertEqual(match(o["project"] | {"scope": "część 1"}, bad)[0], 0)

    def test_ambiguous_title_does_not_create_certain_match(self):
        unrelated = {
            "external_id": "2022/BZP 00058537/01",
            "title": "Meble do szkoły",
            "buyer": "Urząd Gminy gdzie indziej",
            "buyer_identifier": "1234567890",
        }
        score, reasons = match(self.cases[0]["project"], unrelated)
        self.assertLess(score, 0.75)
        self.assertTrue(any("Rozbieżność" in r for r in reasons))
        official = self.cases[0]["records"][0]
        same_name_wrong_nip = {**official, "buyer_identifier": "9999999999"}
        self.assertLess(match(self.cases[0]["project"], same_name_wrong_nip)[0], 0.75)

    def test_pagination_uses_external_cursor(self):
        raw = {
            "noticeNumber": "2024/BZP 00000001/01",
            "htmlBody": "<h3>1.2.) Dane</h3>",
            "objectId": "last-object",
        }
        with patch("riskminer.sources._request", side_effect=[[raw] * 30, []]) as req:
            notices = _bzp_query(BZP, {"NoticeType": "ContractNotice"}, [])
        self.assertEqual(len(notices), 30)
        self.assertIn("SearchAfter=last-object", req.call_args.args[0])
        self.assertNotIn("style", notice_text("<head><style>body{}</style></head><p>Treść</p>"))

    def test_ted_format_normalization_and_independent_failure(self):
        raw = {
            "publication-number": "3577-2024",
            "notice-type": "can-standard",
            "title-proc": {"pol": "Budowa wodociągu"},
            "description-proc": {"pol": "Opis"},
            "buyer-name": {"pol": ["Miasto"]},
            "publication-date": "2024-01-01+01:00",
        }
        with (
            patch("riskminer.sources._search_bzp", side_effect=URLError("niedostępny")),
            patch(
                "riskminer.sources._request", return_value={"notices": [raw], "totalNoticeCount": 1}
            ) as req,
        ):
            result = enrich({"ted": "2024/S 001-003577", "title": "Budowa wodociągu", "buyer": "Miasto"})
        self.assertEqual(result["records"][0]["source"], "TED")
        self.assertFalse(result["complete"])
        self.assertEqual(result["source_status"]["BZP"]["status"], "failed")
        self.assertTrue(any("BZP" in w for w in result["warnings"]))
        self.assertEqual(req.call_args.args[1]["query"], "publication-number = 3577-2024")

    def test_empty_source_is_successfully_checked(self):
        with (
            patch("riskminer.sources._search_bzp", return_value=[]),
            patch("riskminer.sources._search_ted", return_value=[]),
        ):
            result = enrich({"title": "Modernizacja"})
        self.assertTrue(result["complete"])
        self.assertEqual(result["source_status"]["TED"], {"status": "empty", "matched": 0})

    def test_kpo_number_prefix_and_whole_suffix(self):
        project = {"cst": "KPOD.03.15-IW.13-0004/25", "buyer": "Gmina A", "title": "Budowa sieci"}
        text = "24 KPOD.03.15-IW.13-0004/24 Gmina B 1 111 111,00\n25 KPOD.03.15-IW.13-0004/25 Gmina A Budowa sieci 2 345 678,90\n26 KPOD.03.15-IW.13-0040/25 Miasto B"
        with patch("riskminer.kpo._pages", return_value=[text]):
            result = find(project, "2026-11-22")[0]
        self.assertEqual(result["requested_funding_pln"], 2345678.9)
        self.assertNotIn("Miasto B", result["text"])

    def test_fixed_positive_and_negative_pairs_from_independently_read_pdfs(self):
        expected = {
            "RM-2026-001": {"2026/BZP 00147223/01"},
            "RM-2026-008": {"2026/BZP 00255110/01"},
            "RM-2026-009": {"2025/BZP 00568661/01"},
            "RM-2026-022": {"2024/BZP 00621519/01"},
            "RM-2026-002": {"KPOD.03.15-IW.13-0004/25"},
        }
        excluded = {"RM-2026-008": {"2026/BZP 00255135/01"}, "RM-2026-006": {"2023/BZP 00262901/01"}}
        for case in self.cases:
            pid = case["project"]["project_id"]
            keys = {r["external_id"] for r in case["records"]}
            self.assertTrue(expected.get(pid, set()).issubset(keys), pid)
            self.assertTrue(keys.isdisjoint(excluded.get(pid, set())), pid)


if __name__ == "__main__":
    unittest.main()
