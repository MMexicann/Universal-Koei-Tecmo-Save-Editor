"""Small, session-only client for the documented Nexus Mods v3 API.

Nexus currently marks the mod discovery/details endpoints used here as
experimental. Keep transport and schema handling isolated in this module.
"""

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import json
import re
from typing import Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import (HTTPRedirectHandler, Request, build_opener)


API_ROOT = 'https://api.nexusmods.com/v3'
API_DOCS_URL = 'https://api-docs.nexusmods.com/'
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 15
MAX_PAGE = 100
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class NexusGame:
    game_id: str
    domain: str
    title: str


# These are explicit Nexus game domains, not guesses derived from display names.
# Keep this list limited to Windows PC profiles with a confirmed Nexus game page.
SUPPORTED_NEXUS_GAMES = (
    NexusGame('dw8xl', 'dynastywarriors8', 'DYNASTY WARRIORS 8 — Xtreme Legends Complete Edition'),
    NexusGame('pw3', 'onepiecepiratewarriors3', 'ONE PIECE: PIRATE WARRIORS 3'),
    NexusGame('pw4', 'onepiecepiratewarriors4', 'ONE PIECE: PIRATE WARRIORS 4'),
    NexusGame('atelier_sophie2', 'ateliersophie2', 'ATELIER SOPHIE 2'),
    NexusGame('origins', 'dynastywarriorsorigins', 'DYNASTY WARRIORS: ORIGINS'),
    NexusGame('sw4ii', 'samuraiwarriors4ii', 'SAMURAI WARRIORS 4-II'),
    NexusGame('sw2', 'samuraiwarriors2', 'SAMURAI WARRIORS 2'),
    NexusGame('dw6', 'dynastywarriors6', 'DYNASTY WARRIORS 6'),
    NexusGame('stars', 'warriorsallstars', 'WARRIORS ALL-STARS'),
    NexusGame('wo3u', 'warriorsorochi3', 'WARRIORS OROCHI 3 ULTIMATE'),
    NexusGame('wolong', 'wolongfallendynasty', 'WO LONG: FALLEN DYNASTY'),
    NexusGame('p5strikers_pc', 'persona5strikers', 'PERSONA 5 STRIKERS'),
    NexusGame('nioh3', 'nioh3', 'NIOH 3'),
    NexusGame('dqb2_pc', 'dragonquestbuilders2', 'DRAGON QUEST BUILDERS 2'),
    NexusGame('wo4_pc', 'warriorsorochi4', 'WARRIORS OROCHI 4'),
    NexusGame('wo4_ultimate', 'warriorsorochi4', 'WARRIORS OROCHI 4 ULTIMATE'),
    NexusGame('samurai5_pc', 'samuraiwarriors5', 'SAMURAI WARRIORS 5'),
    NexusGame('abyss_pc', 'warriorsabyss', 'WARRIORS: ABYSS'),
    NexusGame('blue_reflection_second_light_pc', 'bluereflectionsecondlight',
              'BLUE REFLECTION: SECOND LIGHT'),
)
_GAME_BY_DOMAIN = {game.domain: game for game in SUPPORTED_NEXUS_GAMES}
_GAMES_BY_ID = {game.game_id: game for game in SUPPORTED_NEXUS_GAMES}
_DOMAIN_RE = re.compile(r'^[a-z0-9_]{1,64}$')
_NUMERIC_ID_RE = re.compile(r'^[0-9]{1,20}$')
_APP_VERSION_RE = re.compile(r'^[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+][0-9A-Za-z.-]+)?$')


class NexusApiError(RuntimeError):
    """A safe API error that never includes the request URL, key, or body."""

    def __init__(self, message, *, status=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class NexusAuthenticationError(NexusApiError):
    pass


class NexusPermissionError(NexusApiError):
    pass


class NexusRateLimitError(NexusApiError):
    pass


class NexusNotFoundError(NexusApiError):
    pass


class NexusNetworkError(NexusApiError):
    pass


class NexusProtocolError(NexusApiError):
    pass


@dataclass(frozen=True)
class ApiResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[Request, float], ApiResponse]


class _RejectRedirects(HTTPRedirectHandler):
    """Never forward the user-supplied API key to a redirect destination."""

    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def _urllib_transport(request, timeout):
    opener = build_opener(_RejectRedirects())
    try:
        response = opener.open(request, timeout=timeout)
    except HTTPError as error:
        try:
            return ApiResponse(error.code, dict(error.headers.items()), error.read(MAX_RESPONSE_BYTES + 1))
        finally:
            error.close()
    except (URLError, TimeoutError, OSError) as error:
        raise NexusNetworkError('Could not reach Nexus Mods. Check the connection and try again.') from None
    try:
        return ApiResponse(response.status, dict(response.headers.items()),
                           response.read(MAX_RESPONSE_BYTES + 1))
    finally:
        response.close()


