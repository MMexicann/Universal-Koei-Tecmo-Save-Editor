"""Mocked contract tests for Nexus Mods discovery and metadata calls."""

import json
import unittest

from koei_editor.game_registry import get_game
from koei_editor.mods.nexus_api import (
    API_ROOT,
    ApiResponse,
    NexusApiClient,
    NexusGame,
    NexusAuthenticationError,
    ModFileVersion,
    ModSummary,
    build_download_request,
    NexusNotFoundError,
    NexusPermissionError,
    NexusRateLimitError,
    NexusProtocolError,
    SUPPORTED_NEXUS_GAMES,
    description_as_text,
    mod_page_url,
    search_loaded_mods,
)
from koei_editor.mods.nexus_browser import NexusModsWorkspace


def json_response(payload, *, status=200, headers=None):
    return ApiResponse(status, headers or {}, json.dumps(payload).encode('utf-8'))


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        if not self.responses:
            raise AssertionError('Unexpected Nexus request.')
        return self.responses.pop(0)


def search_item(*, mod_id='9001', scoped_id='17', name='Koei Mod', summary='Simple description'):
    return {
        'id': mod_id,
        'game_scoped_id': scoped_id,
        'game': {'domain_name': 'dynastywarriors8', 'name': 'Dynasty Warriors 8'},
        'name': name,
        'summary': summary,
        'version': '1.2',
        'author': {'id': '4', 'name': 'ModAuthor'},
        'category': {'id': '3', 'name': 'Gameplay'},
        'thumbnail_url': None,
        'blurred_thumbnail_url': None,
        'endorsements': 12,
        'downloads': 500,
        'unique_downloads': 200,
        'file_size_kilobytes': 5,
        'created_at': '2026-01-01T00:00:00Z',
        'updated_at': '2026-02-01T00:00:00Z',
        'adult': False,
        'supports_vortex': True,
    }


def client(transport, *, api_key=None):
    return NexusApiClient(api_key=api_key, application_name='Test Mod Browser',
                          application_version='3.1', transport=transport)


class _FakeTree:
    def __init__(self, items=(), selection=()):
        self.items = list(items)
        self.selected = tuple(selection)

    def get_children(self):
        return tuple(self.items)

    def delete(self, item):
        self.items.remove(item)

    def selection(self):
        return self.selected

    def insert(self, _parent, _index, *, iid, **_kwargs):
        self.items.append(iid)


class _FakeText:
    def configure(self, **_kwargs):
        pass

    def delete(self, *_args):
        pass

    def insert(self, *_args):
        pass


class _FakeButton:
    def __init__(self, state='normal'):
        self.state = state

    def configure(self, *, state):
        self.state = state


class _FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _FakeStatus:
    def set(self, _value):
        pass


