import test from 'node:test';
import assert from 'node:assert/strict';
import { detectFormat, parseDocument, exportDocument, validateTokens, FormatError, MAX_TEXT_LENGTH, MAX_SEGMENTS, MAX_COLUMNS, MAX_LINES } from '../src/formats.mjs';

function parse(filename, text) {
  return parseDocument({ filename, text });
}

test('detectFormat accepts only the six documented extensions', () => {
  for (const extension of ['csv', 'tsv', 'json', 'srt', 'vtt', 'txt']) {
    assert.equal(detectFormat(`STRINGS.${extension.toUpperCase()}`), extension);
  }
  assert.equal(detectFormat('game.bin'), null);
  assert.equal(detectFormat('strings.json.exe'), null);
  assert.equal(detectFormat('strings.vtt?download=1'), 'vtt');
});

test('CSV catalog no-op export preserves BOM, CRLF, quoted cells, and source bytes', () => {
  const source = '\uFEFFid,source,target,context\r\n"one","Hello, captain","Hi, captain","Deck\r\nbriefing"\r\n"two","A ""quoted"" line","","Menu"\r\n';
  const document = parse('lines.csv', source);
  assert.equal(document.format, 'csv');
  assert.equal(document.segments.length, 2);
  assert.equal(document.segments[0].context, 'Deck\r\nbriefing');
  assert.equal(exportDocument(document), source);
  assert.equal(exportDocument(document, new Map(document.segments.map((segment) => [segment.id, segment.target]))), source);
});

test('CSV export changes only target field tokens and quotes new values correctly', () => {
  const source = '\uFEFFid,source,target,context\r\n"one","Hello, captain","Hi, captain","Deck\r\nbriefing"\r\n"two","A ""quoted"" line","","Menu"\r\n';
  const document = parse('lines.csv', source);
  const output = exportDocument(document, new Map([['one', 'Bonjour, capitaine'], ['two', ''] ]));
  assert.equal(output, source.replace('"Hi, captain"', '"Bonjour, capitaine"'));
  assert.equal(parse('copy.csv', output).segments[0].target, 'Bonjour, capitaine');
});

test('TSV catalog patches only the target column, including tab and newline escaping', () => {
  const source = 'id\tsource\ttarget\tcontext\r\nalpha\tOpen\tOuvrir\tMenu\r\nbeta\tSave\tSpeichern\tMenu\r\n';
  const document = parse('strings.tsv', source);
  assert.equal(document.format, 'tsv');
  assert.equal(exportDocument(document), source);
  const output = exportDocument(document, new Map([['alpha', 'Ouvrir\tles options'], ['beta', 'Enregistrer']]));
  const expected = source.replace('Ouvrir\tMenu', '"Ouvrir\tles options"\tMenu').replace('Speichern', 'Enregistrer');
  assert.equal(output, expected);
  assert.deepEqual(parse('localized.tsv', output).segments.map((segment) => segment.target), ['Ouvrir\tles options', 'Enregistrer']);
});

test('Studio JSON catalog patches only target JSON string values and preserves formatting', () => {
  const source = '\uFEFF{\r\n  "locale": "fr",\r\n  "segments": [\r\n    {"id":"menu","source":"Hello \\u2605","target":"Salut","context":"Menu"},\r\n    {"id": "dialogue", "source": "line", "target": ""}\r\n  ]\r\n}\r\n';
  const document = parse('catalog.json', source);
  assert.equal(document.format, 'json');
  assert.equal(document.segments[0].source, 'Hello ★');
  assert.equal(exportDocument(document), source);
  const output = exportDocument(document, new Map([['menu', 'Salut "toi"'], ['dialogue', '']]));
  assert.equal(output, source.replace('"target":"Salut"', '"target":"Salut \\"toi\\""'));
  assert.equal(parse('translated.json', output).segments[0].target, 'Salut "toi"');
});

