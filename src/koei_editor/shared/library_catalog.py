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


def matching_games(games, query='', platform=ALL_PLATFORMS, series=ALL_SERIES):
    """AND the search terms across titles, short IDs, platforms and features."""
    terms = normalized(query).split()
    matches = []
    for game in games:
        if platform != ALL_PLATFORMS and game.platform != platform:
            continue
        if series != ALL_SERIES and series_for(game) != series:
            continue
        words = normalized(' '.join((game.title, game.subtitle, game.platform,
                                    game.description, game.emblem, game.id,
                                    series_for(game))))
        # Compact IDs support familiar queries such as DW7, PW4 and WO3.
        compact = normalized(game.id).replace(' ', '')
        if all(term in words or term in compact for term in terms):
            matches.append(game)
    return tuple(sorted(matches, key=lambda game: (normalized(game.title),
                                                  normalized(game.subtitle),
                                                  game.platform, game.id)))
