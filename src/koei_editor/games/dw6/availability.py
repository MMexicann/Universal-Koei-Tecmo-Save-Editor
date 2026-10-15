"""Native stage and Musou availability bytes; completion is a separate state."""
from koei_editor.games.dw3.models import SaveError

STAGE_GROUP, MUSOU_GROUP = 'Stage availability', 'Musou availability'
GROUPS = (STAGE_GROUP, MUSOU_GROUP)


def specs(payload, officer_base):
    stages = officer_base + 41 * 168
    musou = stages + 45 * 20
    result = []
    for index in range(45):
        offset = stages + index * 20 + 16
        if payload[offset] in (0, 1):
            result.append(dict(id=f'stage_{index}_available', label='Stage available (1 unlock)',
                               offset=offset, size=1, maximum=1, group=STAGE_GROUP,
                               slot=index + 1, maxable=False, experimental=False))
    for index in range(17):
        offset = musou + index * 4
        if payload[offset] in (0, 1) and payload[officer_base + index * 168 + 164] in (0, 1):
            result.append(dict(id=f'musou_{index}_available', label='Musou mode available (1 unlock)',
                               offset=offset, size=1, maximum=1, group=MUSOU_GROUP,
                               slot=index + 1, maxable=False, experimental=False))
    return tuple(result)


def validate(payload, pending, mapping, officer_base):
    for key, value in pending.items():
        field = mapping[key]
        if field.group not in GROUPS or value == field.value(payload):
            continue
        if value != 1:
            raise SaveError('Stage and Musou availability unlocks are one-way; relocking is unavailable.')
        if field.group == MUSOU_GROUP:
            index = field.slot - 1
            playable = pending.get(f'officer_{index}_unlocked', payload[officer_base + index * 168 + 164])
            if playable != 1:
                raise SaveError('Unlock the corresponding playable officer first, or use Unlock All Musou Modes.')


def stage_values(fields, payload):
    return {field.id: 1 for field in fields if field.group == STAGE_GROUP and field.value(payload) == 0}


def musou_values(fields, payload, officer_base):
    modes = [field for field in fields if field.group == MUSOU_GROUP and field.value(payload) == 0]
    # GUI batches stage one assignment at a time. Playable prerequisites must
    # therefore precede their new Musou availability flags in this ordered map.
    result = {f'officer_{field.slot - 1}_unlocked': 1 for field in modes
              if payload[officer_base + (field.slot - 1) * 168 + 164] == 0}
    result.update({field.id: 1 for field in modes})
    return result


def hint(group):
    if group == STAGE_GROUP:
        return 'Make this existing stage available in Free Mode. Clear records, best results, story and rewards are preserved. One-way unlock; excluded from Max.'
    return 'Make this officer’s Musou mode available after unlocking the playable officer. Completion, endings, gallery and rewards are preserved. One-way unlock; excluded from Max.'
