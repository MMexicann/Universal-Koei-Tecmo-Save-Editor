"""Verified bodyguard equipment and final-state edit planning, separate from UI.

Experimental numeric rolls require an existing owned item or existing bonus
identity in its saved position. IDs, ownership, family/tier eligibility, bonus
counts, growth dependencies and equipment references retain their rules.
"""
from koei_editor.resources import read_json
from koei_editor.shared.experimental_limits import SIGNED_INT32_MAX, within_numeric_limits
import struct
from koei_editor.games.dw3.models import SaveError, fields
import koei_editor.games.dw3.bodyguard_growth as growth

GUARD_ITEMS={r['id']:r for r in read_json('bodyguard_items.json')['items']}
GUARD_WEAPONS={r['id']:r for r in read_json('bodyguard_weapons.json')['weapons']}
FAMILY_NAMES=('Sword','Spear','Pike','Bow','Crossbow')
ITEM_IDS={r['enum']:i for i,r in GUARD_ITEMS.items()}
WEAPON_IDS={r['enum']:i for i,r in GUARD_WEAPONS.items()}
CATEGORIES={'bodyguard','guard_item','guard_weapon','guard_weapon_slot'}
VALUE_STORAGE_MAXIMUM=SIGNED_INT32_MAX


def item_numeric_limits(item_id):
    """Normal-item minimum, supported maximum and IntProperty ceiling."""
    if type(item_id) is not int or item_id not in GUARD_ITEMS or GUARD_ITEMS[item_id]['kind']!='normal':
        raise SaveError('Choose a supported normal bodyguard item.')
    return 1,GUARD_ITEMS[item_id]['max_value'],VALUE_STORAGE_MAXIMUM


def skill_numeric_limits(weapon_id,item_id):
    """Known bonus minimum, supported tier maximum and IntProperty ceiling."""
    if type(weapon_id) is not int or weapon_id not in GUARD_WEAPONS:
        raise SaveError('Choose a supported bodyguard weapon.')
    row=GUARD_WEAPONS[weapon_id]
    if type(item_id) is not int or item_id not in row['allowed_skill_ids']:
        raise SaveError('Choose an eligible bodyguard weapon bonus.')
    return 1,max(row['allowed_values_by_guard_item_id'][str(item_id)]),VALUE_STORAGE_MAXIMUM


def _requests(document,changes):
    result={category:{} for category in CATEGORIES};seen=set()
    for change in changes:
        if not isinstance(change.category,str) or not isinstance(change.field,str) or type(change.index) is not int:
            raise SaveError('Edit category/field must be text and indexes must be integers.')
        if change.category not in CATEGORIES:continue
        ident=(change.category,change.index,change.field)
        if ident in seen:raise SaveError('Duplicate bodyguard changes.')
        seen.add(ident)
        if type(change.index) is not int:raise SaveError('Bodyguard indexes must be integers.')
        allowed={'bodyguard':{'SPoint','BGLevels','MemberItem','MemberWeapon'},
                 'guard_item':{'Owned','Value'},'guard_weapon':{'Owned','MaxBonuses'},
                 'guard_weapon_slot':{'Skills'}}[change.category]
        valid=(0<=change.index<len(document.records('GuardDataArray')) if change.category=='bodyguard' else
               change.index in GUARD_ITEMS and change.index<len(document.records('GuardEquipItemDataArray')) if change.category=='guard_item' else
               change.index in GUARD_WEAPONS if change.category=='guard_weapon' else 0<=change.index<len(document.records('GuardWeaponDataArray')))
        if not valid or change.field not in allowed:raise SaveError('Unsupported bodyguard edit index or field.')
        result[change.category].setdefault(change.index,{})[change.field]=change.value
    return result


