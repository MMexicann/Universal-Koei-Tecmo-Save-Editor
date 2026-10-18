"""Three Houses workspace: shared safe editing and distinct mechanic inspectors."""
from koei_editor.games.three_houses import codec, parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor

PROFICIENCIES = ('Sword', 'Lance', 'Axe', 'Bow', 'Brawling', 'Reason', 'Faith',
                 'Authority', 'Heavy Armor', 'Riding', 'Flying')
STATS = ('Strength', 'Magic', 'Dexterity', 'Speed', 'Luck', 'Defense', 'Resistance',
         'Movement', 'Charm')


class Presentation(ScalarPresentation):
    extra_groups = ('Characters', 'Items', 'Proficiencies', 'Class mastery',
                    'Abilities and arts', 'Battalions', 'Supports')

    def inspection_tables(self, document):
        characters = self.backend.characters(document)
        items = self.backend.items(document)
        raw = document.payload
        profile = document.profile
        stats, skills, mastery, unlocks, battalions = [], [], [], [], []
        # Read-only inspection includes inactive records; qualified ownership is
        # shown separately and never inferred from names, stats or item IDs.
        for row in characters:
            base = row['offset']
            stats.append((row['slot'], row['id'], row['qualified_owner'],
                f"0x{row['flags']:08X}", row['level'], row['exp'], row['class'], row['hp'], raw[base + 0xC4])
                + tuple(raw[base + 0x4E + index] for index in range(len(STATS))))
            rank_mirror = 0x1C8 if profile.revision == 13 else 0x1DC
            for index, name in enumerate(PROFICIENCIES):
                skills.append((row['slot'], row['id'], name,
                    raw[base + 0x88 + index], raw[base + rank_mirror + index],
                    codec.uint(raw, base + 0x32 + index * 2, 2),
                    codec.uint(raw, base + 0xFC + index * 2, 2)))
            class_count = 90 if profile.revision == 13 else 100
            flag_base = 0x1D3 if profile.revision == 13 else 0x1E7
            for index in range(class_count):
                mastery.append((row['slot'], row['id'], index,
                    codec.uint(raw, base + 0x112 + index * 2, 2),
                    raw[base + flag_base + index],
                    codec.uint(raw, base + 0x48, 2) if index == row['class'] else '',
                    raw[base + 0x93] if index == row['class'] else ''))
            unlocks.append((row['slot'], row['id'], raw[base + 0x61:base + 0x7F].hex(),
                tuple(raw[base + 0x7F:base + 0x84]), raw[base + 0x57:base + 0x61].hex(),
                tuple(raw[base + 0x84:base + 0x87])))
            battalions.append(self._battalion(raw, base + 0x18,
                f"Character slot {row['slot']} / ID {row['id']}"))
        player = codec.HEADER_SIZE + profile.player_offset
        for index in range(200):
            battalions.append(self._battalion(raw, player + 0xA30 + index * 8,
                f'Battalion storage slot {index + 1}'))
        supports = tuple((index, codec.uint(raw, player + 0x1080 + index * 2, 2))
                         for index in range(profile.support_count))
        return super().inspection_tables(document) + (
            InspectionTable('Characters', ('Physical slot', 'Native ID', 'Qualified living joined owner',
                'Native flags', 'Stored level', 'Stored EXP', 'Class ID', 'Stored HP', 'Motivation') + STATS,
                tuple(stats), 'Stored stats and character EXP are distinct from class mastery and proficiency. '
                'Held-item writes require a unique living available/joined base-unit owner ID 0–34. '
                'Additional/DLC, unknown and inactive/default owners remain read only. '
                'Availability, joining and death flags are preserved.'),
            InspectionTable('Items', ('Owner', 'Physical slot', 'Item ID', 'Stored durability', 'Convoy quantity'),
                tuple((row['owner'], row['slot'], row['id'], row['durability'], row['quantity']) for row in items),
                'Durability 100 is the native unlimited sentinel. Held amount bytes are not quantities. '
                'Only reviewed ordinary weapon identities admit decreases. Unknown, quest, unique '
                'and DLC-dependent item records remain read only. Identity, inventory counts, '
                'equipment references and ownership remain separate.'),
            InspectionTable('Proficiencies', ('Character slot', 'Native ID', 'Proficiency', 'Rank',
                'Rank mirror', 'EXP', 'EXP mirror'), tuple(skills),
                'Weapon, magic, authority and movement proficiencies are separate rank/EXP records. '
                'Mirrors, derived rewards, learned magic and class prerequisites remain read only.'),
            InspectionTable('Class mastery', ('Character slot', 'Native ID', 'Class ID', 'Class EXP',
                'Mastery flag', 'Current class EXP', 'Current mastery flag'), tuple(mastery),
                'Class EXP, mastery flags, certification unlocks and current-class mirrors are distinct. '
                'Abilities and combat-art rewards require further dependency evidence.'),
            InspectionTable('Abilities and arts', ('Character slot', 'Native ID', 'Ability ownership bytes',
                'Equipped ability IDs', 'Combat-art ownership bytes', 'Equipped art IDs'), tuple(unlocks),
                'Owned, undeployed base-unit loadouts can select only originally equipped learned abilities '
                'or Empty. Duplicate equipped abilities are rejected. Ownership bitmaps, class and rewards are preserved; '
                'combat arts and unqualified loadouts remain read only.'),
            InspectionTable('Battalions', ('Record', 'Stored character ID', 'EXP', 'Stamina', 'Type ID', 'Skill ID'),
                tuple(battalions), 'Storage and equipped copies naturally differ; values remain read only. '
                'Authority rank, gambit, capacity and ownership prerequisites are not inferred.'),
            InspectionTable('Supports', ('Native pair record index', 'Stored support points'), supports,
                'Points are separate from conversations, rank unlocks, route gates and paired endings. '
                'Pair identities and progression dependencies are unqualified; all values remain read only.'),
        )

    @staticmethod
    def _battalion(raw, base, owner):
        return (owner, codec.item_id(raw, base), codec.uint(raw, base + 2, 2),
                codec.uint(raw, base + 4, 2), raw[base + 6], raw[base + 7])


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = ''
    presentation_type = Presentation
    subtitle = 'Nintendo Switch — extracted slot/auto, native revisions 13 / 23'
    summary = ('Known main-campaign exports: rename the existing protagonist; edit qualified instruction motivation and existing ability loadouts; '
               'decrease gold and reviewed ordinary weapon convoy quantities/durability; '
               'held durability requires a qualified living joined base-unit owner. '
               'Inspect distinct character, proficiency, mastery, ability, art, battalion and support records. '
               'Recruitment, progression, rewards and DLC entitlement remain separate.')
