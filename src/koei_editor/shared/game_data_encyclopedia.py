"""Read-only, edition-scoped reference data and its provenance contract."""
from koei_editor.resources import read_json


SCHEMA_VERSION = 1
ALLOWED_LICENSES = frozenset({'MIT', 'CC BY-SA 3.0'})
_DATASET_KEYS = frozenset({
    'schema_version', 'dataset_license', 'dataset_license_note', 'sources',
    'games', 'entities',
})
_SOURCE_REQUIRED = frozenset({
    'id', 'title', 'uri', 'license', 'license_uri', 'attribution', 'scope',
})
_GAME_KEYS = frozenset({
    'id', 'title', 'edition', 'platform', 'profile_source_id', 'scope_note',
})
_ENTITY_REQUIRED = frozenset({
    'id', 'game_id', 'edition', 'kind', 'name', 'field_sources',
})
_ENTITY_OPTIONAL = frozenset({'native_id', 'summary', 'attributes', 'relationships'})


def _text(value):
    return type(value) is str and bool(value.strip())


def validate_dataset(data):
    """Validate the static feed's edition, source, and cross-reference contract.

    Values are facts for reference display only; this validator does not promote
    entries to save-editor controls or certify game support.
    """
    if type(data) is not dict or set(data) != _DATASET_KEYS:
        raise ValueError('Invalid encyclopedia dataset envelope.')
    if type(data['schema_version']) is not int or data['schema_version'] != SCHEMA_VERSION:
        raise ValueError('Unsupported encyclopedia schema version.')
    if (type(data['dataset_license']) is not str
            or data['dataset_license'] not in ALLOWED_LICENSES
            or not _text(data['dataset_license_note'])):
        raise ValueError('Invalid encyclopedia dataset license declaration.')
    if type(data['sources']) is not list or type(data['games']) is not list or type(data['entities']) is not list:
        raise ValueError('Encyclopedia sources, games, and entities must be lists.')

    sources = {}
    for source in data['sources']:
        if type(source) is not dict:
            raise ValueError('Invalid encyclopedia source row.')
        optional = {'revision', 'accessed_on'}
        if not _SOURCE_REQUIRED <= set(source) or set(source) - _SOURCE_REQUIRED - optional:
            raise ValueError('Invalid encyclopedia source fields.')
        if not all(_text(source[key]) for key in _SOURCE_REQUIRED):
            raise ValueError('Encyclopedia sources need titles, links, licenses, attribution, and scope.')
        if (source['license'] not in ALLOWED_LICENSES
                or not source['uri'].startswith('https://')
                or not source['license_uri'].startswith('https://')):
            raise ValueError('Encyclopedia source license or URL is not allowed.')
        if (('revision' in source) == ('accessed_on' in source)
                or ('revision' in source and not _text(source['revision']))
                or ('accessed_on' in source and not _text(source['accessed_on']))):
            raise ValueError('Each encyclopedia source needs one pinned revision or access date.')
        if source['id'] in sources:
            raise ValueError('Duplicate encyclopedia source ID.')
        sources[source['id']] = source

    games = {}
    for game in data['games']:
        if type(game) is not dict or set(game) != _GAME_KEYS:
            raise ValueError('Invalid encyclopedia game profile.')
        if not all(_text(game[key]) for key in _GAME_KEYS):
            raise ValueError('Encyclopedia game profiles require exact edition metadata.')
        if game['id'] in games or game['profile_source_id'] not in sources:
            raise ValueError('Duplicate game profile or missing profile provenance.')
        games[game['id']] = game

    entity_ids = set()
    native_ids = set()
    targets = []
    for entity in data['entities']:
        if type(entity) is not dict:
            raise ValueError('Invalid encyclopedia entity.')
        keys = set(entity)
        if not _ENTITY_REQUIRED <= keys or keys - _ENTITY_REQUIRED - _ENTITY_OPTIONAL:
            raise ValueError('Invalid encyclopedia entity fields.')
        if not all(_text(entity[key]) for key in ('id', 'game_id', 'edition', 'kind', 'name')):
            raise ValueError('Encyclopedia entities need stable IDs and exact edition labels.')
        game = games.get(entity['game_id'])
        if game is None or entity['edition'] != game['edition']:
            raise ValueError('Encyclopedia entity belongs to an unknown or mismatched edition.')
        if entity['id'] in entity_ids:
            raise ValueError('Duplicate encyclopedia entity ID.')
        entity_ids.add(entity['id'])
        if 'native_id' in entity:
            native_id = entity['native_id']
            if type(native_id) is not int or native_id < 0:
                raise ValueError('Native IDs must be non-negative integers.')
            native_key = (entity['game_id'], entity['edition'], entity['kind'], native_id)
            if native_key in native_ids:
                raise ValueError('Duplicate native ID within a game edition and entity kind.')
            native_ids.add(native_key)
        if 'summary' in entity and not _text(entity['summary']):
            raise ValueError('Entity summaries must be non-empty text.')
        if 'attributes' in entity and type(entity['attributes']) is not dict:
            raise ValueError('Entity attributes must be an object.')
        field_sources = entity['field_sources']
        if type(field_sources) is not dict:
            raise ValueError('Every encyclopedia entity needs field-level provenance.')
        required_fields = {'game_id', 'edition', 'kind', 'name'}
        if 'native_id' in entity:
            required_fields.add('native_id')
        if 'summary' in entity:
            required_fields.add('summary')
        if 'attributes' in entity:
            required_fields.update(f'attributes.{key}' for key in entity['attributes'])
        if set(field_sources) != required_fields:
            raise ValueError('Encyclopedia facts are missing field-level source references.')
        if any(type(source_id) is not str or source_id not in sources
               for source_id in field_sources.values()):
            raise ValueError('Encyclopedia field provenance references an unknown source.')
        relationships = entity.get('relationships', [])
        if type(relationships) is not list:
            raise ValueError('Entity relationships must be a list.')
        for relation in relationships:
            if (type(relation) is not dict
                    or set(relation) != {'type', 'entity_id', 'source_id'}
                    or not all(_text(relation[key]) for key in ('type', 'entity_id', 'source_id'))
                    or relation['source_id'] not in sources):
                raise ValueError('Entity relationships need a type, target, and source.')
            targets.append((entity['game_id'], entity['edition'], relation['entity_id']))

    entities_by_id = {entity['id']: entity for entity in data['entities']}
    for game_id, edition, target in targets:
        if target not in entities_by_id:
            raise ValueError('Encyclopedia relationship target does not exist.')
        target_row = entities_by_id[target]
        if target_row['game_id'] != game_id or target_row['edition'] != edition:
            raise ValueError('Encyclopedia relationship crosses game editions.')
    return data


def load_game_data_encyclopedia():
    """Load and validate the bundled reference feed from package resources."""
    return validate_dataset(read_json('game_data_encyclopedia.json'))
