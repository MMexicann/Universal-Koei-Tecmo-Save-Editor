/*
 * Offline format adapters for the Localization Studio.
 *
 * These are deliberately narrow interchange profiles, not Koei Tecmo package
 * parsers. Each adapter records exact offsets in the imported UTF-8 text and
 * export patches only the target value (or subtitle cue payload). The browser
 * keeps the uploaded File untouched and creates a separate download.
 */

export const SUPPORTED_FORMATS = Object.freeze(["csv", "tsv", "json", "srt", "vtt", "txt"]);
export const MAX_TEXT_LENGTH = 5 * 1024 * 1024;
export const MAX_SEGMENTS = 5000;
export const MAX_COLUMNS = 64;
export const MAX_LINES = 50_000;
const MAX_JSON_DEPTH = 64;
const MAX_JSON_NODES = 65_000;

export class FormatError extends Error {
  constructor(message) {
    super(message);
    this.name = "FormatError";
  }
}

const FORMAT_BY_EXTENSION = new Map(SUPPORTED_FORMATS.map((format) => [`.${format}`, format]));

export function detectFormat(filename = "") {
  const cleanName = String(filename).split(/[?#]/, 1)[0];
  const extension = cleanName.slice(cleanName.lastIndexOf(".")).toLowerCase();
  return FORMAT_BY_EXTENSION.get(extension) ?? null;
}

function requireText(text) {
  if (typeof text !== "string") throw new FormatError("The selected file must decode as UTF-8 text.");
  if (text.includes("\0")) throw new FormatError("NUL bytes are not supported. Select a UTF-8 text export, not a game package or binary asset.");
}

function uniqueSegmentId(candidate, fallback, used) {
  const id = candidate == null || String(candidate).trim() === "" ? fallback : String(candidate);
  if (used.has(id)) throw new FormatError(`Duplicate segment id “${id}”. Give each row a unique id or remove the id column.`);
  used.add(id);
  return id;
}

/** Parse delimited text while retaining each complete field token's raw span. */
function scanDelimited(text, delimiter) {
  const rows = [];
  const row = [];
  let index = 0;
  let endedWithRecordBreak = false;

  const finishRow = () => {
    if (rows.length >= MAX_SEGMENTS + 1) {
      throw new FormatError("Files over 5,000 strings are outside the supported browser profile. Split the catalog into smaller files and try again.");
    }
    rows.push(row.splice(0));
  };
  const pushCell = (cell) => {
    if (row.length >= MAX_COLUMNS) throw new FormatError(`Delimited catalogs are limited to ${MAX_COLUMNS} columns.`);
    row.push(cell);
  };

  while (index < text.length) {
    const start = index;
    let value = "";
    let quoted = false;

    if (text[index] === '"') {
      quoted = true;
      index += 1;
      let closed = false;
      while (index < text.length) {
        const character = text[index];
        if (character === '"') {
          if (text[index + 1] === '"') {
            value += '"';
            index += 2;
          } else {
            index += 1;
            closed = true;
            break;
          }
        } else {
          value += character;
          index += 1;
        }
      }
      if (!closed) throw new FormatError("The delimited file contains an unterminated quoted field.");
      if (index < text.length && text[index] !== delimiter && text[index] !== "\r" && text[index] !== "\n") {
        throw new FormatError("A quoted field must be followed by a delimiter or a record break.");
      }
    } else {
      while (index < text.length && text[index] !== delimiter && text[index] !== "\r" && text[index] !== "\n") {
        if (text[index] === '"') throw new FormatError("A quote inside an unquoted field must be escaped by quoting the whole field.");
        value += text[index];
        index += 1;
      }
    }

    pushCell({ value, start, end: index, quoted });
    endedWithRecordBreak = false;

    if (index >= text.length) {
      finishRow();
      break;
    }
    if (text[index] === delimiter) {
      index += 1;
      if (index >= text.length) {
        pushCell({ value: "", start: index, end: index, quoted: false });
        finishRow();
      }
      continue;
    }

    if (text[index] === "\r" || text[index] === "\n") {
      if (text[index] === "\r" && text[index + 1] === "\n") index += 2;
      else index += 1;
      finishRow();
      endedWithRecordBreak = true;
    }
  }

  // A final record break terminates the preceding row; it is not an extra
  // empty data row. The original bytes remain in the document regardless.
  if (rows.length === 0 && text.length === 0) throw new FormatError("The delimited file is empty.");
  if (!endedWithRecordBreak && row.length > 0) finishRow();
  return rows;
}

function parseDelimited({ filename, text, format }) {
  const bomOffset = text.charCodeAt(0) === 0xfeff ? 1 : 0;
  const rows = scanDelimited(text.slice(bomOffset), format === "tsv" ? "\t" : ",");
  if (rows.length < 2) throw new FormatError("A CSV/TSV catalog needs a header row and at least one data row.");

  const headers = rows[0].map((cell, index) => {
    const value = index === 0 ? cell.value.replace(/^\uFEFF/, "") : cell.value;
    return value.trim().toLowerCase();
  });
  const sourceColumn = headers.indexOf("source");
  const targetColumn = headers.indexOf("target");
  const idColumn = headers.indexOf("id");
  const contextColumn = headers.indexOf("context");
  if (sourceColumn < 0 || targetColumn < 0) {
    throw new FormatError("The supported CSV/TSV catalog profile requires ‘source’ and ‘target’ header columns. Optional columns are ‘id’ and ‘context’.");
  }
  if (sourceColumn === targetColumn) throw new FormatError("The source and target columns must be different.");
  if (new Set(headers).size !== headers.length) throw new FormatError("Header names must be unique.");

  const width = headers.length;
  const usedIds = new Set();
  const segments = [];
  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const cells = rows[rowIndex];
    if (cells.length !== width) {
      throw new FormatError(`Row ${rowIndex + 1} has ${cells.length} columns; the header has ${width}.`);
    }
    const source = cells[sourceColumn];
    const target = cells[targetColumn];
    const id = uniqueSegmentId(idColumn >= 0 ? cells[idColumn].value : null, `row-${rowIndex + 1}`, usedIds);
    segments.push({
      id,
      source: source.value,
      target: target.value,
      context: contextColumn >= 0 ? cells[contextColumn].value : "",
      spanStart: target.start + bomOffset,
      spanEnd: target.end + bomOffset,
      spanKind: "delimited-field",
      delimiter: format === "tsv" ? "\t" : ",",
    });
  }
  if (!segments.length) throw new FormatError("The catalog contains no data rows.");
  return { format, filename, originalText: text, segments, headers };
}

function isJsonWhitespace(character) {
  return character === " " || character === "\t" || character === "\n" || character === "\r";
}

function skipJsonWhitespace(text, index) {
  while (index < text.length && isJsonWhitespace(text[index])) index += 1;
  return index;
}

function scanJsonValue(text, initialIndex, depth = 0, budget = null) {
  if (depth > MAX_JSON_DEPTH) throw new FormatError(`JSON nesting is limited to ${MAX_JSON_DEPTH} levels.`);
  if (budget && ++budget.nodes > MAX_JSON_NODES) throw new FormatError(`JSON catalogs are limited to ${MAX_JSON_NODES.toLocaleString()} values and object keys.`);
  const index = skipJsonWhitespace(text, initialIndex);
  const start = index;
  const character = text[index];
  if (character === '"') {
    let cursor = index + 1;
    while (cursor < text.length) {
      if (text[cursor] === "\\") {
        cursor += 2;
        continue;
      }
      if (text[cursor] === '"') {
        cursor += 1;
        const raw = text.slice(start, cursor);
        let value;
        try {
          value = JSON.parse(raw);
        } catch {
          throw new FormatError("The JSON catalog contains an invalid string value.");
        }
        return { node: { type: "string", value, start, end: cursor }, next: cursor };
      }
      cursor += 1;
    }
    throw new FormatError("The JSON catalog contains an unterminated string.");
  }

  if (character === "{") {
    let cursor = skipJsonWhitespace(text, index + 1);
    const properties = new Map();
    if (text[cursor] === "}") return { node: { type: "object", start, end: cursor + 1, properties }, next: cursor + 1 };
    while (cursor < text.length) {
      cursor = skipJsonWhitespace(text, cursor);
      const keyResult = scanJsonValue(text, cursor, depth + 1, budget);
      if (keyResult.node.type !== "string") throw new FormatError("JSON object keys must be strings.");
      const key = keyResult.node.value;
      if (properties.has(key)) throw new FormatError(`The JSON object repeats the key “${key}”; duplicate keys are ambiguous.`);
      if (properties.size >= MAX_COLUMNS) throw new FormatError(`JSON objects are limited to ${MAX_COLUMNS} properties.`);
      cursor = skipJsonWhitespace(text, keyResult.next);
      if (text[cursor] !== ":") throw new FormatError("The JSON catalog is missing a colon after an object key.");
      const valueResult = scanJsonValue(text, cursor + 1, depth + 1, budget);
      properties.set(key, { keyNode: keyResult.node, valueNode: valueResult.node });
      cursor = skipJsonWhitespace(text, valueResult.next);
      if (text[cursor] === "}") return { node: { type: "object", start, end: cursor + 1, properties }, next: cursor + 1 };
      if (text[cursor] !== ",") throw new FormatError("The JSON catalog has an invalid object separator.");
      cursor += 1;
    }
    throw new FormatError("The JSON catalog contains an unterminated object.");
  }

  if (character === "[") {
    let cursor = skipJsonWhitespace(text, index + 1);
    const items = [];
    if (text[cursor] === "]") return { node: { type: "array", start, end: cursor + 1, items }, next: cursor + 1 };
    while (cursor < text.length) {
      if (items.length >= MAX_SEGMENTS) throw new FormatError("Files over 5,000 strings are outside the supported browser profile. Split the catalog into smaller files and try again.");
      const itemResult = scanJsonValue(text, cursor, depth + 1, budget);
      items.push(itemResult.node);
      cursor = skipJsonWhitespace(text, itemResult.next);
      if (text[cursor] === "]") return { node: { type: "array", start, end: cursor + 1, items }, next: cursor + 1 };
      if (text[cursor] !== ",") throw new FormatError("The JSON catalog has an invalid array separator.");
      cursor += 1;
    }
    throw new FormatError("The JSON catalog contains an unterminated array.");
  }

  let cursor = index;
  while (cursor < text.length && !isJsonWhitespace(text[cursor]) && text[cursor] !== "," && text[cursor] !== "}" && text[cursor] !== "]") {
    cursor += 1;
  }
  if (cursor === index) throw new FormatError("The JSON catalog contains an invalid value.");
  const raw = text.slice(index, cursor);
  let value;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new FormatError("The JSON catalog contains an invalid value.");
  }
  return { node: { type: "primitive", value, start, end: cursor }, next: cursor };
}

