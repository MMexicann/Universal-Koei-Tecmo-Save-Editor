"""Serve reviewed browser companions from this application, on loopback only.

Only immutable bundled assets are served. Browser-selected files never pass
through this server; the existing tools keep their own import/export contracts.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
import os
from pathlib import Path, PurePosixPath
import secrets
import socket
import stat
import threading
import time
from types import MappingProxyType
import webbrowser

from koei_editor.games.dw3.models import SaveError


MAX_ASSET_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_REQUEST_LINE = 2048
MAX_HEADERS_BYTES = 8192
MAX_CLIENTS = 8
CLIENT_TIMEOUT = 2.0


class BrowserCompanionError(SaveError):
    """A companion cannot be opened without its complete reviewed resources."""


@dataclass(frozen=True)
class BrowserTool:
    tool_id: str
    title: str


BROWSER_TOOLS = (
    BrowserTool('localization_studio', 'Localization Studio'),
    BrowserTool('mod_testing_sandbox', 'Mod Testing Sandbox'),
)
_TOOL_IDS = frozenset(tool.tool_id for tool in BROWSER_TOOLS)
_SOURCE_DIRECTORIES = {
    'localization_studio': 'localization-studio',
    'mod_testing_sandbox': 'tools/mod_testing_sandbox',
}
_FILES = {
    'localization_studio': (
        'index.html', 'styles.css', 'src/app.mjs', 'src/formats.mjs',
        'docs/SUPPORTED_FORMATS.md', 'docs/RESEARCH.md', 'LICENSE'),
    'mod_testing_sandbox': (
        'index.html', 'src/styles.css', 'src/main.mjs',
        'src/sandbox-core.mjs', 'src/workspace-store.mjs'),
}
# Build and payload verification share this exact runtime-to-public-source map.
# These are the original files, not separately maintained copies in src/.
BROWSER_RESOURCE_SOURCES = MappingProxyType({
    f'koei_editor/browser_tools/{tool_id}/{name}': f'{_SOURCE_DIRECTORIES[tool_id]}/{name}'
    for tool_id, names in _FILES.items() for name in names
})
_MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.md': 'text/plain; charset=utf-8',
}
_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
)


@dataclass(frozen=True)
class _Asset:
    data: bytes
    content_type: str


def _package_root():
    root = resources.files('koei_editor')
    if not isinstance(root, Path):
        raise BrowserCompanionError('Browser companion resources require an extracted application package.')
    return root


def _ordinary_directory(info):
    return (stat.S_ISDIR(info.st_mode)
            and not getattr(info, 'st_file_attributes', 0) & 0x400)


def _directory_bindings(path):
    """Qualify the entire absolute chain before opening any relative child."""
    bindings = []
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not _ordinary_directory(info):
            raise OSError('Browser companion resources cannot use redirected directories.')
        bindings.append((parent, info))
    return bindings


@contextmanager
def _pinned_parent(bindings):
    """Hold no-follow ancestors through the read; never reopen a full file path."""
    if os.name == 'nt':
        from koei_editor.shared.anchored_read_windows import directory_chain
        with directory_chain(bindings) as directory:
            yield directory.open_child
        return
    if (os.open not in os.supports_dir_fd or not hasattr(os, 'O_DIRECTORY')
            or not hasattr(os, 'O_NOFOLLOW')):
        raise OSError('Anchored browser resource access is unavailable on this runtime.')
    descriptors = []
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
        for path, expected in bindings:
            descriptor = os.open(path if not descriptors else path.name, flags,
                                 **({'dir_fd': descriptors[-1]} if descriptors else {}))
            descriptors.append(descriptor)
            opened = os.fstat(descriptor)
            if (not _ordinary_directory(opened)
                    or (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino)):
                raise OSError('A browser companion resource directory changed.')
        def open_child(name):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, 'O_CLOEXEC', 0)
            return os.open(name, flags, dir_fd=descriptors[-1])
        yield open_child
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _verify_bindings(bindings):
    for path, expected in bindings:
        current = path.lstat()
        if (not _ordinary_directory(current)
                or (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino)):
            raise OSError('A browser companion resource directory changed.')


def _read_asset(root, relative):
    """Read one fixed asset with bounds and ordinary-file identity checks."""
    if (type(relative) is not str or '\\' in relative
            or PurePosixPath(relative).is_absolute()
            or any(part in ('', '.', '..') for part in relative.split('/'))):
        raise BrowserCompanionError('Browser companion asset paths must be ordinary relative paths.')
    path = Path(root).absolute().joinpath(*PurePosixPath(relative).parts)
    try:
        bindings = _directory_bindings(path)
        with _pinned_parent(bindings) as open_child:
            before = path.lstat()
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or getattr(before, 'st_file_attributes', 0) & 0x400
                    or not 0 < before.st_size <= MAX_ASSET_BYTES):
                raise BrowserCompanionError('A browser companion asset is missing, redirected or too large.')
            with os.fdopen(open_child(path.name), 'rb') as stream:
                opened = os.fstat(stream.fileno())
                if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                        or getattr(opened, 'st_file_attributes', 0) & 0x400
                        or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                        != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
                    raise BrowserCompanionError('A browser companion asset changed while opening.')
                _verify_bindings(bindings)
                data = stream.read(MAX_ASSET_BYTES + 1)
                after = os.fstat(stream.fileno())
            _verify_bindings(bindings)
            if (len(data) != before.st_size or len(data) > MAX_ASSET_BYTES
                    or after.st_nlink != 1
                    or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                raise BrowserCompanionError('A browser companion asset changed while reading.')
        text = data.decode('utf-8')
        if '\0' in text:
            raise BrowserCompanionError('Browser companion assets must be reviewed text.')
        return data
    except (OSError, UnicodeError, ValueError) as error:
        if isinstance(error, BrowserCompanionError):
            raise
        raise BrowserCompanionError('Browser companion resources are unavailable. Reinstall the complete Toolkit.') from error


def _load_assets():
    package_root = _package_root()
    bundled = package_root / 'browser_tools'
    use_bundle = bundled.exists()
    source_root = Path(__file__).resolve().parents[3]
    if not use_bundle and not (source_root / 'pyproject.toml').is_file():
        raise BrowserCompanionError('Browser companion resources are unavailable. Use the complete Toolkit download.')
    assets, total = {}, 0
    for tool_id, names in _FILES.items():
        for name in names:
            root = package_root if use_bundle else source_root
            relative = (f'browser_tools/{tool_id}/{name}' if use_bundle
                        else f'{_SOURCE_DIRECTORIES[tool_id]}/{name}')
            data = _read_asset(root, relative)
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise BrowserCompanionError('The browser companion resource set exceeds its size bound.')
            assets[(tool_id, name)] = _Asset(data, _MIME_TYPES.get(PurePosixPath(name).suffix, 'text/plain; charset=utf-8'))
    return MappingProxyType(assets)


class _BoundedHeaders:
    def __init__(self, stream):
        self.stream, self.remaining = stream, MAX_HEADERS_BYTES

    def readline(self, limit=-1):
        if self.remaining <= 0:
            raise http.client.LineTooLong('request headers')
        maximum = self.remaining + 1
        line = self.stream.readline(min(limit, maximum) if limit >= 0 else maximum)
        self.remaining -= len(line)
        if self.remaining < 0:
            raise http.client.LineTooLong('request headers')
        return line


class _Handler(BaseHTTPRequestHandler):
    server_version = 'ToolkitBrowser'
    sys_version = ''

    def setup(self):
        self.request.settimeout(CLIENT_TIMEOUT)
        super().setup()

    def log_message(self, *args):
        # Do not log private session tokens, browser request paths or headers.
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', _CSP)
        self.send_header('Connection', 'close')
        super().end_headers()

    def parse_request(self):
        original = self.rfile
        self.rfile = _BoundedHeaders(original)
        try:
            return super().parse_request()
        finally:
            self.rfile = original

    def _reply(self, status, data=b'', content_type='text/plain; charset=utf-8'):
        self.send_response(status)
        if status == 405:
            self.send_header('Allow', 'GET, HEAD')
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def handle_one_request(self):
        try:
            self.raw_requestline = self.rfile.readline(MAX_REQUEST_LINE + 1)
            if len(self.raw_requestline) > MAX_REQUEST_LINE:
                self.requestline, self.request_version, self.command = '', '', ''
                self.send_error(414)
                return
            if not self.raw_requestline or not self.parse_request():
                return
            if self.command not in {'GET', 'HEAD'}:
                self._reply(405, b'Only GET and HEAD are supported.\n')
                return
            if (self.headers.get_all('Host') != [self.server.netloc]
                    or self.headers.get_all('Origin', []) not in ([], [self.server.origin])
                    or self.headers.get('Sec-Fetch-Site') == 'cross-site'):
                self._reply(403)
                return
            if (self.headers.get_all('Transfer-Encoding', [])
                    or self.headers.get_all('Content-Length', []) not in ([], ['0'])):
                self._reply(400)
                return
            target = self.raw_requestline.split()[1].decode('ascii', errors='replace')
            if (not target.startswith('/') or target.startswith('//')
                    or any(character in target for character in ('%', '\\', '?', '#'))):
                self._reply(404)
                return
            asset = self.server.assets.get(target)
            if asset is None:
                self._reply(404)
                return
            self._reply(200, asset.data, asset.content_type)
        except (OSError, TimeoutError):
            pass
        finally:
            self.close_connection = True


class _ResourceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = MAX_CLIENTS

    def __init__(self, assets, token):
        self.assets = {}
        for (tool_id, name), asset in assets.items():
            self.assets[f'/{token}/{tool_id}/{name}'] = asset
            if name == 'index.html':
                self.assets[f'/{token}/{tool_id}/'] = asset
        self._slots = threading.BoundedSemaphore(MAX_CLIENTS)
        self._clients, self._deadlines, self._client_lock = set(), {}, threading.Lock()
        super().__init__(('127.0.0.1', 0), _Handler)
        self.netloc = f'127.0.0.1:{self.server_address[1]}'
        self.origin = f'http://{self.netloc}'

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        with self._client_lock:
            self._clients.add(request)
            self._deadlines[request] = time.monotonic() + CLIENT_TIMEOUT
        try:
            super().process_request(request, client_address)
        except BaseException:
            with self._client_lock:
                self._clients.discard(request)
                self._deadlines.pop(request, None)
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._client_lock:
                self._clients.discard(request)
                self._deadlines.pop(request, None)
            self._slots.release()

    def service_actions(self):
        # Socket timeouts alone allow a slow client to keep a line alive by
        # sending occasional bytes. Enforce an absolute request deadline too.
        now = time.monotonic()
        with self._client_lock:
            expired = tuple(client for client, deadline in self._deadlines.items() if deadline <= now)
        self._close_sockets(expired)

    @staticmethod
    def _close_sockets(clients):
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()

    def close_clients(self):
        with self._client_lock:
            clients = tuple(self._clients)
        self._close_sockets(clients)

    def handle_error(self, request, client_address):
        # Client disconnects must not print session tokens or local paths.
        pass


class BrowserCompanionManager:
    """Own one browser-tools session; the GUI closes it on application exit."""
    def __init__(self, *, browser_opener=None):
        self._browser_opener = browser_opener or (lambda url: webbrowser.open(url, new=2, autoraise=True))
        self._lock = threading.RLock()
        self._server = self._thread = None
        self._token, self._closed = secrets.token_hex(24), False

    def url_for(self, tool_id):
        """Return a local session URL, starting the managed static server once."""
        if type(tool_id) is not str or tool_id not in _TOOL_IDS:
            raise BrowserCompanionError('Choose a supported browser companion.')
        with self._lock:
            if self._closed:
                raise BrowserCompanionError('This browser companion session has closed. Reopen the Toolkit.')
            if self._server is None:
                try:
                    server = _ResourceServer(_load_assets(), self._token)
                except OSError as error:
                    raise BrowserCompanionError('The local browser companion server could not start.') from error
                thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.1},
                                          name='ToolkitBrowserCompanions', daemon=True)
                try:
                    thread.start()
                except BaseException:
                    server.server_close()
                    raise
                self._server, self._thread = server, thread
            return f'{self._server.origin}/{self._token}/{tool_id}/'

    def open(self, tool_id):
        """Open the real bundled tool in the user's default browser."""
        url = self.url_for(tool_id)
        try:
            opened = self._browser_opener(url)
        except (OSError, webbrowser.Error) as error:
            raise BrowserCompanionError('The default browser could not open the companion.') from error
        if not opened:
            raise BrowserCompanionError('The default browser could not open the companion.')
        return url

    def close(self):
        """Stop accepting requests, close owned clients, and release the port."""
        with self._lock:
            self._closed = True
            server, thread = self._server, self._thread
            self._server = self._thread = None
        if server is not None:
            server.shutdown()
            server.close_clients()
            server.server_close()
            thread.join(timeout=2.0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
