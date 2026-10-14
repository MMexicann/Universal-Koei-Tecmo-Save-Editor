"""NPEB01945 Cole; exact original profile, separate from DX and US offsets."""
import re
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.plain_ps3 import NativeField, NativeFormat, PlainPS3Backend

GAME_ID = 'escha_logy_ps3'
SAVE_SIZE = 409600
HEADER = bytes.fromhex('01332a6800000000')
INTEGRITY_KIND = 'external'
FIELDS = (NativeField('cole', 'Cole', 0xBD63, 4, 999999),)
OFFICERS = ('Escha', 'Logy', 'Awin', 'Threia', 'Reyfer', 'Lucille', 'Linca', 'Wilbell', 'Micie', 'Katla')
FORMAT = NativeFormat(GAME_ID, 'Atelier Escha & Logy (EU PS3 PSN)', SAVE_SIZE, FIELDS,
    'Copied PFD-decrypted original NPEB01945 USR-DATA and original PARAM.SFO. Manual Cole editing. '
    'The normal ceiling is a published edit target, not a proven game cap. Max disabled. '
    'Rank, activity funds, assignments, calendar, EXP, items and DLC ownership stay unchanged.')


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:8] != HEADER:
        raise SaveError('Requires the qualified 409,600-byte original EU PSN Escha & Logy USR-DATA profile; DX differs.')


def inspection(payload):
    rows = [{'group': 'Resources', 'label': 'Cole', 'value': str(FIELDS[0].value(payload))}]
    for index, name in enumerate(OFFICERS):
        offset = 0xBD87 + index * 0x2C4
        rows.append({'group': 'Stored progression (read only)', 'label': name,
                     'value': f'Stored EXP {int.from_bytes(payload[offset:offset + 4], "big"):,}; availability unchanged'})
    offset = 0x32F40
    rows.append({'group': 'Alchemy (read only)', 'label': 'Alchemy experience',
                 'value': str(int.from_bytes(payload[offset:offset + 4], 'big'))})
    return tuple(rows)


_backend = PlainPS3Backend(FORMAT, qualify,
    lambda directory: re.fullmatch(r'NPEB01945-LIST-[0-9]{2}', directory) is not None, '', inspection)
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
        raise SaveError('Choose Cole.')
    return 'Current spending money only. Rank, activity funds, job points, assignments, calendar and growth stay unchanged. Normal limit is a source edit target; Max is disabled.'
