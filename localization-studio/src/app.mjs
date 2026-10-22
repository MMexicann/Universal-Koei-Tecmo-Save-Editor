import { detectFormat, parseDocument, exportDocument, validateTokens } from './formats.mjs';

const $ = (id) => document.getElementById(id);
const state = {
  document: null,
  translations: new Map(),
  editedIds: new Set(),
  activeId: null,
  filter: 'all',
  query: '',
  noticeTimer: null,
};

const formatNames = {
  csv: 'CSV catalog', tsv: 'TSV catalog', json: 'JSON catalog',
  srt: 'SubRip subtitles', vtt: 'WebVTT subtitles', txt: 'Line text catalog',
};
const languages = {
  'ja-JP': 'Japanese', 'en-US': 'English', 'zh-Hans': 'Chinese (Simplified)',
  'zh-Hant': 'Chinese (Traditional)', 'ko-KR': 'Korean', 'fr-FR': 'French',
  'de-DE': 'German', 'es-ES': 'Spanish', other: 'Other',
};

const els = {
  fileInput: $('file-input'), dropzone: $('dropzone'), browse: $('browse-button'), demo: $('demo-button'),
  welcome: $('welcome-panel'), studio: $('studio-panel'), fileCardName: $('file-card-name'),
  fileCardFormat: $('file-card-format'), fileIcon: document.querySelector('.file-icon'),
  projectTitle: $('project-title'), projectFormat: $('project-format-label'),
  projectSubtitle: $('project-subtitle'), exportTop: $('export-button'), exportSecondary: $('export-button-secondary'),
  closeProject: $('clear-project'), replaceFile: $('replace-file'),
  list: $('segment-list'), emptyFilter: $('empty-filter'), listCount: $('list-count'),
  search: $('search-input'), inspectorEmpty: $('inspector-empty'), inspector: $('inspector-content'),
  inspectorId: $('inspector-id'), inspectorContext: $('inspector-context'),
  inspectorSource: $('inspector-source'), inspectorTarget: $('inspector-target'),
  inspectorStatus: $('inspector-status'), inspectorPosition: $('inspector-position'),
  charCounter: $('char-counter'), validation: $('validation-box'), notice: $('notice'),
  sourceLanguage: $('source-language'), targetLanguage: $('target-language'),
  sourceLanguageLabel: $('source-language-label'), targetLanguageLabel: $('target-language-label'),
  exportDialog: $('export-dialog'), exportChecks: $('export-checks'), exportSummary: $('export-summary'),
  confirmExport: $('confirm-export'),
};

function currentSegments() {
  return state.document?.segments ?? [];
}

function isInlineFormat() {
  return ['srt', 'vtt', 'txt'].includes(state.document?.format);
}

function translationFor(segment) {
  const value = state.translations.get(String(segment.id)) ?? String(segment.target ?? '');
  // Subtitle and line-text profiles have no separate target column. Their
  // parser seeds the value with the source so an untouched export is exact;
  // show that seed as an empty translation field in the editor. Track edits
  // separately so an intentional identical-to-source translation still counts.
  if (isInlineFormat() && !state.editedIds.has(String(segment.id))) return '';
  return value;
}

function segmentValidation(segment) {
  const target = translationFor(segment);
  if (!target.trim()) return { ok: true, missing: [], extra: [] };
  return validateTokens(String(segment.source ?? ''), target);
}

function isTranslated(segment) {
  return translationFor(segment).trim().length > 0;
}

function needsReview(segment) {
  return isTranslated(segment) && !segmentValidation(segment).ok;
}

function statusFor(segment) {
  if (needsReview(segment)) return 'review';
  return isTranslated(segment) ? 'done' : 'empty';
}

function stats() {
  const segments = currentSegments();
  return {
    total: segments.length,
    translated: segments.filter(isTranslated).length,
    untranslated: segments.filter((segment) => !isTranslated(segment)).length,
    review: segments.filter(needsReview).length,
  };
}

function showNotice(message, kind = 'info') {
  window.clearTimeout(state.noticeTimer);
  els.notice.textContent = message;
  els.notice.classList.toggle('is-error', kind === 'error');
  els.notice.hidden = false;
  state.noticeTimer = window.setTimeout(() => { els.notice.hidden = true; }, 5200);
}

function escapeName(value) {
  return String(value).replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').trim() || 'localization';
}

