"""Registry-derived compatibility information; never imports a game parser."""
from dataclasses import dataclass

from koei_editor.game_registry import GAMES
from koei_editor.shared.library_catalog import normalized
from koei_editor.shared.support_catalog import load_catalog


@dataclass(frozen=True)
class CompatibilityEntry:
    game_id: str
    title: str
    platform: str
    revision_scope: str
    functionality: str
    file_evidence: str
    evidence: str
    remaining_validation: str
    game_validation: str = 'No game-load/re-save attestation in this catalog'


def compatibility_entries():
    """Keep supported profiles separate from unregistered research candidates.

    Edition subtitles are the reviewed revision scope, not inferred exact software
    builds. Genuine-file qualification never implies an edited save loaded.
    """
    evidence = {entry['id']: entry for entry in load_catalog()}
    return tuple(CompatibilityEntry(
        game.id, game.title, game.platform, game.subtitle,
        game.description,
        'Genuine-file qualified' if game.editing_verified else 'Implementation; independent file qualification pending',
        evidence.get(game.id, {}).get('evidence', 'No catalog evidence recorded'),
        evidence.get(game.id, {}).get('needed', 'Exact build and game-load validation must be recorded separately'),
    ) for game in GAMES)


def search_compatibility(entries, query='', platform=''):
    terms = normalized(query).split()
    return tuple(entry for entry in entries if
                 (not platform or entry.platform == platform) and
                 all(term in normalized(' '.join((entry.game_id, entry.title, entry.platform,
                     entry.revision_scope, entry.functionality, entry.file_evidence,
                     entry.evidence, entry.remaining_validation))) for term in terms))
