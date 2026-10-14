"""Native Origins progression scalars; event and reward flags are preserved.

Offsets address the decrypted body. Identifiers are native table indices.
Battle history records replay completion only: it does not finish the active
campaign, trigger story events, grant rewards or establish an ending.
"""

from koei_editor.shared.experimental_limits import within_numeric_limits
PEACE_BASES = {16: 0x1f64b, 17: 0x1f64c, 29: 0x1f716}
BOND_BASES = {16: 0x136e, 17: 0x136e, 29: 0x1436}
HISTORY_BASES = {16: 0x210a1, 17: 0x210a2, 29: 0x21365}

# Native province-name lookup uses the province index unchanged. Bond display
# follows bond catalogue WORD+4 -> character catalogue WORD+18 -> name table.
# Bond47 changes character with story state; placeholder rows remain IDs.
PROVINCE_NAMES = (
    'Sili Province', 'Yu Province', 'Ji Province', 'Yan Province', 'Xu Province',
    'Qing Province', 'Jing Province', 'Yang Province', 'Yi Province',
    'Liang Province', 'Bing Province', 'You Province', 'Jiaozhi',
)
BOND_NAMES = dict(enumerate((
    'Xiahou Dun', 'Dian Wei', 'Zhang Liao', 'Cao Cao', 'Zhou Yu',
    'Sun Shangxiang', 'Gan Ning', 'Sun Jian', 'Zhao Yun', 'Guan Yu',
    'Zhang Fei', 'Zhuge Liang', 'Liu Bei', 'Diaochan', 'Lu Bu', 'Xu Zhu',
    'Xiahou Yuan', 'Xu Huang', 'Zhang He', 'Taishi Ci', 'Lu Meng', 'Huang Gai',
    'Zhou Tai', 'Ling Tong', 'Sun Ce', 'Sun Quan', 'Pang Tong', 'Dong Zhuo',
    'Yuan Shao', 'Zhang Jiao', 'Zhenji', 'Yueying', 'Jia Xu', 'Guo Jia',
    'Xu Shu', 'Yue Jin', 'Li Dian', 'Lu Su', 'Han Dang', 'Yu Jin', 'Chen Gong',
    'Xun Yu', 'Xun You', 'Cheng Pu', 'Zhou Cang', 'Yuan Shu', 'Hua Xiong',
)))
BOND_NAMES.update({48: 'Zhuhe', 99: 'Yuanhua'})

# Native catalogues 427/428, record types 1/7/8. Deduplicated IDs only;
# reserved entries and additional content whose ownership is unverified are
# excluded. The persistent serializer has the same 1,000-byte array in all
# supported revisions.
BATTLE_HISTORY_IDS = tuple(range(16)) + (
    19, 22, 24, 25, 26, 27, 39, 40, 42, 44, 46, 49, 51, 56, 57, 59,
    62, 65, 68,
)


def progression_specs(payload, revision):
    """Return field kwargs after the caller has qualified the complete slot.

    Peace uses 10,000 points for 100%. Bond fields are limited to already
    formed records (level 1..5). Training has a native cap of 999, but three
    trainings satisfy the counter part of the game's completion predicate.
    Max must not inflate this historical count to 999. Conversations, learned
    arts, reward claims and active story flags remain separate. Battle clear
    history is manual-only and is not a complete-story or ending shortcut.
    Cleared history is monotonic, matching the native setter's write of 1.
    """
    if revision not in PEACE_BASES:
        return []
    fields = []
    for index in range(13):
        offset = PEACE_BASES[revision] + index * 2
        if offset + 2 > len(payload):
            continue
        value = int.from_bytes(payload[offset:offset + 2], 'little')
        if within_numeric_limits(value, 0, 10000, storage_maximum=65535):
            fields.append(dict(id=f'peace_{index}',
                               label=f'{PROVINCE_NAMES[index]} peace (10,000 = 100%)',
                               offset=offset, size=2, maximum=10000,
                               group='Provincial peace', slot=index))
    for index in range(101):
        offset = BOND_BASES[revision] + index * 5
        if offset + 5 > len(payload):
            continue
        if not within_numeric_limits(payload[offset], 1, 5, storage_maximum=255):
            continue
        bond_name = BOND_NAMES.get(index, f'Bond ID {index}')
        fields.append(dict(id=f'bond_{index}_level',
                           label=f'{bond_name} bond level (events unchanged)',
                           offset=offset, size=1, maximum=5, minimum=1,
                           group='Existing bonds', slot=index))
        training = int.from_bytes(payload[offset + 2:offset + 4], 'little')
        if within_numeric_limits(training, 0, 999, storage_maximum=65535):
            fields.append(dict(id=f'bond_{index}_training',
                               label=f'{bond_name} training count (threshold 3)',
                               offset=offset + 2, size=2, maximum=999,
                               group='Bond training', slot=index, maxable=False))
    for index in BATTLE_HISTORY_IDS:
        offset = HISTORY_BASES[revision] + index
        if offset >= len(payload) or payload[offset] not in (0, 1):
            continue
        fields.append(dict(id=f'battle_history_{index}',
                           label=f'Battle ID {index} clear history (0 incomplete; 1 cleared)',
                           offset=offset, size=1, maximum=1, minimum=payload[offset],
                           group='Battle clear history', slot=index, maxable=False))
    return fields
