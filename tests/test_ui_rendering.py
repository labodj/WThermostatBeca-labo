"""Contracts on HTML emitted by the actual firmware page builders."""
import json
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

from render_ui import ROOT, raw_asset, render_pages


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.forms = []
        self.fields = []
        self.tags = []
        self.labels = 0
        self.form = None
        self.ids = []
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        self.tags.append(tag)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "label":
            self.labels += 1
        if tag == "form":
            if self.form is not None:
                raise AssertionError("Nested form")
            self.form = attrs
            self.forms.append(attrs)
        if tag in ("input", "select", "textarea"):
            self.fields.append((tag, attrs, self.labels > 0))

    def handle_endtag(self, tag):
        if tag == "label":
            self.labels -= 1
        if tag == "form":
            self.form = None


class UiRenderingTests(unittest.TestCase):
    def test_resync_requires_confirmation_from_home_and_weblog(self):
        for route in ("/config", "/logging_weblog"):
            forms = Document(self.pages[route]).forms
            self.assertIn({"action": "/thermostat_reinit", "method": "get"}, forms)
            self.assertIn("Resync thermostat</button>", self.pages[route])
        confirmation = self.pages["/thermostat_reinit"]
        forms = Document(confirmation).forms
        self.assertIn({"action": "/save_thermostat_reinit", "method": "post"}, forms)
        self.assertIn({"action": "/config", "method": "get"}, forms)
        self.assertIn("name='confirm' value='1'>Confirm resync</button>", confirmation)
        self.assertIn(">Cancel</button>", confirmation)
        self.assertIn("does not restart the ESP8266 or erase", confirmation)

    def test_info_section_headings_are_centered(self):
        for route in ("/info", "/info-bac"):
            sections = re.findall(r"<th colspan='2' scope='rowgroup'>(.*?)</th>", self.pages[route])
            self.assertCountEqual(["Main", "Clock", "Thermostat"], sections)
        self.assertIn("th[scope=rowgroup]{text-align:center}", self.pages["/css"])
        self.assertIn("th,td{text-align:left;", self.pages["/css"])

    def test_display_branding_and_project_links_keep_legacy_identity(self):
        for route, source in self.pages.items():
            if route in ("/css", "/js", "/restart-status-preview"):
                continue
            with self.subTest(route=route):
                self.assertIn("<strong>WThermostat-Labo</strong>", source)
        repo = "https://github.com/labodj/WThermostatBeca-labo"
        for route, urls in (("/info", (repo, repo + "/issues")),
                            ("/info-bac", (repo, repo + "/issues")),
                            ("/firmware", (repo + "/releases",))):
            for url in urls:
                self.assertRegex(self.pages[route], r"<a\b[^>]*href=['\"]" + re.escape(url) + r"['\"]")
        # This value still seeds default hostnames, MQTT client IDs and AP names.
        application = (ROOT / "WThermostat/WThermostat.cpp").read_text()
        self.assertRegex(application, r'#define\s+APPLICATION\s+"WThermostat"')

    @classmethod
    def setUpClass(cls):
        cls.pages = render_pages()

    def test_schedules_are_complete_when_response_reallocation_is_constrained(self):
        constrained = render_pages(response_heap_budget=10000)
        for route in ("/thermostat_schedules", "/schedules-fine", "/schedules-whole"):
            with self.subTest(route=route):
                self.assertEqual(self.pages[route], constrained[route])
                self.assertIn("Save configuration</button>", constrained[route])
                self.assertIn("Back to Home</button>", constrained[route])
                self.assertTrue(constrained[route].rstrip().endswith("</html>"))

    def test_documents_have_landmarks_labels_and_single_footer(self):
        for route, source in self.pages.items():
            if route in ("/css", "/js"):
                continue
            with self.subTest(route=route):
                doc = Document(source)
                for tag in ("html", "head", "body", "main", "h1"):
                    self.assertEqual(1, doc.tags.count(tag), tag)
                    self.assertEqual(1, source.count("</" + tag + ">"), tag)
                self.assertEqual(len(doc.ids), len(set(doc.ids)))
                self.assertNotIn("user-scalable=no", source)
                for tag, attrs, labelled in doc.fields:
                    self.assertTrue(labelled or attrs.get("type") == "hidden", attrs)
                self.assertTrue(all(form.get("action") for form in doc.forms))

    def test_buttons_table_headers_and_restart_navigation_are_explicit(self):
        for route, source in self.pages.items():
            if route in ("/css", "/js"):
                continue
            with self.subTest(route=route):
                self.assertNotIn("<button>", source)
                self.assertNotIn("<th>", source)
                self.assertNotRegex(source, r"http-equiv=['\"]refresh")
        status = Document(self.pages["/restart-status-preview"])
        self.assertIn({"action": "/config", "method": "get"}, status.forms)

    def test_schedules_preserve_all_fields_and_protocol_precision(self):
        for route, step, maximum in (("/thermostat_schedules", "0.5", "35.0"),
                                     ("/schedules-fine", "0.1", "25.5"),
                                     ("/schedules-whole", "1.0", "35.0")):
            with self.subTest(route=route):
                doc = Document(self.pages[route])
                fields = {attrs["name"]: attrs for _, attrs, _ in doc.fields if attrs["name"] != "csrf"}
                self.assertEqual({day + str(period) + kind for day in "wau" for period in range(1, 7)
                                  for kind in "ht"}, set(fields))
                for name, attrs in fields.items():
                    self.assertIn("required", attrs)
                    if name.endswith("t"):
                        self.assertEqual(("number", "5", maximum, step),
                                         tuple(attrs[key] for key in ("type", "min", "max", "step")))
                    else:
                        self.assertEqual("time", attrs["type"])
                self.assertEqual(21, doc.tags.count("fieldset"))

    def test_upload_and_saved_credentials_contract(self):
        upload = Document(self.pages["/firmware"])
        self.assertEqual("/firmware", upload.forms[0]["action"])
        self.assertEqual("post", upload.forms[0]["method"])
        self.assertEqual("multipart/form-data", upload.forms[0]["enctype"])
        file = next(attrs for _, attrs, _ in upload.fields if attrs.get("name") == "update")
        self.assertEqual("file", file["type"])
        self.assertIn("required", file)
        for route in ("/wifi", "/wifi-off", "/wifi-static"):
            fields = {attrs.get("name"): attrs for _, attrs, _ in Document(self.pages[route]).fields}
            for name in ("p", "mp"):
                self.assertEqual("password", fields[name]["type"])
                self.assertEqual("", fields[name]["value"])
                self.assertEqual("64", fields[name]["maxlength"])
                self.assertIn("checked", fields["keepWifiPassword" if name == "p" else "keepMqttPassword"])
                self.assertEqual(name, fields[name]["id"])
        self.assertRegex(self.pages["/thermostat-fine"], r"<option value='01' selected>")

    def test_shared_assets_stay_small_and_self_contained(self):
        self.assertLess(len(self.pages["/css"].encode()), 2048)
        self.assertLess(len(self.pages["/js"].encode()), 2048)
        self.assertNotRegex(self.pages["/css"], r"@import|url\(")
        for route, source in self.pages.items():
            if route not in ("/css", "/js"):
                self.assertNotRegex(source, r'<script[^>]+src=[\'"]https?://')

    def test_home_mutations_are_post_before_javascript(self):
        methods = {form["action"]: form["method"] for form in Document(self.pages["/config"]).forms}
        self.assertEqual("get", methods["/thermostat_reinit"])
        self.assertEqual("post", methods["/reset"])
        self.assertEqual("get", methods["/firmware"])
        for route, heading in (("/config", "Home"), ("/clock", "Clock"), ("/thermostat", "Thermostat")):
            self.assertIn("<h1>" + heading + "</h1>", self.pages[route])

    def test_legacy_network_values_remain_text(self):
        source = self.pages["/wifi-escaped"]
        fields = {attrs.get("name"): attrs for _, attrs, _ in Document(source).fields}
        self.assertEqual("<IP>'&", fields["staticip"]["value"])
        self.assertNotIn("value='<IP>'&'", source)
        self.assertIn("value='&lt;IP&gt;&#39;&amp;'", source)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to test embedded JavaScript")
    def test_live_log_can_pause_without_growing_a_hidden_buffer(self):
        source = raw_asset(ROOT / "WThermostat/WLogDevice.h", "HTTP_WEBLOG_SCRIPT")
        source = source.replace("<script>", "").replace("</script>", "")
        probe = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const text={value:'',scrollTop:0},pause={checked:false};
