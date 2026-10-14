"""Verified byte patches, round-trip validation, backups and atomic output."""
from koei_editor.resources import data_file, read_json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import struct
import uuid
from koei_editor.games.dw3.models import Change, Patch, SaveDocument, SaveError, fields
from koei_editor.games.dw3.save_parser import parse_bytes, safe_path, read_save, MAX_SIZE
import koei_editor.games.dw3.save_codec as save_codec
import koei_editor.games.dw3.bodyguard_editor as bodyguard_editor
import koei_editor.games.dw3.officer_weapon_editor as officer_weapon_editor
import koei_editor.games.dw3.progression_editor as progression_editor
import koei_editor.games.dw3.weapon_collection as weapon_collection
import koei_editor.games.dw3.bodyguard_customization as bodyguard_customization
import koei_editor.games.dw3.collection_editor as collection_editor
import koei_editor.games.dw3.musou_slots as musou_slots
from koei_editor.shared.experimental_limits import within_numeric_limits

CAPS={'SPoint':99999}  # Only limits proved from game code are enabled.
INT32_MAX = 0x7fffffff
OFFICER_FIELDS=('SPoint','MaxHealth','MaxMusou','Attack','Defence')
METADATA=read_json('game_metadata.json')
ITEMS={item['id']:item for item in METADATA['items']}
UNIQUE_WEAPONS={item['weapon_id']:item for item in read_json('unique_weapons.json')['weapons']}
ITEM_CAPS={}
if data_file('item_limits.json').is_file():
    ITEM_CAPS={int(k):int(v) for k,v in read_json('item_limits.json')['maxima'].items()}

def load_verified_limits():
    path=data_file('verified_limits.json')
    if path.is_file():
        data=read_json('verified_limits.json')
        for name,entry in data.get('officers',{}).items():
            if name in OFFICER_FIELDS and entry.get('confirmed') is True:
                CAPS[name]=int(entry['max'])

load_verified_limits()

