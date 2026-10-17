"""Save-management commands registered with the application's existing CLI."""
from dataclasses import asdict, is_dataclass
import json


def add_arguments(parser, actions):
    actions.add_argument('--save-doctor', metavar='COPY', help='Diagnose a separate save copy using --game; never repair input.')
    actions.add_argument('--discover-saves', action='store_true', help='Read-only discovery of supported Steam installs and known save folders.')
    actions.add_argument('--vault-operation', choices=('create', 'list', 'snapshot', 'verify', 'restore', 'compare', 'branch', 'label', 'delete'),
                         help='Manage a local save vault; requires --vault-path.')
    parser.add_argument('--expected-sha256', help='Expected full-file digest for --save-doctor.')
    parser.add_argument('--steam-root', action='append', help='Explicit Steam root for discovery; may be repeated.')
    parser.add_argument('--vault-path', help='Separate local vault folder.')
    parser.add_argument('--save-path', help='Separate copied save to snapshot.')
    parser.add_argument('--snapshot-id', help='Vault snapshot to inspect or manage.')
    parser.add_argument('--other-snapshot', help='Second snapshot for vault comparison.')
    parser.add_argument('--vault-branch', help='Snapshot branch or new branch name.')
    parser.add_argument('--snapshot-label', help='Local snapshot label.')
    parser.add_argument('--parent-snapshot', help='Parent snapshot for a new history entry.')
    parser.add_argument('--restore-dir', help='New directory for verified restoration; existing paths are rejected.')


def _plain(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def handle(parser, args):
    """Return True for a completed command; reject orphan/mixed options first."""
    modifiers = ('expected_sha256', 'steam_root', 'vault_path', 'save_path', 'snapshot_id',
                 'other_snapshot', 'vault_branch', 'snapshot_label', 'parent_snapshot', 'restore_dir')
    active = args.save_doctor is not None or args.discover_saves or args.vault_operation is not None
    if not active:
        if any(getattr(args, key) is not None for key in modifiers):
            parser.error('Save-management options require --save-doctor, --discover-saves or --vault-operation.')
        return False
    unrelated = ('source', 'template', 'output_dir', 'batch_report', 'comparison_report')
    if (args.smoke_test or args.list_games or args.dry_run or args.recursive
            or any(getattr(args, key) is not None for key in unrelated)):
        parser.error('Use save-management commands separately from other workflows.')
    if args.save_doctor is not None:
        if not args.game or not args.save_doctor or any(getattr(args, key) is not None for key in modifiers if key != 'expected_sha256'):
            parser.error('--save-doctor requires an explicit --game and separate save copy; only --expected-sha256 applies.')
        from koei_editor.shared.save_doctor import inspect_save
        try:
            result = inspect_save(args.game, args.save_doctor, expected_sha256=args.expected_sha256)
        except (OSError, ValueError, TypeError):
            parser.exit(1, 'Save Doctor could not inspect this copy. Check the selected profile and input.\n')
        print(result.to_json())
        if result.status not in ('qualified', 'warning'):
            parser.exit(1)
        return True
    if args.discover_saves:
        if args.game or any(getattr(args, key) is not None for key in modifiers if key != 'steam_root'):
            parser.error('--discover-saves accepts only optional --steam-root locations.')
        from koei_editor.shared.save_discovery import discover_saves, report
        try:
            result = discover_saves(steam_roots=args.steam_root)
            print(json.dumps(report(result), indent=2, ensure_ascii=True))
        except (OSError, ValueError, TypeError):
            parser.exit(1, 'Save discovery could not complete. Check the selected roots.\n')
        if result.stop_reason != 'complete':
            parser.exit(3)
        return True
    operation = args.vault_operation
    allowed = {
        'create': (), 'list': ('game', 'vault_branch'),
        'snapshot': ('game', 'save_path', 'vault_branch', 'snapshot_label', 'parent_snapshot'),
        'verify': ('snapshot_id',), 'restore': ('snapshot_id', 'restore_dir'),
        'compare': ('snapshot_id', 'other_snapshot'), 'branch': ('snapshot_id', 'vault_branch'),
        'label': ('snapshot_id', 'snapshot_label'), 'delete': ('snapshot_id',),
    }[operation]
    if (not args.vault_path or any(getattr(args, key) is not None for key in ('game', *modifiers)
                                    if key not in ('vault_path', *allowed))):
        parser.error('This vault operation received unrelated options or lacks --vault-path.')
    required = {'snapshot': ('game', 'save_path'), 'restore': ('snapshot_id', 'restore_dir'),
                'compare': ('snapshot_id', 'other_snapshot'), 'branch': ('snapshot_id', 'vault_branch'),
                'label': ('snapshot_id', 'snapshot_label'), 'delete': ('snapshot_id',)}.get(operation, ())
    if any(getattr(args, key) is None or (key != 'snapshot_label' and not getattr(args, key)) for key in required):
        parser.error('This vault operation is missing its required save, snapshot, branch, label or destination.')
    from koei_editor.shared.save_vault import SaveVault
    try:
        vault = SaveVault.create(args.vault_path) if operation == 'create' else SaveVault(args.vault_path)
        if operation == 'create':
            result = {'created': True}
        elif operation == 'list':
            result = _plain(vault.list_snapshots(game_id=args.game, branch=args.vault_branch))
        elif operation == 'snapshot':
            result = _plain(vault.snapshot(args.game, args.save_path, branch=args.vault_branch or 'main',
                                           label=args.snapshot_label or '', parent_id=args.parent_snapshot))
        elif operation == 'verify':
            verification = vault.verify(args.snapshot_id)
            result = _plain(verification)
        elif operation == 'restore':
            vault.restore(args.snapshot_id, args.restore_dir)
            result = {'restored': True, 'snapshot_id': args.snapshot_id}
        elif operation == 'compare':
            result = _plain(vault.compare(args.snapshot_id, args.other_snapshot))
        elif operation == 'branch':
            result = _plain(vault.branch(args.vault_branch, args.snapshot_id))
        elif operation == 'label':
            result = _plain(vault.relabel(args.snapshot_id, args.snapshot_label))
        else:
            vault.delete(args.snapshot_id)
            result = {'deleted': True, 'snapshot_id': args.snapshot_id}
        print(json.dumps(result, indent=2, ensure_ascii=True))
        if operation == 'verify' and any(not item.valid for item in verification):
            parser.exit(1)
    except (OSError, ValueError, TypeError):
        parser.exit(1, 'Save Vault operation failed. Check the vault integrity, selected copy and destination.\n')
    return True