function parseJsonCatalog({ filename, text }) {
  const bomOffset = text.charCodeAt(0) === 0xfeff ? 1 : 0;
  const content = text.slice(bomOffset);
  let rootResult;
  try {
    rootResult = scanJsonValue(content, 0, 0, { nodes: 0 });
  } catch (error) {
    if (error instanceof FormatError) throw new FormatError(`The JSON catalog is invalid: ${error.message}`);
    throw new FormatError(`The JSON catalog is invalid: ${error.message}`);
  }
  if (skipJsonWhitespace(content, rootResult.next) !== content.length) throw new FormatError("The JSON catalog contains extra content after its root value.");
  const rootNode = rootResult.node;
  if (rootNode.type !== "object") throw new FormatError("The supported JSON catalog must be an object with a ‘segments’ array.");
  const segmentsNode = rootNode.properties.get("segments")?.valueNode;
  if (!segmentsNode || segmentsNode.type !== "array") throw new FormatError("The supported JSON catalog must contain a ‘segments’ array.");
  if (segmentsNode.items.length === 0) throw new FormatError("The JSON catalog ‘segments’ array must contain at least one entry.");

  const usedIds = new Set();
  const segments = [];
  for (let index = 0; index < segmentsNode.items.length; index += 1) {
    const itemNode = segmentsNode.items[index];
    if (itemNode.type !== "object") {
      throw new FormatError(`JSON segment ${index + 1} must be an object.`);
    }
    const sourceNode = itemNode.properties.get("source")?.valueNode;
    const targetNode = itemNode.properties.get("target")?.valueNode;
    if (sourceNode?.type !== "string" || targetNode?.type !== "string") {
      throw new FormatError(`JSON segment ${index + 1} must have string-valued ‘source’ and ‘target’ fields.`);
    }
    const idNode = itemNode.properties.get("id")?.valueNode;
    const contextNode = itemNode.properties.get("context")?.valueNode;
    if (idNode && idNode.type !== "string") throw new FormatError(`JSON segment ${index + 1} has a non-string ‘id’.`);
    if (contextNode && contextNode.type !== "string") throw new FormatError(`JSON segment ${index + 1} has a non-string ‘context’.`);
    const id = uniqueSegmentId(idNode ? idNode.value : null, `segment-${index + 1}`, usedIds);
    segments.push({
      id,
      source: sourceNode.value,
      target: targetNode.value,
      context: contextNode?.value ?? "",
      spanStart: targetNode.start + bomOffset,
      spanEnd: targetNode.end + bomOffset,
      spanKind: "json-string",
    });
  }
  return { format: "json", filename, originalText: text, segments };
}

