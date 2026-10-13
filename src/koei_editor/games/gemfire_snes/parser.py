"""Explicit SNES identity for the native Gemfire battery-record writer."""
from koei_editor.games.gemfire_sram.parser import (
    Backend, Document, Field, Format, INTEGRITY_KIND, MAX_FILE_SIZE, SIZE,
    qualified_blocks, BLOCK_SIZE, MARKER, PROVINCE_START, PROVINCE_STRIDE)

GAME_ID = 'gemfire_snes'
EXTENSION = '.srm'
_backend = Backend(GAME_ID, 'SNES', 0xC004, EXTENSION, 3, 0x24)
FORMAT = _backend.format
get_format = _backend.get_format
decode = _backend.decode
validate_document = _backend.validate_document
read_save = _backend.read_save
field_map = _backend.field_map
fields_for = _backend.fields_for
changed_payload = _backend.changed_payload
stage = _backend.stage
serialize = _backend.serialize
review = _backend.review
limit_values = _backend.limit_values
maximums = _backend.maximums
backup = _backend.backup
save_as = _backend.save_as
restore = _backend.restore
province_records = _backend.province_records
record_label = _backend.record_label
field_hint = _backend.field_hint
