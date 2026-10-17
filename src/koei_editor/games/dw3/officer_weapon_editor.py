"""Officer weapon bonus editing using parsed records and verified fusion rules.

Normal and verified rare bonuses and single elements are editable. Identity,
power definition, hit flags, time, equipment and collection caches stay
unchanged. No material-consuming fusion workflow is performed here.
Experimental numeric rolls only extend a normal bonus already present in its
saved physical slot; new acquisitions, rare values, identities, slot counts,
element flags and references retain their supported rules.
"""
from koei_editor.resources import data_file, read_json
from koei_editor.shared.experimental_limits import SIGNED_INT32_MAX, within_numeric_limits
import struct
from koei_editor.games.dw3.models import Change, SaveError, fields

METADATA=read_json('game_metadata.json')
ITEMS={r['id']:r for r in METADATA['items']}
ITEM_IDS={'EEquipItemID::'+r['enum']:r['id'] for r in METADATA['items']}
WEAPONS={r['id']:r for r in METADATA['weapons']}
WEAPON_IDS={r['enum']:r['id'] for r in METADATA['weapons']}
UNIQUES={r['weapon_id']:r for r in read_json('unique_weapons.json')['weapons']}
UNIQUE_SLOTS={r['unique_save_index']:r for r in UNIQUES.values()}
_rule_file=data_file('weapon_bonus_rules.json')
RULES=read_json('weapon_bonus_rules.json') if _rule_file.is_file() else {}
NORMAL_ITEMS={int(r['id']):r for r in RULES.get('normal_items',[])}
ITEM_CAPS={int(i):v for i,v in read_json('item_limits.json')['maxima'].items()}
RARE_ITEMS={int(r['id']):r for r in RULES.get('rare_items',[])}
ELEMENTS=RULES.get('elements',{})
ELEMENT_MASK=RULES.get('element_mask',0)
CATEGORIES={'weapon_roll','weapon_element'}
VALUE_STORAGE_MAXIMUM=SIGNED_INT32_MAX


def _requests(changes):
    result={}
    for change in changes:
        if not isinstance(change,Change):raise SaveError('Weapon edits must be supported Change records.')
        if not isinstance(change.category,str) or not isinstance(change.field,str):raise SaveError('Weapon edit category and field must be text.')
        if change.category not in CATEGORIES:continue
        expected='Skills' if change.category=='weapon_roll' else 'Elements'
        if type(change.index) is not int or change.field!=expected:
            raise SaveError('Weapon edits need an integer inventory reference and supported field.')
        requested=result.setdefault(change.index,{})
        if change.field in requested:raise SaveError('Duplicate weapon changes.')
        requested[change.field]=change.value
    return result


def _location(document,data_id):
    if type(data_id) is not int:raise SaveError('Weapon inventory references must be integers.')
    if 0<=data_id<min(10000,len(document.records('WeaponDataArray'))):return 'WeaponDataArray',data_id
    if 10000<=data_id<10000+len(document.records('UniqueWeaponDataArray')):
        return 'UniqueWeaponDataArray',data_id-10000
    if data_id>=10000 and data_id-10000 in UNIQUE_SLOTS:
        return 'UniqueWeaponDataArray',data_id-10000
    raise SaveError('Choose an existing officer weapon inventory slot.')


def original_skills(document,data_id):
    array,index=_location(document,data_id)
    if index>=len(document.records(array)):
        return [{'id':None,'value':0} for _ in range(9)]
    result=[]
    for row in fields(document.records(array)[index])['Skill']['value']['records']:
        slot=fields(row);enum=slot['EquipItemID']['value']
        item=None if enum=='EEquipItemID::NUM' else ITEM_IDS.get(enum)
        if item is None and enum!='EEquipItemID::NUM':
            # Native reserved IDs are readable, but have no verified edit rules.
            if enum.startswith('EEquipItemID::EquipItemID_') and enum.rsplit('_',1)[-1].isdigit():
                item=int(enum.rsplit('_',1)[-1])
        result.append({'id':item,'value':slot['Value']['value']})
    return result