function linesWithOffsets(text, offset = 0) {
  const lines = [];
  let start = 0;
  while (start < text.length) {
    let end = start;
    while (end < text.length && text[end] !== "\r" && text[end] !== "\n") end += 1;
    let next = end;
    if (text[next] === "\r" && text[next + 1] === "\n") next += 2;
    else if (text[next] === "\r" || text[next] === "\n") next += 1;
    if (lines.length >= MAX_LINES) throw new FormatError(`Text profiles are limited to ${MAX_LINES.toLocaleString()} physical lines.`);
    lines.push({
      text: text.slice(start, end),
      start: start + offset,
      end: end + offset,
      next: next + offset,
      ending: text.slice(end, next),
    });
    start = next;
  }
  return lines;
}

function* blockGroups(lines) {
  let group = [];
  for (const line of lines) {
    if (line.text.trim() === "") {
      if (group.length) {
        yield group;
        group = [];
      }
    } else {
      group.push(line);
    }
  }
  if (group.length) yield group;
}

function validSrtTime(line) {
  const match = line.match(/^\s*(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})\s+-->\s+(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})\s*$/);
  if (!match) return false;
  const time = (hours, minutes, seconds, milliseconds) =>
    (((Number(hours) * 60 + Number(minutes)) * 60 + Number(seconds)) * 1000) + Number(milliseconds);
  return time(match[5], match[6], match[7], match[8]) > time(match[1], match[2], match[3], match[4]);
}