function exportFilename(filename) {
  const safe = escapeName(filename || 'localization.txt');
  const dot = safe.lastIndexOf('.');
  const stem = dot > 0 ? safe.slice(0, dot) : safe;
  const extension = dot > 0 ? safe.slice(dot) : '.txt';
  return `${stem}.localized${extension}`;
}

function setProject(documentModel) {
  state.document = documentModel;
  state.translations = new Map(documentModel.segments.map((segment) => [String(segment.id), String(segment.target ?? '')]));
  state.editedIds = new Set();
  state.activeId = documentModel.segments.length ? String(documentModel.segments[0].id) : null;
  state.filter = 'all';
  state.query = '';
  els.search.value = '';
  els.welcome.hidden = true;
  els.studio.hidden = false;
  const name = documentModel.filename || `Untitled ${formatNames[documentModel.format] ?? 'project'}`;
  els.projectTitle.textContent = name;
  els.projectFormat.textContent = (formatNames[documentModel.format] ?? 'TEXT CATALOG').toUpperCase();
  els.projectSubtitle.textContent = `${documentModel.segments.length} strings · local editing session · source file remains unchanged`;
  els.fileCardName.textContent = name;
  els.fileCardFormat.textContent = formatNames[documentModel.format] ?? 'Supported text profile';
  if (els.fileIcon) els.fileIcon.textContent = String(documentModel.format || 'TXT').toUpperCase().slice(0, 4);
  updateFilterTabs();
  renderRows();
  renderMetrics();
  selectSegment(state.activeId);
  els.exportTop.disabled = false;
  els.exportSecondary.disabled = false;
}

function clearProject() {
  state.document = null;
  state.translations.clear();
  state.editedIds.clear();
  state.activeId = null;
  state.query = '';
  state.filter = 'all';
  els.search.value = '';
  els.welcome.hidden = false;
  els.studio.hidden = true;
  els.fileCardName.textContent = 'No file loaded';
  els.fileCardFormat.textContent = 'Choose a supported file';
  if (els.fileIcon) els.fileIcon.textContent = 'TXT';
  els.exportTop.disabled = true;
  els.exportSecondary.disabled = true;
  els.fileInput.value = '';
  els.notice.hidden = true;
}

async function loadFile(file) {
  if (!file) return;
  try {
    if (file.size > 5 * 1024 * 1024) throw new Error('Files over 5 MiB are not opened in this browser workspace. Split the catalog into smaller files and try again.');
    const format = detectFormat(file.name);
    const bytes = await file.arrayBuffer();
    const text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
    const documentModel = parseDocument({ filename: file.name, text });
    if (!documentModel.segments?.length) throw new Error('This file has no translatable strings in the supported profile.');
    setProject(documentModel);
    showNotice(`${file.name} opened locally. The source file has not been changed.`);
  } catch (error) {
    const message = error instanceof TypeError && /decode|encoding|encoded/i.test(error.message)
      ? 'This file is not valid UTF-8 text. Export a UTF-8 text file and try again.'
      : (error?.message || `Could not read this ${formatNames[detectFormatSafely(file.name)] ?? 'text'} file.`);
    showNotice(message, 'error');
  } finally {
    els.fileInput.value = '';
  }
}

function detectFormatSafely(filename) {
  try { return detectFormat(filename); } catch { return 'text'; }
}

function setFilter(filter) {
  state.filter = filter;
  const visible = filteredSegments();
  if (!visible.some((segment) => String(segment.id) === state.activeId)) {
    state.activeId = visible.length ? String(visible[0].id) : null;
  }
  updateFilterTabs();
  renderRows();
}

function updateFilterTabs() {
  const counts = stats();
  document.querySelectorAll('.filter-tab').forEach((tab) => {
    const active = tab.dataset.filter === state.filter;
    tab.classList.toggle('is-selected', active);
    tab.setAttribute('aria-pressed', String(active));
  });
  $('filter-all-count').textContent = String(counts.total);
  $('filter-untranslated-count').textContent = String(counts.untranslated);
  $('filter-review-count').textContent = String(counts.review);
  $('nav-count').textContent = String(counts.total);
  $('nav-untranslated-count').textContent = String(counts.untranslated);
  $('nav-attention-count').textContent = String(counts.review);
}

