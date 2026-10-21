"""Separately mapped SW4 resources with explicit endian-aware native writers."""
from koei_editor.games.sw4dx import samurai4dx_parser as pc
from koei_editor.games.sw4_ps3 import parser as ps3
from koei_editor.shared.resource_conversion import ResourceTransfer

TRANSFER = ResourceTransfer(
    {pc.GAME_ID: pc, ps3.GAME_ID: ps3}, ('gold',),
    'SW4 US PS3 ↔ SW4 DX PC: gold only; '
    'all destination officers, weapons, Chronicle, story and edition-specific content retained',
    ('This replaces the gold balance (4 mapped bytes), not a complete save or best-value merge.',
     'US PS3 NPUB31564 requires its original PARAM.SFO and a decrypted DATA.BIN. '
     'PS4, SW4-II and Spirit of Sanada are not endpoints of these routes.',
     'Native source and destination checksums are required. The PC template header and cipher seed '
     'are preserved; only gold and required destination checksums change. Destination gem balances stay intact because cross-edition gem identities are unqualified.'),
)
