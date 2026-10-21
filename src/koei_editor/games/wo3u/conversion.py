"""Two separately mapped WO3U balances; never transplant serialized objects."""
from koei_editor.games.wo3u import wo3u_parser as pc
from koei_editor.games.wo3u_ps3 import parser as ps3
from koei_editor.shared.resource_conversion import ResourceTransfer

TRANSFER = ResourceTransfer(
    {pc.GAME_ID: pc, ps3.GAME_ID: ps3}, ('growth_points', 'gems'),
    'WO3 Ultimate PS3 ↔ Definitive Edition PC: unallocated growth points and gems only; '
    'all destination progression, rare crystals, officers, equipment and serialized markers retained',
    ('This replaces two balances (8 mapped bytes), not a complete save or best-value merge.',
     'US PS3 NPUB31505-SAVEDATA requires its original PARAM.SFO and a decrypted APP.BIN. '
     'PS4 and base WO3 are not endpoints of these routes.',
     'PS3 gems are limited to 999,999; higher PC source balances are rejected without clamping. '
     'Source progression, unlocks, DLC, rewards and inventory are not transferred.'),
)
