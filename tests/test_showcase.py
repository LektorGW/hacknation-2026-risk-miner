from html.parser import HTMLParser
from urllib.parse import urlsplit

from scripts.build_showcase import build


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        self.targets.extend(value for name, value in attrs if name in ("href", "src"))


def test_static_case_files_are_navigable_without_a_server(tmp_path):
    build(tmp_path)
    assert (tmp_path / "index.html").read_bytes() == (tmp_path / "zagrodno.html").read_bytes()
    for page in tmp_path.glob("*.html"):
        links = Links()
        links.feed(page.read_text(encoding="utf-8"))
        for target in links.targets:
            url = urlsplit(target)
            if not url.scheme and url.path:
                assert not url.path.startswith("/") and (tmp_path / url.path).is_file(), (page.name, target)
    first = (tmp_path / "zagrodno-1.html").read_text(encoding="utf-8")
    assert "00143366/01" in first and "00285691/01" not in first
    assert "00285691/01" in (tmp_path / "zagrodno-3.html").read_text(encoding="utf-8")
