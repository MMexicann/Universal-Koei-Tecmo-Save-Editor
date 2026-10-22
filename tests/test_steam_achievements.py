"""Steam achievement snapshots retain exact source state and no credentials."""
from collections import deque
from datetime import datetime, timezone
import json
from urllib.parse import parse_qs, urlsplit
import unittest

from koei_editor.game_registry import get_game
from koei_editor.shared.steam_achievements import fetch_steam_achievements
from tools.build_windows import build_args


API_KEY = '0123456789abcdef0123456789abcdef'
STEAM_ID64 = '76561198000000000'
APP_ID = 3841510


def schema(*, duplicate=False):
    entries = [
        {'name': 'ACH_FIRST', 'displayName': 'First', 'description': 'First description', 'hidden': 0},
        {'name': 'ACH_SECRET', 'displayName': 'Secret title', 'description': 'Spoiler text', 'hidden': 1},
    ]
    if duplicate:
        entries.append(dict(entries[0]))
    return {'game': {'availableGameStats': {'achievements': entries}}}


def player(rows=None, *, success=True, steam_id=STEAM_ID64):
    if rows is None:
        rows = [
            {'apiname': 'ACH_FIRST', 'achieved': 1, 'unlocktime': 1735689600},
            {'apiname': 'ACH_SECRET', 'achieved': 0, 'unlocktime': 0},
        ]
    return {'playerstats': {'success': success, 'steamID': steam_id,
                            'achievements': rows}}


class Response:
    def __init__(self, value, final_url='https://api.steampowered.com/fake'):
        self.body = value if type(value) is bytes else json.dumps(value).encode('utf-8')
        self.final_url = final_url
        self.closed = False

    def read(self, limit):
        return self.body[:limit]

    def geturl(self):
        return self.final_url

    def close(self):
        self.closed = True