class NexusApiTests(unittest.TestCase):
    def test_explicit_allowlist_maps_only_supported_windows_pc_profiles(self):
        self.assertTrue(SUPPORTED_NEXUS_GAMES)
        for nexus_game in SUPPORTED_NEXUS_GAMES:
            with self.subTest(game=nexus_game.game_id):
                game = get_game(nexus_game.game_id)
                self.assertEqual(game.platform, 'Windows PC')
                self.assertTrue(nexus_game.domain)
                self.assertEqual(mod_page_url(nexus_game.domain, '12'),
                                 f'https://www.nexusmods.com/{nexus_game.domain}/mods/12')

    def test_search_uses_documented_game_filter_and_local_result_shape(self):
        transport = FakeTransport(json_response({
            'data': {'mods': [search_item()]},
            'meta': {'page': 2, 'page_size': 30, 'total_count': 77},
        }))
        result = client(transport).search_mods('dynastywarriors8', sort='popular',
                                               time_range='14', page=2, page_size=30)
        request, timeout = transport.requests[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.full_url, API_ROOT + '/mods/search')
        body = json.loads(request.data)
        self.assertEqual(body, {
            'filters': {'games': ['dynastywarriors8'], 'include_adult': False, 'time_range': '14'},
            'sort': {'field': 'popular', 'direction': 'desc'},
            'pagination': {'page': 2, 'page_size': 30},
        })
        headers = {key.casefold(): value for key, value in request.header_items()}
        self.assertNotIn('apikey', headers)
        self.assertEqual(headers['application-name'], 'Test Mod Browser')
        self.assertEqual(headers['application-version'], '3.1')
        self.assertGreater(timeout, 0)
        self.assertEqual((result.page, result.page_size, result.total_count), (2, 30, 77))
        self.assertEqual(result.mods[0].game_scoped_id, '17')
        self.assertEqual(result.mods[0].author, 'ModAuthor')

    def test_search_filters_adult_results_even_if_experimental_api_returns_them(self):
        adult = search_item(mod_id='9002', scoped_id='18', name='Adult entry')
        adult['adult'] = True
        transport = FakeTransport(json_response({
            'data': {'mods': [search_item(), adult]},
            'meta': {'page': 1, 'page_size': 30, 'total_count': 2},
        }))
        page = client(transport).search_mods('dynastywarriors8')
        self.assertEqual([mod.name for mod in page.mods], ['Koei Mod'])

    def test_local_search_is_and_filter_over_loaded_names_summaries_and_authors(self):
        transport = FakeTransport(json_response({
            'data': {'mods': [search_item(name='Koei Guard', summary='Reduces guard cooldown'),
                              search_item(mod_id='9002', scoped_id='18', name='Gold Values',
                                          summary='Changes resource display')]},
            'meta': {'page': 1, 'page_size': 30, 'total_count': 2},
        }))
        page = client(transport).search_mods('dynastywarriors8')
        self.assertEqual([mod.name for mod in search_loaded_mods(page.mods, 'guard cooldown')], ['Koei Guard'])
        self.assertEqual(search_loaded_mods(page.mods, 'absent'), ())
        self.assertEqual(len(search_loaded_mods(page.mods, '')), 2)

    def test_detail_requires_key_and_uses_safe_plain_text(self):
        anonymous = client(FakeTransport())
        with self.assertRaises(NexusAuthenticationError):
            anonymous.get_mod('dynastywarriors8', '17')
        self.assertEqual(anonymous._transport.requests, [])

        transport = FakeTransport(json_response({'data': {
            'id': '9001', 'game_scoped_id': '17', 'name': 'Koei Mod',
            'description': '[b]Bold[/b]\n[url=https://example.invalid]visit[/url] <script>alert(1)</script>',
            'version': '1.2', 'author': 'Uploader', 'category': {'name': 'Gameplay'},
            'adult_content': False,
        }}))
        result = client(transport, api_key='secret-api-key').get_mod('dynastywarriors8', '17')
        request, _timeout = transport.requests[0]
        headers = {key.casefold(): value for key, value in request.header_items()}
        self.assertEqual(request.full_url, API_ROOT + '/games/dynastywarriors8/mods/17')
        self.assertEqual(headers['apikey'], 'secret-api-key')
        self.assertNotIn('secret-api-key', request.full_url)
        self.assertEqual(result.description, 'Bold\nvisit alert(1)')

    def test_files_versions_and_authored_dependencies_use_documented_v3_paths(self):
        transport = FakeTransport(
            json_response({'data': {'mod_files': [{'id': 'file_100.v1', 'name': 'Main file'}]}}),
            json_response({'data': {'versions': [{
                'id': 'version-200.v1', 'game_scoped_id': 'scoped-version-300',
                'file': {'id': 'file_100.v1', 'name': 'Main file'},
                'name': 'Release 1', 'version': '1.0', 'category': 'main',
                'uploaded_at': '2026-02-01T00:00:00Z', 'is_primary': True,
            }]}}),
            json_response({'dependency_definitions': [{
                'id': 'dep1', 'ranges': [{
                    'id': 'range1',
                    'target_mod_file': {'id': '401', 'name': 'Base File',
                                        'mod': {'id': '402', 'name': 'Base Mod'}},
                    'min_version': {'version': '2.0'}, 'max_version': None,
                }],
            }], 'dlc_dependency_definitions': [{
                'id': 'dlc1', 'dlc_targets': [{'id': '1', 'dlc_id': '1', 'name': 'Expansion'}],
            }]}),
        )
        api = client(transport, api_key='private-key')
        files = api.get_files('9001')
        versions = api.get_versions(files[0].file_id)
        dependencies = api.get_dependencies(versions[0].version_id)
        self.assertEqual(files[0].name, 'Main file')
        self.assertEqual(versions[0].game_scoped_version_id, 'scoped-version-300')
        self.assertEqual(versions[0].file_id, 'file_100.v1')
        self.assertTrue(versions[0].is_primary)
        self.assertEqual(dependencies.definitions[0].alternatives[0].mod_name, 'Base Mod')
        self.assertEqual(dependencies.definitions[0].alternatives[0].minimum_version, '2.0')
        self.assertEqual(dependencies.dlc_definitions[0].alternatives, ('Expansion',))
        self.assertEqual([request.full_url for request, _timeout in transport.requests], [
            API_ROOT + '/mods/9001/files',
            API_ROOT + '/mod-files/file_100.v1/versions',
            API_ROOT + '/mod-file-versions/version-200.v1/dependencies',
        ])

    def test_required_response_arrays_reject_schema_drift(self):
        with self.assertRaises(NexusProtocolError):
            client(FakeTransport(json_response({'data': {'files': []}})),
                   api_key='private-key').get_files('9001')
        with self.assertRaises(NexusProtocolError):
            client(FakeTransport(json_response({'dependency_definitions': []})),
                   api_key='private-key').get_dependencies('version-200')

    def test_opaque_ids_are_url_escaped_and_path_separators_are_rejected(self):
        transport = FakeTransport(json_response({'data': {'versions': []}}))
        api = client(transport, api_key='private-key')
        self.assertEqual(api.get_versions('file:100 ?'), ())
        self.assertEqual(transport.requests[0][0].full_url,
                         API_ROOT + '/mod-files/file%3A100%20%3F/versions')
        with self.assertRaises(ValueError):
            api.get_versions('file/100')

    def test_permissions_rate_limits_and_not_found_are_not_retried(self):
        cases = (
            (ApiResponse(401, {}, b'private body'), NexusAuthenticationError, None),
            (ApiResponse(403, {}, b'private body'), NexusPermissionError, None),
            (ApiResponse(404, {}, b'private body'), NexusNotFoundError, None),
            (ApiResponse(429, {'Retry-After': '60'}, b'private body'), NexusRateLimitError, '60'),
        )
        for response, error_type, retry_after in cases:
            with self.subTest(status=response.status):
                transport = FakeTransport(response)
                with self.assertRaises(error_type) as caught:
                    client(transport, api_key='private-key').get_mod('dynastywarriors8', '17')
                self.assertEqual(len(transport.requests), 1)
                self.assertEqual(caught.exception.retry_after, retry_after)
                self.assertNotIn('private body', str(caught.exception))

    def test_rejects_unknown_domains_bad_ids_and_bad_search_bounds(self):
        api = client(FakeTransport())
        for domain in ('../../host', 'Nexus', 'unlistedgame'):
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                api.search_mods(domain)
        for bad_id in ('../17', '17?x=1', -1, True):
            with self.subTest(mod_id=bad_id), self.assertRaises(ValueError):
                api.get_mod('dynastywarriors8', bad_id)
        with self.assertRaises(ValueError):
            api.get_versions('../file')
        with self.assertRaises(ValueError):
            api.search_mods('dynastywarriors8', page=101)
        with self.assertRaises(ValueError):
            api.search_mods('dynastywarriors8', page_size=101)

    def test_download_handoff_contract_contains_ids_only_and_no_signed_link_or_key(self):
        summary = ModSummary('9001', '17', 'dynastywarriors8', 'Koei Mod', '', '1.2',
                             'ModAuthor', 'Gameplay', 1, 2, '', False, True)
        version = ModFileVersion('version-a', 'scope-version-a', 'file-a', 'Main file', 'Release 1',
                                 '1.0', 'main', '', True)
        request = build_download_request(summary, version)
        self.assertEqual(request.provider, 'nexus')
        self.assertNotIn('api_key', request.__dataclass_fields__)
        self.assertNotIn('download_url', request.__dataclass_fields__)
        self.assertEqual(request.mod_page_url, 'https://www.nexusmods.com/dynastywarriors8/mods/17')