def allowed_values(info,item_id):
    if type(item_id) is not int:raise SaveError('Weapon bonus IDs must be integers.')
    if item_id in RARE_ITEMS:return [0]
    if item_id not in NORMAL_ITEMS:raise SaveError('Only verified transferable weapon bonuses can be edited.')
    values=set(NORMAL_ITEMS[item_id]['allowed_values'])
    if info['array']=='UniqueWeaponDataArray' and info['weapon_id'] in UNIQUES:
        for slot in UNIQUES[info['weapon_id']]['skill_slots']:
            if slot['item_id']==item_id:values.add(slot['value'])
    return sorted(v for v in values if v>0)


def skill_numeric_limits(info,item_id):
    """Normal bonus minimum, supported maximum and signed IntProperty ceiling."""
    if type(item_id) is not int or item_id not in NORMAL_ITEMS:
        raise SaveError('Only normal weapon bonuses have numeric limits.')
    return 1,max(allowed_values(info,item_id)),VALUE_STORAGE_MAXIMUM


def _experimental_roll(info,index,skill):
    """Extend an existing normal bonus value without creating a new identity."""
    item,value=skill['id'],skill['value'];original=info['skills'][index]
    if not info.get('experimental_existing') or original['id']!=item or item not in NORMAL_ITEMS:
        return False
    minimum,maximum,storage_maximum=skill_numeric_limits(info,item)
    return (type(value) is int and value>maximum and
            within_numeric_limits(value,minimum,maximum,storage_maximum=storage_maximum))


def allowed_elements(info):
    return {label:mask for label,mask in ELEMENTS.items() if mask or not info['elements']}


def validate_elements(info,mask):
    if not info.get('element_editable'):raise SaveError(info.get('element_reason') or 'Choose a supported owned weapon.')
    if type(mask) is not int or mask<0 or mask & ~ELEMENT_MASK:
        raise SaveError('Choose a verified weapon element without changing hit or unique flags.')
    if mask==info['elements']:return mask  # Preserve an existing combined mask; never manufacture one.
    if mask not in allowed_elements(info).values():
        raise SaveError('Choose one verified element. Existing elements can be replaced, not removed.')
    return mask


def _base_state(document,data_id,changes):
    array,index=_location(document,data_id)
    record=fields(document.records(array)[index]) if index<len(document.records(array)) else None
    weapon_id=WEAPON_IDS.get(record['WeaponID']['value']) if record else None
    owned=record is not None and record['WeaponID']['value']!='EWeaponID::NUM'
    skills=original_skills(document,data_id);attr=record['Attr']['value'] if record else 0
    template=UNIQUE_SLOTS.get(index) if array=='UniqueWeaponDataArray' else None
    pending=template is not None and any(c.category=='unique_weapon' and c.index==template['weapon_id'] and c.field=='Owned' and c.value is True for c in changes)
    newly_acquired=not owned and pending
    if newly_acquired:
        weapon_id=template['weapon_id'];owned=True;attr=template['attribute_bitmask']
        skills=[{'id':s['item_id'] if s['item_id'] in ITEMS else None,'value':s['value']} for s in template['skill_slots']]
    metadata=WEAPONS.get(weapon_id,{})
    minimum=sum(s['item_id'] in NORMAL_ITEMS for s in template['skill_slots']) if template else (0 if metadata.get('initial_possession') else 1)
    info={'data_id':data_id,'array':array,'index':index,'weapon_id':weapon_id,'owned':owned,
          'experimental_existing':record is not None and owned and not newly_acquired,
          'skills':skills,'metadata':metadata,'attr':attr,'elements':attr & ELEMENT_MASK,
          'blue_limit':None,'blue_minimum':minimum,'red_limit':1,
          'red_minimum':sum(s['id'] in ITEMS and ITEMS[s['id']]['kind']=='rare' for s in skills),
          'editable':False,'reason':'','element_editable':False,'element_reason':''}
    if not owned:info['reason']='Unlock this unique weapon before editing its rolls.'
    elif array=='WeaponDataArray' and weapon_id not in set(range(89))|{188,189,190}:
        info['reason']='This ordinary inventory identity is not a supported playable weapon.'
    elif array=='UniqueWeaponDataArray' and (template is None or weapon_id!=template['weapon_id']):
        info['reason']='This unique weapon identity does not match its inventory slot.'
    elif array=='WeaponDataArray' and len(document.records(array))>10000:
        info['reason']='This inventory exceeds the native unique-reference boundary; preserve it without editing.'
    elif not newly_acquired and (record['ID']['value']!=record['WeaponID']['value'] or record['DataID']['value']!=data_id):
        info['reason']='Weapon identity or inventory reference is inconsistent.'
    if info['reason']:
        info['element_reason']=info['reason']
        return info
    # An element edit replaces only the four proven Attr bits. Bonus
    # transfer rules do not govern this leaf; unusual saved bonuses remain
    # byte-for-byte intact even when their own controls are unavailable.
    if not ELEMENTS or not ELEMENT_MASK:
        info['element_reason']='Element transfer rules are unavailable.'
    elif not newly_acquired and (record['Attr'].get('type')!='Int64Property' or
                                 record['Attr'].get('data_size')!=8 or
                                 type(attr) is not int or not -(1<<63)<=attr<(1<<63)):
        info['element_reason']='This weapon has no verified Int64 attribute field.'
    else:info['element_editable']=True

    if not NORMAL_ITEMS:info['reason']='Weapon bonus limits have not been verified.'
    elif any(s['id'] is not None and s['id'] not in ITEMS for s in skills):
        info['reason']='This copy contains a reserved bonus identity with no verified edit rules.'
    elif record and any(fields(s)['EquipItemID']['value']!='EEquipItemID::NUM' and fields(s)['EquipItemID']['value'] not in ITEM_IDS for s in record['Skill']['value']['records']):
        info['reason']='This copy contains an unknown bonus identity; preserve it without editing.'
    elif record and any(fields(s)['GuardEquipItemID']['value']!='EGuardEquipItemID::NUM' for s in record['Skill']['value']['records']):
        info['reason']='Bodyguard bonuses cannot be changed in an officer weapon.'
    else:
        rank_row=RULES.get('weapon_rules',{}).get(str(weapon_id))
        if not rank_row:info['reason']='Weapon rank limits are unsupported.'
        else:
            info['rank']=rank_row['rank'];info['blue_limit']=rank_row['max_blue'];info['editable']=True
            try:validate_skills(info,skills)
            except SaveError as error:
                info['editable']=False;info['reason']=str(error)
    if not info['element_editable'] and not info['element_reason']:
        info['element_reason']=info['reason'] or 'Element transfer rules are unavailable.'
    return info


