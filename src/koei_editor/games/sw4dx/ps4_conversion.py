"""One-way original US SW4 PS4 gold transfer to a native SW4 DX PC template."""
from koei_editor.games.sw4dx import samurai4dx_parser as pc
from koei_editor.games.sw4dx import ps4_export as ps4
from koei_editor.shared.resource_conversion import ResourceTransfer


TRANSFER = ResourceTransfer(
    {pc.GAME_ID: pc, ps4.GAME_ID: ps4}, ('gold',),
    'Samurai Warriors 4 US PS4 CUSA00919 → Samurai Warriors 4 DX PC: gold only; '
    'destination officers, gems, weapons, Chronicle, story and edition-specific '
    'content retained',
    ('This replaces the gold balance (4 mapped bytes), including a lower source '
     'balance. It does not migrate a complete save or merge best values.',
     'Requires a copied decrypted original SW4 US CUSA00919 app.dat and its '
     'original sce_sys/param.sfo. Only the qualified little-endian revision '
     '0x2118 profile with its bounded zero region is accepted. SW4-II, other '
     'PS4 regions and PS4 DX are not source profiles.',
     'Gold is mapped from the independently matched shared original-SW4 '
     'layout; a controlled in-game PS4 gold change has not been supplied.',
     'All four stored PS4 checksum values for the restricted profile and native '
     'PC envelope/section checksums must pass. The opaque PS4 tail is not '
     'integrity-qualified. The PC template header, cipher seed and every '
     'payload byte outside gold and required integrity fields are retained.',
     'A changed PC gold balance must be within 0–999,999. Incompatible values '
     'are rejected without clamping, including in experimental editing mode. '
     'An exact unusual opened PC target remains a no-op.',
     'Cross-edition gem identities and complete progression migration remain '
     'unqualified. No PS4 signing, reverse conversion or converted in-game '
     'load/re-save validation is claimed.'),
    TRANSFER_SCOPE='sw4-ps4-gold-only',
    ROUTE_LABEL='gold only',
    directions=frozenset({(ps4.GAME_ID, pc.GAME_ID)}),
)
