"""Real loopback HTTP, bundled resources and lifecycle for browser companions."""
import http.client
import os
from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from koei_editor.shared import browser_companions as browser
from tools import build_windows


ROOT = Path(__file__).resolve().parents[1]


def request(url, *, method='GET', path=None, headers=None, body=None):
    parsed = urlsplit(url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=4)
    try:
        connection.request(method, path or parsed.path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


class BrowserCompanionTests(unittest.TestCase):
    def setUp(self):
        self.opened = []
        self.manager = browser.BrowserCompanionManager(
            browser_opener=lambda url: self.opened.append(url) or True)
        self.addCleanup(self.manager.close)

    def test_real_assets_match_original_files_and_browser_open_reuses_one_session(self):
        urls = {tool.tool_id: self.manager.open(tool.tool_id) for tool in browser.BROWSER_TOOLS}
        self.assertEqual(self.opened, list(urls.values()))
        self.assertEqual(len({urlsplit(url).netloc for url in urls.values()}), 1)
        for runtime, source in browser.BROWSER_RESOURCE_SOURCES.items():
            suffix = runtime.removeprefix('koei_editor/browser_tools/')
            tool_id, name = suffix.split('/', 1)
            status, headers, data = request(urls[tool_id] + name)
            self.assertEqual(status, 200, name)
            self.assertEqual(data, (ROOT / source).read_bytes(), name)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
            self.assertEqual(headers['Cross-Origin-Resource-Policy'], 'same-origin')
            self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
            if name.endswith('.mjs'):
                self.assertEqual(headers['Content-Type'], 'text/javascript; charset=utf-8')
        status, headers, body = request(urls['localization_studio'], method='HEAD')
        self.assertEqual((status, body), (200, b''))
        self.assertEqual(int(headers['Content-Length']), len((ROOT / 'localization-studio/index.html').read_bytes()))

    def test_host_origin_and_cross_site_requests_are_rejected(self):
        url = self.manager.url_for('localization_studio')
        parsed = urlsplit(url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        for headers in ({'Host': 'evil.example'}, {'Origin': 'https://evil.example'},
                        {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(request(url, headers=headers)[0], 403, headers)
        self.assertEqual(request(url, headers={'Origin': origin, 'Sec-Fetch-Site': 'same-origin'})[0], 200)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=4)
        try:
            connection.putrequest('GET', parsed.path, skip_host=True)
            connection.putheader('Host', parsed.netloc)
            connection.putheader('Host', 'evil.example')
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
        finally:
            connection.close()

    def test_only_exact_tokenized_routes_are_served_without_filesystem_fallback(self):
        url = self.manager.url_for('localization_studio')
        parsed = urlsplit(url)
        paths = ('/', '/favicon.ico', '/localization_studio/index.html',
                 parsed.path.replace(parsed.path.split('/')[1], 'wrong-token', 1),
                 parsed.path + '../LICENSE', parsed.path + '%2e%2e/LICENSE',
                 parsed.path + 'src%2fapp.mjs', parsed.path + 'index.html?path=../LICENSE',
                 parsed.path + 'src\\app.mjs', '/' + parsed.path,
                 f'http://{parsed.netloc}{parsed.path}',
                 parsed.path + '../../../pyproject.toml')
        for path in paths:
            status, _, data = request(url, path=path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b'[project]', data)
        self.assertEqual(request(url)[0], 200)

    def test_methods_and_request_bodies_cannot_upload_or_modify_resources(self):
        url = self.manager.url_for('mod_testing_sandbox')
        original = request(url)[2]
        for method in ('POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'):
            status, headers, _ = request(url, method=method, body=b'{"private":"never accepted"}')
            self.assertEqual(status, 405)
            self.assertEqual(headers['Allow'], 'GET, HEAD')
        self.assertEqual(request(url, body=b'x', headers={'Content-Length': '1'})[0], 400)
        self.assertEqual(request(url, headers={'Transfer-Encoding': 'chunked'})[0], 400)
        self.assertEqual(request(url)[2], original)

    def test_request_line_and_header_budgets_are_enforced(self):
        url = self.manager.url_for('localization_studio')
        parsed = urlsplit(url)
        cases = (
            (b'GET /' + b'x' * browser.MAX_REQUEST_LINE + b' HTTP/1.1\r\n\r\n', 414),
            (f'GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nX-Large: '.encode()
             + b'x' * browser.MAX_HEADERS_BYTES + b'\r\n\r\n', 431),
        )
        for raw, expected in cases:
            with socket.create_connection((parsed.hostname, parsed.port), timeout=4) as client:
                client.sendall(raw)
                response = client.recv(1024)
                self.assertIn(f' {expected} '.encode(), response.split(b'\r\n')[0])

    def test_client_capacity_and_closing_an_idle_request_are_bounded(self):
        with patch.object(browser, 'CLIENT_TIMEOUT', 10):
            url = self.manager.url_for('localization_studio')
            parsed = urlsplit(url)
            clients = []
            try:
                for _ in range(browser.MAX_CLIENTS):
                    client = socket.create_connection((parsed.hostname, parsed.port), timeout=4)
                    client.sendall(b'GET ')
                    clients.append(client)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    with self.manager._server._client_lock:
                        count = len(self.manager._server._clients)
                    if count == browser.MAX_CLIENTS:
                        break
                    time.sleep(0.01)
                self.assertEqual(count, browser.MAX_CLIENTS)
                with socket.create_connection((parsed.hostname, parsed.port), timeout=4) as overflow:
                    try:
                        overflow.sendall(f'GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\n\r\n'.encode())
                        self.assertEqual(overflow.recv(1024), b'')
                    except ConnectionResetError:
                        pass
                thread = self.manager._thread
                self.manager.close()
                self.assertFalse(thread.is_alive())
                for client in clients:
                    self.assertEqual(client.recv(1), b'')
            finally:
                for client in clients:
                    client.close()
        self.manager.close()
        with self.assertRaises(browser.BrowserCompanionError):
            self.manager.url_for('localization_studio')
        with self.assertRaises(OSError):
            socket.create_connection((parsed.hostname, parsed.port), timeout=1)

    def test_source_resources_do_not_depend_on_the_working_directory(self):
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                os.chdir(folder)
                url = self.manager.url_for('localization_studio')
                self.assertEqual(request(url)[2], (ROOT / 'localization-studio/index.html').read_bytes())
        finally:
            os.chdir(previous)

    def test_slow_input_cannot_extend_the_absolute_request_deadline(self):
        with patch.object(browser, 'CLIENT_TIMEOUT', 0.3):
            url = self.manager.url_for('localization_studio')
            parsed = urlsplit(url)
            with socket.create_connection((parsed.hostname, parsed.port), timeout=3) as client:
                client.settimeout(0.05)
                closed = False
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        client.sendall(b'G')
                        try:
                            if client.recv(1) == b'':
                                closed = True
                                break
                        except socket.timeout:
                            pass
                    except (BrokenPipeError, ConnectionResetError):
                        closed = True
                        break
                self.assertTrue(closed, 'Continuously arriving bytes must not retain a request slot.')

    def test_packaged_resources_are_preferred_and_incomplete_bundles_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / 'koei_editor'
            for runtime, source in browser.BROWSER_RESOURCE_SOURCES.items():
                target = Path(folder) / runtime
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / source, target)
            with patch.object(browser, '_package_root', return_value=package):
                with browser.BrowserCompanionManager() as manager:
                    self.assertEqual(request(manager.url_for('mod_testing_sandbox'))[2],
                                     (ROOT / 'tools/mod_testing_sandbox/index.html').read_bytes())
                (package / 'browser_tools/localization_studio/src/app.mjs').unlink()
                with browser.BrowserCompanionManager() as manager:
                    with self.assertRaises(browser.BrowserCompanionError):
                        manager.url_for('localization_studio')
                    self.assertIsNone(manager._server)

    def test_resource_reader_refuses_aliases_binary_and_oversized_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'valid.html').write_bytes(b'<h1>Reviewed asset</h1>')
            for relative in ('../valid.html', '/valid.html', 'a\\valid.html', 'a//valid.html'):
                with self.assertRaises(browser.BrowserCompanionError):
                    browser._read_asset(root, relative)
            for name, data in (('binary.html', b'a\0b'), ('large.html', b'x' * (browser.MAX_ASSET_BYTES + 1))):
                (root / name).write_bytes(data)
                with self.assertRaises(browser.BrowserCompanionError):
                    browser._read_asset(root, name)

    def test_redirected_resource_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'index.html').write_bytes(b'must not be served')
            try:
                (root / 'browser_tools').symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f'Host cannot create directory symlinks: {error}')
            with self.assertRaises(browser.BrowserCompanionError):
                browser._read_asset(root, 'browser_tools/index.html')

    def test_parent_swap_after_directory_checks_cannot_read_outside_assets(self):
        for replacement in ('directory', 'symlink'):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as folder:
                area = Path(folder)
                root, outside = area / 'package', area / 'outside'
                parent = root / 'browser_tools'
                parent.mkdir(parents=True)
                outside.mkdir()
                original = b'reviewed original asset'
                marker = b'procedural outside private marker'
                target = parent / 'index.html'
                target.write_bytes(original)
                (outside / 'index.html').write_bytes(marker)
                if replacement == 'symlink':
                    try:
                        (area / 'link-probe').symlink_to(outside, target_is_directory=True)
                    except OSError:
                        continue  # The ordinary-directory replacement still runs on this host.
                    (area / 'link-probe').unlink()
                original_lstat = Path.lstat
                attempted = False

                def swap_before_leaf_stat(path, *args, **kwargs):
                    nonlocal attempted
                    if path == target and not attempted:
                        attempted = True
                        # Windows may refuse the rename because its open ancestor
                        # handles deny delete sharing. POSIX permits it, but the
                        # file must still be opened relative to the pinned parent.
                        parent.rename(root / 'reviewed-assets')
                        if replacement == 'symlink':
                            parent.symlink_to(outside, target_is_directory=True)
                        else:
                            outside.rename(parent)
                    return original_lstat(path, *args, **kwargs)

                with patch.object(Path, 'lstat', swap_before_leaf_stat):
                    with self.assertRaises(browser.BrowserCompanionError):
                        browser._read_asset(root, 'browser_tools/index.html')
                self.assertTrue(attempted)
                self.assertEqual((root / 'reviewed-assets/index.html').read_bytes()
                                 if (root / 'reviewed-assets').exists() else target.read_bytes(), original)
                marker_path = (outside if outside.exists() else parent) / 'index.html'
                self.assertEqual(marker_path.read_bytes(), marker)

    def test_invalid_tool_and_browser_failures_are_explicit_and_close_cleanly(self):
        for invalid in ('unknown', '../localization_studio', None, []):
            with self.assertRaises(browser.BrowserCompanionError):
                self.manager.url_for(invalid)
        self.assertIsNone(self.manager._server)
        with browser.BrowserCompanionManager(browser_opener=lambda url: False) as manager:
            with self.assertRaises(browser.BrowserCompanionError):
                manager.open('localization_studio')
        with browser.BrowserCompanionManager(browser_opener=lambda url: (_ for _ in ()).throw(OSError('unavailable'))) as manager:
            with self.assertRaises(browser.BrowserCompanionError):
                manager.open('mod_testing_sandbox')

    def test_all_native_build_modes_collect_exact_original_companion_assets(self):
        for runtime, source in browser.BROWSER_RESOURCE_SOURCES.items():
            destination = Path(runtime).parent.as_posix()
            self.assertIn((source, destination), build_windows.DATA)
            self.assertTrue((ROOT / source).is_file())
            for options in ({}, {'standalone': True}, {'cli': True}):
                args = build_windows.build_args(**options)
                self.assertIn(str(ROOT / source) + os.pathsep + destination, args)
                self.assertIn('koei_editor.shared.browser_companions', args)


if __name__ == '__main__':
    unittest.main()
