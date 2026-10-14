"""Transfer the complete common English header and ten slots without trimming data."""
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.p5strikers_pc import codec
from koei_editor.games.p5strikers_switch.codec import SLOTS_END


def gameplay(document):
    return document.payload[:SLOTS_END]


def encode(source, template):
    if source.format.id == 'p5strikers_pc' and any(source.payload[SLOTS_END:-4]):
        raise SaveError('The PC save has nonzero data beyond the ten shared slots. Conversion would discard it; no output was made.')
    native = gameplay(source) + template.payload[SLOTS_END:]
    if template.format.id == 'p5strikers_pc':
        return codec.encode(codec.with_checksum(native), template.seed)
    return native
