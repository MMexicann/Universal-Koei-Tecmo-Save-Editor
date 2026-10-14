"""BLUS30639 Leaf word, qualified on two independent original US exports."""
import re
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.plain_ps3 import NativeField, NativeFormat, PlainPS3Backend

GAME_ID = 'ar_tonelico_qoga_ps3'
SAVE_SIZE = 1048576
HEADER = bytes.fromhex('0132908500000000')
INTEGRITY_KIND = 'external'
FIELDS = (NativeField('leaf', 'Leaf', 0xCCC8, 4, 9999999),)
CHARACTER_EXP = (('Aoto', 0xCCE8), ('Tatsumi', 0xCDB8), ('Character record 3', 0xCE20),
                 ('Saki', 0xCE88), ('Finnel', 0xCEF0), ('Tilia', 0xCF58))
FORMAT = NativeFormat(GAME_ID, 'Ar tonelico Qoga (US PS3)', SAVE_SIZE, FIELDS,
    'Copied PFD-decrypted BLUS30639 USR-DATA and exact original PARAM.SFO. Manual Leaf editing. '
    'The normal ceiling is an observed/source editing value, not a proven gameplay cap. Max disabled. '
    'Dive points, growth, equipment, talk topics, endings and system gallery remain unchanged.')


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:8] != HEADER:
        raise SaveError('Requires the qualified 1,048,576-byte original US Ar tonelico Qoga USR-DATA profile.')


def inspection(payload):
    rows = [{'group': 'Resources', 'label': 'Leaf', 'value': str(FIELDS[0].value(payload))}]
    for name, offset in CHARACTER_EXP:
        rows.append({'group': 'Stored progression (read only)', 'label': name,
                     'value': f'Stored EXP {int.from_bytes(payload[offset:offset + 4], "big"):,}; availability unchanged'})
    for index, name in enumerate(('Saki', 'Finnel', 'Tilia')):
        offset = 0xA12D5 + index * 4
        rows.append({'group': 'Dive points (read only)', 'label': name,
                     'value': str(int.from_bytes(payload[offset:offset + 4], 'big'))})
    return tuple(rows)


_backend = PlainPS3Backend(FORMAT, qualify,
    lambda directory: re.fullmatch(r'BLUS30639-LIST-[0-9]{2}', directory) is not None, '', inspection)
get_format, decode, read_save = _backend.get_format, _backend.decode, _backend.read_save
validate_document, fields_for, field_map = _backend.validate_document, _backend.fields_for, _backend.field_map
stage, changed_payload, serialize = _backend.stage, _backend.changed_payload, _backend.serialize
review, maximums, limit_values = _backend.review, _backend.maximums, _backend.limit_values
context_raw, inspection_rows = _backend.context_raw, _backend.inspection_rows
backup, save_as, restore = _backend.storage.backup, _backend.storage.save_as, _backend.storage.restore
prepare_copy_context = _backend.storage.prepare_copy_context
prepare_self_test_copy = _backend.storage.prepare_self_test_copy


def field_hint(document, key):
    if key not in field_map(document):
        raise SaveError('Choose Leaf.')
    return 'Spendable Leaf only. The normal ceiling is an observed/source editing value, not a game cap. Dive points, EXP, equipment, talk topics, endings and gallery stay unchanged; Max is disabled.'
