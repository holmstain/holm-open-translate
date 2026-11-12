"""Admission gate / fail-fast regression tests (offline, mocked provider)."""
import io
import json
import os
import socket
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from openai import OpenAI, _base_client
import test_translation_flow as flow

module = flow.module
http = getattr(_base_client, 'httpx2', None) or _base_client.httpx


def reset_gate():
    with module.ADMISSION_GATE._lock:
        module.ADMISSION_GATE._cooldown_until = 0.0
        module.ADMISSION_GATE._emergency_lock = False
        module.ADMISSION_GATE._active = 0


class AdmissionGateUnitTests(unittest.TestCase):
    def setUp(self):
        reset_gate()

    def test_admit_release_tracks_active_count(self):
        gate = module.ADMISSION_GATE
        self.assertTrue(gate.admit("req-1"))
        self.assertEqual(gate.active_count(), 1)
        self.assertTrue(gate.admit("req-2"))
        self.assertEqual(gate.active_count(), 2)
        gate.release()
        self.assertEqual(gate.active_count(), 1)
        gate.release()
        self.assertEqual(gate.active_count(), 0)

    def test_cooldown_blocks_new_admits(self):
        gate = module.ADMISSION_GATE
        gate.set_cooldown(10, "req-1")
        self.assertFalse(gate.admit("req-2"))
        self.assertEqual(gate.active_count(), 0)

    def test_terminal_lock_blocks_new_admits(self):
        gate = module.ADMISSION_GATE
        gate.set_terminal("req-1")
        self.assertFalse(gate.admit("req-2"))
        self.assertEqual(gate.active_count(), 0)


class AdmissionGateFlowTests(unittest.TestCase):
    upload = flow.TranslationFlowTests.upload

    def setUp(self):
        flow.TranslationFlowTests.setUp(self)
        reset_gate()
        self.sleep = patch('time.sleep')
        self.sleeper = self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def use_provider(self, replies):
        self.requests = []
        self.replies = iter(replies)
        def handle(request):
            self.requests.append(json.loads(request.content))
            reply = next(self.replies)
            if reply == 'timeout':
                raise http.ReadTimeout('synthetic timeout', request=request)
            if reply == 'connection':
                raise http.ConnectError('synthetic private connection detail', request=request)
            status, text, headers = reply
            if status == 200:
                payload = {'id': 'offline', 'object': 'chat.completion', 'created': 0, 'model': module.MODEL_NAME,
                    'choices': [{'index': 0, 'message': {
                        'role': 'assistant',
                        'content': text.get('text') if isinstance(text, dict) else text,
                        'finish_reason': text.get('reason', 'stop') if isinstance(text, dict) else 'stop'}}]}
            else:
                payload = {'error': {'message': 'synthetic private provider payload', 'type': 'upstream', 'code': None}}
            return http.Response(status, json=payload, headers=headers)
        transport = http.MockTransport(handle)
        client = OpenAI(base_url='https://offline.invalid/v1', api_key='offline-test-key',
            http_client=http.Client(transport=transport), timeout=30.0, max_retries=0)
        self.addCleanup(client.close)
        replacement = patch.object(module, 'client', client)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_429_long_retry_after_trips_emergency_lock_and_blocks_new_starts(self):
        # 429 with retry-after 100 -> cooldown + emergency lock -> 502, no retry
        self.use_provider([(429, '', {'retry-after': '100'})])
        result = self.upload()
        self.assertEqual(result.status_code, 502)
        self.assertEqual(len(self.requests), 1)
        # Emergency lock active: a second request is blocked without calling the provider
        result2 = self.upload()
        self.assertEqual(result2.status_code, 502)
        self.assertEqual(len(self.requests), 1)

    def test_terminal_error_blocks_new_starts_fail_fast(self):
        # A terminal (non-allowlisted) status trips the emergency lock
        self.use_provider([(401, '', {'x-should-retry': 'true'})])
        result = self.upload()
        self.assertEqual(result.status_code, 502)
        self.assertEqual(len(self.requests), 1)
        # Second request blocked without provider call (fail-fast / cancellation)
        result2 = self.upload()
        self.assertEqual(result2.status_code, 502)
        self.assertEqual(len(self.requests), 1)

    def test_no_sensitive_data_in_logs(self):
        self.use_provider([(429, '', {'retry-after': '100'})])
        with self.assertLogs('app', level='INFO') as captured:
            self.assertEqual(self.upload().status_code, 502)
        output = ' '.join(captured.output)
        for private in ['Hello', 'offline-test-key', 'synthetic private provider payload']:
            self.assertNotIn(private, output)


class RequestLimitTests(unittest.TestCase):
    upload = flow.TranslationFlowTests.upload

    def setUp(self):
        flow.TranslationFlowTests.setUp(self)
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("Offline tests cannot access network"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.client = module.app.test_client()

    def test_more_than_ten_files_rejected_400(self):
        files = [(io.BytesIO(b'{"a":"Hello"}'), f"file{i}.json") for i in range(11)]
        result = self.client.post("/translate", data={
            "files": files,
            "languages": ["tr"],
            "source_language": "en",
        })
        self.assertEqual(result.status_code, 400)
        self.assertIn("10 JSON dosyası", result.get_data(as_text=True))

    def test_more_than_eight_languages_rejected_400(self):
        langs = ["tr","de","fr","es-ES","pt-PT","it","nl","pl","ru"]
        result = self.upload(b'{"a":"Hello"}', targets=langs, source="en")
        self.assertEqual(result.status_code, 400)
        self.assertIn("8 hedef dil", result.get_data(as_text=True))

    def test_exactly_ten_files_and_eight_languages_accepted(self):
        with patch.object(module.client.chat.completions, "create", return_value=flow.response()):
            files = [(io.BytesIO(b'{"a":"Hello"}'), f"file{i}.json") for i in range(10)]
            langs = ["tr","de","fr","es-ES","pt-PT","it","nl","pl"]
            result = self.client.post("/translate", data={
                "files": files,
                "languages": langs,
                "source_language": "en",
            })
        self.assertEqual(result.status_code, 200)


if __name__ == '__main__':
    unittest.main()
