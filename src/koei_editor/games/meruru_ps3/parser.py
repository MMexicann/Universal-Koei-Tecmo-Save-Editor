"""Explicit original PS3 profile; PFD authentication is external."""

from koei_editor.games.arland_ps3.backend import Backend

GAME_ID = "meruru_ps3"
SAVE_SIZE = 558080
INTEGRITY_KIND = "external"
BACKEND = Backend(
    GAME_ID,
    "Atelier Meruru: The Apprentice of Arland (original PS3 US)",
    SAVE_SIZE,
    (
        46120,
        5880,
        4,
        5628,
        179724,
        121,
        100768,
        4,
        6968,
        1,
        8,
        68,
        592,
        1588,
        8,
        3584,
        95968,
        1469,
        84,
        384,
        77612,
        4800,
        104,
        80,
    ),
    ("BLUS30941",),
    52056,
    (
        "Meruru",
        "Keina",
        "Lias",
        "Totori",
        "Rorona",
        "Gio",
        "Esty",
        "Sterk",
        "Gino",
        "Mimi",
        "Rufus",
        "Hanna",
        "Pamela",
    ),
    432,
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