test('SubRip parser keeps cue indexes, timings, multiline text, and CRLF on export', () => {
  const source = '\uFEFF1\r\n00:00:01,000 --> 00:00:02,000\r\nHello\r\nthere\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\nOkay\r\n';
  const document = parse('scene.srt', source);
  assert.equal(document.format, 'srt');
  assert.equal(document.segments[0].source, 'Hello\nthere');
  assert.equal(exportDocument(document), source);
  const output = exportDocument(document, new Map([['1', 'Bonjour\nà vous'], ['2', 'D’accord']]));
  assert.equal(output, source.replace('Hello\r\nthere', 'Bonjour\r\nà vous').replace('Okay', 'D’accord'));
  assert.match(output, /00:00:01,000 --> 00:00:02,000/);
  assert.match(output, /00:00:03,000 --> 00:00:04,000/);
  assert.equal(exportDocument(document, new Map([['1', ''], ['2', '']])), source);
  assert.throws(() => exportDocument(document, new Map([['1', 'first\n\nthird']])), /cannot contain blank lines/);
});

test('WebVTT parser edits cue text while preserving header, settings, and metadata blocks', () => {
  const source = 'WEBVTT - sample\r\n\r\nNOTE keep this note\r\nmetadata remains\r\n\r\ncue-one\r\n00:00:01.000 --> 00:00:03.000 position:10%\r\n<v Ada>Hello <b>there</b></v>\r\n\r\nSTYLE\r\n::cue { color: lime; }\r\n\r\ncue-two\r\n00:00:04.000 --> 00:00:05.000\r\nGoodbye\r\n';
  const document = parse('scene.vtt', source);
  assert.equal(document.format, 'vtt');
  assert.equal(document.segments.length, 2);
  assert.equal(exportDocument(document), source);
  const output = exportDocument(document, new Map([['cue-one', '<v Ada>Bonjour <b>vous</b></v>'], ['cue-two', 'Au revoir']]));
  assert.equal(output, source.replace('Hello <b>there</b>', 'Bonjour <b>vous</b>').replace('Goodbye', 'Au revoir'));
  assert.match(output, /NOTE keep this note\r\nmetadata remains/);
  assert.match(output, /STYLE\r\n::cue \{ color: lime; \}/);
  assert.match(output, /00:00:01.000 --> 00:00:03.000 position:10%/);
  assert.throws(() => exportDocument(document, new Map([['cue-one', 'first\n\nthird']])), /cannot contain blank lines/);
});

test('TXT line catalog preserves blank lines and untouched line endings', () => {
  const source = '\uFEFFfirst line\r\n\r\nsecond line\nlast line\n';
  const document = parse('strings.txt', source);
  assert.equal(document.format, 'txt');
  assert.deepEqual(document.segments.map((segment) => segment.id), ['line-1', 'line-3', 'line-4']);
  assert.equal(exportDocument(document), source);
  const output = exportDocument(document, new Map([['line-1', 'first line'], ['line-3', 'deuxième'], ['line-4', 'last line']]));
  assert.equal(output, source.replace('second line', 'deuxième'));
  assert.throws(() => exportDocument(document, new Map([['line-3', 'two\nlines']])), FormatError);
});

test('token validation detects missing and extra placeholders, tags, and bracket tokens', () => {
  const source = '{player_name} has %1$d items. <i>[ACTION]</i>';
  assert.deepEqual(validateTokens(source, '{player_name} tiene %1$d objetos. <i>[ACTION]</i>'), { ok: true, missing: [], extra: [] });
  const mismatch = validateTokens(source, 'Tiene %s objetos. <i>[ACTION]');
  assert.equal(mismatch.ok, false);
  assert.deepEqual(mismatch.missing, ['{player_name}', '%1$d', '</i>']);
  assert.deepEqual(mismatch.extra, ['%s']);
});

