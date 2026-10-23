"""Headless commands for the Universal Koei Tecmo Game Toolkit.

The frontend reuses the application's validated copy operations and reviewed
automation engine. It never selects the interactive editor or creates a Tk root.
"""
import argparse
from dataclasses import asdict
import json
import sys


class _Version(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        from koei_editor.application import VERSION
        print('Universal Koei Tecmo Game Toolkit ' + VERSION)
        parser.exit(0)


def _parser():
    parser = argparse.ArgumentParser(
        prog='universal-koei-toolkit',
        description='Inspect and compare supported save copies, review conversions, and run explicit workflows.',
        epilog='Use separate save copies. Commands retain format checks, backups and new-destination protections. Guide: https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/blob/main/docs/CLI.md.')
    parser.add_argument('--version', action=_Version, help='Show the application version and exit.')
    commands = parser.add_subparsers(dest='command', metavar='COMMAND')
    for name, help_text in (
            ('games', 'List registered save-editing profiles and their exact scope.'),
            ('routes', 'List scoped conversion routes; no files are opened.')):
        command = commands.add_parser(name, help=help_text)
        command.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
        command.add_argument('--query', metavar='TEXT', help='Case-insensitive text filter.')
        command.add_argument('--output', metavar='NEW.json', help='Also export JSON to a new report file.')
        if name == 'games':
            command.add_argument('--platform', metavar='PLATFORM', help='Exact platform name from games.')
        else:
            command.add_argument('--from-game', metavar='ID', help='Exact conversion source endpoint ID.')
            command.add_argument('--to-game', metavar='ID', help='Exact conversion target endpoint ID.')
    command = commands.add_parser('diagnostics', help='Show a path-free local support report; no game folders are scanned.')
    command.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    command.add_argument('--output', metavar='NEW.json', help='Also export JSON to a new report file.')
    command = commands.add_parser('mods', help='Review mod ZIPs or import into an application-owned library; never deploy.')
    mod_commands = command.add_subparsers(dest='mod_command', required=True)
    mod_commands.add_parser('games', help='List exact supported mod loader methods and their evidence limits.')
    for name in ('validate', 'import', 'list'):
        mod = mod_commands.add_parser(name, help={'validate': 'Review a ZIP without writing files.',
                                                 'import': 'Add a ZIP to a mod library; no game files are changed.',
                                                 'list': 'List a mod library without modifying it.'}[name])
        mod.add_argument('--game', required=True, metavar='ID')
        if name != 'list':
            mod.add_argument('archive', metavar='PACKAGE.zip')
        if name != 'validate':
            mod.add_argument('--library', required=True, metavar='FOLDER', help='Explicit application-owned library folder, never a game folder.')
        if name == 'import':
            mod.add_argument('--dry-run', action='store_true', help='Review only; do not create or change the library.')
    for name in ('workshop-review', 'workshop-export'):
        mod = mod_commands.add_parser(name, help='Review or export a Workshop project using the selected manager rules.')
        mod.add_argument('project', metavar='PROJECT_FOLDER')
        mod.add_argument('--context', required=True, metavar='CONTEXT.json')
        if name == 'workshop-export':
            mod.add_argument('--output', required=True, metavar='NEW.zip')
            mod.add_argument('--review-token', required=True, metavar='SHA256')
    command = commands.add_parser('fields', help='Inspect a scalar save copy and its verified editable fields.')
    command.add_argument('--game', required=True, metavar='ID')
    command.add_argument('source', metavar='COPY')
    command = commands.add_parser('compare', help='Compare two copied saves without editing either.')
    command.add_argument('--game', required=True, metavar='ID')
    command.add_argument('first', metavar='FIRST')
    command.add_argument('second', metavar='SECOND')
    command.add_argument('--report', metavar='NEW.json', help='Also export to a new JSON report.')
    command = commands.add_parser('scan', help='Inspect a copied-save folder; print a path-free JSON summary.')
    command.add_argument('--game', required=True, metavar='ID')
    command.add_argument('folder', metavar='FOLDER')
    command.add_argument('--recursive', action='store_true')
    command = commands.add_parser('doctor', help='Diagnose a separate save copy without repairing it.')
    command.add_argument('--game', required=True, metavar='ID')
    command.add_argument('source', metavar='COPY')
    command.add_argument('--expected-sha256', metavar='DIGEST')
    command = commands.add_parser('discover', help='Discover supported Steam installs and known save folders.')
    command.add_argument('--steam-root', action='append', metavar='FOLDER', help='May be repeated.')
    command = commands.add_parser('convert', help='Review or export an explicit conversion using a qualified template.')
    command.add_argument('route', metavar='ROUTE')
    command.add_argument('--source', required=True, metavar='COPY')
    command.add_argument('--template', required=True, metavar='COPY')
    command.add_argument('--output-dir', metavar='NEW_FOLDER')
    command.add_argument('--dry-run', action='store_true', help='Validate/review without creating output or backups.')
    command = commands.add_parser('batch-convert', help='Review or export an explicit JSON conversion queue.')
    command.add_argument('plan', metavar='PLAN.json')
    command.add_argument('--report', metavar='NEW.json')
    command.add_argument('--dry-run', action='store_true')
    command = commands.add_parser('automation', add_help=False,
                                  help='Build, preview, apply or recover reviewed workflows; use automation --help.')
    command.add_argument('arguments', nargs=argparse.REMAINDER)
    return parser


def _print_text(text):
    # Redirected Windows terminals may use ASCII/cp1252. Keep listings usable.
    encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    print(text.encode(encoding, errors='backslashreplace').decode(encoding))


def _export_inventory(report, destination):
    if destination is not None:
        from koei_editor.shared.report_export import write_report_bytes
        raw = (json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + '\n').encode('ascii')
        write_report_bytes(raw, destination)


def _inventory(arguments, parser):
    query = arguments.query.casefold() if arguments.query is not None else None
    if arguments.command == 'games':
        from koei_editor.supported_games import SUPPORTED_GAMES
        full_items = [asdict(game) for game in SUPPORTED_GAMES]
        platforms = {game['platform'] for game in full_items}
        if arguments.platform is not None and arguments.platform not in platforms:
            parser.error('Unknown save platform; use games to list exact platform names.')
        items = [game for game in full_items
                 if (arguments.platform is None or game['platform'] == arguments.platform)
                 and (query is None or query in ' '.join(
                     game[key] for key in ('id', 'title', 'edition', 'platform', 'features')).casefold())]
        report = {'schema': 'koei-toolkit-games', 'schema_version': 1,
                  'read_only': True, 'in_game_verified': False,
                  'profile_count': len(items), 'full_profile_count': len(full_items),
                  'platform_count': len({game['platform'] for game in items}),
                  'full_platform_count': len(platforms),
                  'filters': {'query_applied': query is not None, 'platform': arguments.platform},
                  'games': items}
        lines = [game['id'] + ': ' + game['title'] + ' / ' + game['edition']
                 + ' [' + game['platform'] + ']\n  ' + game['features'] for game in items]
    else:
        from koei_editor.conversion import ENDPOINTS, ROUTES
        for field, option in (('from_game', '--from-game'), ('to_game', '--to-game')):
            if getattr(arguments, field) is not None and getattr(arguments, field) not in ENDPOINTS:
                parser.error('Unknown conversion endpoint for ' + option + '; use routes to list exact IDs.')
        full_items = [{'id': route.id, 'source_id': route.source_id, 'target_id': route.target_id,
                       'label': route.label, 'transfer_scope': route.transfer_scope,
                       'scope_description': route.scope_description} for route in ROUTES]
        items = [route for route in full_items
                 if (arguments.from_game is None or route['source_id'] == arguments.from_game)
                 and (arguments.to_game is None or route['target_id'] == arguments.to_game)
                 and (query is None or query in ' '.join(route.values()).casefold())]
        report = {'schema': 'koei-toolkit-routes', 'schema_version': 1,
                  'read_only': True, 'in_game_verified': False,
                  'route_count': len(items), 'full_route_count': len(full_items),
                  'filters': {'query_applied': query is not None, 'from_game': arguments.from_game,
                              'to_game': arguments.to_game}, 'routes': items}
        lines = [route['id'] + ': ' + route['label'] + '\n  ' + route['scope_description']
                 for route in items]
    try:
        _export_inventory(report, arguments.output)
    except (OSError, ValueError, TypeError, ImportError):
        parser.exit(1, 'Catalog report export failed. Choose a separate new report file.\n')
    if arguments.json:
        print(json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False))
    else:
        if arguments.command == 'games':
            _print_text(str(report['profile_count']) + ' matching save profiles ('
                        + str(report['full_profile_count']) + ' total).')
        else:
            _print_text(str(report['route_count']) + ' matching conversion routes ('
                        + str(report['full_route_count']) + ' total).')
        for line in lines:
            _print_text(line)
    return 0


