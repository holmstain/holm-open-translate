"""Offline provider retries through the real OpenAI SDK and in-memory HTTP."""
import io
import json
import os
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
import unittest
import zipfile
from unittest.mock import patch
from openai import OpenAI, _base_client
import test_translation_flow as flow
module = flow.module

# Match the transport used by the installed SDK (httpx or its httpx2 successor).
http = getattr(_base_client, 'httpx2', None) or _base_client.httpx


def reset_admission_gate():
    with module.ADMISSION_GATE._lock:
        module.ADMISSION_GATE._cooldown_until = 0.0
        module.ADMISSION_GATE._emergency_lock = False
        module.ADMISSION_GATE._active = 0


class ProviderRetryTests(unittest.TestCase):
    upload = flow.TranslationFlowTests.upload
    def setUp(self):
        flow.TranslationFlowTests.setUp(self)
        reset_admission_gate()
        self.sleep = patch('time.sleep')
        self.sleeper = self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def use_provider(self, replies):
        self.requests = []
        self.replies = iter(replies)
        def handle(request):
            self.requests.append(json.loads(request.content))
            self.assertEqual(request.extensions['timeout']['read'], 30.0)
            reply = next(self.replies)
            if reply == 'timeout':
                raise http.ReadTimeout('synthetic timeout', request=request)
            if reply == 'connection':
                raise http.ConnectError('synthetic private connection detail', request=request)
            status, text, headers = reply
            if status == 200:
                payload = {'id':'offline', 'object':'chat.completion', 'created':0, 'model':module.MODEL_NAME,
                    'choices':[{'index':0, 'message':{'role':'assistant','content':text.get('text') if isinstance(text,dict) else text}, 'finish_reason':text.get('reason','stop') if isinstance(text,dict) else 'stop'}]}
            else:
                payload = {'error':{'message':'synthetic private provider payload', 'type':'upstream', 'code':None}}
            return http.Response(status, json=payload, headers=headers)
        transport = http.MockTransport(handle)
        client = OpenAI(base_url='https://offline.invalid/v1', api_key='offline-test-key',
            http_client=http.Client(transport=transport), timeout=30.0, max_retries=0)
        self.addCleanup(client.close)
        replacement = patch.object(module, 'client', client)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_gateway_retries_only_failed_string_and_returns_complete_zip(self):
        self.use_provider([(200,'Merhaba',{}),(502,'',{}),(200,'Dünya',{})])
        result = self.upload(b'{"a":"Hello","b":"World"}')
        self.assertEqual(result.status_code, 200)
        self.assertEqual([r['messages'][1]['content'] for r in self.requests], ['Hello','World','World'])
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertEqual(json.loads(archive.read('common_tr.json')), {'a':'Merhaba','b':'Dünya'})
        self.assertEqual([c.args[0] for c in self.sleeper.call_args_list], [.5])

    def test_persistent_gateway_is_limited_and_publishes_no_archive(self):
        self.use_provider([(502,'',{})]*3)
        result = self.upload()
        self.assertEqual(result.status_code, 502)
        self.assertIn('temporarily', result.get_data(as_text=True))
        self.assertEqual(len(self.requests), 3)
        self.assertEqual([c.args[0] for c in self.sleeper.call_args_list], [.5,1.0])
        self.assertFalse(any(files for _,_,files in os.walk(self.directory.name)))

    def test_timeout_retries_are_bounded(self):
        self.use_provider(['timeout']*3)
        result = self.upload()
        self.assertEqual(result.status_code, 502)
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(len(self.sleeper.call_args_list), 2)

    def test_auth_and_invalid_requests_ignore_provider_retry_header(self):
        for status in (400,401,403,408,409):
            with self.subTest(status=status):
                reset_admission_gate()
                self.use_provider([(status,'',{'x-should-retry':'true'})])
                self.assertEqual(self.upload().status_code, 502)
                self.assertEqual(len(self.requests), 1)

    def test_retry_after_wait_is_bounded_and_large_wait_is_not_ignored(self):
        self.use_provider([(429,'',{'retry-after':'3'}),(200,'Merhaba',{})])
        self.assertEqual(self.upload().status_code,200)
        self.assertEqual(self.sleeper.call_args.args,(3.0,))
        self.sleeper.reset_mock()
        self.use_provider([(503,'',{'retry-after':'100000'})])
        result = self.upload()
        self.assertEqual(result.status_code,502)
        self.assertEqual(len(self.requests),1)
        self.assertFalse(self.sleeper.called)

    def test_invalid_translation_content_is_not_retried(self):
        for content in ['', {'text':'partial','reason':'length'}, 'Wrong {isim}']:
            with self.subTest(content=content):
                self.use_provider([(200,content,{})])
                self.assertEqual(self.upload(b'{"a":"Hello {name}"}').status_code,502)
                self.assertEqual(len(self.requests),1)
                self.assertFalse(self.sleeper.called)

    def test_connection_retry_recovers_and_logs_only_safe_metadata(self):
        self.use_provider(['connection',(200,'Merhaba',{})])
        with self.assertLogs('app',level='WARNING') as captured:
            self.assertEqual(self.upload().status_code,200)
        self.assertEqual(len(self.requests),2)
        self.assertIn('category=connection_or_timeout',captured.output[0])
        for private in ['Hello','offline-test-key','synthetic private']:
            self.assertNotIn(private,' '.join(captured.output))

    def test_http_date_retry_after_is_bounded(self):
        date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=4), usegmt=True)
        self.use_provider([(503,'',{'retry-after':date}),(200,'Merhaba',{})])
        self.assertEqual(self.upload().status_code,200)
        delay = self.sleeper.call_args.args[0]
        self.assertGreater(delay,0)
        self.assertLessEqual(delay,5)

    def test_pivot_retries_keep_intermediate_and_do_not_repeat_first_hop(self):
        self.use_provider([(200,'Hello {name}',{}),(502,'',{}),(200,'Hallo {name}',{})])
        result = self.upload(b'{"a":"Merhaba {name}"}', source='tr', targets=['de'])
        self.assertEqual(result.status_code,200)
        self.assertEqual([(r['messages'][0]['content'],r['messages'][1]['content']) for r in self.requests],
            [('tr-en','Merhaba {name}'),('en-de','Hello {name}'),('en-de','Hello {name}')])


if __name__ == '__main__':
    unittest.main()