function filteredSegments() {
  const query = state.query.trim().toLocaleLowerCase();
  return currentSegments().filter((segment) => {
    if (state.filter === 'untranslated' && isTranslated(segment)) return false;
    if (state.filter === 'review' && !needsReview(segment)) return false;
    if (!query) return true;
    const haystack = [segment.id, segment.source, translationFor(segment), segment.context]
      .map((value) => String(value ?? '').toLocaleLowerCase()).join('\n');
    return haystack.includes(query);
  });
}

function statusLabel(status) {
  if (status === 'done') return 'Translated';
  if (status === 'review') return 'Review';
  return 'To do';
}

function createRow(segment, index) {
  const row = document.createElement('article');
  const id = String(segment.id);
  const status = statusFor(segment);
  row.className = `segment-row${id === state.activeId ? ' is-active' : ''}`;
  row.dataset.segmentId = id;
  row.setAttribute('role', 'listitem');
  row.tabIndex = 0;

  const meta = document.createElement('div');
  meta.className = 'segment-meta';
  const key = document.createElement('span');
  key.className = 'segment-id';
  key.textContent = id || `STRING_${index + 1}`;
  const context = document.createElement('span');
  context.className = 'segment-context';
  context.textContent = String(segment.context ?? `String ${index + 1}`);
  meta.append(key, context);

  const source = document.createElement('div');
  source.className = 'segment-source';
  source.textContent = String(segment.source ?? '');

  const target = document.createElement('textarea');
  target.className = 'segment-target';
  target.rows = 2;
  target.value = translationFor(segment);
  target.placeholder = 'Add translation…';
  target.setAttribute('aria-label', `Translation for ${id}`);
  target.dataset.segmentId = id;

  const badge = document.createElement('span');
  badge.className = `segment-status${status === 'done' ? ' is-done' : ''}${status === 'review' ? ' is-review' : ''}`;
  badge.textContent = statusLabel(status);
  row.append(meta, source, target, badge);
  return row;
}

function renderRows() {
  const segments = filteredSegments();
  const fragment = document.createDocumentFragment();
  for (const [index, segment] of segments.entries()) fragment.append(createRow(segment, index));
  els.list.replaceChildren(fragment);
  els.emptyFilter.hidden = segments.length > 0;
  els.listCount.textContent = `${segments.length} ${segments.length === 1 ? 'string' : 'strings'}`;
  if (state.activeId && segments.some((segment) => String(segment.id) === state.activeId)) {
    renderInspector();
  } else {
    els.inspectorEmpty.hidden = false;
    els.inspector.hidden = true;
  }
}

function renderMetrics() {
  const counts = stats();
  const percent = counts.total ? Math.round((counts.translated / counts.total) * 100) : 0;
  $('metric-total').textContent = String(counts.total);
  $('metric-translated').textContent = String(counts.translated);
  $('metric-untranslated').textContent = String(counts.untranslated);
  $('metric-review').textContent = String(counts.review);
  $('translated-percent').textContent = `${percent}% complete`;
  $('progress-label').textContent = `${percent}%`;
  $('progress-bar').style.width = `${percent}%`;
  document.querySelector('.progress-track').setAttribute('aria-valuenow', String(percent));
  $('progress-complete').textContent = `${counts.translated} translated`;
  $('progress-remaining').textContent = `${counts.untranslated} remaining`;
  updateFilterTabs();
}

function renderInspector() {
  const segment = currentSegments().find((item) => String(item.id) === state.activeId);
  if (!segment) {
    els.inspectorEmpty.hidden = false;
    els.inspector.hidden = true;
    return;
  }
  els.inspectorEmpty.hidden = true;
  els.inspector.hidden = false;
  els.inspectorId.textContent = String(segment.id);
  els.inspectorSource.value = String(segment.source ?? '');
  els.inspectorTarget.value = translationFor(segment);
  els.charCounter.textContent = `${[...els.inspectorTarget.value].length} chars`;
  els.inspectorContext.textContent = String(segment.context ?? '');
  els.inspectorContext.hidden = !segment.context;
  const position = currentSegments().indexOf(segment) + 1;
  els.inspectorPosition.textContent = `${position} / ${currentSegments().length}`;
  els.sourceLanguageLabel.textContent = languages[els.sourceLanguage.value] ?? 'Source language';
  els.targetLanguageLabel.textContent = languages[els.targetLanguage.value] ?? 'Target language';
  updateInspectorStatus(segment);
}