def validate_skills(info,skills):
    if not info['owned'] or info['blue_limit'] is None:raise SaveError(info.get('reason') or 'Choose a supported owned weapon.')
    if not isinstance(skills,(list,tuple)) or len(skills)!=9:raise SaveError('Officer weapons have exactly nine saved bonus slots.')
    result=[];seen=set();blue=0;red=0
    for index,skill in enumerate(skills):
        if not isinstance(skill,dict) or set(skill)!={'id','value'}:raise SaveError('Each weapon slot needs an item ID and value.')
        item,value=skill['id'],skill['value'];original=info['skills'][index]
        if item is not None and type(item) is not int:raise SaveError('Weapon bonus IDs must be integers or None.')
        if type(value) is not int or not -(1<<31)<=value<=VALUE_STORAGE_MAXIMUM:
            raise SaveError('Weapon bonus values must fit their signed IntProperty.')
        if original['id'] is not None and original['id'] not in NORMAL_ITEMS and original['id'] not in RARE_ITEMS:
            if skill!=original:raise SaveError('Existing unsupported weapon skills must be preserved in their saved slots.')
        elif item is None:
            if value!=0:raise SaveError('Empty weapon bonus slots require zero value.')
        elif item in RARE_ITEMS:
            if value!=0 and skill!=original:raise SaveError('Rare weapon bonuses have no numeric roll; use value zero.')
        elif item not in NORMAL_ITEMS:
            raise SaveError('Only verified transferable bonus identities can be added or changed.')
        if item is not None:
            if item in seen:raise SaveError('A weapon cannot have duplicate bonus identities.')
            seen.add(item)
            if item in NORMAL_ITEMS:
                blue+=1
                if value not in allowed_values(info,item) and not (value>0 and skill==original) and not _experimental_roll(info,index,skill):
                    raise SaveError(f'{ITEMS[item]["name"]} has an unsupported weapon roll. An existing saved value can only be preserved in its original slot.')
            else:red+=1
        result.append({'id':item,'value':value})
    if blue>info['blue_limit']:raise SaveError(f'This weapon supports at most {info["blue_limit"]} normal bonuses.')
    if blue<info['blue_minimum']:raise SaveError(f'Keep at least {info["blue_minimum"]} normal bonuses for this weapon. Replace their types instead of removing them.')
    if red>info.get('red_limit',1):raise SaveError('A weapon supports at most one rare bonus.')
    if red<info.get('red_minimum',0):raise SaveError('Replace the existing rare bonus instead of removing it.')
    old_red=[(i,s) for i,s in enumerate(info['skills']) if s['id'] is not None and s['id'] not in NORMAL_ITEMS]
    new_red=[(i,s) for i,s in enumerate(result) if s['id'] is not None and s['id'] not in NORMAL_ITEMS]
    if new_red and new_red!=old_red:
        # Native fusion puts normal bonuses first and its single rare bonus in
        # the final slot. Numeric-only edits preserve earlier saved rare slots.
        normal=[s for s in result if s['id'] in NORMAL_ITEMS]
        result=normal+[{'id':None,'value':0} for _ in range(8-len(normal))]+[new_red[0][1]]
        for index,skill in enumerate(result):
            if skill['id'] in NORMAL_ITEMS and skill['value'] not in allowed_values(info,skill['id']) and skill!=info['skills'][index]:
                raise SaveError('An existing unsupported roll must stay in its original saved slot when replacing rare bonuses.')
    return result


