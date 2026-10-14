"""Lossless common-revision PC/PS3/Vita DW8 XL gameplay transfer."""
import struct
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl_vita.parser import SIGNATURE
from koei_editor.shared.koei_codec import byte_cipher, mix_word, word_cipher, word_sum


def gameplay(document):
    if document.payload[:5] != SIGNATURE:
        raise SaveError('Conversion requires DW8 XL revision 0x131002F0; modded PC headers remain editable in the PC editor.')
    return document.payload


def encode(source, template):
    payload = gameplay(source)
    gameplay(template)
    if template.format.id == 'dw8xl':
        seed = template.seed
        inner = byte_cipher(payload, 0x13100200)
        return (struct.pack('<HH', word_sum(inner), seed) + word_cipher(inner, seed)
                + bytes(((sum(payload) & 255) ^ (mix_word(seed) & 255),)))
    if template.format.id == 'dw8xl_ps3':
        return byte_cipher(payload, 0x13100200) + bytes((sum(payload) & 255,))
    return payload + bytes((sum(payload) & 255,))
