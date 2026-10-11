"""Explicit game registration. Parsers never probe or fall back to another game."""
from dataclasses import dataclass
from importlib import import_module
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter, validate_session


@dataclass(frozen=True)
class Game:
    id: str
    title: str
    subtitle: str
    description: str
    status: str
    extension: str
    accent: str
    editor_module: str
    parser_module: str
    editing_verified: bool = False
    emblem: str = ''
    published_format: bool = False
    platform: str = 'Windows PC'
    scalar_backend: str | None = None

    def get_scalar_adapter(self):
        if self not in ALL_ADAPTERS:
            raise SaveError('Unregistered game.')
        if self.scalar_backend is None:
            raise SaveError('This editor uses its own document workflow.')
        return BoundScalarAdapter(self.id, self.extension, import_module(self.scalar_backend))

    def create_editor(self, root, parent, theme='Light', on_theme=None):
        if self not in ALL_ADAPTERS:
            raise SaveError('Unregistered game.')
        Editor = import_module(self.editor_module).Editor
        if getattr(Editor, 'game_id', self.id) != self.id:
            raise SaveError('The registered editor belongs to a different game/platform.')
        if self.scalar_backend is not None and hasattr(Editor, 'backend'):
            if Editor.backend is not import_module(self.scalar_backend):
                raise SaveError('The registered editor and scalar backend do not match.')
            if getattr(Editor, 'save_extension', None) != self.extension:
                raise SaveError('The registered editor and save extension do not match.')
        return validate_session(Editor(root, parent=parent, theme=theme, on_theme=on_theme), self.id)

    def read_save(self, path):
        # Extension check happens before invoking a game's decryption code.
        from pathlib import Path
        if Path(path).suffix.lower() != self.extension:
            raise SaveError(f'{self.title} requires an explicit {self.extension} copy.')
        if self not in ALL_ADAPTERS:
            raise SaveError('Unregistered game.')
        if self.scalar_backend is not None:
            return self.get_scalar_adapter().read_save(path)
        read_save = import_module(self.parser_module).read_save
        return read_save(path)