def max_skills(weapon_id,skills=None,original_skills=None):
    """Maximize a known profile without replacing types or decreasing rolls.

    Calling with no existing skills returns the stock acquisition profile.
    Saved high rolls are kept only in their original logical/physical slot;
    callers must use the existing-record writer to retain physical positions.
    """
    if type(weapon_id) is not int or weapon_id not in GUARD_WEAPONS:raise SaveError('Unsupported bodyguard weapon.')
    stock=[dict(skill) for skill in GUARD_WEAPONS[weapon_id]['max_bonus_profile']]
    if skills is None:return stock
    baseline=skills if original_skills is None else original_skills
    skills=validate_skills(weapon_id,skills,baseline)
    values=GUARD_WEAPONS[weapon_id]['allowed_values_by_guard_item_id'];result=[]
    for index,skill in enumerate(skills):
        original=baseline[index] if index<len(baseline) else None
        saved=original['value'] if original and original['id']==skill['id'] else 0
        result.append({'id':skill['id'],'value':max(skill['value'],saved,max(values[str(skill['id'])]))})
    for skill in stock:
        if len(result)>=GUARD_WEAPONS[weapon_id]['max_skills']:break
        if not any(row['id']==skill['id'] for row in result):result.append(skill)
    return result


def validate_skills(weapon_id,skills,original_skills=()):
    if type(weapon_id) is not int or weapon_id not in GUARD_WEAPONS:raise SaveError('Unlock a supported bodyguard weapon first.')
    row=GUARD_WEAPONS[weapon_id]
    if not isinstance(skills,(list,tuple)) or len(skills)>row['max_skills']:
        raise SaveError('Bodyguard weapons support at most three bonuses.')
    if not skills and row['tier']!=1:
        raise SaveError('Dropped upgraded bodyguard weapons require at least one bonus.')
    result=[];seen=set()
    for index,skill in enumerate(skills):
        if not isinstance(skill,dict) or set(skill)!={'id','value'}:raise SaveError('Each weapon bonus needs an item ID and value.')
        item,value=skill['id'],skill['value']
        if type(item) is not int or item not in row['allowed_skill_ids'] or item in seen:
            raise SaveError('Duplicate or ineligible bodyguard weapon bonus.')
        original=original_skills[index] if index<len(original_skills) else None
        preserved=(type(value) is int and 0<value<=VALUE_STORAGE_MAXIMUM and skill==original)
        minimum,maximum,storage_maximum=skill_numeric_limits(weapon_id,item)
        experimental=(original is not None and original['id']==item and type(value) is int and value>maximum
                      and within_numeric_limits(value,minimum,maximum,storage_maximum=storage_maximum))
        if type(value) is not int or value not in row['allowed_values_by_guard_item_id'][str(item)] and not (preserved or experimental):
            raise SaveError('This bonus value cannot be generated for this weapon tier.')
        seen.add(item);result.append({'id':item,'value':value})
    return result


def validate_saved_skills(skills):
    """Validate representation separately from conservative authored drop rules.

    Existing positive, distinct normal bonuses can be read and preserved even
    when their family/tier values have no verified editing profile.
    """
    if not isinstance(skills,(list,tuple)) or len(skills)>3:
        raise SaveError('Bodyguard weapons support at most three saved bonuses.')
    seen=set()
    for skill in skills:
        if not isinstance(skill,dict) or set(skill)!={'id','value'}:
            raise SaveError('Each saved weapon bonus needs an item ID and value.')
        item,value=skill['id'],skill['value']
        if type(item) is not int or item not in GUARD_ITEMS or GUARD_ITEMS[item]['kind']!='normal' or item in seen:
            raise SaveError('Saved bodyguard weapon bonuses need distinct normal item IDs.')
        if type(value) is not int or not 1<=value<=0x7fffffff:
            raise SaveError('Saved bodyguard weapon bonus values must be positive integers.')
        seen.add(item)
    return skills


