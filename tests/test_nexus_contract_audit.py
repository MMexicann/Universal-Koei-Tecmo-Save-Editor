"""Additional mocked Nexus contract coverage for rate-limit telemetry."""

import json
import unittest

from koei_editor.mods.nexus_api import API_ROOT, ApiResponse, NexusApiClient


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return self.response


class NexusRateLimitTelemetryTests(unittest.TestCase):
    def test_quota_headers_are_captured_case_insensitively_without_other_headers(self):
        transport = FakeTransport(ApiResponse(
            200,
            {
                'X-RL-Hourly-Limit': '500',
                'x-rl-hourly-remaining': '499',
                'X-RL-Hourly-Reset': '1761000000',
                'Retry-After': '2',
                'Set-Cookie': 'session=private',
            },
            json.dumps({'data': {'mods': []},
                        'meta': {'page': 1, 'page_size': 30, 'total_count': 0}}).encode(),
        ))
        api = NexusApiClient(application_name='Nexus browser', application_version='1.0',
                             api_key='private-key', transport=transport)

        api.search_mods('dynastywarriors8')

        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(transport.requests[0].full_url, API_ROOT + '/mods/search')
        self.assertEqual(api.last_rate_headers, {
            'x-rl-hourly-limit': '500',
            'x-rl-hourly-remaining': '499',
            'x-rl-hourly-reset': '1761000000',
            'retry-after': '2',
        })
        self.assertNotIn('session', repr(api.last_rate_headers))


if __name__ == '__main__':
    unittest.main()
