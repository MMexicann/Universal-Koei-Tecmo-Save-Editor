"""Pure library filtering; never selects a save parser or probes a file."""
import re
import unicodedata

ALL_PLATFORMS = 'All platforms'
ALL_SERIES = 'All series'

_SERIES = (
    ('DYNASTY WARRIORS', 'Dynasty Warriors'),
    ('WARRIORS OROCHI', 'Warriors Orochi'),
    ('SAMURAI WARRIORS', 'Samurai Warriors'),
    ('ONE PIECE', 'Pirate Warriors'),
    ('HYRULE WARRIORS', 'Hyrule Warriors'),
    ('FIRE EMBLEM', 'Fire Emblem'),
    ('ATELIER', 'Atelier'),
    ('NIOH', 'Nioh'),
    ('NINJA GAIDEN', 'Ninja Gaiden'),
    ('FATAL FRAME', 'Fatal Frame / Project Zero'),
    ('PROJECT ZERO', 'Fatal Frame / Project Zero'),
    ('FIST OF THE NORTH STAR', 'Fist of the North Star'),
    ('BLUE REFLECTION', 'Blue Reflection'),
    ('DEAD OR ALIVE', 'Dead or Alive'),
    ('MONSTER RANCHER', 'Monster Rancher'),
    ('UNCHARTED WATERS', 'Uncharted Waters'),
    ('ROMANCE OF THE THREE KINGDOMS', 'Romance of the Three Kingdoms'),
    ("NOBUNAGA'S AMBITION", "Nobunaga's Ambition"),
)


def normalized(text):
    text = unicodedata.normalize('NFKD', text.casefold())
    return re.sub(r'[^\w]+', ' ', ''.join(char for char in text
                  if not unicodedata.combining(char))).strip().replace('_', ' ')


def series_for(game):
    for prefix, label in _SERIES:
        if game.title.upper().startswith(prefix):
            return label
    return game.title.title()


class LibraryCatalog:
    """Search index for one immutable registry snapshot.

    Build once per library, then reuse for each keystroke. Normalized metadata,
    series and alphabetical ordering are computed once, without importing any
    editor or backend. Rebuild the index after changing the available profiles.
    Queries are not cached: memory remains proportional to the registry rather
    than the number or contents of searches.
    """

    __slots__ = ('_entries',)

    def __init__(self, games):
        ordered = sorted(games, key=lambda game: (normalized(game.title),
                         normalized(game.subtitle), game.platform, game.id))
        entries = []
        for game in ordered:
            series = series_for(game)
            words = normalized(' '.join((game.title, game.subtitle, game.platform,
                                        game.description, game.emblem, game.id, series)))
            compact = normalized(game.id).replace(' ', '')
            entries.append((game, game.platform, series, words, compact))
        self._entries = tuple(entries)

    def matching_games(self, query='', platform=ALL_PLATFORMS, series=ALL_SERIES):
        """AND terms across titles, short IDs, platforms and features."""
        terms = normalized(query).split()
        return tuple(game for game, game_platform, game_series, words, compact in self._entries
                     if (platform == ALL_PLATFORMS or game_platform == platform)
                     and (series == ALL_SERIES or game_series == series)
                     and all(term in words or term in compact for term in terms))


def matching_games(games, query='', platform=ALL_PLATFORMS, series=ALL_SERIES):
    """Filter an iterable, or reuse an existing :class:`LibraryCatalog` index."""
    catalog = games if isinstance(games, LibraryCatalog) else LibraryCatalog(games)
    return catalog.matching_games(query, platform, series)