function parseSrt({ filename, text }) {
  const bomOffset = text.charCodeAt(0) === 0xfeff ? 1 : 0;
  const lines = linesWithOffsets(text.slice(bomOffset), bomOffset);
  const usedIds = new Set();
  const segments = [];
  const documentLineEnding = lines.find((line) => line.ending)?.ending || "\n";
  let groupIndex = 0;
  for (const group of blockGroups(lines)) {
    groupIndex += 1;
    if (segments.length >= MAX_SEGMENTS) throw new FormatError("Files over 5,000 strings are outside the supported browser profile. Split the catalog into smaller files and try again.");
    const hasIndex = /^\d+$/.test(group[0].text.trim());
    const timingLine = group[hasIndex ? 1 : 0];
    const textLines = group.slice(hasIndex ? 2 : 1);
    if (!timingLine || !validSrtTime(timingLine.text) || textLines.length === 0) {
      throw new FormatError(`SRT block ${groupIndex} is outside the supported profile: expected an optional numeric cue index, a basic time range, and one or more text lines.`);
    }
    const cueId = hasIndex ? group[0].text.trim() : `cue-${groupIndex}`;
    const id = uniqueSegmentId(cueId, `cue-${groupIndex}`, usedIds);
    segments.push({
      id,
      source: textLines.map((line) => line.text).join("\n"),
      // Without a separate target column, the initial value is a pass-through
      // so an unchanged export is byte-identical; the UI can label source-equal
      // values as untranslated.
      target: textLines.map((line) => line.text).join("\n"),
      context: "",
      spanStart: textLines[0].start,
      spanEnd: textLines[textLines.length - 1].end,
      spanKind: "subtitle-text",
      lineEndings: textLines.slice(0, -1).map((line) => line.ending),
      fallbackLineEnding: textLines.find((line) => line.ending)?.ending || documentLineEnding,
    });
  }
  if (!segments.length) throw new FormatError("The SRT file contains no subtitle cues.");
  return { format: "srt", filename, originalText: text, segments };
}

function validVttTime(line) {
  const match = line.match(/^\s*((?:\d{2,}:)?\d{2}:\d{2}\.\d{3})\s+-->\s+((?:\d{2,}:)?\d{2}:\d{2}\.\d{3})(?:\s+.*)?$/);
  if (!match) return false;
  const check = (value) => {
    const parts = value.split(":");
    const seconds = Number(parts.at(-1).split(".")[0]);
    const minutes = Number(parts.at(-2));
    return seconds < 60 && minutes < 60;
  };
  const toMilliseconds = (value) => {
    const parts = value.split(":");
    const [secondsText, millisecondsText] = parts.pop().split(".");
    const milliseconds = Number(millisecondsText);
    const seconds = Number(secondsText);
    const minutes = Number(parts.pop());
    const hours = parts.length ? Number(parts.pop()) : 0;
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds;
  };
  return check(match[1]) && check(match[2]) && toMilliseconds(match[2]) > toMilliseconds(match[1]);
}

