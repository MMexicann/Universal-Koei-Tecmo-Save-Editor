"""Explicit original PS3 profile; PFD authentication is external."""

from koei_editor.games.arland_ps3.backend import Backend

GAME_ID = "totori_ps3"
SAVE_SIZE = 270336
INTEGRITY_KIND = "external"
BACKEND = Backend(
    GAME_ID,
    "Atelier Totori: The Adventurer of Arland (original PS3 US/EU)",
    SAVE_SIZE,
    (
        33264,
        4908,
        4,
        3972,
        130956,
        51,
        57164,
        4,
        5632,
        1,
        20,
        68,
        932,
        1314,
        8,
        4536,
        400,
        1812,
        14325,
        168,
        88,
        64,
    ),
    ("BLUS30735", "BLES01221"),
    38228,
    (
        "Totori",
        "Gino",
        "Mimi",
        "Melvia",
        "Marc",
        "Rorona",
        "Sterk",
        "Ceci",
        "Iksel",
        "Cordelia",
    ),
    396,
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