test('unknown, malformed, and binary-like files fail closed', () => {
  assert.throws(() => parse('archive.bin', 'text'), /Unsupported extension/);
  assert.throws(() => parse('catalog.csv', 'id,source\none,hello\n'), /requires.*source.*target/);
  assert.throws(() => parse('catalog.csv', 'id,source,target\none,"broken,\n'), /unterminated quoted field/);
  assert.throws(() => parse('catalog.json', '[{"source":"a","target":"b"}]'), /object with a.*segments.*array/);
  assert.throws(() => parse('catalog.json', '{"segments":[{"source":"a","target":3}]}'), /string-valued/);
  assert.throws(() => parse('scene.srt', '1\nnot a timestamp\ncaption\n'), /outside the supported profile/);
  assert.throws(() => parse('scene.srt', '1\n00:00:02,000 --> 00:00:01,000\ncaption\n'), /outside the supported profile/);
  assert.throws(() => parse('scene.vtt', 'not a header\n\n'), /WEBVTT header/);
  assert.throws(() => parse('empty.txt', '\n\r\n'), /no non-empty lines/);
  assert.throws(() => parse('game.bin', '\u0000\u0001'), /NUL bytes/);
  assert.throws(() => parse('strings.txt', 'text\u0000binary'), /NUL bytes/);
});

test('JSON accepts only RFC 8259 whitespace outside string values', () => {
  for (const whitespace of ['\u00a0', '\u2028', '\u2029', '\v', '\f']) {
    const invalid = `{"segments"${whitespace}:[{"source":"a","target":"b"}]}`;
    assert.throws(() => parse('catalog.json', invalid), /invalid|missing a colon/);
  }
});

test('input limits reject oversized files and catalogs before export', () => {
  assert.throws(() => parse('oversized.txt', 'x'.repeat(MAX_TEXT_LENGTH + 1)), /over 5 MiB/);
  const tooManyLines = Array.from({ length: MAX_SEGMENTS + 1 }, () => 'x').join('\n');
  assert.throws(() => parse('too-many.txt', tooManyLines), /over 5,000 strings/);
  const tooManyCsvRows = `source,target\n${Array.from({ length: MAX_SEGMENTS + 1 }, (_, i) => `s${i},t${i}`).join('\n')}`;
  assert.throws(() => parse('too-many.csv', tooManyCsvRows), /over 5,000 strings/);
  const tooManyJsonRows = JSON.stringify({ segments: Array.from({ length: MAX_SEGMENTS + 1 }, () => ({ source: 'x', target: '' })) });
  assert.throws(() => parse('too-many.json', tooManyJsonRows), /over 5,000 strings/);
  const tooDeepJson = `{"nested":${'['.repeat(65)}0${']'.repeat(65)},"segments":[{"source":"x","target":""}]}`;
  assert.throws(() => parse('too-deep.json', tooDeepJson), /nesting is limited/);
  const tooManyJsonProperties = JSON.stringify({ segments: [{ source: 'x', target: '', ...Object.fromEntries(Array.from({ length: MAX_COLUMNS }, (_, i) => [`extra_${i}`, ''])) }] });
  assert.throws(() => parse('too-many-properties.json', tooManyJsonProperties), /limited to 64 properties/);
  const tooManyJsonNodes = JSON.stringify({ segments: Array.from({ length: MAX_SEGMENTS }, () => ({ source: 'x', target: '', a: 0, b: 0, c: 0, d: 0 })) });
  assert.throws(() => parse('too-many-nodes.json', tooManyJsonNodes), /limited to 65,000 values and object keys/);
  const tooManyPhysicalLines = Array.from({ length: MAX_LINES + 2 }, () => '').join('\n');
  assert.throws(() => parse('too-many-lines.txt', tooManyPhysicalLines), /physical lines/);
  const tooManyColumns = ['source', 'target', ...Array.from({ length: MAX_COLUMNS - 1 }, (_, i) => `c${i}`)].join(',');
  assert.throws(() => parse('too-many-columns.csv', `${tooManyColumns}\n${Array(MAX_COLUMNS + 1).fill('x').join(',')}`), /limited to.*columns/);
});
