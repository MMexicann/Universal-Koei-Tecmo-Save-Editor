"""Original Rorona PS3 US complete native profile, not Plus or DX."""

from koei_editor.games.arland_ps3.backend import Backend

GAME_ID = "rorona_ps3"
SAVE_SIZE = 593920
INTEGRITY_KIND = "external"
BACKEND = Backend(
    GAME_ID,
    "Atelier Rorona: The Alchemist of Arland (original PS3 US)",
    SAVE_SIZE,
    (
        23620,
        16,
        15,
        4,
        4,
        44,
        57164,
        74,
        4772,
        8,
        1274,
        4,
        20,
        1748,
        23808,
        4204,
        1,
        388116,
        107,
        5600,
        5128,
        4504,
    ),
    ("BLUS30465",),
    0x15453,
    ("Rorona", "Sterk", "Cordelia", "Iksel", "Gio", "Tantris", "Lionela"),
    248,
    header=bytes.fromhex("01328e29"),
    money_tag=12,
    character_tag=14,
    calendar_tag=None,
)
FORMAT = BACKEND.FORMAT
get_format = BACKEND.get_format
decode = BACKEND.decode
read_save = BACKEND.read_save
validate_document = BACKEND.validate_document
fields_for = BACKEND.fields_for
field_map = BACKEND.field_map
changed_payload = BACKEND.changed_payload
serialize = BACKEND.serialize
stage = BACKEND.stage
limit_values = BACKEND.limit_values
maximums = BACKEND.maximums
review = BACKEND.review
backup = BACKEND.backup
save_as = BACKEND.save_as
restore = BACKEND.restore
prepare_copy_context = BACKEND.prepare_copy_context
inspection_rows = BACKEND.inspection_rows
field_hint = BACKEND.field_hint
record_label = BACKEND.record_label
