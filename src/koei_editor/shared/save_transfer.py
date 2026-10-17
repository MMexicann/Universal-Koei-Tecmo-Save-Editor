"""Selective semantic scalar transfers; parsers own every native write/check.

No bytes, record identities, signing context, inventory objects or unknown flags
are copied. Qualification is deliberately limited to the policies below.
"""
from collections import Counter
from dataclasses import dataclass

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import edit_presets, preset_portability
from koei_editor.shared.adapter_contract import is_opened_value
from koei_editor.shared.experimental_limits import experimental_limits


@dataclass(frozen=True)
class TransferChoice:
    id: str
    source_field: object
    target_field: object
    identity: tuple
    category: str
    source_value: int | str
    target_value: int | str


@dataclass(frozen=True)
class TransferExclusion:
    field: str
    reason: str


@dataclass(frozen=True)
class TransferCatalogue:
    choices: tuple[TransferChoice, ...]
    exclusions: tuple[TransferExclusion, ...]
    policy: str


@dataclass(frozen=True)
class TransferPlan:
    adapter: object
    source: object
    target: object
    selected: tuple[str, ...]
    catalogue: TransferCatalogue
    preview: edit_presets.PresetPlan

    @property
    def pending(self):
        return self.preview.pending

    @property
    def result(self):
        return self.preview.result

    @property
    def rows(self):
        return self.preview.rows

    @property
    def experimental_count(self):
        return self.preview.experimental_count



def _profile(adapter):
    # Exact registered backend identity, not an arbitrary matching field ID.
    from koei_editor.games.gundam1_ps3 import parser as gundam
    from koei_editor.games.pokemon_conquest_ds import parser as conquest
    from koei_editor.games.origins import origins_parser
    from koei_editor.games.wo3u import wo3u_parser
    from koei_editor.shared import verified_editor
    return {('gundam1_ps3', gundam): 'gundam',
            ('pokemon_conquest_ds', conquest): 'conquest',
            ('origins', origins_parser): 'resources',
            ('wo3u', wo3u_parser): 'wo3',
            ('dw8xl', verified_editor): 'resources'}.get((adapter.game_id, adapter.backend))


def _identities(adapter, document, kind):
    fields = adapter.field_map(document)
    excluded = []
    identities = {}
    if kind in ('resources', 'wo3'):
        policy = preset_portability.policy(adapter, document)
        for key, field in fields.items():
            if key in policy.fields:
                identities[('resource', key)] = field
            elif kind == 'wo3' and key in ('mount_loadout_0', 'mount_loadout_1'):
                identities[('equipment', 'mount-loadout', key)] = field
            else:
                excluded.append(TransferExclusion(key, preset_portability.exclusion_reason(policy, field)))
        return identities, excluded, preset_portability.identity(policy)
    if kind == 'gundam':
        from koei_editor.games.gundam1_ps3 import parser
        for key, name, _offset in parser.PILOTS:
            for skill in range(parser.SKILL_COUNT):
                field = fields.get(f'{key}_skill_{skill}')
                if field is not None:
                    identities[('progression', key, 'learned', skill)] = field
            for position in range(4):
                field = fields.get(f'{key}_equipped_{position}')
                if field is not None:
                    identities[('equipment', key, 'selected-skill-position', position)] = field
            if not any(identity[1] == key for identity in identities):
                excluded.append(TransferExclusion(name, 'Pilot is not natively qualified at level 30 with learned references.'))
        excluded.append(TransferExclusion('Other progression', 'EXP, levels, inherent skills, suits and mission/story progress have no transfer policy.'))
        # Title identity is qualified through original PARAM.SFO on every read.
        # Keep regional title variants separate; no owner/signing data is used.
        return identities, excluded, 'gundam1-named-pilots-v1:' + document.native_directory[:9]
    from koei_editor.games.pokemon_conquest_ds import parser
    records = parser.gallery_records(document)
    counts = Counter((row[0], row[4]) for row in records)
    for bank, _generation, slot, name, species, *_values in records:
        if not 0 <= species < 200 or counts[(bank, species)] != 1:
            excluded.append(TransferExclusion(f'Bank {bank}: {name} record {slot}',
                             'Unknown species or duplicate species within this physical gallery bank.'))
            continue
        for component in range(1, 5):
            field = fields.get(f'bank_{bank}_pokemon_{slot}_iv_{component}')
            if field is not None:
                identities[('statistics', 'gallery-bank', bank, species, component)] = field
    excluded.append(TransferExclusion('Scenario and story', 'Scenario Pokémon, ownership, links, EXP and story have no transfer policy.'))
    return identities, excluded, 'conquest-us-vanilla-gallery-v1'