@dataclass(frozen=True)
class ModSummary:
    mod_id: str
    game_scoped_id: str
    game_domain: str
    name: str
    summary: str
    version: str
    author: str
    category: str
    endorsements: int
    downloads: int
    updated_at: str
    adult: bool
    supports_vortex: bool


@dataclass(frozen=True)
class ModPage:
    mods: tuple[ModSummary, ...]
    page: int
    page_size: int
    total_count: int

    @property
    def has_more(self):
        return self.page < MAX_PAGE and self.page * self.page_size < self.total_count


@dataclass(frozen=True)
class ModDetails:
    mod_id: str
    game_scoped_id: str
    game_domain: str
    name: str
    description: str
    version: str
    author: str
    category: str
    adult: bool


@dataclass(frozen=True)
class ModFile:
    file_id: str
    name: str


@dataclass(frozen=True)
class ModFileVersion:
    version_id: str
    game_scoped_version_id: str
    file_id: str
    file_name: str
    name: str
    version: str
    category: str
    uploaded_at: str
    is_primary: bool


@dataclass(frozen=True)
class DependencyRange:
    mod_name: str
    file_name: str
    minimum_version: str
    maximum_version: str | None


@dataclass(frozen=True)
class DependencyDefinition:
    # Nexus defines ranges in one group as alternatives; groups are independent.
    alternatives: tuple[DependencyRange, ...]


@dataclass(frozen=True)
class DlcDependencyDefinition:
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class ModDependencies:
    definitions: tuple[DependencyDefinition, ...]
    dlc_definitions: tuple[DlcDependencyDefinition, ...]


@dataclass(frozen=True)
class NexusDownloadRequest:
    """Metadata handoff; it deliberately contains no key or signed download URL."""

    provider: str
    game_domain: str
    game_scoped_mod_id: str
    mod_id: str
    file_id: str
    file_version_id: str
    game_scoped_file_version_id: str
    mod_page_url: str


class DownloadHandoff(Protocol):
    """Structural contract implemented by the separate Mod Manager component."""

    def enqueue_nexus_download(self, request: NexusDownloadRequest) -> bool:
        """Return true only after the manager accepts this user-selected request."""
        ...


def build_download_request(summary, version):
    """Build the manager payload from selected API rows, never a resolved URL."""
    _validate_supported_domain(summary.game_domain)
    _validate_id(summary.game_scoped_id, 'mod id')
    _validate_id(summary.mod_id, 'mod id')
    _validate_opaque_id(version.file_id, 'file id')
    _validate_opaque_id(version.version_id, 'file version id')
    _validate_opaque_id(version.game_scoped_version_id, 'game scoped file version id')
    return NexusDownloadRequest(
        provider='nexus', game_domain=summary.game_domain,
        game_scoped_mod_id=summary.game_scoped_id, mod_id=summary.mod_id,
        file_id=version.file_id, file_version_id=version.version_id,
        game_scoped_file_version_id=version.game_scoped_version_id,
        mod_page_url=mod_page_url(summary.game_domain, summary.game_scoped_id),
    )


def nexus_game_for_id(game_id):
    return _GAMES_BY_ID.get(game_id)


def mod_page_url(game_domain, game_scoped_id):
    _validate_game_domain(game_domain)
    _validate_id(game_scoped_id, 'mod id')
    return f'https://www.nexusmods.com/{game_domain}/mods/{quote(str(game_scoped_id), safe="")}'


