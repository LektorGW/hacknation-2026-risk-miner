"""Sprawdza działający pokaz przez publiczny HTTPS. Opcja --reset-test przywraca stan wzorcowy jury."""

import argparse
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZipFile

from jury import PRIVATE, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--reset-test", action="store_true")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    if not base.startswith("https://"):
        parser.error("Podaj adres HTTPS kopii dla jury.")
    token = (PRIVATE / "jury.txt").read_text().strip()
    bearer = "Bearer " + token
    basic = "Basic " + base64.b64encode(("jury:" + token).encode()).decode()

    def request(path, auth=None, body=None, status=200):
        headers = {"Authorization": auth} if auth else {}
        if body is not None:
            headers.update({"Origin": base, "Content-Type": "application/json"})
        payload = json.dumps(body).encode() if body is not None else None
        try:
            with urlopen(
                Request(base + path, data=payload, headers=headers), timeout=90
            ) as res:
                assert res.status == status, (path, res.status)
                return res.read()
        except HTTPError as exc:
            if exc.code != status:
                raise

    def state():
        return json.loads(request("/api/state", bearer))

    request("/healthz")
    request("/api/state", status=401)
    request("/materialy/", status=401)
    original = state()
    assert original["auth"]["role"] == "expert" and original["stats"]["projects"] == 22
    print("Konto jury i dostęp do 22 inwestycji: OK", flush=True)
    film = request("/materialy/film.mp4", basic)
    assert (
        hashlib.sha256(film).digest()
        == hashlib.sha256(
            (ROOT / "deliverables/demo-risk-miner.mp4").read_bytes()
        ).digest()
    )
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    with ZipFile(io.BytesIO(request("/materialy/kod.zip", basic))) as archive:
        assert archive.comment.decode() == expected and archive.testzip() is None
    with tempfile.TemporaryDirectory() as temp:
        env = dict(
            os.environ,
            GIT_CONFIG_COUNT="2",
            GIT_CONFIG_KEY_0="http.extraHeader",
            GIT_CONFIG_VALUE_0="Authorization: " + basic,
            GIT_CONFIG_KEY_1="credential.helper",
            GIT_CONFIG_VALUE_1="",
            GIT_TERMINAL_PROMPT="0",
        )
        subprocess.run(
            ["git", "clone", "--quiet", base + "/materialy/risk-miner.git", temp],
            env=env,
            check=True,
        )
        assert (
            subprocess.check_output(
                ["git", "-C", temp, "rev-parse", "HEAD"], text=True
            ).strip()
            == expected
        )
    print("Film, archiwum i klon Git przez HTTPS: OK", expected, flush=True)
    if args.reset_test:
        data = {
            "project": {
                "title": "Próba odtworzenia " + uuid4().hex,
                "description": "Budowa sieci kanalizacji sanitarnej z przepompownią.",
                "type": "Sieć kanalizacji sanitarnej",
            },
            "filters": {"preview_links": True},
        }
        result = json.loads(request("/api/analyze", bearer, data))
        path = "/api/analyses/" + result["analysis_id"]
        request(path, bearer)
        with ZipFile(
            io.BytesIO(
                request("/api/brief", bearer, {"analysis_id": result["analysis_id"]})
            )
        ) as doc:
            assert "word/document.xml" in doc.namelist()
        subprocess.run(
            [sys.executable, str(Path(__file__).with_name("jury.py")), "reset"],
            check=True,
        )
        for attempt in range(30):
            try:
                request("/healthz")
                break
            except OSError:
                if attempt == 29:
                    raise
                time.sleep(1)
        request(path, bearer, status=404)
        restored = state()
        for key in ("stats", "reviews", "audit"):
            assert restored[key] == original[key], key
        print("Analiza przez HTTPS, eksport DOCX i reset do wzorca: OK")


if __name__ == "__main__":
    main()
