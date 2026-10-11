"""Read-only story envelope and field inspection. No registered gameplay writer."""
from dataclasses import dataclass, field
from pathlib import Path
import hmac
import struct
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.ninja_gaiden_black_xbox import codec, owner

@dataclass(frozen=True)
class Story:
    raw: bytes = field(repr=False)
    payload: bytes = field(repr=False)
    context: owner.Context = field(repr=False)


def read_story(path):
    source = owner.ordinary(path)
    context = owner.read_story_context(source)
    try:
        with source.open('rb') as stream:
            raw = stream.read(codec.SIZE + 1)
    except OSError:
        raise SaveError('The copied story file is unavailable.') from None
    if len(raw) != codec.SIZE or not hmac.compare_digest(raw[:20], owner.signature(raw, context.key)):
        raise SaveError('Original Xbox story envelope signature is invalid.')
    _plain, payload, _extent, _counts = codec.decrypt(raw)
    owner.validate_story_context(context, source)
    return Story(raw, payload, context)


def records(story):
    if type(story) is not Story:
        raise SaveError('Requires a read-only original Xbox story snapshot.')
    return {'karma_score': struct.unpack_from('<I', story.payload, 42 + 0x16620)[0],
            'frames': struct.unpack_from('<I', story.payload, 42 + 0x16628)[0],
            'difficulty': story.payload[42 + 0x16815],
            'chapter': story.payload[42 + 0x16817],
            'category': story.payload[42 + 0x1681a]}