def catalogue(adapter, source, target):
    """List qualified matched values and explicit exclusions without staging."""
    edit_presets.validate_source(adapter, source)
    edit_presets.validate_source(adapter, target)
    if source.source.samefile(target.source):
        raise SaveError('Choose two separate source and destination save copies.')
    kind = _profile(adapter)
    if kind is None:
        raise SaveError('Selective transfer is not qualified for this game/platform. No fields were copied.')
    incoming, source_excluded, policy = _identities(adapter, source, kind)
    outgoing, target_excluded, target_policy = _identities(adapter, target, kind)
    if policy != target_policy:
        raise SaveError('The source and destination have different qualified native revisions or title profiles.')
    exclusions = [TransferExclusion('Source: ' + item.field, item.reason) for item in source_excluded]
    exclusions.extend(TransferExclusion('Destination: ' + item.field, item.reason) for item in target_excluded)
    choices = []
    for identity, target_field in outgoing.items():
        source_field = incoming.get(identity)
        if source_field is None:
            exclusions.append(TransferExclusion(target_field.id, 'No unique matching native identity exists in the source.'))
            continue
        value = source_field.value(source.payload)
        opened = target_field.value(target.payload)
        try:
            # Field bounds alone never qualify the full batch; prepare does.
            with experimental_limits(adapter.experimental):
                if not is_opened_value(target, target_field, value):
                    target_field.validate(value)
            if kind == 'wo3' and identity[0] == 'equipment':
                if value not in dict(adapter.backend.field_options(target, target_field.id)):
                    raise SaveError('Mount is not originally owned with supported rank in the destination.')
            if kind == 'gundam':
                if identity[0] == 'progression' and value < opened:
                    raise SaveError('Already learned destination skills cannot be removed.')
                if identity[0] == 'equipment' and value not in dict(adapter.backend.field_options(target, target_field.id)):
                    raise SaveError('Skill is not originally learned and non-inherent in the destination. Save and reopen learned changes first.')
        except SaveError as error:
            exclusions.append(TransferExclusion(target_field.id, str(error)))
            continue
        choices.append(TransferChoice(target_field.id, source_field, target_field, identity,
                                      identity[0].capitalize(), value, opened))
    edit_presets.validate_source(adapter, source)
    edit_presets.validate_source(adapter, target)
    return TransferCatalogue(tuple(choices), tuple(exclusions), policy)


def prepare(adapter, source, target, changes, selected):
    """Validate the final selected batch, including existing pending edits."""
    available = catalogue(adapter, source, target)
    if not isinstance(selected, (tuple, list, set, frozenset)) or not selected:
        raise SaveError('Select at least one individually qualified field to transfer.')
    if any(type(key) is not str for key in selected) or len(set(selected)) != len(selected):
        raise SaveError('Transfer selection must contain distinct verified field IDs.')
    selected = tuple(sorted(selected))
    choices = {choice.id: choice for choice in available.choices}
    if any(key not in choices for key in selected):
        raise SaveError('A selected field is excluded or has no unique compatible native identity.')
    assignments = {key: choices[key].source_value for key in selected}
    preview = edit_presets.prepare_assignments(adapter, target, changes, assignments, 'Selected save transfer')
    plan = TransferPlan(adapter, source, target, selected, available, preview)
    validate_sources(plan)
    return plan


def validate_sources(plan):
    edit_presets.validate_source(plan.adapter, plan.source)
    edit_presets.validate_source(plan.adapter, plan.target)


def confirm(plan, adapter, target, changes):
    """Reject stale source, target, session, dependencies or selection previews."""
    if type(plan) is not TransferPlan or plan.adapter is not adapter or plan.target is not target:
        raise SaveError('The editor session changed. Prepare a fresh transfer preview.')
    current = edit_presets.confirm(plan.preview, adapter, target, changes)
    expected = prepare(adapter, plan.source, target, changes, plan.selected)
    if expected != plan:
        raise SaveError('The transfer preview changed. Prepare a fresh preview.')
    return current