def item_state(document,changes=()):
    requests=_requests(document,changes)['guard_item'];result={}
    for i,row in enumerate(document.records('GuardEquipItemDataArray')):
        if i not in GUARD_ITEMS:continue  # Reserved/future rows are preserved.
        item=GUARD_ITEMS[i];record=fields(row);wanted=requests.get(i,{})
        enum=record['GuardEquipItemID']['value']
        editable=(enum in ('EGuardEquipItemID::NUM',item['enum']) and
                  record['EquipItemID']['value']=='EEquipItemID::NUM')
        if wanted and not editable:raise SaveError('This bodyguard item slot has an unknown identity and is view-only.')
        original_owned=enum==item['enum'];original_value=record['Value']['value']
        owned=wanted.get('Owned',original_owned);value=wanted.get('Value',original_value)
        if type(owned) is not bool:raise SaveError('Item ownership requires a boolean.')
        if 'Value' in wanted:
            preserved=original_owned and owned and type(value) is int and 0<value<=VALUE_STORAGE_MAXIMUM and value==original_value
            valid=(item['kind']=='normal' and within_numeric_limits(value,1,item['max_value'],storage_maximum=VALUE_STORAGE_MAXIMUM)
                   and (value<=item['max_value'] or original_owned and owned))
            if item['kind']!='normal' or not (valid or preserved):
                raise SaveError(f'{item["name"]} requires a verified normal-item value from 1 to {item["max_value"]}.')
            if 'Owned' not in wanted:owned=True
        if wanted and owned!=original_owned:
            if not owned or item['kind']=='rare':value=0
            elif 'Value' not in wanted:value=1
        elif wanted and not owned and 'Value' in wanted:
            raise SaveError('An unowned bodyguard item cannot receive a value.')
        result[i]={'owned':owned,'value':value,'editable':editable,
                   'reason':'' if editable else 'Unknown item placement; this record is preserved.'}
    return result


def max_item_value(document,item_id,changes=()):
    """Return a normal-drop maximum, retaining higher owned saved values."""
    if type(item_id) is not int or item_id not in GUARD_ITEMS or GUARD_ITEMS[item_id]['kind']!='normal' or item_id>=len(document.records('GuardEquipItemDataArray')):
        raise SaveError('Choose a supported normal bodyguard item present in this save.')
    current=item_state(document,changes)[item_id]
    if not current['editable']:raise SaveError(current['reason'])
    original=fields(document.records('GuardEquipItemDataArray')[item_id]);item=GUARD_ITEMS[item_id]
    saved=original['Value']['value'] if original['GuardEquipItemID']['value']==item['enum'] else 0
    return max(item['max_value'],saved,current['value'] if current['owned'] else 0)


def _skill_positions(row,count):
    """Keep existing positions, then prefer unused positions after them."""
    occupied=row['skill_positions'];last=max(occupied,default=-1)
    free=[i for i in range(last+1,9) if i not in occupied]
    free.extend(i for i in range(last+1) if i not in occupied)
    return (occupied+free)[:count]


def _skill_baseline(row,positions):
    saved=dict(zip(row['original_skill_positions'],row['original_skills']))
    return [saved.get(position) for position in positions]


def _set_skills(row,skills,positions=None):
    positions=_skill_positions(row,len(skills)) if positions is None else positions
    pairs=sorted(zip(positions,skills))
    row['skill_positions']=[position for position,skill in pairs]
    row['skills']=[dict(skill) for position,skill in pairs]
    row['preservation_baseline']=_skill_baseline(row,row['skill_positions'])


