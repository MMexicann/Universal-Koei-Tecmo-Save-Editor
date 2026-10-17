"""Opened-save progression projections; no XP-to-level or ownership inference."""
from koei_editor.games.origins.origins_progression import BATTLE_HISTORY_IDS, BOND_NAMES, PROVINCE_NAMES
from koei_editor.games.origins.origins_proficiency import proficiency_records
from koei_editor.games.origins.origins_weapons import weapon_records
from koei_editor.shared.progression import DashboardMetric as Metric, DashboardCard as Card
from koei_editor.shared.progression import DashboardSection as Section, ProgressionDashboard


def dashboard(backend, document):
    """Use only the original qualified slot and independently mapped records."""
    backend.validate_document(document)
    fields = {field.id: field for field in backend.fields_for(document)}

    def metric(identity, label, *, total=None, note=''):
        value = fields[identity].value(document.payload)
        bounded = total is not None and 0 <= value <= total
        return Metric(identity, label, str(value), field_id=identity,
                      current=value if bounded else None, total=total if bounded else None,
                      note=note)

    resources = tuple(metric(identity, fields[identity].label)
                      for identity in ('gold', 'skill_points', 'dlc_skill_points') if identity in fields)
    character_cards = [Card('protagonist', 'Protagonist',
                           'Verified resources; protagonist level and combat stats are not mapped.',
                           (Metric('level', 'Character level', 'Not mapped',
                                   note='Resource balances and weapon proficiency do not establish protagonist level.'),
                            *resources))]
    for index in range(101):
        identity = f'bond_{index}_level'
        if identity not in fields:
            continue
        metrics = [metric(identity, 'Bond level', total=5,
                          note='Bond events and reward claims are separate.')]
        training = f'bond_{index}_training'
        if training in fields:
            metrics.append(metric(training, 'Training count',
                                  note='Three trainings satisfy the count condition; conversations and arts are separate.'))
        character_cards.append(Card(f'bond-{index}', BOND_NAMES.get(index, f'Bond ID {index}'),
                                    'Existing bond', tuple(metrics),
                                    search_text=f'bond {index} training'))

    weapons = []
    inventory = weapon_records(document.payload, document.revision)
    copies = {}
    for record in inventory:
        copies[record.weapon_id] = copies.get(record.weapon_id, 0) + 1
    for record in inventory:
        identity = f'weapon_{record.index:04d}_upgrade'
        upgrade = (metric(identity, 'Reinforcement', total=99,
                          note='Native reforging cap +99; separate from proficiency, collection and achievement flags.') if identity in fields else
                   Metric('reinforcement', 'Reinforcement', str(record.upgrade),
                          note='Inspection only; this upgrade is not qualified for editing.'))
        traits = tuple(Metric(f'trait-{index}', f'Trait slot {index + 1}',
                              f'ID {trait} · level {level}')
                       for index, (trait, level) in enumerate(zip(record.traits, record.trait_levels)))
        weapons.append(Card(f'weapon-{record.index}', f'Weapon ID {record.weapon_id}',
                            f'Inventory slot {record.index + 1} · reinforcement +{record.upgrade}',
                            (upgrade, Metric('copies', 'Inventory copies with this ID', str(copies[record.weapon_id]),
                                             note='Copies in occupied mapped inventory records; not a weapon catalogue completion count.'),
                             *traits), section='Equipment',
                            search_text=f'weapon {record.weapon_id} slot {record.index + 1} traits ' +
                                        ' '.join(map(str, record.traits))))

    proficiency = tuple(Card(
        f'family-{record.index}', record.family, 'Stored proficiency · ownership is not inferred',
        (Metric('stored-xp', 'Stored XP', str(record.stored_xp),
                note='Level thresholds and reward dependencies are not mapped.'),
         *(Metric(f'art-{index}', f'Equipped Battle Art {index + 1}',
                  'Empty' if art is None else f'ID {art}')
           for index, art in enumerate(record.battle_arts))), section='Proficiency',
        search_text=f'family {record.index} {record.family} battle arts')
        for record in proficiency_records(document))

    completion = []
    peace = tuple(metric(f'peace_{index}', name, total=10000,
                         note='10,000 stored peace points = 100% provincial peace.')
                  for index, name in enumerate(PROVINCE_NAMES) if f'peace_{index}' in fields)
    if peace:
        completion.append(Card('peace', 'Provincial peace', 'Per-province peace; separate from story completion.',
                               peace, section='Completion'))
    history = tuple(metric(f'battle_history_{index}', f'Battle ID {index} cleared', total=1)
                    for index in BATTLE_HISTORY_IDS if f'battle_history_{index}' in fields)
    if history:
        cleared = sum(int(item.value) for item in history)
        completion.append(Card('battle-history', 'Mapped battle clear history',
                               'Replay clear flags; these do not establish campaign completion or endings.',
                               (Metric('mapped-clears', 'Cleared mapped records',
                                       f'{cleared} / {len(history)}',
                                       current=cleared, total=len(history),
                                       note='Denominator covers only the recognized mapped battle records.'),
                                *history), section='Completion'))

    overview = [Card('equipment-snapshot', 'Weapon inventory', 'Occupied mapped inventory records', (
        Metric('copies', 'Weapon copies', str(len(inventory))),
        Metric('identities', 'Distinct weapon IDs', str(len(copies))),
        Metric('reinforcement', 'Highest stored reinforcement',
               f'+{max(record.upgrade for record in inventory)}' if inventory else 'No occupied records',
               note='Stored value only; no collection, proficiency or achievement state is inferred.'),
    ), section='Overview'), Card('progression-scope', 'Character progression', 'Verified inspection scope', (
        Metric('bonds', 'Mapped bond records', str(len(character_cards) - 1)),
        Metric('proficiencies', 'Recognized proficiency families', str(len(proficiency)) if proficiency else 'Unavailable',
               note='Existing records do not establish weapon ownership; XP thresholds and reward dependencies remain unmapped.'),
        Metric('campaign', 'Campaign completion', 'Not mapped',
               note='Battle replay flags and provincial peace are independent from campaign endings.'),
    ), section='Overview')]
    if history:
        overview.append(Card('battle-snapshot', 'Mapped battle history', 'Verified replay clear flags',
                             (completion[-1].metrics[0],), section='Overview'))

    return ProgressionDashboard('Dynasty Warriors: Origins', (
        Section('overview', 'Overview', tuple(overview),
                'Snapshot counts and scoped history only; no overall completion percentage.'),
        Section('characters', 'Characters', tuple(character_cards)),
        Section('equipment', 'Equipment', tuple(weapons),
                'Existing occupied inventory only. Numeric IDs are retained where names are not mapped; equipped weapon references are not mapped.'),
        Section('resources', 'Resources', (Card('resource-balances', 'Resource balances', metrics=resources,
                                               section='Resources'),),
                'Old Coins and crafting material balances are not mapped.'),
        Section('proficiency', 'Proficiency', proficiency,
                'Stored XP is read-only; no proficiency levels, learned arts or ownership are inferred.' if proficiency else
                'The optional proficiency record layout is unavailable for this copy.'),
        Section('completion', 'Completion', tuple(completion),
                'No overall completion percentage: active campaign, endings and rewards are not fully mapped.'),
    ), note='Opened-save snapshot. Dashboard navigation does not stage edits.')