def plan_changes(document: SaveDocument, changes: list[Change]) -> list[Patch]:
    patches=[]; seen=set(); item_changes={}; size_deltas={}
    all_properties=[]
    def walk(properties):
        for prop in properties:
            all_properties.append(prop)
            value=prop['value']
            if isinstance(value,list) and value and isinstance(value[0],dict):walk(value)
            elif isinstance(value,dict) and 'records' in value:
                for record in value['records']:walk(record)
    walk(document.parsed['properties'])
    def add_property(prop,after,reason):
        offset=prop['data_offset'];before=document.plaintext[offset:offset+prop['data_size']]
        # Whole bool-array actions and individual unlock controls may share
        # the same array. Merge compatible earlier byte edits, never overlap.
        if prop['type']=='ArrayProperty(BoolProperty)':
            covered=[p for p in patches if offset<=p.offset and p.offset+len(p.before)<=offset+len(before)]
            if covered:
                merged=bytearray(after)
                for patch in covered:
                    relative=patch.offset-offset
                    if len(patch.before)!=len(patch.after) or relative+len(patch.after)>len(merged):
                        raise SaveError('Conflicting array size changes.')
                    segment=bytes(merged[relative:relative+len(patch.after)])
                    if segment not in (patch.before,patch.after):
                        raise SaveError('Conflicting unlock choices in this pending batch.')
                    merged[relative:relative+len(patch.after)]=patch.after
                    patches.remove(patch)
                after=bytes(merged)
        if before==after:return
        patches.append(Patch(offset,before,after,reason))
        delta=len(after)-len(before)
        if delta:
            for parent in all_properties:
                if parent['data_offset']<=offset and offset+len(before)<=parent['data_offset']+parent['data_size']:
                    size_deltas[parent['size_offset']]=size_deltas.get(parent['size_offset'],0)+delta
    def add_insertion(offset,after,reason):
        if type(offset) is not int or not 4<=offset<len(document.plaintext):
            raise SaveError('Unsupported property insertion position.')
        if not isinstance(after,bytes) or not after:raise SaveError('Property insertions require nonempty bytes.')
        for previous in patches:
            if previous.offset==offset and not previous.before:
                previous_index=patches.index(previous)
                patches[previous_index]=Patch(offset,b'',previous.after+after,previous.reason+'; '+reason)
                break
        else:patches.append(Patch(offset,b'',after,reason))
        # Nested lazy tags contribute to every enclosing tagged payload size.
        for parent in all_properties:
            if parent['data_offset']<=offset<parent['data_offset']+parent['data_size']:
                size_deltas[parent['size_offset']]=size_deltas.get(parent['size_offset'],0)+len(after)
    for change in changes:
        if not isinstance(change,Change) or not isinstance(change.category,str) or not isinstance(change.field,str) or type(change.index) is not int:
            raise SaveError('Edits need a supported category, field and integer index.')
        ident=(change.category,change.index,change.field)
        if ident in seen: raise SaveError('Duplicate changes.')
        seen.add(ident)
        if change.category in bodyguard_editor.CATEGORIES or change.category in officer_weapon_editor.CATEGORIES or change.category in progression_editor.CATEGORIES:
            continue
        if change.category=='unique_weapon' or change.category in weapon_collection.CATEGORIES or change.category in bodyguard_customization.CATEGORIES or change.category in collection_editor.CATEGORIES or change.category in musou_slots.CATEGORIES:
            continue
        if change.category=='item':
            if type(change.index) is not int or change.index not in ITEMS or change.field not in ('Owned','Value'):
                raise SaveError('Unsupported equipment item index or field.')
            item_changes.setdefault(change.index,{})[change.field]=change.value
            continue
        if change.category=='officer':
            records='PCSaveDataArray'
            if not 0<=change.index<min(42,len(document.records(records))):
                raise SaveError('Choose a playable officer record present in this save.')
            if change.field not in CAPS:
                raise SaveError('This permanent stat limit has not been verified; editing is disabled.')
            low=1 if change.field in ('MaxHealth','MaxMusou') else 0
            prop=fields(document.records(records)[change.index])[change.field]
            unchanged = type(change.value) is int and change.value == prop['value']
            if not within_numeric_limits(change.value, low, CAPS[change.field], storage_maximum=INT32_MAX) and not unchanged:
                raise SaveError(f'{change.field}: supported {low}–{CAPS[change.field]}; experimental storage maximum {INT32_MAX}.')
            offset=prop['data_offset']; after=struct.pack('<i',change.value)
            reason=f'{change.category.title()} {change.index}: {change.field} {prop["value"]} -> {change.value}'
        elif change.category=='unlock':
            counts={'CanUseCharaArray':42,'CanUseScenarioArray':108}
            if change.field not in counts or type(change.index) is not int or not 0<=change.index<counts[change.field]:
                raise SaveError('This unlock index is not supported.')
            if type(change.value) is not bool: raise SaveError('Unlocks require a boolean.')
            prop=document.properties[change.field]
            if prop['type']!='ArrayProperty(BoolProperty)': raise SaveError('Unsupported unlock type.')
            if change.index>=len(prop['value']['values']):
                raise SaveError('This unlock index is absent from the save.')
            offset=prop['data_offset']+4+change.index; after=bytes([change.value])
            reason=f'{change.field}[{change.index}] -> {change.value}'
        else: raise SaveError('This edit category is not yet supported.')
        before=document.plaintext[offset:offset+len(after)]
        if before!=after: patches.append(Patch(offset,before,after,reason))
    for index,requested in item_changes.items():
        if index>=len(document.records('EquipItemDataArray')):
            raise SaveError('This item slot is absent from the save.')
        item=ITEMS[index];record=fields(document.records('EquipItemDataArray')[index])
        expected='EEquipItemID::'+item['enum']
        old_enum=record['EquipItemID']['value']
        if old_enum not in ('EEquipItemID::NUM',expected) or record['GuardEquipItemID']['value']!='EGuardEquipItemID::NUM':
            raise SaveError('This item has an unrecognized placement and is view-only.')
        owned=requested.get('Owned',old_enum==expected)
        if type(owned) is not bool:raise SaveError('Item ownership requires a boolean.')
        value=requested.get('Value',record['Value']['value'])
        original_owned=old_enum==expected
        if 'Value' in requested:
            if item['kind']!='normal' or index not in ITEM_CAPS:raise SaveError('The maximum for this item has not been verified.')
            preserved_high=(original_owned and owned and type(value) is int and value>0
                            and value==record['Value']['value'])
            allowed = within_numeric_limits(value, 1, ITEM_CAPS[index], storage_maximum=INT32_MAX)
            if type(value) is int and value > ITEM_CAPS[index] and not (original_owned and owned):
                allowed = False
            if not allowed and not preserved_high:
                raise SaveError(f'{item["name"]}: supported 1–{ITEM_CAPS[index]}; experimental storage maximum {INT32_MAX}, or its unchanged saved value.')
            if 'Owned' not in requested:owned=True
        if owned!=original_owned:
            if not owned or item['kind']=='rare':value=0
            elif 'Value' not in requested:value=1  # Native minimum for newly acquired normal items.
        new_enum=expected if owned else 'EEquipItemID::NUM'
        encoded=new_enum.encode('utf-8')+b'\0'
        add_property(record['EquipItemID'],struct.pack('<i',len(encoded))+encoded,f'{item["name"]}: owned -> {owned}')
        add_property(record['Value'],struct.pack('<i',value),f'{item["name"]}: value -> {value}')
    bodyguard_editor.plan_bodyguard_changes(document,changes,add_property)
    officer_weapon_editor.plan_weapon_roll_changes(document,changes,add_property)
    weapon_collection.plan_weapon_collection_changes(document,changes,add_property)
    progression_editor.plan_progression_changes(document,changes,add_property,add_insertion)
    bodyguard_customization.plan_customization_changes(document,changes,add_property,add_insertion)
    collection_editor.plan_collection_changes(document,changes,add_property,add_insertion)
    musou_slots.plan_slot_changes(document,changes,add_property)
    for offset,delta in size_deltas.items():
        before=document.plaintext[offset:offset+4]
        value=struct.unpack('<i',before)[0]+delta
        patches.append(Patch(offset,before,struct.pack('<i',value),'Regenerate enclosing tagged-property byte size'))
    patches.sort(key=lambda p:p.offset)
    for a,b in zip(patches,patches[1:]):
        if a.offset+len(a.before)>b.offset: raise SaveError('Overlapping patches.')
    return patches