def _diagnostics(arguments, parser):
    try:
        from koei_editor.application import VERSION
        from koei_editor.shared import toolkit_diagnostics
        report = toolkit_diagnostics.collect_diagnostics(VERSION)
        rendered = toolkit_diagnostics.report_json(report)
        if arguments.output is not None:
            toolkit_diagnostics.export_report(report, arguments.output)
    except (OSError, ValueError, TypeError, ImportError):
        parser.exit(1, 'Support report could not be completed. Use a separate new report file when exporting.\n')
    if arguments.json:
        print(rendered, end='')
    else:
        app, runtime, catalog = (report[name] for name in ('application', 'runtime', 'catalog'))
        _print_text(app['name'] + ' ' + app['version'] + ' (' + app['mode'] + ')')
        _print_text('Runtime: ' + runtime['os_family'] + ' ' + runtime['architecture']
                    + '; ' + runtime['implementation'] + ' ' + runtime['python'])
        _print_text('Catalog: ' + str(catalog['profiles']) + ' save profiles, '
                    + str(catalog['platforms']) + ' save platforms, '
                    + str(catalog['conversion_routes']) + ' conversion routes.')
        vault = report['capabilities']['save_vault_profiles']
        _print_text('Save Vault and Profiles: ' + ('Windows platform supported; destination checks still apply.'
                    if vault['supported_platform'] else 'require Windows.'))
        for dependency in report['dependencies']:
            _print_text('Dependency metadata: ' + dependency['name'] + ' '
                        + (dependency['version'] or dependency['status']))
        _print_text('Dependency versions describe installed metadata; native functional checks are separate.')
    return 0


