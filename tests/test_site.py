from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import unittest
import unicodedata
from urllib.parse import unquote, urlsplit

import pymupdf
import yaml

from build import ROOT, PDF_FILES, UniqueKeyLoader, latex_escape, load_data, render_html


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.text = []
        self.targets = []
        self.ids = set()
        self.feed(source)

    def handle_data(self, value):
        self.text.append(value)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        for field in ("href", "src"):
            if field in attributes:
                self.targets.append(attributes[field])


def normalized(value):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", value).lower())


class BuildBehaviorTests(unittest.TestCase):
    def test_yaml_webinar_edits_reach_homepage(self):
        data = load_data()
        webinar = data["flyer"]["webinar"]
        webinar["date"] = "December 5, 2026"
        webinar["times"] = ["8:00 AM", "4:00 PM"]
        webinar["signup_url"] = "https://example.com/updated-registration"
        with tempfile.TemporaryDirectory() as directory:
            render_html(data, Path(directory))
            home = Page((Path(directory) / "index.html").read_text(encoding="utf-8"))
            rendered = " ".join(home.text)
            for time in webinar["times"]:
                self.assertIn(f"{webinar['date']} at {time}", rendered)
            self.assertIn(webinar["timezone"], rendered)
            self.assertIn(webinar["signup_url"], home.targets)

    def test_yaml_edit_reaches_html_and_latex_escaping(self):
        data = load_data()
        sample = 'A & B <test> 50% $funding #1_{x}\\path'
        data["flyer"]["sections"][0]["items"][0] = sample
        with tempfile.TemporaryDirectory() as directory:
            render_html(data, Path(directory))
            html = (Path(directory) / "flyer.html").read_text(encoding="utf-8")
            self.assertIn(sample, "".join(Page(html).text))
            self.assertIn("&lt;test&gt;", html)
            self.assertNotIn("<test>", html)
        escaped = latex_escape(sample)
        for expected in (r"\&", r"\%", r"\$", r"\#", r"\_", r"\{", r"\textbackslash{}"):
            self.assertIn(expected, escaped)

    def test_duplicate_yaml_and_unsafe_url_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "Duplicate YAML key"):
            yaml.load("title: one\ntitle: two", Loader=UniqueKeyLoader)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            data = load_data()
            data["links"]["items"][0]["url"] = "javascript:alert(1)"
            for name, value in data.items():
                (root / "data" / f"{name}.yml").write_text(
                    yaml.safe_dump(value), encoding="utf-8"
                )
            with self.assertRaisesRegex(ValueError, "HTTPS URL"):
                load_data(root)


class GeneratedSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_data()
        cls.site = ROOT / "_site"
        cls.pages = {
            name: Page((cls.site / f"{name}.html").read_text(encoding="utf-8"))
            for name in ("index", "links", "flyer")
        }

    def test_homepage_contains_webinar_sessions_and_registration(self):
        webinar = self.data["flyer"]["webinar"]
        home = self.pages["index"]
        rendered = " ".join(home.text)
        for time in webinar["times"]:
            self.assertIn(f"{webinar['date']} at {time}", rendered)
        for field in ("title", "timezone", "signup_label"):
            self.assertIn(webinar[field], rendered)
        self.assertIn(webinar["signup_url"], home.targets)

    def test_navigation_assets_and_both_pdf_links_on_every_page(self):
        for name, page in self.pages.items():
            with self.subTest(page=name):
                for filename in PDF_FILES.values():
                    self.assertIn(f"assets/{filename}", page.targets)
                for destination in self.pages:
                    self.assertIn(f"{destination}.html", page.targets)
                for target in page.targets:
                    parsed = urlsplit(target)
                    if parsed.scheme:
                        continue
                    relative = unquote(parsed.path)
                    path = self.site / (relative or f"{name}.html")
                    self.assertTrue(path.is_file(), f"Missing target: {target}")
                    if parsed.fragment:
                        destination = Path(relative).stem if relative else name
                        self.assertIn(parsed.fragment, self.pages[destination].ids)

    def test_all_yaml_content_and_hyperlinks_reach_html_and_pdfs(self):
        for name, filename in PDF_FILES.items():
            with self.subTest(document=name):
                data = self.data[name]
                values = [data["title"]]
                urls = ["mailto:" + data["contact_email"]]
                if name == "links":
                    values.append(data["subtitle"])
                    for item in data["items"]:
                        values.extend([item["title"], item["url"]])
                        urls.append(item["url"])
                else:
                    values.append(data["deadline"])
                    urls.append(data["apply_url"])
                    for section in data["sections"]:
                        values.extend([section["title"], *section["items"]])
                        if "introduction" in section:
                            values.append(section["introduction"])
                        if "more" in section:
                            urls.append(section["more"]["url"])
                            values.extend([section["more"]["prefix"], section["more"]["label"]])
                document = pymupdf.open(self.site / "assets" / filename)
                self.assertEqual(len(document), 1, "The supplied flyer and links should each fit one page")
                pdf_text = normalized(" ".join(page.get_text() for page in document))
                html_text = normalized(" ".join(self.pages[name].text))
                for value in values:
                    self.assertIn(normalized(value), html_text)
                    self.assertIn(normalized(value), pdf_text)
                pdf_urls = {
                    link["uri"]
                    for page in document
                    for link in page.get_links()
                    if "uri" in link
                }
                for url in urls:
                    self.assertIn(url, self.pages[name].targets)
                    self.assertIn(url, pdf_urls)
                for page in document:
                    for word in page.get_text("words"):
                        self.assertTrue(page.rect.contains(pymupdf.Rect(word[:4])))


if __name__ == "__main__":
    unittest.main()