def search_loaded_mods(mods, query):
    """Filter only the pages already fetched; Nexus v3 has no text query field."""
    tokens = query.casefold().split()
    if not tokens:
        return tuple(mods)
    matches = []
    for mod in mods:
        searchable = ' '.join((mod.name, mod.summary, mod.version, mod.author)).casefold()
        if all(token in searchable for token in tokens):
            matches.append(mod)
    return tuple(matches)


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ('br', 'p', 'div', 'li', 'tr', 'blockquote'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('p', 'div', 'li', 'tr', 'blockquote'):
            self.parts.append('\n')


_BBCODE_TAG_RE = re.compile(r'\[/?(?:/?(?:b|i|u|s|center|left|right|quote|code|spoiler|list|\*|hr|br|p|h[1-6])|(?:color|font|size|url|img|youtube|video)(?:=[^\]]*)?)\]', re.I)
_HTML_TAG_RE = re.compile(r'<[^>]*>')


def description_as_text(raw_description):
    """Return untrusted BBCode/HTML as plain text; never interpret remote markup."""
    source = str(raw_description or '')
    source = _BBCODE_TAG_RE.sub('', source)
    source = _HTML_TAG_RE.sub('', source)
    parser = _PlainText()
    try:
        parser.feed(unescape(source))
        parser.close()
        source = ''.join(parser.parts)
    except Exception:
        # Preserve readable plain text if an uploader supplied malformed markup.
        source = unescape(source)
    lines = [' '.join(line.split()) for line in source.splitlines()]
    compact = []
    for line in lines:
        if line or (compact and compact[-1]):
            compact.append(line)
    return '\n'.join(compact).strip()


class NexusApiClient:
    """Nexus API client with an in-memory API key and injectable HTTP transport."""

    def __init__(self, *, api_key=None, application_name, application_version,
                 transport=None, timeout=DEFAULT_TIMEOUT_SECONDS):
        if not isinstance(application_name, str) or not application_name.strip():
            raise ValueError('Application-Name must be provided.')
        if (not isinstance(application_version, str)
                or not _APP_VERSION_RE.fullmatch(application_version.strip())):
            raise ValueError('Application-Version must be a semantic version.')
        if api_key is not None and (not isinstance(api_key, str) or '\n' in api_key or '\r' in api_key):
            raise ValueError('The Nexus API key is invalid.')
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 60:
            raise ValueError('Timeout must be between 1 and 60 seconds.')
        self._api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        self._application_name = application_name.strip()
        self._application_version = application_version.strip()
        self._transport = transport or _urllib_transport
        self._timeout = float(timeout)
        self.last_rate_headers = {}

    @property
    def has_api_key(self):
        return self._api_key is not None

    def search_mods(self, game_domain, *, sort='trending', direction='desc',
                    time_range=None, page=1, page_size=30):
        _validate_game_domain(game_domain)
        if game_domain not in _GAME_BY_DOMAIN:
            raise ValueError('This Nexus game domain is not in the supported game list.')
        if sort not in ('new', 'updated', 'trending', 'popular', 'endorsements'):
            raise ValueError('Unsupported Nexus mod sort.')
        if direction not in ('asc', 'desc'):
            raise ValueError('Unsupported Nexus sort direction.')
        if time_range is not None and str(time_range) not in ('1', '7', '14', '28', '365', 'all'):
            raise ValueError('Unsupported Nexus time range.')
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= MAX_PAGE:
            raise ValueError('Nexus page must be between 1 and 100.')
        if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError('Nexus page size must be between 1 and 100.')
        filters = {'games': [game_domain], 'include_adult': False}
        if time_range is not None:
            filters['time_range'] = str(time_range)
        payload = self._request('POST', '/mods/search', authenticated=False, body={
            'filters': filters,
            'sort': {'field': sort, 'direction': direction},
            'pagination': {'page': page, 'page_size': page_size},
        })
        data = _mapping(payload.get('data'), 'search data')
        meta = _mapping(payload.get('meta'), 'search pagination')
        mods = data.get('mods')
        if not isinstance(mods, list):
            raise NexusProtocolError('Nexus returned an unrecognized mod search response.')
        parsed_mods = tuple(_parse_mod_summary(item, game_domain) for item in mods)
        return ModPage(
            # The request explicitly excludes adult entries; also enforce that
            # boundary client-side if an experimental API response drifts.
            mods=tuple(mod for mod in parsed_mods if not mod.adult),
            page=_integer(meta.get('page'), page),
            page_size=_integer(meta.get('page_size'), page_size),
            total_count=_integer(meta.get('total_count'), len(mods)),
        )

    def get_mod(self, game_domain, game_scoped_id):
        _validate_supported_domain(game_domain)
        _validate_id(game_scoped_id, 'mod id')
        payload = self._request('GET', f'/games/{game_domain}/mods/{quote(str(game_scoped_id), safe="")}')
        data = _mapping(payload.get('data'), 'mod details')
        return ModDetails(
            mod_id=_text(data.get('id')),
            game_scoped_id=_text(data.get('game_scoped_id'), str(game_scoped_id)),
            game_domain=game_domain,
            name=_required_text(data.get('name'), 'mod name'),
            description=description_as_text(data.get('description')),
            version=_text(data.get('version')),
            author=_text(data.get('author')),
            category=_text(_nested(data, 'category', 'name')),
            adult=bool(data.get('adult_content', False)),
        )

    def get_files(self, mod_id):
        _validate_id(mod_id, 'mod id')
        payload = self._request('GET', f'/mods/{quote(str(mod_id), safe="")}/files')
        data = _mapping(payload.get('data'), 'mod files')
        raw_files = data.get('mod_files')
        if not isinstance(raw_files, list):
            raise NexusProtocolError('Nexus returned an unrecognized file list.')
        files = []
        for item in raw_files:
            item = _mapping(item, 'mod file')
            files.append(ModFile(_required_text(item.get('id'), 'file id'),
                                 _required_text(item.get('name'), 'file name')))
        return tuple(files)

    def get_versions(self, file_id):
        _validate_opaque_id(file_id, 'file id')
        payload = self._request('GET', f'/mod-files/{quote(str(file_id), safe="")}/versions')
        data = _mapping(payload.get('data'), 'file versions')
        raw_versions = data.get('versions')
        if not isinstance(raw_versions, list):
            raise NexusProtocolError('Nexus returned an unrecognized version list.')
        versions = []
        for item in raw_versions:
            item = _mapping(item, 'mod file version')
            file = _mapping(item.get('file'), 'version file')
            versions.append(ModFileVersion(
                version_id=_required_text(item.get('id'), 'file version id'),
                game_scoped_version_id=_required_text(item.get('game_scoped_id'), 'game scoped file version id'),
                file_id=_required_text(file.get('id'), 'file id'),
                file_name=_required_text(file.get('name'), 'file name'),
                name=_required_text(item.get('name'), 'file version name'),
                version=_required_text(item.get('version'), 'file version'),
                category=_required_text(item.get('category'), 'file category'),
                uploaded_at=_required_text(item.get('uploaded_at'), 'file upload date'),
                is_primary=bool(item.get('is_primary', False)),
            ))
        return tuple(versions)

    def get_dependencies(self, version_id):
        _validate_opaque_id(version_id, 'file version id')
        payload = self._request('GET', f'/mod-file-versions/{quote(str(version_id), safe="")}/dependencies')
        data = payload.get('data', payload)
        data = _mapping(data, 'file dependencies')
        raw_definitions = data.get('dependency_definitions')
        raw_dlc_definitions = data.get('dlc_dependency_definitions')
        if not isinstance(raw_definitions, list) or not isinstance(raw_dlc_definitions, list):
            raise NexusProtocolError('Nexus returned an unrecognized dependency list.')
        definitions = []
        for definition in raw_definitions:
            definition = _mapping(definition, 'dependency definition')
            raw_ranges = definition.get('ranges')
            if not isinstance(raw_ranges, list):
                raise NexusProtocolError('Nexus returned an unrecognized dependency range list.')
            ranges = []
            for item in raw_ranges:
                item = _mapping(item, 'dependency range')
                target = _mapping(item.get('target_mod_file'), 'dependency target file')
                mod = _mapping(target.get('mod'), 'dependency target mod')
                minimum = _required_text(
                    _mapping(item.get('min_version'), 'minimum dependency version').get('version'),
                    'minimum dependency version')
                maximum_obj = item.get('max_version')
                maximum = (_required_text(_mapping(maximum_obj, 'maximum dependency version').get('version'),
                                          'maximum dependency version')
                           if maximum_obj is not None else None)
                ranges.append(DependencyRange(
                    mod_name=_required_text(mod.get('name'), 'dependency mod name'),
                    file_name=_required_text(target.get('name'), 'dependency file name'),
                    minimum_version=minimum,
                    maximum_version=maximum,
                ))
            definitions.append(DependencyDefinition(tuple(ranges)))
        dlc_definitions = []
        for definition in raw_dlc_definitions:
            definition = _mapping(definition, 'DLC dependency definition')
            raw_targets = definition.get('dlc_targets')
            if not isinstance(raw_targets, list):
                raise NexusProtocolError('Nexus returned an unrecognized DLC dependency list.')
            targets = tuple(_required_text(_mapping(item, 'DLC dependency target').get('name'),
                                           'DLC dependency name') for item in raw_targets)
            dlc_definitions.append(DlcDependencyDefinition(targets))
        return ModDependencies(tuple(definitions), tuple(dlc_definitions))

    def _request(self, method, path, *, authenticated=True, body=None):
        if authenticated and self._api_key is None:
            raise NexusAuthenticationError('Add your Nexus API key to load details, files and dependencies.')
        if not path.startswith('/') or '://' in path or '\\' in path:
            raise ValueError('Invalid Nexus API path.')
        url = API_ROOT + path
        headers = {
            'Accept': 'application/json',
            'Application-Name': self._application_name,
            'Application-Version': self._application_version,
        }
        if self._api_key is not None:
            headers['apikey'] = self._api_key
        data = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body, separators=(',', ':')).encode('utf-8')
        request = Request(url, data=data, headers=headers, method=method)
        response = self._transport(request, self._timeout)
        if not isinstance(response, ApiResponse):
            raise TypeError('Nexus transport must return ApiResponse.')
        self.last_rate_headers = {
            str(key).casefold(): str(value)
            for key, value in response.headers.items()
            if str(key).casefold().startswith('x-rl-')
            or 'ratelimit' in str(key).casefold()
            or str(key).casefold() == 'retry-after'
        }
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise NexusProtocolError('Nexus response exceeded the size limit.', status=response.status)
        if response.status == 401:
            raise NexusAuthenticationError('Nexus rejected the API key. Check it in Nexus account settings.', status=401)
        if response.status == 403:
            raise NexusPermissionError('Nexus denied access to this content or action.', status=403)
        if response.status == 404:
            raise NexusNotFoundError('Nexus could not find this mod or file.', status=404)
        if response.status == 429:
            retry_after = _header(response.headers, 'retry-after')
            raise NexusRateLimitError('Nexus request limit reached. Wait before trying again.',
                                      status=429, retry_after=retry_after)
        if response.status < 200 or response.status >= 300:
            raise NexusApiError(f'Nexus API returned HTTP {response.status}.', status=response.status)
        try:
            result = json.loads(response.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise NexusProtocolError('Nexus returned invalid JSON.', status=response.status) from None
        if not isinstance(result, dict):
            raise NexusProtocolError('Nexus returned an unexpected response.', status=response.status)
        return result


def _validate_game_domain(game_domain):
    if not isinstance(game_domain, str) or not _DOMAIN_RE.fullmatch(game_domain):
        raise ValueError('Invalid Nexus game domain.')


def _validate_supported_domain(game_domain):
    _validate_game_domain(game_domain)
    if game_domain not in _GAME_BY_DOMAIN:
        raise ValueError('This Nexus game domain is not in the supported game list.')


def _validate_id(value, label):
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not _NUMERIC_ID_RE.fullmatch(str(value)):
        raise ValueError(f'Invalid {label}.')


def _validate_opaque_id(value, label):
    if (not isinstance(value, str) or not value or len(value) > 512
            or value in ('.', '..') or '/' in value or '\\' in value
            or any(ord(character) < 0x20 or ord(character) == 0x7f for character in value)):
        raise ValueError(f'Invalid {label}.')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        raise ValueError(f'Invalid {label}.') from None


def _parse_mod_summary(item, game_domain):
    if not isinstance(item, dict):
        raise NexusProtocolError('Nexus returned an invalid mod entry.')
    game = item.get('game') if isinstance(item.get('game'), dict) else {}
    author = item.get('author') if isinstance(item.get('author'), dict) else {}
    category = item.get('category') if isinstance(item.get('category'), dict) else {}
    if _required_text(game.get('domain_name'), 'game domain') != game_domain:
        raise NexusProtocolError('Nexus returned a mod for an unexpected game.')
    mod_id = _required_text(item.get('id'), 'mod id')
    game_scoped_id = _required_text(item.get('game_scoped_id'), 'game scoped mod id')
    _validate_id(mod_id, 'mod id')
    _validate_id(game_scoped_id, 'game scoped mod id')
    return ModSummary(
        mod_id=mod_id,
        game_scoped_id=game_scoped_id,
        game_domain=game_domain,
        name=_required_text(item.get('name'), 'mod name'),
        summary=description_as_text(item.get('summary')),
        version=_text(item.get('version')),
        author=_text(author.get('name')),
        category=_text(category.get('name')),
        endorsements=_integer(item.get('endorsements'), 0),
        downloads=_integer(item.get('downloads'), 0),
        updated_at=_text(item.get('updated_at')),
        adult=bool(item.get('adult', False)),
        supports_vortex=bool(item.get('supports_vortex', False)),
    )


def _mapping(value, label):
    if not isinstance(value, dict):
        raise NexusProtocolError(f'Nexus returned an invalid {label} response.')
    return value


def _nested(value, key, child):
    nested = value.get(key) if isinstance(value, dict) else None
    return nested.get(child) if isinstance(nested, dict) else None


def _integer(value, fallback):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else fallback


def _text(value, fallback=''):
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _required_text(value, label):
    result = _text(value)
    if not result:
        raise NexusProtocolError(f'Nexus returned a mod entry without a {label}.')
    return result


def _header(headers, name):
    target = name.casefold()
    return next((str(value) for key, value in headers.items() if str(key).casefold() == target), None)
