"""Build the public BZP case files without a database or application credentials."""

import argparse
import shutil
from pathlib import Path

from riskminer.db import ROOT
from riskminer.dossier import archive, dossier


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Wybierz pusty katalog dla publicznych akt.")
    for asset in ("static/dossier.css", "static/assets/znak.svg", "static/assets/oczyszczalnia.webp"):
        target = output / asset
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / asset, target)
    for slug, (_, _, notices) in archive().items():
        for step in range(1, len(notices) + 1):
            html = dossier(slug, step, static_site=True)
            (output / f"{slug}-{step}.html").write_text(html, encoding="utf-8")
        shutil.copyfile(output / f"{slug}-{len(notices)}.html", output / f"{slug}.html")
    shutil.copyfile(output / "zagrodno.html", output / "index.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
