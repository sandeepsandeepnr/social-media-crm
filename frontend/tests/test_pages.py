from html.parser import HTMLParser
from pathlib import Path
import unittest


FRONTEND = Path(__file__).resolve().parents[1]
PAGES = {
    "dashboard": "dashboard-tab",
    "inbox": "inbox-tab",
    "monitoring": "monitoring-tab",
    "tickets": "tickets-tab",
    "customers": "customers-tab",
    "analytics": "analytics-tab",
    "team": "users-tab",
    "integrations": "platforms-tab",
    "settings": "settings-tab",
}
ADMIN_PAGES = {"admin", "team", "integrations", "settings"}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.body = {}
        self.main = None
        self.scripts = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "body":
            self.body = attrs
        if tag == "main":
            self.main = attrs
        if tag == "script" and "src" in attrs:
            self.scripts.add(attrs["src"])


class IndependentPageTests(unittest.TestCase):
    def test_each_page_owns_its_section_and_shared_assets(self):
        all_sections = set(PAGES.values())
        for page in [*PAGES, "admin"]:
            with self.subTest(page=page):
                parser = PageParser()
                parser.feed((FRONTEND / f"{page}.html").read_text(encoding="utf-8"))
                self.assertEqual(parser.body.get("data-page"), page)
                self.assertIsNotNone(parser.main)
                self.assertTrue({"layout.js", "dashboard.js", "theme.js"} <= parser.scripts)
                self.assertEqual(parser.ids & all_sections, {PAGES[page]} if page in PAGES else set())
                if page in ADMIN_PAGES:
                    self.assertEqual(parser.body.get("data-admin"), "true")
                    self.assertIn("hidden", parser.main)
                    self.assertIn("adminAccessDenied", parser.ids)
                else:
                    self.assertNotIn("hidden", parser.main)


if __name__ == "__main__":
    unittest.main()
