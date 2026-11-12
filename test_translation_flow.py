"""Offline regressions. Only the external provider boundary is replaced."""
import io
import json
import os
import socket
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch

# Importing the application must not require production credentials.
with patch.dict(os.environ, {"NVIDIA_API_KEY": "offline-test-key"}):
    import app as module


def response(text="Merhaba", reason="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=reason)])


class TranslationFlowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = patch.object(module, "BASE_OUTPUT_DIR", self.directory.name)
        self.output.start()
        self.addCleanup(self.output.stop)
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("Offline tests cannot access network"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.client = module.app.test_client()
        with module.ADMISSION_GATE._lock:
            module.ADMISSION_GATE._cooldown_until = 0.0
            module.ADMISSION_GATE._emergency_lock = False
            module.ADMISSION_GATE._active = 0

    def upload(self, value=b'{"hello":"Hello"}', targets=None, source="en", filename="common.json"):
        return self.client.post("/translate", data={"files": (io.BytesIO(value), filename), "languages": targets or ["tr"], "source_language": source})

    def test_homepage_renders_form_controls_in_body_and_valid_scripts(self):
        class PageParser(HTMLParser):
            void_tags = {"meta", "link", "input", "img", "br", "hr"}
            def __init__(self):
                super().__init__()
                self.tags = []
                self.stack = []
                self.scripts = []
                self.styles = []
            def handle_starttag(self, tag, attrs):
                self.tags.append((tag, dict(attrs), tuple(self.stack)))
                if tag not in self.void_tags:
                    self.stack.append(tag)
                if tag == "script":
                    self.scripts.append("")
                elif tag == "style":
                    self.styles.append("")
            def handle_endtag(self, tag):
                if tag in self.stack:
                    del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]
            def handle_data(self, data):
                if self.stack and self.stack[-1] == "script":
                    self.scripts[-1] += data
                elif self.stack and self.stack[-1] == "style":
                    self.styles[-1] += data
        result = self.client.get("/")
        parser = PageParser()
        parser.feed(result.get_data(as_text=True))
        forms = [(attrs, ancestors) for tag, attrs, ancestors in parser.tags if tag == "form"]
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0][0]["action"], "/translate")
        self.assertIn("body", forms[0][1])
        controls = [(tag, attrs) for tag, attrs, ancestors in parser.tags if "form" in ancestors]
        self.assertTrue(any(tag == "input" and attrs.get("type") == "file" and attrs.get("name") == "files" for tag, attrs in controls))
        self.assertTrue(any(tag == "select" and attrs.get("name") == "source_language" for tag, attrs in controls))
        self.assertTrue(any(tag == "button" and attrs.get("type") == "submit" for tag, attrs in controls))
        self.assertTrue(parser.styles)
        self.assertTrue(any(script.strip() for script in parser.scripts))
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required to parse the rendered inline scripts")
        for script in parser.scripts:
            check = subprocess.run([node, "--check", "-"], input=script, text=True, capture_output=True)
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_provider_receives_language_pair_and_unmodified_source(self):
        with patch.object(module.client.chat.completions, "create", return_value=response()) as provider:
            self.assertEqual(module.translate_text("Hello", "tr"), "Merhaba")
        self.assertEqual(provider.call_args.kwargs["messages"], [{"role":"system","content":"en-tr"},{"role":"user","content":"Hello"}])

    def test_provider_alias_and_reverse_english_pair(self):
        with patch.object(module.client.chat.completions, "create", return_value=response()) as provider:
            self.assertEqual(self.upload(targets=["es-419"]).status_code, 200)
            self.assertEqual(provider.call_args.kwargs["messages"][0]["content"], "en-es-us")
            self.assertEqual(self.upload(source="tr", targets=["en"]).status_code, 200)
            self.assertEqual(provider.call_args.kwargs["messages"][0]["content"], "tr-en")

    def test_invalid_pairs_are_rejected_before_provider(self):
        for source, targets in [("",["tr"]),("xx",["tr"]),("en",["tr","xx"])]:
            with self.subTest(source=source, targets=targets):
                self.assertEqual(self.upload(source=source, targets=targets).status_code, 400)

    def test_non_english_pair_uses_validated_english_intermediate(self):
        with patch.object(module.client.chat.completions, "create", side_effect=[response("Hello {name}"), response("Hallo {name}")]) as provider:
            result = self.upload(b'{"hello":"Merhaba {name}"}', source="tr", targets=["de"])
        self.assertEqual(result.status_code, 200)
        self.assertEqual([call.kwargs["messages"] for call in provider.call_args_list], [
            [{"role":"system","content":"tr-en"},{"role":"user","content":"Merhaba {name}"}],
            [{"role":"system","content":"en-de"},{"role":"user","content":"Hello {name}"}],
        ])
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertEqual(json.loads(archive.read("common_de.json")), {"hello":"Hallo {name}"})

    def test_same_language_copies_exact_values_without_provider(self):
        data = b'{"hello":"  Merhaba {name}  ","nested":[42,true,null,""]}'
        with patch.object(module.client.chat.completions, "create", side_effect=AssertionError("No provider call expected")):
            result = self.upload(data, source="tr", targets=["tr"])
            self.assertEqual(module.translate_text("  Merhaba  ", "tr", "tr"), "  Merhaba  ")
        self.assertEqual(result.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertEqual(json.loads(archive.read("common_tr.json")), json.loads(data))

    def test_mixed_targets_share_request_local_english_intermediate(self):
        calls = []
        def provider(**kwargs):
            pair = kwargs["messages"][0]["content"]
            calls.append((pair, kwargs["messages"][1]["content"]))
            return response({"tr-en":"Hello {name}","en-de":"Hallo {name}","en-fr":"Bonjour {name}"}[pair])
        data = b'{"hello":"Merhaba {name}","nested":[42,true,null," "]}'
        with patch.object(module.client.chat.completions, "create", side_effect=provider):
            result = self.upload(data, source="tr", targets=["tr","en","de","fr"])
        self.assertEqual(result.status_code, 200)
        self.assertCountEqual(calls, [("tr-en","Merhaba {name}"),("en-de","Hello {name}"),("en-fr","Hello {name}")])
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            for code, text in [("tr","Merhaba {name}"),("en","Hello {name}"),("de","Hallo {name}"),("fr","Bonjour {name}")]:
                self.assertEqual(json.loads(archive.read(f"common_{code}.json")), {"hello":text,"nested":[42,True,None," "]})

    def test_either_pivot_hop_failure_prevents_archive_publication(self):
        for hop in (1, 2):
            for invalid in [RuntimeError("provider unavailable"),response(""),response("partial", "length"),response("Changed {isim}")]:
                with self.subTest(hop=hop, invalid=invalid):
                    completions = [invalid] if hop == 1 else [response("Hello {name}"), invalid]
                    with patch.object(module.client.chat.completions, "create", side_effect=completions):
                        self.assertEqual(self.upload(b'{"hello":"Merhaba {name}"}', source="tr", targets=["de"]).status_code, 502)
                    self.assertFalse(any(files for _, _, files in os.walk(self.directory.name)))

    def test_invalid_uploads_are_bad_requests(self):
        # .json files with invalid/empty content are rejected. .txt and .pdf are
        # now accepted formats, so they are no longer part of this list.
        for data, filename in [(b"{", "bad.json"), (b"", "empty.json")]:
            with self.subTest(filename=filename):
                self.assertEqual(self.upload(data, filename=filename).status_code, 400)

    def test_partial_provider_failure_does_not_publish_archive(self):
        with patch.object(module.client.chat.completions, "create", side_effect=[response(), RuntimeError("provider unavailable")]):
            self.assertEqual(self.upload(b'{"a":"Hello","b":"World","blank":" "}').status_code, 502)
        self.assertFalse(any(files for _, _, files in os.walk(self.directory.name)))

    def test_empty_truncated_or_changed_placeholders_are_errors(self):
        for completion in [response(""),response("partial", "length"),response("Merhaba {isim} %s %d")]:
            with self.subTest(completion=completion):
                with patch.object(module.client.chat.completions, "create", return_value=completion):
                    self.assertEqual(self.upload(b'{"hello":"Hello {name} %s %d"}').status_code, 502)

    def test_zip_preserves_json_types_keys_placeholders_and_session_download(self):
        data = b'{"hello":"Hello {name} %s %d","nested":[42,true,null,"",{"id":" "}]}'
        with patch.object(module.client.chat.completions, "create", return_value=response("Merhaba {name} %s %d")):
            result = self.upload(data, filename="../../common.json")
        self.assertEqual(result.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertEqual(archive.namelist(), ["common_tr.json"])
            self.assertEqual(json.loads(archive.read("common_tr.json")), {"hello":"Merhaba {name} %s %d","nested":[42,True,None,"",{"id":" "}]})
        filename = result.headers["Content-Disposition"].split("filename=")[1].strip('"')
        download = self.client.get("/download/" + filename)
        self.assertEqual(download.data, result.data)
        download.close()

    def test_txt_file_translated_per_target_language(self):
        with patch.object(module.client.chat.completions, "create", side_effect=[response("Merhaba")]) as provider:
            result = self.upload(b"Hello world", filename="greeting.txt", targets=["tr"])
        self.assertEqual(result.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertIn("greeting_tr.txt", archive.namelist())
            self.assertEqual(archive.read("greeting_tr.txt").decode("utf-8"), "Merhaba")
        self.assertEqual(provider.call_args.kwargs["messages"], [{"role":"system","content":"en-tr"},{"role":"user","content":"Hello world"}])

    def test_txt_same_language_copies_without_provider(self):
        with patch.object(module.client.chat.completions, "create", side_effect=AssertionError("No provider call expected")):
            result = self.upload(b"Merhaba", filename="greeting.txt", source="tr", targets=["tr"])
        self.assertEqual(result.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertEqual(archive.read("greeting_tr.txt").decode("utf-8"), "Merhaba")

    def test_pdf_file_extracted_and_translated(self):
        class FakePage:
            def extract_text(self):
                return "Hello PDF"

        class FakeReader:
            def __init__(self, stream):
                self.pages = [FakePage()]

        with patch.object(module, "PdfReader", FakeReader), \
             patch.object(module.client.chat.completions, "create", return_value=response("Merhaba PDF")) as provider:
            result = self.upload(b"%PDF-1.4 fake", filename="doc.pdf", targets=["tr"])
        self.assertEqual(result.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertEqual(archive.read("doc_tr.txt").decode("utf-8"), "Merhaba PDF")
        self.assertEqual(provider.call_args.kwargs["messages"], [{"role":"system","content":"en-tr"},{"role":"user","content":"Hello PDF"}])

    def test_invalid_extension_rejected_400(self):
        result = self.upload(b"not a document", filename="image.png")
        self.assertEqual(result.status_code, 400)
        self.assertIn("kabul edilir", result.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
