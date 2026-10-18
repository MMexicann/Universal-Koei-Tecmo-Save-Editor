"""Lint an explicitly selected data-only plugin directory without enabling it."""
import argparse
import json

from koei_editor.game_registry import ALL_ADAPTERS
from koei_editor.shared.community_plugins import PluginCatalog, PluginError, discover_plugins


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', help='Directory containing *.plugin.json files (not recursive).')
    args = parser.parse_args(argv)
    try:
        candidates = discover_plugins(args.directory, known_game_ids=(game.id for game in ALL_ADAPTERS))
        catalog = PluginCatalog(candidates, reserved_ids=(game.id for game in ALL_ADAPTERS))
    except PluginError as error:
        print(json.dumps({'valid': False, 'error': str(error)}))
        return 1
    records = []
    for entry in catalog.entries:
        candidate = entry.candidate
        manifest = candidate.manifest
        records.append({'file': candidate.filename, 'id': manifest.id if manifest else None,
                        'api': manifest.api if manifest else None, 'sha256': candidate.sha256,
                        'capabilities': manifest.capabilities if manifest else (),
                        'enabled': entry.enabled, 'error': entry.error})
    valid = bool(records) and not any(record['error'] for record in records)
    print(json.dumps({'valid': valid, 'plugins': records}, indent=2))
    return 0 if valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