const scope={document:{},location:{host:'thermostat'},WebSocket:class{},eb(id){return id==='pauseLog'?pause:text;},setTimeout(){}};
vm.runInNewContext(SOURCE,scope);text.value='before';pause.checked=true;scope.msg('discarded');assert.equal(text.value,'before');
pause.checked=false;scope.msg('after');assert.equal(text.value,'beforeafter');
'''
        subprocess.run(["node", "-e", "const SOURCE=" + json.dumps(source) + ";\n" + probe], check=True)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to test embedded JavaScript")
    def test_log_initialization_waits_for_deferred_helpers(self):
        source = raw_asset(ROOT / "WThermostat/WLogDevice.h", "HTTP_WEBLOG_SCRIPT")
        source = source.replace("<script>", "").replace("</script>", "")
        probe = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
let ready,created=0;
for(const [protocol,prefix] of [['http:','ws://'],['https:','wss://']]){
created=0;
const scope={document:{readyState:'loading',addEventListener(event,fn){assert.equal(event,'DOMContentLoaded');ready=fn;}},
location:{host:'thermostat',protocol},WebSocket:class{constructor(url){assert.equal(url,prefix+'thermostat/wslog');created++;}},eb(){return {value:'',scrollTop:0};},setTimeout(){},clearInterval(){},setInterval(){}};
vm.runInNewContext(SOURCE,scope);assert.equal(created,0);assert(ready);ready();assert.equal(created,1);
}
'''
        subprocess.run(["node", "-e", "const SOURCE=" + json.dumps(source) + ";\n" + probe], check=True)


if __name__ == "__main__":
    unittest.main()