def _same_parsed_tree(saved, current):
    """Compare verified parse trees strictly, preserving nonfinite float fields.

    A fresh decode creates different NaN objects, which ordinary container
    equality rejects. The original encrypted/plaintext comparison still checks
    their exact payload bytes; this comparison checks structure and offsets.
    """
    if type(saved) is not type(current):
        return False
    if isinstance(saved, dict):
        if (saved.keys()!=current.keys() or
                any(type(key) is not str for key in saved) or
                any(type(key) is not str for key in current)):
            return False
        return all(_same_parsed_tree(value,current[key]) for key,value in saved.items())
    if isinstance(saved, list):
        return len(saved)==len(current) and all(_same_parsed_tree(a,b) for a,b in zip(saved,current))
    if isinstance(saved, float):
        if math.isnan(saved):
            return math.isnan(current)
        if saved==0 and current==0:
            return math.copysign(1,saved)==math.copysign(1,current)
    return saved==current


def serialize(document: SaveDocument, changes: list[Change]=()) -> tuple[bytes,dict]:
    fresh=parse_bytes(document.encrypted,document.source)
    if fresh.plaintext!=document.plaintext or not _same_parsed_tree(fresh.parsed,document.parsed):
        raise SaveError('Document bytes or offsets changed outside verified edit operations.')
    patches=plan_changes(document,list(changes))
    original_payload_size=struct.unpack_from('>I',document.plaintext)[0]
    plain=bytearray(document.plaintext[:4+original_payload_size])
    for p in reversed(patches):
        if plain[p.offset:p.offset+len(p.before)]!=p.before: raise SaveError('Stale patch data.')
        plain[p.offset:p.offset+len(p.before)]=p.after
    payload_size=len(plain)-4
    struct.pack_into('>I',plain,0,payload_size)
    plain.extend(bytes((-len(plain))%16))
    raw=save_codec.encrypt(bytes(plain))
    reread=parse_bytes(raw)
    if reread.plaintext!=bytes(plain): raise SaveError('Edited save failed decode validation.')
    changed_blocks=[i//16 for i in range(0,max(len(raw),len(document.encrypted)),16) if raw[i:i+16]!=document.encrypted[i:i+16]]
    resized=payload_size!=original_payload_size
    if not resized:
        # Enum replacements can relocate fields but cancel in total length.
        # Compare the complete plaintext, rather than assuming old offsets
        # still describe every changed byte in that equal-size result.
        expected_blocks=sorted({i//16 for i,(before,after) in enumerate(zip(document.plaintext,plain)) if before!=after})
        if changed_blocks!=expected_blocks: raise SaveError('Unexpected encrypted blocks changed.')
    elif patches:
        first_block=min(p.offset for p in patches)//16
        if raw[16:first_block*16]!=document.encrypted[16:first_block*16]:
            raise SaveError('Unrelated encrypted prefix changed during resizing.')
    audit={'source_sha256':hashlib.sha256(document.encrypted).hexdigest(),
           'output_sha256':hashlib.sha256(raw).hexdigest(),'plaintext_changes':[
               {'offset':p.offset,'old_length':len(p.before),'length':len(p.after),'before_hex':p.before.hex(),
                'after_hex':p.after.hex(),'reason':p.reason} for p in patches],
           'changed_aes_blocks':changed_blocks,'source_payload_size':original_payload_size,'output_payload_size':payload_size,
           'resized':resized,'fields_relocated':any(len(p.before)!=len(p.after) for p in patches),'unchanged_bytes_preserved':True,
           'game_load_validation':'not performed'}
    audit['preserved_compatibility_notes']=list(document.compatibility_warnings)
    return raw,audit

def _atomic_write(data: bytes,path: Path,overwrite=False,expected_bytes=None):
    path=safe_path(path)
    if path.exists() and not overwrite: raise FileExistsError('Destination exists.')
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if temp.read_bytes()!=data: raise SaveError('Temporary output verification failed.')
        if overwrite:
            if expected_bytes is None:
                raise SaveError('Replacing a copy requires the bytes that were backed up.')
            # Recheck immediately before commit: serialization/report creation
            # can take time, during which another editor may change the copy.
            with path.open('rb') as stream:
                current=stream.read(MAX_SIZE+1)
            if current!=expected_bytes:
                raise SaveError('The destination changed while saving. Reopen it before replacing it.')
            os.replace(temp,path)
        else:
            # On Windows os.rename fails if destination exists, including races.
            # It also works on FAT/exFAT, which lack hard links.
            if os.name == 'nt':
                os.rename(temp,path)
            else:
                # Link creation is atomic and refuses an existing destination.
                os.link(temp,path)
                temp.unlink()
    finally:
        if temp.exists(): temp.unlink()
    return path

def backup_save(document: SaveDocument,folder: Path | None=None) -> Path:
    if document.source is None and folder is None: raise SaveError('Select a backup folder.')
    folder=Path(folder) if folder else document.source.parent/'DW3EditorBackups'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path=folder/f'GameStatusData.{stamp}.{uuid.uuid4().hex[:8]}.sav'
    path=_atomic_write(document.encrypted,path)
    metadata={'size_bytes':len(document.encrypted),'sha256':hashlib.sha256(document.encrypted).hexdigest()}
    try:
        _atomic_write(json.dumps(metadata,indent=2).encode(),path.with_suffix('.json'))
    except Exception:
        # Only this newly created, uniquely named incomplete backup is removed.
        try:path.unlink()
        except OSError:pass
        raise
    return path

def write_save(document: SaveDocument,path: Path,changes: list[Change]=(),overwrite=False) -> tuple[Path,dict]:
    path=safe_path(path)
    if path.suffix.lower()!='.sav':raise SaveError('Edited saves must use the .sav extension.')
    expected_bytes=None
    if document.source and path==document.source:
        if not overwrite: raise SaveError('Replacing the opened copy requires confirmation.')
        if not path.exists() or read_save(path).encrypted!=document.encrypted:
            raise SaveError('The opened copy changed on disk. Reopen it before replacing it.')
        backup_save(document)
        expected_bytes=document.encrypted
    elif path.exists() and overwrite:
        previous=read_save(path)
        backup_save(previous)
        expected_bytes=previous.encrypted
    else:
        # A destination that did not exist at selection time may appear later.
        # Never replace such a file; it was neither reviewed nor backed up.
        overwrite=False
    raw,audit=serialize(document,changes)
    # Prepare the change report before the save's final commit. If report
    # creation fails, the destination is still untouched. Never raise an
    # "unsaved" error after a successful save commit.
    audit_path=path.with_name(path.name+'.'+uuid.uuid4().hex[:8]+'.changes.json')
    _atomic_write(json.dumps(audit,indent=2).encode(),audit_path)
    try:
        _atomic_write(raw,path,overwrite,expected_bytes=expected_bytes)
    except Exception:
        try:
            audit_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path,audit

def restore_backup(backup: Path,destination: Path) -> Path:
    backup=safe_path(backup)
    destination=safe_path(destination)
    if Path(destination).suffix.lower()!='.sav':raise SaveError('Restore to a new .sav copy.')
    raw=read_save(backup).encrypted
    manifest=safe_path(backup.with_suffix('.json'))
    with manifest.open('rb') as stream:
        data=stream.read(4097)
    if len(data)>4096:raise SaveError('Backup manifest exceeds the supported size.')
    try:metadata=json.loads(data)
    except (ValueError,UnicodeError) as error:raise SaveError('Backup manifest is damaged.') from error
    if not isinstance(metadata,dict):raise SaveError('Backup manifest must contain an object.')
    if metadata.get('sha256')!=hashlib.sha256(raw).hexdigest() or metadata.get('size_bytes')!=len(raw):
        raise SaveError('Backup hash or size does not match its manifest.')
    return _atomic_write(raw,destination)
