"""Core forms must remain protected and usable when external JavaScript fails."""

import unittest
from html.parser import HTMLParser

from render_ui import render_pages


class Forms(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"attrs": attrs, "inputs": []}
            self.forms.append(self.current)
        elif tag == "input" and self.current is not None:
            self.current["inputs"].append(attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


class ServerFormTests(unittest.TestCase):
    def test_every_post_form_has_one_server_generated_csrf_token(self):
        checked = 0
        for route, body in render_pages().items():
            if route in ("/css", "/js"):
                continue
            for form in Forms(body).forms:
                tokens = [f for f in form["inputs"] if f.get("name") == "csrf"]
                with self.subTest(route=route, action=form["attrs"].get("action")):
                    if form["attrs"].get("method", "get").lower() == "post":
                        checked += 1
                        self.assertEqual(1, len(tokens))
                        self.assertEqual("hidden", tokens[0].get("type"))
                        self.assertEqual("preview-token", tokens[0].get("value"))
                    else:
                        self.assertEqual([], tokens)
        self.assertGreaterEqual(checked, 10)