def _legacy_arguments(arguments):
    command = arguments.command
    if command == 'compare':
        result = ['--game=' + arguments.game, '--compare', arguments.first, arguments.second]
        if arguments.report is not None:
            result += ['--comparison-report=' + arguments.report]
    elif command == 'scan':
        result = ['--game=' + arguments.game, '--scan-saves=' + arguments.folder]
        if arguments.recursive:
            result.append('--recursive')
    elif command == 'doctor':
        result = ['--game=' + arguments.game, '--save-doctor=' + arguments.source]
        if arguments.expected_sha256 is not None:
            result += ['--expected-sha256=' + arguments.expected_sha256]
    elif command == 'discover':
        result = ['--discover-saves']
        for root in arguments.steam_root or ():
            result += ['--steam-root=' + root]
    elif command == 'convert':
        result = ['--convert=' + arguments.route, '--source=' + arguments.source,
                  '--template=' + arguments.template]
        if arguments.output_dir is not None:
            result += ['--output-dir=' + arguments.output_dir]
    elif command == 'batch-convert':
        result = ['--batch-convert=' + arguments.plan]
        if arguments.report is not None:
            result += ['--batch-report=' + arguments.report]
    else:
        raise ValueError('No headless operation was selected.')
    if getattr(arguments, 'dry_run', False):
        result.append('--dry-run')
    return result