function updateInspectorStatus(segment) {
  const status = statusFor(segment);
  els.inspectorStatus.textContent = status === 'done' ? 'TRANSLATED' : status === 'review' ? 'CHECK TOKENS' : 'UNTRANSLATED';
  els.inspectorStatus.className = `status-badge${status === 'done' ? ' is-done' : ''}${status === 'review' ? ' is-review' : ''}`;
  const result = segmentValidation(segment);
  if (!isTranslated(segment)) {
    els.validation.className = 'validation-box';
    els.validation.textContent = 'Keep placeholders and control tags intact when you translate this string.';
  } else if (result.ok) {
    els.validation.className = 'validation-box is-good';
    els.validation.textContent = 'Protected tokens match the source.';
  } else {
    const missing = result.missing?.length ? `Missing: ${result.missing.join(', ')}.` : '';
    const extra = result.extra?.length ? ` Added: ${result.extra.join(', ')}.` : '';
    els.validation.className = 'validation-box is-warning';
    els.validation.textContent = `Review protected tokens. ${missing}${extra}`.trim();
  }
}

function selectSegment(id) {
  if (!id) return;
  state.activeId = String(id);
  document.querySelectorAll('.segment-row').forEach((row) => row.classList.toggle('is-active', row.dataset.segmentId === state.activeId));
  renderInspector();
}

function updateTranslation(id, text) {
  const segment = currentSegments().find((item) => String(item.id) === String(id));
  if (!segment) return;
  const hasInlineText = isInlineFormat() && String(text).trim().length > 0;
  if (isInlineFormat()) {
    if (hasInlineText) state.editedIds.add(String(id));
    else state.editedIds.delete(String(id));
  }
  const value = isInlineFormat() && !hasInlineText ? String(segment.source ?? '') : String(text);
  state.translations.set(String(id), value);
  const row = [...els.list.querySelectorAll('.segment-row')].find((item) => item.dataset.segmentId === String(id));
  if (row) {
    const target = row.querySelector('.segment-target');
    if (target && target.value !== text) target.value = text;
    const badge = row.querySelector('.segment-status');
    const status = statusFor(segment);
    badge.textContent = statusLabel(status);
    badge.className = `segment-status${status === 'done' ? ' is-done' : ''}${status === 'review' ? ' is-review' : ''}`;
  }
  if (String(id) === state.activeId) {
    if (els.inspectorTarget.value !== text) els.inspectorTarget.value = text;
    els.charCounter.textContent = `${[...text].length} chars`;
    updateInspectorStatus(segment);
  }
  renderMetrics();
}

function openExportReview() {
  if (!state.document) return;
  const counts = stats();
  const checks = [
    { warning: false, text: `${counts.total} strings will be written as a separate localized copy.` },
    { warning: counts.untranslated > 0, text: counts.untranslated ? `${counts.untranslated} strings still have no translation.` : 'Every string has a translation.' },
    { warning: counts.review > 0, text: counts.review ? `${counts.review} translations have token differences to review.` : 'Placeholder and tag checks are clear.' },
    { warning: false, text: 'The imported source file will remain unchanged.' },
  ];
  els.exportChecks.replaceChildren(...checks.map((check) => {
    const row = document.createElement('div');
    row.className = 'dialog-check-row';
    const mark = document.createElement('span');
    mark.className = `dialog-check-mark${check.warning ? ' is-warning' : ''}`;
    mark.textContent = check.warning ? '!' : '✓';
    const text = document.createElement('span');
    text.textContent = check.text;
    row.append(mark, text);
    return row;
  }));
  const format = formatNames[state.document.format] ?? 'text';
  els.exportSummary.textContent = `A new ${format} file will download with your translations. Nothing is written back to the imported file or a game folder.`;
  els.exportDialog.showModal();
}

function downloadExport() {
  if (!state.document) return;
  try {
    const text = exportDocument(state.document, state.translations);
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = exportFilename(state.document.filename);
    link.hidden = true;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    els.exportDialog.close();
    showNotice(`Downloaded ${exportFilename(state.document.filename)}. Your original remains unchanged.`);
  } catch (error) {
    els.exportDialog.close();
    showNotice(error?.message || 'Could not export this file.', 'error');
  }
}

