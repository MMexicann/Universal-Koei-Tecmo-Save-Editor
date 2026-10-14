"""Keep the source index, README and supported-game document synchronized."""
from pathlib import Path
import argparse

from koei_editor.supported_games import SUPPORTED_GAMES, markdown_table


ROOT = Path(__file__).resolve().parents[1]
START = '<!-- BEGIN SUPPORTED GAMES -->'
END = '<!-- END SUPPORTED GAMES -->'
SOURCE_START = '# BEGIN GENERATED SUPPORTED GAME INDEX'
SOURCE_END = '# END GENERATED SUPPORTED GAME INDEX'


def replace_block(text, start, end, body):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f'Exactly one {start} / {end} block is required.')
    before, tail = text.split(start, 1)
    _, after = tail.split(end, 1)
    return before + start + '\n' + body.rstrip() + '\n' + end + after


def expected_files():
    source = ROOT / 'src/koei_editor/supported_games.py'
    index = '\n'.join(f'# {game.id}: {game.title} / {game.edition} [{game.platform}]'
                      for game in SUPPORTED_GAMES)
    yield source, replace_block(source.read_text(encoding='utf-8'), SOURCE_START, SOURCE_END, index)
    document = ROOT / 'docs/SUPPORTED_GAMES.md'
    yield document, ('# Supported games and platforms\n\n'
                     'Generated from `koei_editor.game_registry.GAMES`. Run '
                     '`python -m tools.update_supported_games` after changing an adapter.\n\n'
                     'Version 2.1.1 adds a separate Save Converter and original US DW6 PS3 editor; '
                     'see [conversion routes and boundaries](SAVE_CONVERSION.md). '
                     'Optional experimental numeric editing applies across the library. '
                     'Supported maxima and encoding limits remain separate; see '
                     '[experimental scope and warnings](EXPERIMENTAL_EDITING.md).\n\n'
                     + markdown_table() + '\n'
                     'Scope is specific to each edition and supported save revision. '
                     'File-level qualification and actual game loading are separate; '
                     'see [coverage and blockers](EXPANSION_COVERAGE.md) and '
                     '[validation](VALIDATION.md). Research-only codecs are excluded.\n')
    readme = ROOT / 'README.md'
    text = readme.read_text(encoding='utf-8')
    if START not in text:
        text += '\n## Supported game/platform inventory\n\n' + START + '\n' + END + '\n'
    yield readme, replace_block(text, START, END, markdown_table())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if any generated inventory is stale.')
    args = parser.parse_args()
    stale = []
    for path, expected in expected_files():
        current = path.read_text(encoding='utf-8') if path.exists() else None
        if current != expected:
            stale.append(path.relative_to(ROOT).as_posix())
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(expected, encoding='utf-8')
    if args.check and stale:
        parser.error('Supported inventory is stale: ' + ', '.join(stale))
    print(f'{len(SUPPORTED_GAMES)} supported game/platform adapters; inventory '
          + ('checked.' if args.check else 'updated.'))


if __name__ == '__main__':
    main()