def _mods(arguments, parser):
    from koei_editor.shared import mod_manager
    from koei_editor.shared.copy_storage import ChildPublishedUncertainError
    command = arguments.mod_command
    if hasattr(arguments, 'game'):
        try:
            mod_manager.get_mod_adapter(arguments.game)
        except mod_manager.ModManagerError:
            parser.error('Unknown mod game ID; use mods games for supported loader methods.')
    try:
        report = {'schema': 'koei-toolkit-mods', 'schema_version': 1,
                  'success': True, 'read_only': True, 'in_game_verified': False}
        if command == 'games':
            report.update(status='listed', games=[{
                key: getattr(item, key) for key in ('game_id', 'title', 'platform', 'method_id',
                                                   'scope', 'evidence', 'in_game_verified')
            } for item in mod_manager.supported_mod_games()])
        elif command.startswith('workshop-'):
            from koei_editor.shared.mod_workshop.manager_export import review_manager_package, export_manager_package
            from koei_editor.shared.mod_workshop.validation import CompatibilityContext, InstalledMod
            from koei_editor.shared.save_safety import safe_path
            # Explicit, bounded context only. No installed games or user paths
            # are scanned to infer compatibility or dependencies.
            with safe_path(arguments.context).open('rb') as stream:
                raw = stream.read(64 * 1024 + 1)
            if len(raw) > 64 * 1024:
                raise ValueError('Context exceeds its size limit.')
            context_value = json.loads(raw.decode('utf-8'))
            if not isinstance(context_value, dict) or set(context_value) - {'game_id', 'game_version', 'platform', 'installed_mods'}:
                raise ValueError('Invalid context fields.')
            installed = context_value.get('installed_mods', [])
            if not isinstance(installed, list) or any(not isinstance(item, dict) or set(item) != {'mod_id', 'version'} for item in installed):
                raise ValueError('Invalid installed mod list.')
            context = CompatibilityContext(context_value['game_id'], context_value['game_version'],
                                           context_value['platform'], tuple(InstalledMod(**item) for item in installed))
            if any(not isinstance(value, str) or not value for value in
                   (context.game_id, context.game_version, context.platform)) or any(
                       not isinstance(value, str) or not value for item in context.installed_mods
                       for value in (item.mod_id, item.version)):
                raise ValueError('Context strings must be nonempty.')
            if command == 'workshop-review':
                report = review_manager_package(arguments.project, context)
            else:
                report = export_manager_package(arguments.project, arguments.output, context,
                                                review_token=arguments.review_token)
        elif command == 'validate' or command == 'import' and arguments.dry_run:
            review = mod_manager.review_archive(arguments.archive, game_id=arguments.game)
            report.update(status='validated', game_id=arguments.game, package_review=asdict(review))
        else:
            if command == 'import':
                # Reject malformed packages before the manager's mutation lock
                # can create a previously absent application library directory.
                mod_manager.review_archive(arguments.archive, game_id=arguments.game)
            manager = mod_manager.ModManager(arguments.library, game_id=arguments.game)
            if command == 'list':
                report.update(status='listed', game_id=arguments.game, mods=[asdict(item) for item in manager.mods()])
            else:
                record = manager.import_archive(arguments.archive)
                report.update(status='imported', game_id=arguments.game, read_only=False, mod=asdict(record))
    except ChildPublishedUncertainError:
        parser.exit(1, 'The package may already be exported. Inspect the selected folder before trying another export.\n')
    except (mod_manager.ModManagerError, OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, 'Mod operation failed (' + type(error).__name__ + '). Check the package, explicit game/context, and library or new output destination.\n')
    print(json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False))
    return 0


def main(argv=None):
    """Run a headless command; no arguments show help rather than opening the GUI."""
    argv = list(sys.argv[1:] if argv is None else argv)
    # Let the existing parser own all workflow options, errors and JSON contracts.
    if argv and argv[0] == 'automation':
        from koei_editor.automation_cli import main as automation_main
        return automation_main(argv[1:])
    parser = _parser()
    if not argv:
        parser.print_help()
        return 0
    arguments = parser.parse_args(argv)
    if any(value == '' or isinstance(value, list) and '' in value
           for value in vars(arguments).values()):
        parser.error('Command options and paths must not be empty.')
    if arguments.command in ('games', 'routes'):
        return _inventory(arguments, parser)
    if arguments.command == 'diagnostics':
        return _diagnostics(arguments, parser)
    if arguments.command == 'mods':
        return _mods(arguments, parser)
    if arguments.command == 'fields':
        from koei_editor.automation_cli import main as automation_main
        return automation_main(['fields', '--game=' + arguments.game, '--', arguments.source])
    if arguments.command is None:
        parser.error('Choose a headless command; use --help.')
    if arguments.command == 'convert' and not arguments.dry_run and not arguments.output_dir:
        parser.error('convert requires --output-dir unless --dry-run is selected.')
    from koei_editor.application import main as application_main
    return application_main(_legacy_arguments(arguments)) or 0


if __name__ == '__main__':
    raise SystemExit(main())