class Opener:
    def __init__(self, *responses):
        self.responses = deque(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response


class SteamAchievementTests(unittest.TestCase):
    def fetch(self, opened):
        return fetch_steam_achievements(
            API_KEY, STEAM_ID64, APP_ID, opener=opened,
            now=lambda: datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )

    def test_verified_states_join_to_official_schema_without_retaining_identity(self):
        opened = Opener(Response(schema()), Response(player()))
        result = self.fetch(opened)

        self.assertEqual(result.status, 'verified')
        self.assertEqual(result.source, 'Steam Web API')
        self.assertEqual(result.retrieved_at, '2025-01-02T03:04:05Z')
        self.assertEqual((result.unlocked_count, result.total_count), (1, 2))
        self.assertEqual([item.state for item in result.achievements], ['unlocked', 'locked'])
        self.assertEqual(result.achievements[0].unlocked_at, '2025-01-01T00:00:00Z')
        self.assertEqual(result.achievements[1].name, 'Hidden achievement')
        self.assertEqual(result.achievements[1].description, '')
        self.assertNotIn(API_KEY, repr(result))
        self.assertNotIn(STEAM_ID64, repr(result))
        self.assertEqual(len(opened.requests), 2)
        for request, timeout in opened.requests:
            parsed = urlsplit(request.full_url)
            self.assertEqual(parsed.scheme, 'https')
            self.assertEqual(parsed.hostname, 'api.steampowered.com')
            self.assertEqual(timeout, 10)
            query = parse_qs(parsed.query)
            self.assertEqual(query['key'], [API_KEY])
            self.assertEqual(query['appid'], [str(APP_ID)])
        self.assertNotIn('steamid', parse_qs(urlsplit(opened.requests[0][0].full_url).query))
        self.assertEqual(parse_qs(urlsplit(opened.requests[1][0].full_url).query)['steamid'], [STEAM_ID64])

    def test_missing_player_state_is_unavailable_and_has_no_count(self):
        opened = Opener(Response(schema()), Response(player([
            {'apiname': 'ACH_FIRST', 'achieved': 1, 'unlocktime': 1735689600},
        ])))
        result = self.fetch(opened)

        self.assertEqual(result.status, 'unavailable')
        self.assertEqual([item.state for item in result.achievements], ['unlocked', 'unavailable'])
        self.assertIsNone(result.unlocked_count)
        self.assertIsNone(result.total_count)

    def test_malformed_first_row_cannot_hide_a_duplicate_api_name(self):
        opened = Opener(Response(schema()), Response(player([
            {'apiname': 'ACH_FIRST', 'achieved': 'invalid', 'unlocktime': 0},
            {'apiname': 'ACH_FIRST', 'achieved': 1, 'unlocktime': 1735689600},
            {'apiname': 'ACH_SECRET', 'achieved': 0, 'unlocktime': 0},
        ])))
        result = self.fetch(opened)

        self.assertEqual(result.status, 'unavailable')
        self.assertEqual([item.state for item in result.achievements], ['unavailable', 'locked'])
        self.assertIsNone(result.unlocked_count)
        self.assertIsNone(result.total_count)

    def test_malformed_extra_player_rows_cannot_verify_schema_match(self):
        valid_rows = [
            {'apiname': 'ACH_FIRST', 'achieved': 1, 'unlocktime': 1735689600},
            {'apiname': 'ACH_SECRET', 'achieved': 0, 'unlocktime': 0},
        ]
        malformed_rows = (
            None,
            {},
            {'apiname': 'UNMAPPED', 'achieved': 'invalid', 'unlocktime': 0},
            {'apiname': 'UNMAPPED', 'achieved': 1, 'unlocktime': 'invalid'},
        )
        for malformed in malformed_rows:
            with self.subTest(row=malformed):
                opened = Opener(Response(schema()),
                                Response(player([*valid_rows, malformed])))
                result = self.fetch(opened)
                self.assertEqual(result.status, 'unavailable')
                self.assertIsNone(result.unlocked_count)
                self.assertIsNone(result.total_count)

    def test_private_profile_marks_every_state_unavailable_not_locked(self):
        opened = Opener(Response(schema()), Response(player(success=False)))
        result = self.fetch(opened)

        self.assertEqual(result.status, 'unavailable')
        self.assertEqual([item.state for item in result.achievements], ['unavailable', 'unavailable'])
        self.assertTrue(all(word not in result.note.casefold() for word in ('locked', '0%')))
        self.assertIsNone(result.unlocked_count)

    def test_wrong_profile_and_duplicate_schema_fail_closed(self):
        wrong_profile = self.fetch(Opener(Response(schema()), Response(player(steam_id='76561198000000001'))))
        duplicate_schema = self.fetch(Opener(Response(schema(duplicate=True))))

        self.assertEqual(wrong_profile.status, 'unavailable')
        self.assertTrue(all(item.state == 'unavailable' for item in wrong_profile.achievements))
        self.assertEqual(duplicate_schema.status, 'unavailable')
        self.assertEqual(duplicate_schema.achievements, ())

    def test_malformed_hidden_flags_fail_closed_without_exposing_schema_text(self):
        for malformed in ('true', True, 2, None):
            with self.subTest(hidden=malformed):
                response = schema()
                response['game']['availableGameStats']['achievements'][1]['hidden'] = malformed
                opened = Opener(Response(response))
                result = self.fetch(opened)

                self.assertEqual(result.status, 'unavailable')
                self.assertEqual(result.achievements, ())
                self.assertEqual(len(opened.requests), 1)
                self.assertNotIn('Secret title', repr(result))
                self.assertNotIn('Spoiler text', repr(result))
        missing = schema()
        del missing['game']['availableGameStats']['achievements'][1]['hidden']
        result = self.fetch(Opener(Response(missing)))
        self.assertEqual(result.status, 'unavailable')
        self.assertEqual(result.achievements, ())
        self.assertNotIn('Secret title', repr(result))
        self.assertNotIn('Spoiler text', repr(result))

    def test_invalid_credentials_do_not_make_a_request(self):
        opened = Opener()
        result = fetch_steam_achievements('bad-key', STEAM_ID64, APP_ID, opener=opened)
        self.assertEqual(result.status, 'unavailable')
        self.assertEqual(opened.requests, [])
        self.assertEqual(result.achievements, ())

    def test_network_errors_and_redirects_never_leak_request_details(self):
        timed_out = self.fetch(Opener(TimeoutError(f'leaked {API_KEY} {STEAM_ID64}')))
        redirect = self.fetch(Opener(Response(schema(), 'https://example.org/steal'), Response(player())))

        for result in (timed_out, redirect):
            self.assertEqual(result.status, 'unavailable')
            self.assertNotIn(API_KEY, repr(result))
            self.assertNotIn(STEAM_ID64, repr(result))

    def test_game_registry_exposes_only_the_reviewed_mapping_and_build_import(self):
        source = get_game('dw3').get_achievement_source()
        self.assertEqual(source.STEAM_APP_ID, APP_ID)
        self.assertIsNone(get_game('pw3').get_achievement_source())
        args = build_args()
        self.assertIn('koei_editor.games.dw3.achievements', args)


if __name__ == '__main__':
    unittest.main()