async function copySource() {
  const source = els.inspectorSource.value;
  try {
    await navigator.clipboard.writeText(source);
    showNotice('Source text copied.');
  } catch {
    els.inspectorSource.focus();
    els.inspectorSource.select();
    showNotice('Select the source text and copy it with your keyboard shortcut.');
  }
}

function loadDemo() {
  const text = JSON.stringify({
    segments: [
      { id: 'UI_CONTINUE', source: '続ける', target: 'Continue', context: 'Menu · button label' },
      { id: 'UI_LOAD', source: 'ロード', target: 'Load Game', context: 'Menu · button label' },
      { id: 'DIALOGUE_01', source: '夜が明ける前に、街道を抜けましょう。', target: 'We should leave the road before dawn.', context: 'Dialogue · companion' },
      { id: 'ITEM_HERB', source: '旅人の薬草', target: '', context: 'Inventory · item name' },
      { id: 'BATTLE_03', source: '敵が西から来る！', target: 'They are coming from the west!', context: 'Subtitle · battle callout' },
      { id: 'RESULT_01', source: '{player_name}は{count}枚の証を手に入れた。', target: '{player_name} earned {count} tokens.', context: 'Result message · placeholders' },
    ],
  }, null, 2);
  try {
    setProject(parseDocument({ filename: 'sample-dialogue.json', text }));
    els.sourceLanguage.value = 'ja-JP';
    els.targetLanguage.value = 'en-US';
    renderInspector();
    showNotice('Loaded a small, fictional sample catalog.');
  } catch (error) {
    showNotice(error?.message || 'Could not load the sample project.', 'error');
  }
}

els.fileInput.addEventListener('change', (event) => loadFile(event.currentTarget.files?.[0]));
els.browse.addEventListener('click', (event) => { event.stopPropagation(); els.fileInput.click(); });
els.replaceFile.addEventListener('click', () => els.fileInput.click());
els.dropzone.addEventListener('dragover', (event) => { event.preventDefault(); els.dropzone.classList.add('is-dragging'); });
els.dropzone.addEventListener('dragleave', () => els.dropzone.classList.remove('is-dragging'));
els.dropzone.addEventListener('drop', (event) => {
  event.preventDefault();
  els.dropzone.classList.remove('is-dragging');
  loadFile(event.dataTransfer.files?.[0]);
});
els.demo.addEventListener('click', loadDemo);
els.closeProject.addEventListener('click', clearProject);
els.exportTop.addEventListener('click', openExportReview);
els.exportSecondary.addEventListener('click', openExportReview);
els.confirmExport.addEventListener('click', downloadExport);
$('cancel-export').addEventListener('click', () => els.exportDialog.close());
$('close-export-dialog').addEventListener('click', () => els.exportDialog.close());
$('copy-source').addEventListener('click', copySource);

els.list.addEventListener('click', (event) => {
  const row = event.target.closest('.segment-row');
  if (row && !event.target.closest('.segment-target')) selectSegment(row.dataset.segmentId);
});
els.list.addEventListener('keydown', (event) => {
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('.segment-row')) {
    event.preventDefault();
    selectSegment(event.target.dataset.segmentId);
  }
});
els.list.addEventListener('input', (event) => {
  if (event.target.matches('.segment-target')) updateTranslation(event.target.dataset.segmentId, event.target.value);
});
els.inspectorTarget.addEventListener('input', (event) => updateTranslation(state.activeId, event.currentTarget.value));
els.search.addEventListener('input', (event) => { state.query = event.currentTarget.value; renderRows(); });
document.querySelectorAll('.filter-tab').forEach((tab) => tab.addEventListener('click', () => setFilter(tab.dataset.filter)));
$('nav-project').addEventListener('click', () => setFilter('all'));
$('nav-untranslated').addEventListener('click', () => setFilter('untranslated'));
$('nav-attention').addEventListener('click', () => setFilter('review'));
$('reset-filter').addEventListener('click', () => { state.query = ''; els.search.value = ''; setFilter('all'); });
els.sourceLanguage.addEventListener('change', renderInspector);
els.targetLanguage.addEventListener('change', renderInspector);
window.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    els.search.focus();
  }
  if (event.key === 'Escape' && els.exportDialog.open) els.exportDialog.close();
});

clearProject();