class NexusWorkspaceAndDescriptionTests(unittest.TestCase):
    def test_hiding_a_selected_mod_invalidates_its_pending_details_request(self):
        workspace = NexusModsWorkspace.__new__(NexusModsWorkspace)
        selected = ModSummary('9001', '17', 'dynastywarriors8', 'Selected Mod', '', '1.0',
                              'Author', 'Gameplay', 1, 2, '', False, True)
        other = ModSummary('9002', '18', 'dynastywarriors8', 'Other Mod', '', '1.0',
                           'Author', 'Gameplay', 1, 2, '', False, True)
        workspace._selected_summary = selected
        workspace._loaded_mods = [other]
        workspace._shown_mods = {selected.mod_id: selected}
        workspace._request_generation = 7
        workspace.language = 'en'
        workspace.filter_var = _FakeVar('no match')
        workspace.mod_tree = _FakeTree(items=(selected.mod_id,), selection=(selected.mod_id,))
        workspace.status_var = _FakeStatus()
        workspace._clear_current_selection = lambda: setattr(workspace, '_selected_summary', None)

        workspace._refresh_mod_list()

        self.assertEqual(workspace._request_generation, 8)
        self.assertIsNone(workspace._selected_summary)

    def test_loading_another_file_disables_old_version_handoff_immediately(self):
        workspace = NexusModsWorkspace.__new__(NexusModsWorkspace)
        summary = ModSummary('9001', '17', 'dynastywarriors8', 'Koei Mod', '', '1.2',
                             'ModAuthor', 'Gameplay', 1, 2, '', False, True)
        old_version = ModFileVersion('version-old', 'scope-old', 'file-old', 'Old file',
                                     'Old release', '1.0', 'main', '', True)
        workspace._request_generation = 4
        workspace._client = object()
        workspace._selected_file_id = 'file-old'
        workspace._selected_version = old_version
        workspace._versions = {old_version.version_id: old_version}
        workspace._selected_summary = summary
        workspace._shown_mods = {summary.mod_id: summary}
        workspace.download_handoff = None
        workspace._game_by_label = {
            'Dynasty Warriors 8': NexusGame('dw8xl', 'dynastywarriors8', 'Dynasty Warriors 8')}
        workspace.game_var = _FakeVar('Dynasty Warriors 8')
        workspace.file_tree = _FakeTree(selection=('file-new',))
        workspace.versions_tree = _FakeTree(items=('version-old',), selection=('version-old',))
        workspace.dependencies_text = _FakeText()
        workspace.manager_button = _FakeButton()
        workspace.language = 'en'
        submitted = {}
        workspace._submit = lambda operation, callback, *, generation: submitted.update(
            operation=operation, callback=callback, generation=generation)

        workspace._load_versions('file-new')

        self.assertEqual(workspace._selected_file_id, 'file-new')
        self.assertIsNone(workspace._selected_version)
        self.assertEqual(workspace._versions, {})
        self.assertEqual(workspace.versions_tree.get_children(), ())
        self.assertEqual(workspace.manager_button.state, 'disabled')
        self.assertEqual(submitted['generation'], 5)

    def test_descriptions_are_plain_text_and_markup_is_not_preserved(self):
        text = description_as_text('[quote][b]Hello[/b][/quote]\n[url]https://example.invalid[/url]')
        self.assertIn('Hello', text)
        self.assertIn('https://example.invalid', text)
        self.assertNotIn('[b]', text)
        self.assertNotIn('[url]', text)


if __name__ == '__main__':
    unittest.main()
