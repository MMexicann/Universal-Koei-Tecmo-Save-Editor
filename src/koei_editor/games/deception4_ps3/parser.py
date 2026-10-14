"""NPUB31442 Warl word corroborated by a complete native chapter-one export."""
import re
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.plain_ps3 import NativeField, NativeFormat, PlainPS3Backend

GAME_ID = 'deception4_ps3'
SAVE_SIZE = 409600
HEADER = bytes.fromhex('0000000000000100')
INTEGRITY_KIND = 'external'
FIELDS = (NativeField('warl', 'Warl', 0x20, 4, 999999, byteorder='little'),)
FORMAT = NativeFormat(GAME_ID, 'Deception IV: Blood Ties (US PS3 PSN)', SAVE_SIZE, FIELDS,
    'Copied PFD-decrypted NPUB31442 DATA.BIN with original PARAM.SFO. Manual Warl editing; '
    'the normal limit is a published edit target, not a proven gameplay cap. Max disabled. '
    'Traps, requests, abilities, XP and endings are preserved. Reimport/resign externally.')


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:8] != HEADER:
        raise SaveError('Requires the qualified 409,600-byte original US PSN Deception IV DATA.BIN profile.')


def inspection(payload):
    rows = [{'group': 'Resources', 'label': 'Warl', 'value': str(FIELDS[0].value(payload))}]
    for index, name in enumerate(('Elaborate', 'Sadistic', 'Humiliating')):
        rows.append({'group': 'Progression (read only)', 'label': name,
                     'value': f'Stored experience {int.from_bytes(payload[0x24 + index * 4:0x28 + index * 4], "little"):,}'})
    return tuple(rows)


_backend = PlainPS3Backend(FORMAT, qualify,
    lambda directory: re.fullmatch(r'NPUB31442-GAMEDATA-[0-9]{2}', directory) is not None, '.bin', inspection)
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
        raise SaveError('Choose Warl.')
    return 'Spendable Warl only. The normal ceiling follows a published edit target; Max is disabled. Traps, requests, abilities, XP and endings stay unchanged.'