GAMES = (
    Game('dw3', 'DYNASTY WARRIORS 3', 'Complete Edition Remastered',
         'Character progression, equipment, companions and unlocks.',
         '', '.sav', '#92353b', 'koei_editor.games.dw3.gui', 'koei_editor.games.dw3.save_parser', True, 'III'),
    Game('dw8xl', 'DYNASTY WARRIORS 8', 'Xtreme Legends Complete Edition · PC',
         'Resources, officer stats, weapon compatibility, affinity, attribute ranks and equipped weapon order.',
         '', '.dat', '#475f8d', 'koei_editor.games.dw8xl.dw8xl_editor', 'koei_editor.games.dw8xl.dw8xl_editor', True, 'VIII', scalar_backend='koei_editor.shared.verified_editor'),
    Game('dw7xl', 'DYNASTY WARRIORS 7', 'Xtreme Legends Definitive Edition · PC',
         'Gold, officer stats, skill points, active weapons and existing unlearned seal-meter reductions.',
         '', '.dat', '#526985', 'koei_editor.games.dw7xl.dw7xl_editor', 'koei_editor.games.dw7xl.dw7xl_parser', True, 'VII',
         scalar_backend='koei_editor.games.dw7xl.dw7xl_parser'),
    Game('pw3', 'ONE PIECE: PIRATE WARRIORS 3', 'Windows PC edition',
         'Individual or bulk character stats, special bars and skill slots.',
         '', '.dat', '#257a78', 'koei_editor.games.pw3.pw3_editor', 'koei_editor.games.pw3.pw3_editor', True, 'PW3', scalar_backend='koei_editor.shared.verified_editor'),
    Game('pw4', 'ONE PIECE: PIRATE WARRIORS 4', 'Windows PC · WW/JP/EA revision 15',
         'Beli, existing obtained coin quantities and searchable resource history.',
         '', '.dat', '#297b73', 'koei_editor.games.pw4.pw4_editor', 'koei_editor.games.pw4.pw4_parser', True, 'PW4',
         scalar_backend='koei_editor.games.pw4.pw4_parser'),
    Game('dw4hyper', 'DYNASTY WARRIORS 4 HYPER', 'Native Windows PC edition',
         'Character stats, weapon levels, items, owned harness/orb and occupied general-item equipment, bodyguards and customization.',
         '', '.dat', '#785d8a',
         'koei_editor.games.dw4hyper.dw4hyper_editor', 'koei_editor.games.dw4hyper.dw4hyper_parser', True, 'IV', True, scalar_backend='koei_editor.games.dw4hyper.dw4hyper_parser'),
    Game('atelier_sophie2', 'ATELIER SOPHIE 2', 'The Alchemist of the Mysterious Dream · PC',
         'Item quality, battle-item refills, inventory inspection and alchemy EXP.',
         '', '.dat', '#827050', 'koei_editor.games.sophie2.atelier_sophie2_editor', 'koei_editor.games.sophie2.atelier_sophie2_parser',
         False, 'SOPHIE 2', True, scalar_backend='koei_editor.games.sophie2.atelier_sophie2_parser'),
    Game('atelier_sophie', 'ATELIER SOPHIE', 'Original Steam PC · GAMEDATA slots',
         'Cole, Tess tickets and existing basket/container quality; searchable inventory and alchemy progression.',
         '', '', '#827050', 'koei_editor.games.sophie.editor', 'koei_editor.games.sophie.parser',
         True, 'SOPHIE', True, scalar_backend='koei_editor.games.sophie.parser'),
    Game('atelier_ryza2', 'ATELIER RYZA 2', 'Lost Legends & the Secret Fairy · original Steam PC',
         'Ordinary item/equipment quality from 1–100 and qualified unspent skill-tree SP reductions; inventory inspection.',
         '', '.dat', '#827050', 'koei_editor.games.ryza.editor2', 'koei_editor.games.ryza.parser',
         True, 'RYZA 2', True, scalar_backend='koei_editor.games.ryza.parser'),
    Game('meruru_plus_vita', 'ATELIER MERURU PLUS', 'The Apprentice of Arland · US decrypted PCSE00296',
         'Cole; 13 named characters’ base stats (attack/defense/speed), base HP/MP/LP increases and current-gauge reductions; searchable records.',
         '', '', '#827050', 'koei_editor.games.meruru_plus_vita.editor', 'koei_editor.games.meruru_plus_vita.parser',
         True, 'MERURU PLUS', True, 'PlayStation Vita', scalar_backend='koei_editor.games.meruru_plus_vita.parser'),
    Game('fatal_frame2_remake', 'FATAL FRAME II', 'Crimson Butterfly REMAKE · Steam PC',
         'Shared system Photo Point reductions; per-slot inventory, camera and collection inspection.',
         '', '.bin', '#72505e', 'koei_editor.games.fatal_frame2_remake.editor', 'koei_editor.games.fatal_frame2_remake.parser',
         True, 'FF II', True, scalar_backend='koei_editor.games.fatal_frame2_remake.parser'),
    Game('dw4xl_ps2', 'DYNASTY WARRIORS 4', 'Xtreme Legends · SLUS-20812',
         'Character stats, weapon levels, items, owned harness/orb and occupied general-item equipment, and bodyguard growth.',
         '', '.psu', '#785d8a',
         'koei_editor.games.dw4xl.dw4xl_editor', 'koei_editor.games.dw4xl.dw4xl_parser', True, 'IV XL', True, 'PlayStation 2', scalar_backend='koei_editor.games.dw4xl.dw4xl_parser'),
    Game('origins', 'DYNASTY WARRIORS: ORIGINS', 'Steam PC · slot saves',
         'Gold, Skill Points, bonds, provincial peace, weapon upgrades and battle history.',
         '', '.dat', '#806126', 'koei_editor.games.origins.origins_game_editor', 'koei_editor.games.origins.origins_parser', True,
         'ORIGINS', scalar_backend='koei_editor.games.origins.origins_parser'),
    Game('wo3u', 'WARRIORS OROCHI 3 ULTIMATE', 'Definitive Edition · PC',
         'Officer stats, growth points, upgrade stones, gems, crafting, weapon attributes and owned ordinary-item equipment.',
         '', '.bin', '#775c82', 'koei_editor.games.wo3u.wo3u_editor', 'koei_editor.games.wo3u.wo3u_parser', True, 'WO3',
         scalar_backend='koei_editor.games.wo3u.wo3u_parser'),
    Game('wo1', 'WARRIORS OROCHI', 'Original Windows PC · save revision 2',
         'Growth Points, weapon bonuses, attribute capacity, effect ranks and existing own-pool weapon selection.',
         '', '.dat', '#775c82', 'koei_editor.games.wo1_pc.wo1_editor', 'koei_editor.games.wo1_pc.wo1_parser',
         True, 'OROCHI', True, scalar_backend='koei_editor.games.wo1_pc.wo1_parser'),
    Game('samurai4dx', 'SAMURAI WARRIORS 4 DX', 'Windows PC edition',
         'Gold, gems, officers, existing weapons and attached skills.',
         '', '.dat', '#91613d', 'koei_editor.games.sw4dx.samurai4dx_editor', 'koei_editor.games.sw4dx.samurai4dx_parser', True, 'SW4',
         scalar_backend='koei_editor.games.sw4dx.samurai4dx_parser'),
    Game('sw4ii', 'SAMURAI WARRIORS 4-II', 'Windows PC edition',
         'Gold, tomes, officer stats, existing weapons, mount stats and occupied-mount selection.',
         '', '.dat', '#91613d', 'koei_editor.games.sw4ii.sw4ii_editor', 'koei_editor.games.sw4ii.sw4ii_parser', True, 'SW4-II',
         scalar_backend='koei_editor.games.sw4ii.sw4ii_parser'),
    Game('sw2', 'SAMURAI WARRIORS 2', 'Original Windows PC · save revision 2',
         'Money, stored officer growth, acquired skills, weapon bonuses and existing own-pool weapon selection.',
         '', '.dat', '#91613d', 'koei_editor.games.sw2.sw2_editor', 'koei_editor.games.sw2.sw2_parser',
         True, 'SW2', True, scalar_backend='koei_editor.games.sw2.sw2_parser'),
    Game('dw6', 'DYNASTY WARRIORS 6', 'Native Windows PC edition',
         'Named officer unlocks, horse combat stats, existing weapon elements and damage bonuses; searchable records.',
         '', '.dat', '#526985', 'koei_editor.games.dw6.dw6_editor', 'koei_editor.games.dw6.dw6_parser',
         True, 'VI', True, scalar_backend='koei_editor.games.dw6.dw6_parser'),
    Game('dw9emp', 'DYNASTY WARRIORS 9 EMPIRES', 'Windows PC · SYSTEMDATA',
         'Existing item quantities; searchable inventory and custom officer records.',
         '', '.bin', '#806126', 'koei_editor.games.dw9emp.dw9emp_editor', 'koei_editor.games.dw9emp.dw9emp_parser',
         False, 'IX E', True, scalar_backend='koei_editor.games.dw9emp.dw9emp_parser'),
    Game('orochiz', 'WARRIORS OROCHI Z', 'Native Windows PC edition',
         'Stock EXP, officer base attack, existing weapon bonuses/attributes and own-pool equipment selection.',
         '', '.dat', '#775c82', 'koei_editor.games.orochiz.orochiz_editor', 'koei_editor.games.orochiz.orochiz_parser',
         True, 'OROCHI Z', True, scalar_backend='koei_editor.games.orochiz.orochiz_parser'),
    Game('stars', 'WARRIORS ALL-STARS', 'Windows PC · revision F4',
         'Gold, existing materials, owned Hero Card selection and searchable card records; separate lifetime earnings.',
         '', '.bin', '#827050', 'koei_editor.games.stars.stars_editor', 'koei_editor.games.stars.stars_parser',
         True, 'ALL-STARS', True, scalar_backend='koei_editor.games.stars.stars_parser'),
    Game('hyrule_warriors', 'HYRULE WARRIORS', 'Wii U · APP.BIN',
         'Rupees, existing materials and map cards, weapon stars and ordinary seal KO counters.',
         '', '.bin', '#548247', 'koei_editor.games.hyrule_warriors.editor', 'koei_editor.games.hyrule_warriors.parser',
         True, 'HYRULE', True, 'Wii U', scalar_backend='koei_editor.games.hyrule_warriors.parser'),
    Game('hyrule_definitive', 'HYRULE WARRIORS', 'Definitive Edition · zmha.bin',
         'Rupees, existing materials, weapon stars, ordinary seal KO counters and searchable records.',
         '', '.bin', '#548247', 'koei_editor.games.hyrule_definitive.editor', 'koei_editor.games.hyrule_definitive.parser',
         True, 'HYRULE DE', True, 'Nintendo Switch', scalar_backend='koei_editor.games.hyrule_definitive.parser'),
    Game('age_of_calamity', 'HYRULE WARRIORS: AGE OF CALAMITY', 'Switch · svdt',
         'Rupees, discovered materials, trophies and reports; existing weapon protection and inspection.',
         '', '', '#657b43', 'koei_editor.games.age_of_calamity.editor', 'koei_editor.games.age_of_calamity.parser',
         True, 'CALAMITY', True, 'Nintendo Switch', scalar_backend='koei_editor.games.age_of_calamity.parser'),
    Game('fire_emblem_warriors', 'FIRE EMBLEM WARRIORS', 'Switch · scenario0/1/2 exports',
         'Gold, existing ordinary materials, generic weapon stars and ordinary seal KO counters; named inspection.',
         '', '', '#657b43', 'koei_editor.games.fire_emblem_warriors.editor', 'koei_editor.games.fire_emblem_warriors.parser',
         True, 'FIRE EMBLEM', True, 'Nintendo Switch', scalar_backend='koei_editor.games.fire_emblem_warriors.parser'),
    Game('dw7_ps3', 'DYNASTY WARRIORS 7', 'US/EU · decrypted APP.BIN',
         'Gold and 62 officers’ health, attack, defense, power, speed and skill points.',
         '', '.bin', '#526985', 'koei_editor.games.dw7_ps3.editor', 'koei_editor.games.dw7_ps3.parser',
         True, 'VII PS3', True, 'PlayStation 3', scalar_backend='koei_editor.games.dw7_ps3.parser'),
    Game('dw7e_ps3', 'DYNASTY WARRIORS 7 EMPIRES', 'US · decrypted SYSTEM DATA.BIN',
         'Manual system bonus-point editing; campaign saves use a separate format.',
         '', '.bin', '#526985', 'koei_editor.games.dw7e_ps3.editor', 'koei_editor.games.dw7e_ps3.parser',
         True, 'VII E PS3', True, 'PlayStation 3', scalar_backend='koei_editor.games.dw7e_ps3.parser'),
    Game('sw4_ps3', 'SAMURAI WARRIORS 4', 'US · decrypted DATA.BIN',
         'Gold, eight gems and searchable weapon proficiency/EXP inspection.',
         '', '.bin', '#91613d', 'koei_editor.games.sw4_ps3.editor', 'koei_editor.games.sw4_ps3.parser',
         True, 'SW4 PS3', True, 'PlayStation 3', scalar_backend='koei_editor.games.sw4_ps3.parser'),

    Game('dw8e', 'DYNASTY WARRIORS 8 EMPIRES', 'Windows PC · SystemSave.dat',
         'Existing custom-horse appearance choices; searchable horse stats and ability records.',
         '', '.dat', '#526985', 'koei_editor.games.dw8e.dw8e_editor', 'koei_editor.games.dw8e.dw8e_parser',
         True, 'VIII E', True, scalar_backend='koei_editor.games.dw8e.dw8e_parser'),
    Game('wolong', 'WO LONG: FALLEN DYNASTY', 'Windows PC · USERDATA',
         'Genuine Qi, copper, accolades, ordinary stack reductions, existing battle-set names and equipment inspection.',
         '', '.bin', '#806126', 'koei_editor.games.wolong.wolong_editor', 'koei_editor.games.wolong.wolong_parser',
         True, 'WO LONG', True, scalar_backend='koei_editor.games.wolong.wolong_parser'),
    Game('p5strikers_pc', 'PERSONA 5 STRIKERS', 'Windows PC · SAVEDATA.BIN',
         'Money, Persona/BOND points and existing consumables, cooking supplies, incenses, remedies and selected skill cards.',
         '', '.bin', '#92353b', 'koei_editor.games.p5strikers_pc.editor', 'koei_editor.games.p5strikers_pc.parser',
         True, 'P5S', True, scalar_backend='koei_editor.games.p5strikers_pc.parser'),
    Game('hyrule_legends', 'HYRULE WARRIORS LEGENDS', 'Nintendo 3DS · zmha.bin',
         'Rupees, materials, map cards, weapon stars, ordinary seals, My Fairy names and existing fairy trust reductions.',
         '', '.bin', '#548247', 'koei_editor.games.hyrule_legends.editor', 'koei_editor.games.hyrule_legends.parser',
         True, 'LEGENDS', True, 'Nintendo 3DS', scalar_backend='koei_editor.games.hyrule_legends.parser'),

    Game('ayesha_ps3', 'ATELIER AYESHA', 'The Alchemist of Dusk · PS3 US/Japanese export',
         'Cole, existing stack reductions and searchable inventory quality, properties and effects.',
         '', '.bin', '#827050', 'koei_editor.games.ayesha_ps3.editor', 'koei_editor.games.ayesha_ps3.parser',
         True, 'AYESHA', True, 'PlayStation 3', scalar_backend='koei_editor.games.ayesha_ps3.parser'),

    Game('dw5special', 'DYNASTY WARRIORS 5 SPECIAL', 'Shin Sangokumusou 4 Special · Windows PC',
         'Existing item ranks, stored officer attack/defense, weapon attack/weight and attributes; named records.',
         '', '.dat', '#526985', 'koei_editor.games.dw5special.dw5special_editor', 'koei_editor.games.dw5special.dw5special_parser',
         True, 'V SPECIAL', True, scalar_backend='koei_editor.games.dw5special.dw5special_parser'),

    Game('three_hopes', 'FIRE EMBLEM WARRIORS: THREE HOPES', 'Switch · extracted SlotData exports',
         'Gold reductions, owned Shez/Byleth name customization and searchable character/weapon records.',
         '', '', '#657b43', 'koei_editor.games.three_hopes.editor', 'koei_editor.games.three_hopes.parser',
         True, 'THREE HOPES', True, 'Nintendo Switch', scalar_backend='koei_editor.games.three_hopes.parser'),
    Game('dw8e_ps3', 'DYNASTY WARRIORS 8 EMPIRES', 'US · decrypted SYSTEM APP.BIN',
         'Existing custom-horse appearance choices; searchable horse stats and ability records.',
         '', '.bin', '#526985', 'koei_editor.games.dw8e_ps3.editor', 'koei_editor.games.dw8e_ps3.parser',
         True, 'VIII E PS3', True, 'PlayStation 3', scalar_backend='koei_editor.games.dw8e_ps3.parser'),

    Game('wo3u_ps3', 'WARRIORS OROCHI 3 ULTIMATE', 'US · decrypted APP.BIN · NPUB31505',
         'Manual unallocated growth points and gems; searchable officer, weapon and inventory inspection.',
         '', '.bin', '#775c82', 'koei_editor.games.wo3u_ps3.editor', 'koei_editor.games.wo3u_ps3.parser',
         True, 'WO3U PS3', True, 'PlayStation 3', scalar_backend='koei_editor.games.wo3u_ps3.parser'),
    Game('nioh3', 'NIOH 3', 'Windows PC · USER revisions 0x01030001 / 0x01040000',
         'Amrita and Gold deductions, eighteen named ordinary consumable reductions; separate equipment inspection.',
         '', '.bin', '#806126', 'koei_editor.games.nioh3.editor', 'koei_editor.games.nioh3.parser',
         True, 'NIOH 3', True, scalar_backend='koei_editor.games.nioh3.parser'),
    Game('ninjagaiden2_x360', 'NINJA GAIDEN II', 'Original Xbox 360 / Xenia · extracted revision-6 story',
         'Yellow Essence, existing consumable and ammunition reductions; searchable inventory and separate Karma inspection.',
         '', '.dat', '#92353b', 'koei_editor.games.ninja_gaiden_ii.editor', 'koei_editor.games.ninja_gaiden_ii.parser',
         True, 'NG II', True, 'Xbox 360 / Xenia', scalar_backend='koei_editor.games.ninja_gaiden_ii.parser'),

    Game('gundam1_ps3', 'DYNASTY WARRIORS: GUNDAM', 'US/EU · decrypted DATA.BIN + PARAM.SFO',
         'Learn skill flags and choose already learned equipped skills on six qualified level-30 pilots; progression inspection.',
         '', '.bin', '#475f8d', 'koei_editor.games.gundam1_ps3.editor', 'koei_editor.games.gundam1_ps3.parser',
         True, 'GUNDAM', True, 'PlayStation 3', scalar_backend='koei_editor.games.gundam1_ps3.parser'),

    Game('kens_rage1_ps3', "FIST OF THE NORTH STAR: KEN'S RAGE", 'US/EU · decrypted DATA.BIN + PARAM.SFO',
         'Manual existing skill-point balances for eight base fighters; inspect progression resources.',
         '', '.bin', '#91613d', 'koei_editor.games.kens_rage1_ps3.editor', 'koei_editor.games.kens_rage1_ps3.parser',
         False, 'KR1', True, 'PlayStation 3', scalar_backend='koei_editor.games.kens_rage1_ps3.parser'),

    Game('kens_rage2_ps3', "FIST OF THE NORTH STAR: KEN'S RAGE 2", 'EU · decrypted DATA.BIN + PARAM.SFO',
         'Unlock locked music, movie and event gallery entries; preserve existing collection states.',
         '', '.bin', '#91613d', 'koei_editor.games.kens_rage2_ps3.editor', 'koei_editor.games.kens_rage2_ps3.parser',
         False, 'KR2', True, 'PlayStation 3', scalar_backend='koei_editor.games.kens_rage2_ps3.parser'),

    Game('rotk13_pc', 'ROMANCE OF THE THREE KINGDOMS XIII', 'Original PC · revision 14 · TC',
         'City gold, supplies, population, wounded troops, fealty, commerce, farming, culture and troop proficiencies.',
         '', '.s13', '#806126', 'koei_editor.games.rotk13.editor', 'koei_editor.games.rotk13.parser',
         True, 'XIII', True, scalar_backend='koei_editor.games.rotk13.parser'),
    Game('three_houses', 'FIRE EMBLEM: THREE HOUSES', 'Switch · gameplay save-format v13/v23',
         'Instruction motivation, existing learned ability loadouts, gold and ordinary convoy quantity/durability reductions.',
         '', '', '#657b43', 'koei_editor.games.three_houses.editor', 'koei_editor.games.three_houses.parser',
         True, 'THREE HOUSES', True, 'Nintendo Switch', scalar_backend='koei_editor.games.three_houses.parser'),

    Game('berserk_vita', 'BERSERK AND THE BAND OF THE HAWK', 'EU PS Vita · decrypted PCSB01085',
         'Gold deductions, eighteen named existing enhancement materials and searchable character status.',
         '', '.dat', '#805043', 'koei_editor.games.berserk_vita.editor', 'koei_editor.games.berserk_vita.parser',
         True, 'B&H', True, platform='PlayStation Vita', scalar_backend='koei_editor.games.berserk_vita.parser'),
    Game('doa5_ps3', 'DEAD OR ALIVE 5', 'Original US/EU PS3 PSN · SAVE_SYS.DAT + PARAM.SFO',
         'Sixty-three individual costume unlock controls and searchable costume records.',
         '', '.dat', '#796070', 'koei_editor.games.doa5_ps3.editor', 'koei_editor.games.doa5_ps3.parser',
         False, 'DOA5', True, platform='PlayStation 3', scalar_backend='koei_editor.games.doa5_ps3.parser'),
    Game('pokemon_conquest_ds', 'POKÉMON CONQUEST', 'US Nintendo DS · raw native save',
         'Existing gallery Pokémon IV components and Speed IV; searchable gallery Pokémon records.',
         '', '.sav', '#99752b', 'koei_editor.games.pokemon_conquest_ds.editor', 'koei_editor.games.pokemon_conquest_ds.parser',
         True, 'PCQ', True, platform='Nintendo DS', scalar_backend='koei_editor.games.pokemon_conquest_ds.parser'),
    Game('atelier_ryza_switch', 'ATELIER RYZA', 'Ever Darkness & the Secret Hideout · original Switch main game',
         'Existing ordinary item/equipment quality 1–100; searchable inventory, equipment and read-only trait slots.',
         '', '.dat', '#827050', 'koei_editor.games.ryza.editor1switch', 'koei_editor.games.ryza.parser',
         True, 'RYZA', True, 'Nintendo Switch', scalar_backend='koei_editor.games.ryza.parser'),
    Game('dw8xl_ps3', 'DYNASTY WARRIORS 8', 'Xtreme Legends · US PS3 PSN NPUB31449 · APP.BIN + PARAM.SFO',
         'Gold, gems, facility/weapon materials, 82 officers’ stored stats, weapon-action aptitudes and existing weapon attribute ranks.',
         '', '.bin', '#a54b48', 'koei_editor.games.dw8xl_ps3.editor', 'koei_editor.games.dw8xl_ps3.parser',
         True, 'DW8 XL', True, 'PlayStation 3', scalar_backend='koei_editor.games.dw8xl_ps3.parser'),
    Game('dqb2_pc', 'DRAGON QUEST BUILDERS 2', 'Original Steam PC · CMNDAT.BIN',
         'Existing named medicine/seed stack reductions; searchable pockets, bag and player/equipment status.',
         '', '.bin', '#657b43', 'koei_editor.games.dqb2_pc.editor', 'koei_editor.games.dqb2_pc.parser',
         True, 'DQB2', True, scalar_backend='koei_editor.games.dqb2_pc.parser'),
    Game('atelier_ryza2_switch', 'ATELIER RYZA 2', 'Lost Legends & the Secret Fairy · original Switch',
         'Unspent skill-tree SP reductions; searchable existing inventory and equipment records.',
         '', '.dat', '#827050', 'koei_editor.games.ryza.editor2switch', 'koei_editor.games.ryza.parser',
         True, 'RYZA 2', True, 'Nintendo Switch', scalar_backend='koei_editor.games.ryza.parser'),
    Game('dqb2_switch', 'DRAGON QUEST BUILDERS 2', 'Original Nintendo Switch · CMNDAT.BIN',
         'Existing named medicine/seed stack reductions; searchable pockets, bag and player/equipment status.',
         '', '.bin', '#657b43', 'koei_editor.games.dqb2_switch.editor', 'koei_editor.games.dqb2_switch.parser',
         True, 'DQB2', True, 'Nintendo Switch', scalar_backend='koei_editor.games.dqb2_switch.parser'),
    Game('p5strikers_switch', 'PERSONA 5 STRIKERS', 'English Nintendo Switch · savedata export',
         'Money, Persona points, unspent BOND points and existing named consumable, ingredient, incense, remedy and skill-card stacks.',
         '', '', '#92353b', 'koei_editor.games.p5strikers_switch.editor', 'koei_editor.games.p5strikers_switch.parser',
         True, 'P5S', True, 'Nintendo Switch', scalar_backend='koei_editor.games.p5strikers_switch.parser'),
    Game('rotk2_dos', 'ROMANCE OF THE THREE KINGDOMS II', 'Original Chinese DOS · raw save copies',
         'Owned-province gold and rice reductions; searchable province ownership, population and resource records.',
         '', '', '#806126', 'koei_editor.games.rotk2_dos.editor', 'koei_editor.games.rotk2_dos.parser',
         False, 'II', True, 'DOS PC', scalar_backend='koei_editor.games.rotk2_dos.parser'),
    Game('p5strikers_ps4', 'PERSONA 5 STRIKERS', 'English PS4 · decrypted APP.BIN + original sce_sys/param.sfo',
         'Money, Persona/BOND points and existing named consumables, ingredients, incenses, remedies and skill-card stacks.',
         '', '.bin', '#92353b', 'koei_editor.games.p5strikers_ps4.editor', 'koei_editor.games.p5strikers_ps4.parser',
         True, 'P5S', True, 'PlayStation 4', scalar_backend='koei_editor.games.p5strikers_ps4.parser'),
    Game('uncharted_waters2_dos', 'UNCHARTED WATERS: NEW HORIZONS', 'Original English DOS · KOUKAI2.DAT',
         'Existing-slot gold and eight protagonist attributes; searchable campaign and sailor records.',
         '', '.dat', '#257a78', 'koei_editor.games.uncharted_waters2_dos.editor', 'koei_editor.games.uncharted_waters2_dos.parser',
         False, 'NEW HORIZONS', True, 'DOS PC', scalar_backend='koei_editor.games.uncharted_waters2_dos.parser'),
    Game('project_zero_ps2', 'PROJECT ZERO / FATAL FRAME', 'Original European PS2 · SLES-50821 PSU export',
         'Existing camera-point and base-upgrade tier reductions; searchable slots, camera functions and inventory.',
         '', '.psu', '#72505e', 'koei_editor.games.project_zero_ps2.editor', 'koei_editor.games.project_zero_ps2.parser',
         True, 'PROJECT ZERO', True, 'PlayStation 2', scalar_backend='koei_editor.games.project_zero_ps2.parser'),
    Game('atelier_ryza3_dx_pc', 'ATELIER RYZA 3 DX', 'Alchemist of the End & the Secret Key · Steam PC revision 4',
         'Unspent skill-tree SP and gem reductions for rebuilding/duplication; searchable inventory, secret-key and Party records.',
         '', '.dat', '#827050', 'koei_editor.games.ryza3_dx_pc.editor', 'koei_editor.games.ryza3_dx_pc.parser',
         True, 'RYZA 3 DX', True, scalar_backend='koei_editor.games.ryza3_dx_pc.parser'),
    Game('monster_rancher_ds', 'MONSTER RANCHER DS', 'US Nintendo DS · raw 32/64 KiB export',
         'Existing matched monster stats and lifespan, breeder/ranch/monster names and gold reductions; searchable records.',
         '', '.sav', '#548247', 'koei_editor.games.monster_rancher_ds.editor', 'koei_editor.games.monster_rancher_ds.parser',
         True, 'MR DS', True, 'Nintendo DS', scalar_backend='koei_editor.games.monster_rancher_ds.parser'),
    Game('tecmo_super_bowl_nes', 'TECMO SUPER BOWL', 'NES · compatible original 28-team battery SRAM',
         'Team control, healthy player conditions and per-slot playbooks; searchable standings, conditions and injury records.',
         '', '.sav', '#475f8d', 'koei_editor.games.tecmo_super_bowl_nes.editor', 'koei_editor.games.tecmo_super_bowl_nes.parser',
         True, 'TSB', True, 'NES', scalar_backend='koei_editor.games.tecmo_super_bowl_nes.parser'),
)

# Opaque research tools stay outside the gameplay library.
RESEARCH_TOOLS = ()
ALL_ADAPTERS = GAMES + RESEARCH_TOOLS

if any(not (game.editing_verified or game.published_format) for game in GAMES):
    raise RuntimeError('The editor library requires native file validation or an implemented published format.')


def get_game(game_id):
    try:
        return next(game for game in ALL_ADAPTERS if game.id == game_id)
    except StopIteration as error:
        raise SaveError('Choose an explicitly registered editor or research tool.') from error