function parseVtt({ filename, text }) {
  const bomOffset = text.charCodeAt(0) === 0xfeff ? 1 : 0;
  const lines = linesWithOffsets(text.slice(bomOffset), bomOffset);
  if (!lines.length || !/^WEBVTT(?:[\t ].*)?$/.test(lines[0].text)) {
    throw new FormatError("A WebVTT file must start with a WEBVTT header.");
  }
  const remainingLines = lines.slice(1);
  const usedIds = new Set();
  const segments = [];
  let cueNumber = 0;
  const documentLineEnding = lines.find((line) => line.ending)?.ending || "\n";
  for (const group of blockGroups(remainingLines)) {
    const first = group[0].text;
    if (/^(?:NOTE)(?:\s|$)/.test(first) || /^(?:STYLE|REGION)\s*$/.test(first)) continue;
    if (segments.length >= MAX_SEGMENTS) throw new FormatError("Files over 5,000 strings are outside the supported browser profile. Split the catalog into smaller files and try again.");
    const hasIdentifier = !validVttTime(first);
    const timingLine = group[hasIdentifier ? 1 : 0];
    const textLines = group.slice(hasIdentifier ? 2 : 1);
    if (!timingLine || !validVttTime(timingLine.text) || textLines.length === 0) {
      throw new FormatError("This WebVTT file contains a block outside the supported caption/subtitle cue profile.");
    }
    cueNumber += 1;
    const id = uniqueSegmentId(hasIdentifier ? first : null, `cue-${cueNumber}`, usedIds);
    segments.push({
      id,
      source: textLines.map((line) => line.text).join("\n"),
      target: textLines.map((line) => line.text).join("\n"),
      context: "",
      spanStart: textLines[0].start,
      spanEnd: textLines[textLines.length - 1].end,
      spanKind: "subtitle-text",
      lineEndings: textLines.slice(0, -1).map((line) => line.ending),
      fallbackLineEnding: textLines.find((line) => line.ending)?.ending || documentLineEnding,
    });
  }
  if (!segments.length) throw new FormatError("The WebVTT file contains no supported subtitle or caption cues.");
  return { format: "vtt", filename, originalText: text, segments };
}

function parseTextLines({ filename, text }) {
  const bomOffset = text.charCodeAt(0) === 0xfeff ? 1 : 0;
  const lines = linesWithOffsets(text.slice(bomOffset), bomOffset);
  const segments = [];
  const usedIds = new Set();
  lines.forEach((line, index) => {
    if (line.text.length === 0) return;
    if (segments.length >= MAX_SEGMENTS) throw new FormatError("Files over 5,000 strings are outside the supported browser profile. Split the catalog into smaller files and try again.");
    const id = uniqueSegmentId(null, `line-${index + 1}`, usedIds);
    segments.push({
      id,
      source: line.text,
      // TXT has no target field, so a pass-through value preserves no-op export.
      target: line.text,
      context: "",
      spanStart: line.start,
      spanEnd: line.end,
      spanKind: "plain-text-line",
    });
  });
  if (!segments.length) throw new FormatError("The line catalog contains no non-empty lines.");
  return { format: "txt", filename, originalText: text, segments };
}

export function parseDocument({ filename, text }) {
  requireText(text);
  if (text.length > MAX_TEXT_LENGTH) throw new FormatError("Files over 5 MiB are outside the supported browser profile. Split the catalog into smaller files and try again.");
  const format = detectFormat(filename);
  if (!format) throw new FormatError("Unsupported extension. Supported profiles are CSV, TSV, Studio JSON, SRT, WebVTT, and line-oriented TXT.");
  let document;
  if (format === "csv" || format === "tsv") document = parseDelimited({ filename, text, format });
  else if (format === "json") document = parseJsonCatalog({ filename, text });
  else if (format === "srt") document = parseSrt({ filename, text });
  else if (format === "vtt") document = parseVtt({ filename, text });
  else document = parseTextLines({ filename, text });
  if (document.segments.length > MAX_SEGMENTS) throw new FormatError("Files over 5,000 strings are outside the supported browser profile. Split the catalog into smaller files and try again.");
  return document;
}

