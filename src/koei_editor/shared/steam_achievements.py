"""Opt-in Steam Web API achievement snapshots.

The caller supplies credentials for one explicit lookup. No key, SteamID64,
response body, save document or path is retained in the returned snapshot.
Missing or malformed player states stay unavailable; only explicit API values
of 0 and 1 become locked and unlocked.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_HOST = 'api.steampowered.com'
TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_API_KEY = re.compile(r'[A-Fa-f0-9]{32}\Z')
_STEAM_ID64 = re.compile(r'[0-9]{17}\Z')


@dataclass(frozen=True)
class SteamAchievement:
    id: str
    name: str
    description: str
    state: str
    unlocked_at: str | None = None


@dataclass(frozen=True)
class SteamAchievementSnapshot:
    app_id: int
    status: str
    source: str = 'Steam Web API'
    retrieved_at: str | None = None
    achievements: tuple[SteamAchievement, ...] = ()
    unlocked_count: int | None = None
    total_count: int | None = None
    note: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'achievements', tuple(self.achievements))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


_OFFICIAL_OPENER = build_opener(_NoRedirect())


def _unavailable(app_id, entries=(), note='Steam achievement data is unavailable.'):
    rows = tuple(SteamAchievement(
        id=item['id'],
        name=item['name'],
        description=item['description'],
        state='unavailable',
    ) for item in entries)
    return SteamAchievementSnapshot(
        app_id=app_id, status='unavailable', achievements=rows, note=note,
    )


def _read_json(url, opener):
    request = Request(url, headers={'Accept': 'application/json',
                                    'User-Agent': 'UniversalKoeiTecmoSaveEditor'})
    response = opener(request, timeout=TIMEOUT_SECONDS)
    try:
        final_url = urlsplit(response.geturl())
        if final_url.scheme != 'https' or final_url.hostname != API_HOST:
            raise ValueError('Unexpected Steam API host.')
        body = response.read(MAX_RESPONSE_BYTES + 1)
    finally:
        response.close()
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError('Steam API response exceeds the size limit.')
    return json.loads(body.decode('utf-8'))


def _schema_entries(response):
    game = response.get('game') if type(response) is dict else None
    stats = game.get('availableGameStats') if type(game) is dict else None
    achievements = stats.get('achievements') if type(stats) is dict else None
    if type(achievements) is not list or not achievements or len(achievements) > 10000:
        raise ValueError('Steam returned no bounded achievement schema.')
    entries = []
    seen = set()
    for row in achievements:
        if type(row) is not dict:
            raise ValueError('Steam returned an invalid achievement schema.')
        identity = row.get('name')
        if type(identity) is not str or not identity or identity in seen or len(identity) > 256:
            raise ValueError('Steam returned an ambiguous achievement schema.')
        seen.add(identity)
        hidden = row.get('hidden') in (1, True, '1')
        display_name = row.get('displayName')
        description = row.get('description')
        if hidden:
            display_name, description = 'Hidden achievement', ''
        else:
            if type(display_name) is not str or not display_name.strip():
                display_name = identity
            if type(description) is not str:
                description = ''
        entries.append({'id': identity, 'name': display_name[:512],
                        'description': description[:2048]})
    return tuple(entries)


def _player_states(response, requested_steam_id):
    stats = response.get('playerstats') if type(response) is dict else None
    if type(stats) is not dict or stats.get('success') is not True:
        raise ValueError('Steam did not provide public player achievement states.')
    if stats.get('steamID') != requested_steam_id:
        raise ValueError('Steam returned a different profile.')
    rows = stats.get('achievements')
    if type(rows) is not list or len(rows) > 10000:
        raise ValueError('Steam returned no bounded player achievement list.')
    states = {}
    ambiguous = set()
    for row in rows:
        if type(row) is not dict:
            continue
        identity = row.get('apiname')
        achieved = row.get('achieved')
        unlocktime = row.get('unlocktime')
        if type(identity) is not str or not identity or len(identity) > 256:
            continue
        if identity in states or identity in ambiguous:
            states.pop(identity, None)
            ambiguous.add(identity)
            continue
        if type(achieved) is not int or achieved not in (0, 1):
            continue
        if type(unlocktime) is not int or unlocktime < 0:
            continue
        states[identity] = (achieved, unlocktime)
    return states, ambiguous


def _utc_time(timestamp):
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    except (OverflowError, OSError, ValueError):
        return None


def fetch_steam_achievements(api_key, steam_id64, app_id, *, opener=None, now=None):
    """Fetch schema and one public player's Steam achievement states.

    The returned object contains no account identifier or credential. Only
    call this after the user explicitly chooses Steam and supplies both values.
    """
    if type(app_id) is not int or app_id <= 0:
        return _unavailable(0, note='This game has no verified Steam achievement mapping.')
    if (type(api_key) is not str or not _API_KEY.fullmatch(api_key)
            or type(steam_id64) is not str or not _STEAM_ID64.fullmatch(steam_id64)):
        return _unavailable(app_id, note='Enter a Steam Web API key and a 17-digit SteamID64.')
    open_url = opener or _OFFICIAL_OPENER.open
    params = {'key': api_key, 'appid': str(app_id)}
    schema_url = f'https://{API_HOST}/ISteamUserStats/GetSchemaForGame/v2/?{urlencode(params)}'
    player_url = (f'https://{API_HOST}/ISteamUserStats/GetPlayerAchievements/v1/?'
                  f'{urlencode({**params, "steamid": steam_id64})}')
    entries = ()
    try:
        entries = _schema_entries(_read_json(schema_url, open_url))
        player = _read_json(player_url, open_url)
        states, ambiguous = _player_states(player, steam_id64)
        mapped_ids = {item['id'] for item in entries}
        complete = mapped_ids == set(states) and not ambiguous
        achievement_rows = []
        for item in entries:
            state = states.get(item['id'])
            if item['id'] in ambiguous or state is None:
                achievement_rows.append(SteamAchievement(**item, state='unavailable'))
                continue
            achieved, unlocktime = state
            achievement_rows.append(SteamAchievement(
                **item,
                state='unlocked' if achieved == 1 else 'locked',
                unlocked_at=_utc_time(unlocktime) if achieved == 1 else None,
            ))
        if not complete:
            return SteamAchievementSnapshot(
                app_id=app_id, status='unavailable', achievements=tuple(achievement_rows),
                note='Steam’s player response did not exactly match its achievement schema; missing or extra states remain unavailable.',
            )
        unlocked = sum(state[0] == 1 for state in states.values())
        stamp = (now or (lambda: datetime.now(timezone.utc)))()
        retrieved_at = stamp.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        return SteamAchievementSnapshot(
            app_id=app_id, status='verified', retrieved_at=retrieved_at,
            achievements=tuple(achievement_rows), unlocked_count=unlocked,
            total_count=len(entries), note='States verified from the Steam Web API for this retrieval.',
        )
    except Exception:
        # API error messages may echo request details. Never display or persist
        # raw errors, URLs, API keys, SteamIDs or response bodies.
        return _unavailable(app_id, entries,
                            'Steam could not provide a complete public achievement snapshot. Check the profile visibility and try again.')
