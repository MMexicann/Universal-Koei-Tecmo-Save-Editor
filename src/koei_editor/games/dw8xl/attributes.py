"""Replace an existing ranked element using the opened native weapon palette.

The PC permanent weapon structure describes the six ID bytes at +6..11 and
ranks at +12..17. The qualified native reference witnesses the ranked IDs used
by the existing rank editor. The game's fusion mechanic independently permits
replacing an existing element while retaining the other weapon properties.
Only IDs also witnessed with a normal rank in this opened save are offered;
this is a direct property edit, never a simulated fusion or acquisition action.
"""
from dataclasses import dataclass

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.verified_editor import Field


@dataclass(frozen=True)
class AttributeIdentityField(Field):
    allowed_ids: tuple = ()

    @property
    def experimental_maximum(self):
        return None

    def validate(self, value):
        if type(value) is not int or value not in self.allowed_ids:
            raise SaveError('Choose a verified ranked attribute present in this opened weapon pool.')


def fields_for_payload(payload, weapon_record, weapon_count, weapon_base, weapon_stride, ranked_ids):
    records = tuple(record for index in range(weapon_count)
                    if (record := weapon_record(payload, index)) is not None)
    palette = tuple(sorted({identity for record in records
                            for identity, rank in record['attributes']
                            if identity in ranked_ids and 1 <= rank <= 10}))
    fields = []
    for record in records:
        identities = tuple(identity for identity, _ in record['attributes'] if identity != 255)
        if len(identities) != len(set(identities)):
            # Preserve unusual native combinations instead of granting permission
            # to create or normalize duplicate identities.
            continue
        index = record['slot'] - 1
        for attribute, (identity, rank) in enumerate(record['attributes']):
            if identity not in palette or not 1 <= rank <= 10:
                continue
            fields.append(AttributeIdentityField(
                f'weapon_{index}_attribute_{attribute}_identity',
                f'Attribute {attribute + 1} identity (opened ID {identity})',
                weapon_base + index * weapon_stride + 6 + attribute,
                1, max(palette), 'Weapon attribute identities', index + 1,
                maxable=False, experimental=False, allowed_ids=palette))
    return tuple(fields)


def validate_pending(payload, changes, fields, weapon_base, weapon_stride):
    affected = {fields[key].slot for key, value in changes.items()
                if isinstance(fields[key], AttributeIdentityField)
                and value != fields[key].value(payload)}
    for slot in affected:
        offset = weapon_base + (slot - 1) * weapon_stride + 6
        identities = list(payload[offset:offset + 6])
        for attribute in range(6):
            key = f'weapon_{slot - 1}_attribute_{attribute}_identity'
            if key in changes:
                identities[attribute] = changes[key]
                if changes[key] != payload[offset + attribute]:
                    rank_key = f'weapon_{slot - 1}_attribute_{attribute}_rank'
                    rank = changes.get(rank_key, payload[offset + 6 + attribute])
                    if not 1 <= rank <= 10:
                        raise SaveError('An attribute replacement requires its paired rank from 1 to 10.')
        populated = [identity for identity in identities if identity != 255]
        if len(populated) != len(set(populated)):
            raise SaveError(f'Weapon slot {slot:04} cannot contain duplicate attribute identities.')


def stage_swap(payload, changes, key, value, fields):
    """Expand a deliberate occupied-ID choice into two visible identity edits.

    The caller validates the complete pending map before and after this helper.
    Original assignments retain the normal unstage path, including rejection
    of a partial restoration that would leave duplicate identities.
    """
    field = fields[key]
    current = changes.get(key, field.value(payload))
    if current == value:
        return dict(changes)
    result = dict(changes)
    for peer_key, peer in fields.items():
        if (peer_key == key or not isinstance(peer, AttributeIdentityField)
                or peer.slot != field.slot
                or changes.get(peer_key, peer.value(payload)) != value):
            continue
        # Only an originally qualified ranked slot may receive the displaced
        # identity. Unknown/unranked/empty slots have no such field.
        peer.validate(current)
        if current == peer.value(payload):
            result.pop(peer_key, None)
        else:
            result[peer_key] = current
        break
    result[key] = value
    return result