function getTranslation(translationsById, segment) {
  const hasValue = translationsById instanceof Map
    ? translationsById.has(segment.id)
    : translationsById != null && Object.prototype.hasOwnProperty.call(translationsById, segment.id);
  const value = hasValue
    ? (translationsById instanceof Map ? translationsById.get(segment.id) : translationsById[segment.id])
    : segment.target;
  if (typeof value !== "string") throw new FormatError(`Translation for segment “${segment.id}” must be a string.`);
  return value;
}

function normalizeSubtitleLineEndings(value, segment) {
  const lines = value.replace(/\r\n|\r/g, "\n").split("\n");
  if (lines.length === 1) return value;
  if (lines.some((line) => line.trim() === "")) {
    throw new FormatError(`Translation for cue “${segment.id}” cannot contain blank lines; blank lines separate subtitle cues.`);
  }
  const originalEndings = segment.lineEndings ?? [];
  const endings = lines.slice(0, -1).map((_, index) => originalEndings[index] || segment.fallbackLineEnding || "\n");
  return lines.reduce((output, line, index) => output + line + (endings[index] || ""), "");
}

function encodeDelimitedField(value, delimiter) {
  if (value.includes('"') || value.includes("\r") || value.includes("\n") || value.includes(delimiter) || /^\s|\s$/.test(value)) {
    return `"${value.replaceAll('"', '""')}"`;
  }
  return value;
}

export function exportDocument(document, translationsById = null) {
  if (!document || typeof document.originalText !== "string" || !Array.isArray(document.segments)) {
    throw new FormatError("No parsed document is available to export.");
  }
  const replacements = document.segments.map((segment) => {
    const requestedValue = getTranslation(translationsById, segment);
    const preserveEmptyInline = ["subtitle-text", "plain-text-line"].includes(segment.spanKind) && requestedValue.trim() === "";
    const value = preserveEmptyInline ? segment.source : requestedValue;
    if (value === segment.target) return null;
    if (segment.spanKind === "plain-text-line" && /[\r\n]/.test(value)) {
      throw new FormatError(`Translation for line “${segment.id}” must stay on one line in the TXT line-catalog profile.`);
    }
    let replacement = segment.spanKind === "subtitle-text" ? normalizeSubtitleLineEndings(value, segment) : value;
    if (segment.spanKind === "json-string") replacement = JSON.stringify(value);
    if (segment.spanKind === "delimited-field") replacement = encodeDelimitedField(value, segment.delimiter);
    return { start: segment.spanStart, end: segment.spanEnd, replacement, id: segment.id };
  }).filter(Boolean).sort((a, b) => b.start - a.start);

  let output = document.originalText;
  let previousStart = Number.POSITIVE_INFINITY;
  for (const replacement of replacements) {
    if (!Number.isInteger(replacement.start) || !Number.isInteger(replacement.end) || replacement.start < 0 || replacement.end < replacement.start || replacement.end > output.length) {
      throw new FormatError(`Segment “${replacement.id}” has an invalid export span.`);
    }
    if (replacement.end > previousStart) throw new FormatError("Export spans overlap; the document was not changed.");
    output = output.slice(0, replacement.start) + replacement.replacement + output.slice(replacement.end);
    previousStart = replacement.start;
  }
  return output;
}

const TOKEN_PATTERN = /\{\{?\w[\w.-]*\}?\}|%(?:\d+\$)?[bcdeEfFgGiosuxX]|<\/?[A-Za-z][\w:-]*(?:\s+[^<>]*?)?\s*\/?>|\[[A-Z][A-Z0-9_:-]*\]/g;

function tokenCounts(value) {
  const counts = new Map();
  for (const match of String(value ?? "").matchAll(TOKEN_PATTERN)) {
    const token = match[0].replace(/\s+/g, " ");
    counts.set(token, (counts.get(token) ?? 0) + 1);
  }
  return counts;
}

function repeatedDifference(from, to) {
  const difference = [];
  for (const [token, count] of from) {
    const delta = count - (to.get(token) ?? 0);
    for (let index = 0; index < delta; index += 1) difference.push(token);
  }
  return difference;
}

export function validateTokens(source, target) {
  const sourceCounts = tokenCounts(source);
  const targetCounts = tokenCounts(target);
  const missing = repeatedDifference(sourceCounts, targetCounts);
  const extra = repeatedDifference(targetCounts, sourceCounts);
  return { ok: missing.length === 0 && extra.length === 0, missing, extra };
}