def state(document,data_id,changes=()):
    changes=list(changes);info=_base_state(document,data_id,changes);requests=_requests(changes)
    if data_id in requests:
        if 'Skills' in requests[data_id]:
            if not info['editable']:raise SaveError(info['reason'])
            info['skills']=validate_skills(info,requests[data_id]['Skills'])
        if 'Elements' in requests[data_id]:
            info['elements']=validate_elements(info,requests[data_id]['Elements'])
            info['attr']=(info['attr'] & ~ELEMENT_MASK)|info['elements']
    return info


def states(document,changes=()):
    changes=list(changes)
    for array,base in [('WeaponDataArray',0),('UniqueWeaponDataArray',10000)]:
        for index in range(len(document.records(array))):
            if array=='WeaponDataArray' and index>=10000:
                continue  # Ambiguous native references cannot become edit targets.
            info=state(document,base+index,changes)
            if info['owned']:yield info
    existing=len(document.records('UniqueWeaponDataArray'))
    for index,template in sorted(UNIQUE_SLOTS.items()):
        if index>=existing:
            info=state(document,10000+index,changes)
            if info['owned']:yield info


def element_changes(document,data_ids,mask,changes=()):
    """Validate a whole selection before returning pending element edits.

    No bonus roll, inventory identity or non-element flag is authored here.
    Callers merge the returned records into their pending changes by key.
    """
    changes=list(changes);result=[];seen=set()
    for data_id in data_ids:
        if type(data_id) is not int or data_id in seen:
            raise SaveError('Choose distinct integer weapon inventory references.')
        seen.add(data_id)
        info=state(document,data_id,changes)
        wanted=validate_elements(info,mask)
        if wanted!=info['elements']:
            result.append(Change('weapon_element',data_id,'Elements',wanted))
    if not seen:raise SaveError('Choose at least one supported owned weapon.')
    return result


def owned_unique_element_changes(document,mask,changes=()):
    """Apply one chosen native element to supported owned unique copies."""
    changes=list(changes)
    data_ids=[row['data_id'] for row in states(document,changes)
              if row['array']=='UniqueWeaponDataArray' and row['element_editable']]
    return element_changes(document,data_ids,mask,changes)


def max_existing_skills(document,data_id,changes=()):
    info=state(document,data_id,changes)
    if not info['editable']:raise SaveError(info['reason'])
    saved=original_skills(document,data_id)
    result=[]
    for index,skill in enumerate(info['skills']):
        value=skill['value']
        if skill['id'] in NORMAL_ITEMS:
            baseline=saved[index]['value'] if index<len(saved) and saved[index]['id']==skill['id'] else 0
            value=max(value,baseline,max(allowed_values(info,skill['id'])))
        result.append({'id':skill['id'],'value':value})
    return result