def weapon_state(document,changes=()):
    requests=_requests(document,changes);result=[]
    for index,row in enumerate(document.records('GuardWeaponDataArray')):
        record=fields(row);enum=record['WeaponID']['value']
        weapon_id=None if enum=='EWeaponID::NUM' else WEAPON_IDS.get(enum)
        skills=[];positions=[];unknown=False
        for physical,slot in enumerate(record['Skill']['value']['records']):
            skill=fields(slot);item=skill['GuardEquipItemID']['value']
            if item!='EGuardEquipItemID::NUM':
                if item not in ITEM_IDS:unknown=True
                else:skills.append({'id':ITEM_IDS[item],'value':skill['Value']['value']});positions.append(physical)
            elif skill['Value']['value']!=0:unknown=True
            if skill['EquipItemID']['value']!='EEquipItemID::NUM':unknown=True
        empty=(enum=='EWeaponID::NUM' and record['ID']['value']=='EWeaponID::NUM'
               and not skills and not unknown and record['Attr']['value']==0
               and len(record['Skill']['value']['records'])==9)
        identity_valid=(weapon_id is not None and record['ID']['value']==enum
               and record['DataID']['value']==index and record['Attr']['value']==0
               and len(record['Skill']['value']['records'])==9)
        known=identity_valid and not unknown
        editable=False;reason='Unlock a supported bodyguard weapon first.' if empty else 'Unknown saved weapon profile; this copy is view-only and preserved.'
        if known:
            try:
                validate_saved_skills(skills)
                validate_skills(weapon_id,skills,skills)
                editable=True;reason=''
            except SaveError:
                reason='This copy has bonuses outside the verified drop profiles. Its bonuses are view-only and preserved.'
        result.append({'slot':index,'weapon_id':weapon_id,'data_id':record['DataID']['value'],
                       'skills':skills,'skill_positions':positions,'original_skills':[dict(s) for s in skills],
                       'original_skill_positions':list(positions),'preservation_baseline':[dict(s) for s in skills],
                       'editable':editable,'reason':reason,'empty':empty,'identity_valid':identity_valid})
    for weapon_id,wanted in requests['guard_weapon'].items():
        for value in wanted.values():
            if value is not True:raise SaveError('Bodyguard weapon actions require True; removal is unsupported.')
        owned=[row for row in result if row['weapon_id']==weapon_id]
        if wanted.get('Owned') and not owned:
            blank=next((row for row in result if row['empty']),None)
            if blank is None:raise SaveError('Bodyguard weapon inventory is full. No existing weapon will be replaced.')
            blank.update(weapon_id=weapon_id,data_id=blank['slot'],editable=True,reason='',empty=False,identity_valid=True)
            _set_skills(blank,max_skills(weapon_id));owned=[blank]
        if wanted.get('MaxBonuses'):
            if not owned:raise SaveError('Unlock the bodyguard weapon before maximizing it.')
            for row in owned:
                if row['editable']:_set_skills(row,max_skills(weapon_id,row['skills'],row['preservation_baseline']))
    for index,wanted in requests['guard_weapon_slot'].items():
        if not result[index]['editable']:raise SaveError(result[index]['reason'])
        # A pending Max can add a slot before a late saved bonus. Compare high
        # preservation against physical saved positions, not compact indexes.
        if not isinstance(wanted['Skills'],(list,tuple)):raise SaveError('Bodyguard weapon bonuses must be a list.')
        positions=_skill_positions(result[index],len(wanted['Skills']))
        skills=validate_skills(result[index]['weapon_id'],wanted['Skills'],_skill_baseline(result[index],positions))
        _set_skills(result[index],skills,positions)
    return result


def team_state(document,index,changes=()):
    if type(index) is not int or not 0<=index<len(document.records('GuardDataArray')):raise SaveError('Choose a bodyguard team present in this save.')
    wanted=_requests(document,changes)['bodyguard'].get(index,{})
    original=fields(document.records('GuardDataArray')[index])
    merit=wanted.get('SPoint',original['SPoint']['value'])
    levels=wanted.get('BGLevels',original['BGLevels']['value']['values'])
    growth_editable=True;growth_reason=''
    try:
        if 'BGLevels' in wanted:
            levels=growth.automatic_levels(merit,levels)
        elif 'SPoint' in wanted:
            if merit<original['SPoint']['value']:
                raise ValueError('Bodyguard Merit can only be increased in this version.')
            levels=growth.advance_automatic_levels(merit,levels)
        else:
            levels=list(growth.validate_saved_growth(merit,levels))
    except ValueError as error:
        if 'SPoint' in wanted or 'BGLevels' in wanted:raise SaveError(str(error)) from error
        growth_editable=False;growth_reason=str(error)
    enum=original['MemberItem']['value']
    item=wanted.get('MemberItem',None if enum=='EGuardEquipItemID::NUM' else ITEM_IDS.get(enum))
    if item is not None and (type(item) is not int or item not in GUARD_ITEMS):raise SaveError('Unsupported equipped bodyguard item.')
    weapons=wanted.get('MemberWeapon',original['MemberWeapon']['value']['values'])
    if 'MemberWeapon' in wanted and (not isinstance(weapons,(list,tuple)) or len(weapons)!=10 or any(type(i) is not int for i in weapons)):
        raise SaveError('Bodyguard weapon choices must contain the ten saved integer references.')
    if 'MemberWeapon' in wanted and list(weapons)[5:]!=original['MemberWeapon']['value']['values'][5:]:
        raise SaveError('Unmapped extra bodyguard weapon references must be preserved.')
    return {'SPoint':merit,'BGLevels':list(levels),'MemberItem':item,'MemberWeapon':list(weapons),
            'growth_editable':growth_editable,'growth_reason':growth_reason}


