"""One-way directly mapped PS4 crystals/orbs/materials to native PC balances."""
from koei_editor.games.wo3u import wo3u_parser as pc
from koei_editor.games.wo3u import ps4_export as ps4
from koei_editor.shared.resource_conversion import ResourceTransfer

TRANSFER = ResourceTransfer(
    {pc.GAME_ID: pc, ps4.GAME_ID: ps4}, tuple(field.id for field in ps4.RESOURCES),
    'WO3 Ultimate US PS4 CUSA00588 → Definitive Edition PC: rare crystals, '
    '58 attribute-orb balances and 295 material balances only; destination gems, '
    'growth points, officers, weapons, progression and serialized platform contexts retained',
    ('This replaces 354 balances (355 mapped bytes), including lower source values. '
     'It does not migrate complete saves, story progress, equipment, DLC or reward state.',
     'Requires the exact PS4 serialized-marker profile and original CUSA00588 '
     'sce_sys/param.sfo beside a decrypted APP.BIN. The public reference lacks '
     'original metadata; generated-context tests are not independent owner-export evidence.',
     'Each assigned PC crystal balance must be within its supported 0–999 bound, '
     'and each orb/material balance within 0–99. Incompatible incoming values '
     'are rejected without clamping. Experimental numeric expansion cannot widen these limits.',
     'Unallocated growth points and gems are excluded because acquired PS4-specific '
     'facts do not independently locate those two words. All other PC bytes remain unchanged.',
     'No native PS4 aggregate checksum, console signing or converted in-game '
     'load/re-save validation is claimed. Reverse conversion to PS4 is unavailable.'),
    TRANSFER_SCOPE='wo3u-ps4-crystals-orbs-materials',
    ROUTE_LABEL='crystals, orbs and materials only',
    directions=frozenset({(ps4.GAME_ID, pc.GAME_ID)}),
)


STATS_TRANSFER = ResourceTransfer(
    {pc.GAME_ID: pc, ps4.GAME_ID: ps4}, tuple(field.id for field in ps4.SOURCE_FIELDS),
    'WO3 Ultimate US PS4 CUSA00588 → Definitive Edition PC: five stored base stats '
    'for 145 playable officers plus rare crystals, 58 orb balances and 295 material '
    'balances; destination levels, EXP, promotions, equipped references, story '
    'and complete saved-state context retained',
    ('This replaces 1,079 mapped values (1,805 bytes): 725 officer base stats and '
     '354 resource balances. It does not transfer character levels, EXP, promotions, '
     'ownership, equipped loadouts, weapons, story progress, DLC or reward state.',
     'Only 145 playable officers are included; the five internal officer records and '
     'all 145 saved-state officer snapshots remain byte-exact from the PC template.',
     'Assigned PC health, Musou, attack and defense must be within 0–999; assigned '
     'speed must be within 0–180. An exact unusual opened PC target remains a no-op. '
     'A new higher value is rejected without clamping, even under experimental policy.',
     *TRANSFER.NOTES[1:]),
    TRANSFER_SCOPE='wo3u-ps4-base-stats-and-materials',
    ROUTE_LABEL='145 officer base stats, crystals, orbs and materials',
    directions=frozenset({(ps4.GAME_ID, pc.GAME_ID)}),
)
