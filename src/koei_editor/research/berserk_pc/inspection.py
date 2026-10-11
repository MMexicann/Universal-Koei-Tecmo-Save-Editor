"""Recognize the observed Windows title header without authorizing edits.

Three independently acquired complete PC files agree on these header bytes and
the existing three-advance envelope. A title string does not establish a save
revision, ownership, gameplay mappings or absence of additional integrity.
"""
from dataclasses import dataclass, field

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.berserk_aot import envelope


TITLE = b'BERSERK and the Band of the Hawk'
TITLE_HEADER = TITLE.ljust(0x40, b'\0')
OBSERVED_SLOT_LABEL = b'Saved Data: 1'.ljust(0x10, b'\0')


@dataclass(frozen=True)
class Inspection:
    """Private snapshot with an explicitly limited, non-writable conclusion."""

    outer: envelope.EnvelopeInspection = field(repr=False)

    @property
    def title_matches(self):
        return True

    @property
    def revision_verified(self):
        return False

    @property
    def all_integrity_verified(self):
        return False

    @property
    def writable(self):
        return False


def _check_header(payload):
    if payload[:0x40] != TITLE_HEADER:
        raise SaveError('Berserk observed PC title header does not match.')
    if payload[0x80:0x90] != OBSERVED_SLOT_LABEL:
        raise SaveError('Berserk observed slot-one display header does not match.')


def inspect(raw):
    """Validate the observed envelope/title only; reject foreign header data."""
    outer = envelope.inspect(raw, profile='berserk')
    _check_header(outer.payload)
    return Inspection(outer)


def reencode_unchanged(document):
    """Return a qualified original snapshot; no replacement payload accepted."""
    if type(document) is not Inspection:
        raise SaveError('Expected a Berserk read-only inspection snapshot.')
    if (type(document.outer) is not envelope.EnvelopeInspection
            or document.outer.profile_id != 'berserk'):
        raise SaveError('Expected the explicit Berserk outer envelope profile.')
    raw = envelope.reencode_unchanged(document.outer)
    _check_header(document.outer.payload)
    return raw