def best_weapon_refs(document,changes=()):
    pool=weapon_state(document,changes);result=[]
    for family in range(5):
        options=[row for row in pool if row['identity_valid'] and GUARD_WEAPONS[row['weapon_id']]['family_index']==family]
        if not options:raise SaveError(f'No owned {FAMILY_NAMES[family]} bodyguard weapon.')
        best=max(options,key=lambda row:(GUARD_WEAPONS[row['weapon_id']]['tier'],sum(s['value'] for s in row['skills']),-row['slot']))
        result.append(best['slot'])
    return result


def plan_bodyguard_changes(document,changes,add_property):
    requests=_requests(document,changes)
    if not any(requests.values()):return
    items=item_state(document,changes);pool=weapon_state(document,changes)
    teams=[team_state(document,i,changes) for i in range(len(document.records('GuardDataArray')))]
    # Validate only references that the user changes or removes. Unchanged
    # historical/future relationships must not block an unrelated team edit.
    for index,team in enumerate(teams):
        wanted=requests['bodyguard'].get(index,{})
        item=team['MemberItem']
        if ('MemberItem' in wanted or item in requests['guard_item'] and not items.get(item,{}).get('owned')):
            if item is not None and (item not in items or not items[item]['owned']):
                raise SaveError('An equipped bodyguard item must be owned. Unequip it before removing it.')
        if 'MemberWeapon' in wanted:
            original_refs=fields(document.records('GuardDataArray')[index])['MemberWeapon']['value']['values']
            for family,slot in enumerate(team['MemberWeapon'][:5]):
                if slot==original_refs[family]:continue
                if slot==-1:continue
                if not 0<=slot<len(pool) or not pool[slot]['identity_valid'] or GUARD_WEAPONS[pool[slot]['weapon_id']]['family_index']!=family:
                    raise SaveError('Equipped bodyguard weapon references must point to an owned weapon of the correct family.')
    for i,wanted in requests['guard_item'].items():
        if items[i]['owned']:continue
        for row in document.records('PCSaveDataArray'):
            if fields(row)['BGMusouEquipItem']['value']==GUARD_ITEMS[i]['enum']:
                raise SaveError('This bodyguard item is referenced by an officer bodyguard-Musou setup and cannot be removed safely.')
    def integer(prop,value,reason):add_property(prop,struct.pack('<i',value),reason)
    def enum(prop,value,reason):
        data=value.encode('utf-8')+b'\0';add_property(prop,struct.pack('<i',len(data))+data,reason)
    def array(prop,values,reason):add_property(prop,struct.pack('<i',len(values))+struct.pack('<'+'i'*len(values),*values),reason)
    for i in requests['guard_item']:
        original=fields(document.records('GuardEquipItemDataArray')[i]);state=items[i]
        enum(original['GuardEquipItemID'],GUARD_ITEMS[i]['enum'] if state['owned'] else 'EGuardEquipItemID::NUM',f'{GUARD_ITEMS[i]["name"]}: ownership')
        integer(original['Value'],state['value'],f'{GUARD_ITEMS[i]["name"]}: verified item roll')
    for i,wanted in requests['bodyguard'].items():
        original=fields(document.records('GuardDataArray')[i]);state=teams[i]
        if 'SPoint' in wanted:integer(original['SPoint'],state['SPoint'],f'Bodyguard team {i+1}: Merit')
        if 'BGLevels' in wanted or 'SPoint' in wanted:
            array(original['BGLevels'],state['BGLevels'],f'Bodyguard team {i+1}: growth and earned Count/AI')
        if 'MemberItem' in wanted:
            item=state['MemberItem']
            enum(original['MemberItem'],'EGuardEquipItemID::NUM' if item is None else GUARD_ITEMS[item]['enum'],f'Bodyguard team {i+1}: equipped item')
        if 'MemberWeapon' in wanted:array(original['MemberWeapon'],state['MemberWeapon'],f'Bodyguard team {i+1}: equipped weapon references')
        if 'BGLevels' in wanted or 'SPoint' in wanted:
            old_count=growth.derive_stats(original['BGLevels']['value']['values'])['member_count']
            new_count=growth.derive_stats(state['BGLevels'])['member_count']
            if old_count!=new_count:
                for officer,row in enumerate(document.records('PCSaveDataArray')[:42]):
                    record=fields(row);count=record['MemCnt']['value']
                    if record['BGTeamID']['value']==i and (count==old_count or count>new_count):
                        integer(record['MemCnt'],new_count,f'Officer {officer}: synchronize chosen bodyguard count after team growth')
    def write_weapon(record,state,reason,new=False,data_id=None):
        if new:
            for name in ('ID','WeaponID'):enum(record[name],GUARD_WEAPONS[state['weapon_id']]['enum'],reason+' identity')
            add_property(record['Attr'],struct.pack('<q',0),reason+' guard attribute flags')
            integer(record['DataID'],state['data_id'] if data_id is None else data_id,reason+' inventory/collection reference')
        records=record['Skill']['value']['records']
        targets=dict(zip(state['skill_positions'],state['skills']))
        for index,slot in enumerate(records):
            target=fields(slot);skill=targets.get(index)
            enum(target['EquipItemID'],'EEquipItemID::NUM',reason+' ordinary item sentinel')
            enum(target['GuardEquipItemID'],'EGuardEquipItemID::NUM' if skill is None else GUARD_ITEMS[skill['id']]['enum'],reason+' bodyguard bonus ID')
            integer(target['Value'],0 if skill is None else skill['value'],reason+' legitimate bonus value')
    for state,row in zip(pool,document.records('GuardWeaponDataArray')):
        if state['weapon_id'] is None:continue
        original=fields(row);new=original['WeaponID']['value']=='EWeaponID::NUM'
        requested=requests['guard_weapon'].get(state['weapon_id'],{})
        if state['editable'] and (new or requested.get('MaxBonuses') or state['slot'] in requests['guard_weapon_slot']):
            write_weapon(original,state,f'Bodyguard {GUARD_WEAPONS[state["weapon_id"]]["name"]} copy {state["slot"]+1}',new)
    for weapon_id,wanted in requests['guard_weapon'].items():
        if not wanted.get('Owned'):continue
        if weapon_id>=len(document.records('CollectedWeaponDataArray')):
            raise SaveError('The weapon collection array has no slot for this bodyguard weapon.')
        record=fields(document.records('CollectedWeaponDataArray')[weapon_id])
        if record['WeaponID']['value']=='EWeaponID::NUM':
            first=next((state for state in pool if state['weapon_id']==weapon_id and state['editable']),None)
            # Do not manufacture a cache template from an unverified existing copy.
            if first is None:continue
            write_weapon(record,first,f'Bodyguard {GUARD_WEAPONS[weapon_id]["name"]}: first acquisition collection cache',True,weapon_id)
        elif record['WeaponID']['value']!=GUARD_WEAPONS[weapon_id]['enum']:
            raise SaveError('Bodyguard weapon collection cache has an unexpected identity.')