def copy_bonus_changes(document,source_data_id,target_data_ids,changes=()):
    """Copy a verified bonus layout to existing owned copies, atomically.

    This is a direct edit using the same native transfer outcomes as the
    individual slot controls, not material-consuming fusion. Every destination
    applies its own rank, stock-value exceptions and saved-slot preservation
    rules. Source-only unique rolls and experimental high rolls cannot become
    transferable merely because they are already present on the source.
    Identity, elements, hit flags, inventory and first-acquisition snapshots
    are not copied. A view-only source or destination refuses the whole batch.
    """
    changes=list(changes)
    source=state(document,source_data_id,changes)
    if not source['editable']:raise SaveError(source['reason'])
    result=[];seen=set()
    for data_id in target_data_ids:
        if type(data_id) is not int or data_id in seen:
            raise SaveError('Choose distinct integer destination inventory references.')
        seen.add(data_id)
        if data_id==source_data_id:
            raise SaveError('Choose a different destination weapon copy.')
        target=state(document,data_id,changes)
        if not target['editable']:raise SaveError(target['reason'])
        try:
            saved=original_skills(document,data_id)
            for index,skill in enumerate(source['skills']):
                if (skill['id'] in NORMAL_ITEMS and
                        skill['value'] not in allowed_values(target,skill['id']) and skill!=saved[index]):
                    raise SaveError('A source-only or above-limit weapon roll cannot be copied to this destination.')
            skills=validate_skills(target,source['skills'])
        except SaveError as error:
            raise SaveError(f'Weapon copy {data_id}: {error}') from error
        # Return equal assignments as well: the normal staging path removes
        # an earlier pending layout when the copied layout matches opened data.
        result.append(Change('weapon_roll',data_id,'Skills',skills))
    if not seen:raise SaveError('Choose at least one destination weapon copy.')
    return result


def max_item_value(document,item_id,changes=()):
    """Normal-drop maximum without decreasing an owned saved/pending roll."""
    if type(item_id) is not int or item_id not in ITEM_CAPS or item_id>=len(document.records('EquipItemDataArray')):
        raise SaveError('Choose a supported normal item present in this save.')
    record=fields(document.records('EquipItemDataArray')[item_id]);expected='EEquipItemID::'+ITEMS[item_id]['enum']
    if record['EquipItemID']['value'] not in ('EEquipItemID::NUM',expected) or record['GuardEquipItemID']['value']!='EGuardEquipItemID::NUM':
        raise SaveError('This item has an unknown saved placement; preserve it without editing.')
    saved=record['Value']['value'] if record['EquipItemID']['value']==expected else 0
    owned=record['EquipItemID']['value']==expected;pending=saved;explicit_owned=False;has_value=False
    for change in changes:
        if change.category=='item' and change.index==item_id:
            if change.field=='Owned':owned=change.value;explicit_owned=True
            elif change.field=='Value':pending=change.value;has_value=True
    if has_value and not explicit_owned:owned=True
    if type(owned) is not bool or type(pending) is not int:
        raise SaveError('Normal-item ownership and values need their supported types.')
    return max(ITEM_CAPS[item_id],saved,pending if owned else 0)


def plan_weapon_roll_changes(document,changes,add_property):
    for data_id,requested in _requests(changes).items():
        info=state(document,data_id,changes)
        if info['array']=='UniqueWeaponDataArray':continue  # Collection planner combines acquisition and unique edits.
        record=fields(document.records(info['array'])[info['index']])
        if 'Elements' in requested:
            add_property(record['Attr'],struct.pack('<q',info['attr']),f'{info["metadata"].get("name") or "Weapon"} copy {data_id}: element; preserve other flags')
        if 'Skills' not in requested:continue
        for index,skill in enumerate(info['skills']):
            slot=fields(record['Skill']['value']['records'][index])
            enum='EEquipItemID::NUM' if skill['id'] is None else 'EEquipItemID::'+ITEMS[skill['id']]['enum']
            encoded=enum.encode('utf-8')+b'\0'
            reason=f'{info["metadata"].get("name") or "Weapon"} copy {data_id}: bonus slot {index+1}'
            add_property(slot['EquipItemID'],struct.pack('<i',len(encoded))+encoded,reason+' identity')
            add_property(slot['Value'],struct.pack('<i',skill['value']),reason+' verified numeric roll')
