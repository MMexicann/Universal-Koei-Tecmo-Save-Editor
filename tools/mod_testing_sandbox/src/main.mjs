import {
  SUPPORTED_GAMES,
  LIMITS,
  parseManifest,
  validateMod,
  buildWorkspacePlan,
  createAuditReport,
  createTroubleshootingCenterReport,
  buildProfileComponentSnapshot,
  createZipBlob,
  createNioh2ManagerPackageBlob,
  sanitizeRelativePath,
  normalizeFolderPaths,
  createImportGate,
} from "./sandbox-core.mjs";
import { saveStagedMod, loadStagedMods, removeStagedMod, clearStagedProfile } from "./workspace-store.mjs";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const ICONS = ["◈", "◇", "▧", "✳"];
const COLOR_CLASSES = ["gold", "green", "blue", "red"];
const MANIFEST_NAMES = new Set(["mod-manifest.json", "koei-mod.json", "manifest.json", "mod.json"]);

const state = {
  gameId: "wolong",
  gameVersion: "demo-1.0",
  mods: [],
  demo: true,
  route: "sandbox",
  lastHandoff: null,
  baselineInventory: null,
  persistence: "indexeddb",
};
const runExclusiveImport = createImportGate();

function fixtureMod(id, name, version, descriptors, tint, note) {
  const manifest = {
    schemaVersion: 1,
    id,
    name,
    version,
    game: "wolong",
    gameVersion: "demo-1.0",
    author: "Sandbox demo",
    description: note,
    files: descriptors.map(({ source, target }) => ({ source, target })),
  };
  const inventory = descriptors.map(({ source, content }) => ({ path: source, size: content.length }));
  const result = validateMod(manifest, state.gameId, inventory, state.gameVersion);
  const payloads = new Map(descriptors.map(({ source, content }) => [source, new TextEncoder().encode(content)]));
  return {
    ...result.mod,
    manifest,
    inventory,
    payloads,
    storageKey: `workspaces/${manifest.game}/${encodeURIComponent(manifest.gameVersion)}/${manifest.id}`,
    tint,
    demoFixture: true,
    valid: result.ok,
    validationErrors: result.errors,
  };
}

function loadDemo() {
  state.gameId = "wolong";
  state.gameVersion = "demo-1.0";
  state.mods = [
    fixtureMod("warm-ember-lighting", "Warm Ember Lighting", "1.0.4", [
      { source: "data/tone-map.bin", target: "Data/ToneMap.bin", content: "safe inert demo fixture: tone map" },
      { source: "data/ambient-table.bin", target: "Data/Ambient/Table.bin", content: "safe inert demo fixture: ambient table" },
      { source: "textures/ember-palette.dds", target: "Textures/EmberPalette.dds", content: "safe inert demo fixture: texture" },
    ], 0, "A local-only lighting sample with inert placeholder payloads."),
    fixtureMod("quiet-hud", "Quiet HUD Rework", "2.1.0", [
      { source: "data/tone-map.bin", target: "data/tonemap.BIN", content: "safe inert demo fixture: alternate tone map" },
      { source: "ui/compass.bin", target: "UI/Compass.bin", content: "safe inert demo fixture: compass" },
    ], 1, "A sample package that intentionally collides with the lighting mod."),
  ];
  state.baselineInventory = null;
  state.demo = true;
  state.persistence = "memory";
  render();
}

function fillGameOptions() {
  const select = $("#game-select");
  for (const game of SUPPORTED_GAMES) {
    const option = document.createElement("option");
    option.value = game.id;
    option.textContent = game.label;
    select.append(option);
  }
  select.value = state.gameId;
  $("#game-build").value = state.gameVersion;
}

function gameLabel(gameId = state.gameId) {
  return SUPPORTED_GAMES.find((game) => game.id === gameId)?.label || "Unsupported game";
}

function gameMark(gameId = state.gameId) {
  return ({ dw8xl: "DW8", wolong: "WL", nioh3: "N3", samurai5_pc: "SW5", wo4_ultimate: "WO4", atelier_ryza3_dx_pc: "A3" })[gameId] || "PC";
}

function savedItemToMod(item, index, gameId, gameVersion) {
  const result = validateMod(item.manifest, gameId, item.inventory, gameVersion);
  return {
    ...item,
    ...result.mod,
    payloads: item.payloads,
    inventory: item.inventory,
    storageKey: item.storageKey,
    tint: index % COLOR_CLASSES.length,
    storageBackend: item.storageBackend || "indexeddb",
    demoFixture: false,
    valid: result.ok,
    validationErrors: result.errors,
  };
}

async function switchWorkspaceProfile(gameId, gameVersion) {
  if (gameId === state.gameId && gameVersion === state.gameVersion) return;
  state.gameId = gameId;
  state.gameVersion = gameVersion;
  state.demo = false;
  if (state.baselineInventory && (state.baselineInventory.gameId !== gameId || state.baselineInventory.gameVersion !== gameVersion)) state.baselineInventory = null;
  let allStored = [];
  try { allStored = await loadStagedMods(); } catch { allStored = []; }
  state.mods = await Promise.all(allStored
    .filter((item) => item.gameId === gameId && item.gameVersion === gameVersion)
    .map((item, index) => savedItemToMod(item, index, gameId, gameVersion)));
  state.persistence = state.mods.length ? "indexeddb" : globalThis.indexedDB ? "indexeddb" : "memory";
  render();
}

function digits(value) {
  return String(value).padStart(2, "0");
}

function textNode(tag, text, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = String(text ?? "");
  return node;
}

function currentPlan() {
  return buildWorkspacePlan(state.mods.map((mod) => ({
    ...mod,
    valid: mod.valid,
    status: mod.valid ? "ready" : "blocked",
  })), matchingBaselinePaths(), { gameId: state.gameId, gameVersion: state.gameVersion });
}

function storageSummary() {
  if (state.demo) return "memory/demo-fixtures";
  const types = new Set(state.mods.map((mod) => mod.storageBackend || "memory"));
  if (types.size > 1) return "mixed-browser-storage/per-mod-id-namespace";
  if (types.has("indexeddb")) return "browser-indexeddb/per-mod-id-namespace";
  return "browser-memory/per-mod-id-namespace";
}

function matchingBaselinePaths() {
  if (!state.baselineInventory) return [];
  if (state.baselineInventory.gameId !== state.gameId || state.baselineInventory.gameVersion !== state.gameVersion) return [];
  return state.baselineInventory.paths;
}

function revalidateMods() {
  state.mods = state.mods.map((item) => {
    const result = validateMod(item.manifest, state.gameId, item.inventory, state.gameVersion);
    if (!result.ok) return { ...item, valid: false, validationErrors: result.errors };
    return { ...item, ...result.mod, valid: true, validationErrors: [], payloads: item.payloads, storageKey: item.storageKey, tint: item.tint, demoFixture: item.demoFixture };
  });
}

function renderModRows(plan) {
  const body = $("#mod-list");
  body.replaceChildren();
  $("#empty-mods").classList.toggle("hidden", state.mods.length > 0);
  for (let index = 0; index < state.mods.length; index++) {
    const mod = state.mods[index];
    const row = document.createElement("tr");
    const titleCell = document.createElement("td");
    const titleWrap = document.createElement("div"); titleWrap.className = "mod-title-cell";
    const tile = textNode("span", ICONS[mod.tint ?? index % ICONS.length], `mod-tile ${COLOR_CLASSES[mod.tint ?? index % COLOR_CLASSES.length]}`);
    const title = document.createElement("span"); title.className = "mod-name";
    title.append(textNode("b", mod.name));
    title.append(textNode("small", `browser namespace · ${mod.gameVersion} · ${mod.id}`));
    titleWrap.append(tile, title); titleCell.append(titleWrap); row.append(titleCell);
    row.append(textNode("td", `v${mod.version}`, "mono"));
    const count = document.createElement("td"); const countWrap = document.createElement("span"); countWrap.className = "file-count";
    countWrap.append(textNode("span", "▤", "file-count-icon"), textNode("span", (mod.files || []).length)); count.append(countWrap); row.append(count);
    const manifestCell = document.createElement("td");
    const collidingModIds = new Set(plan.conflicts.filter((conflict) => conflict.mods?.includes(mod.name)).flatMap((conflict) => conflict.mods || []));
    const incompatible = !mod.valid || mod.gameId !== state.gameId || mod.gameVersion !== state.gameVersion;
    const status = textNode("span", incompatible ? "Blocked" : collidingModIds.size ? "Conflict" : "Ready", `status-pill${incompatible ? " blocked" : collidingModIds.size ? " warning" : ""}`);
    status.prepend(textNode("span", "", "tiny-live"));
    manifestCell.append(status); row.append(manifestCell);
    const menuCell = document.createElement("td");
    const remove = textNode("button", "×", "row-menu"); remove.type = "button"; remove.dataset.action = "remove-mod"; remove.dataset.modId = mod.id; remove.setAttribute("aria-label", `Remove ${mod.name}`); remove.title = "Remove from this workspace";
    menuCell.append(remove); row.append(menuCell); body.append(row);
  }
}

function renderChanges(plan) {
  const list = $("#change-list"); list.replaceChildren();
  for (const change of plan.changes.slice(0, 80)) {
    const row = document.createElement("div"); row.className = "change-row";
    const path = document.createElement("div"); path.className = "change-path";
    const pathText = textNode("b", change.path); pathText.title = change.path;
    path.append(pathText, textNode("small", `from ${change.mods.join(", ")}`));
    const action = document.createElement("span"); action.className = `change-action ${change.action === "replace" ? "replace" : ""}`;
    action.append(textNode("span", "", "action-dot"), textNode("span", change.action === "replace" ? "REPLACE" : "ADD"));
    row.append(path, action, textNode("span", change.mods.join(" · "), "source-label"), textNode("span", change.action === "replace" ? "baseline" : "staged", "change-kind"));
    list.append(row);
  }
  if (plan.changes.length > 80) list.append(textNode("div", `${plan.changes.length - 80} additional destinations are included in the audit report.`, "change-kind"));
  $("#change-count").textContent = digits(plan.fileCount);
  const baseline = $("#baseline-state"); baseline.replaceChildren();
  if (!state.baselineInventory) {
    baseline.append(textNode("span", "◎", "baseline-orb"), textNode("span", "No Mod Manager inventory loaded"), textNode("span", "Preview shows staged additions", "baseline-note"));
  } else if (state.baselineInventory.gameId !== state.gameId || state.baselineInventory.gameVersion !== state.gameVersion) {
    baseline.append(textNode("span", "!", "baseline-orb"), textNode("span", "Inventory profile does not match this workspace"), textNode("span", "REPLACE preview paused", "baseline-note"));
  } else {
    baseline.append(textNode("span", "◎", "baseline-orb"), textNode("span", `Mod Manager inventory · ${state.baselineInventory.paths.length} paths`), textNode("span", "Matching targets show REPLACE", "baseline-note"));
  }
  const conflictBanner = $("#conflict-banner");
  conflictBanner.classList.toggle("hidden", plan.conflicts.length === 0);
  if (plan.conflicts.length) {
    $("#conflict-title").textContent = `${plan.conflicts.length} path collision${plan.conflicts.length === 1 ? "" : "s"} detected`;
    $("#conflict-description").textContent = plan.conflicts[0].message;
  }
}

function renderGate(plan) {
  const hasMods = state.mods.length > 0;
  const allValid = hasMods && state.mods.every((mod) => mod.valid && mod.gameId === state.gameId && mod.gameVersion === state.gameVersion);
  const uniqueTargets = plan.conflicts.length === 0;
  const checks = [
    { label: "Package manifests present", pass: hasMods, hint: hasMods ? "LOADED" : "MISSING" },
    { label: "Game & build profile match", pass: allValid, hint: allValid ? "MATCHED" : "REVIEW" },
    { label: "Required dependencies are staged", pass: !plan.validationIssues.some((item) => item.code.startsWith("dependency_")), hint: plan.validationIssues.some((item) => item.code.startsWith("dependency_")) ? "MISSING" : "CLEAR" },
    { label: "Install destinations are unique", pass: uniqueTargets && hasMods, hint: uniqueTargets && hasMods ? "CLEAR" : "COLLISION" },
  ];
  const container = $("#gate-checks"); container.replaceChildren();
  for (const check of checks) {
    const row = document.createElement("div"); row.className = `gate-check ${check.pass ? "pass" : "fail"}`;
    row.append(textNode("span", check.pass ? "✓" : "!", "gate-check-mark"), textNode("span", check.label), textNode("em", check.hint)); container.append(row);
  }
  const passed = checks.filter((check) => check.pass).length;
  $("#gate-progress-fill").style.width = `${Math.round((passed / checks.length) * 100)}%`;
  $("#gate-progress-label").textContent = `${passed} of ${checks.length} checks passed`;
  const ready = plan.ok && allValid;
  $("#export-button").disabled = !ready;
  $("#export-button-rail").disabled = !ready;
  $("#manifest-health").replaceChildren(textNode("span", ready ? "✓" : "!", `health-ring${ready ? " healthy" : ""}`), textNode("span", ready ? "Ready to review" : "Review needed"));
  const issueCount = state.mods.reduce((count, mod) => count + (mod.validationErrors?.length || 0), 0) + plan.conflicts.length;
  $("#manifest-health-note").textContent = ready ? "All preflight checks passed" : issueCount ? `${issueCount} item${issueCount === 1 ? "" : "s"} need attention` : "Add a compatible package";
}

function buildHandoff(contract = "koei.mod-sandbox.handoff/v1") {
  const plan = currentPlan();
  return {
    contract,
    createdAt: new Date().toISOString(),
    workspace: { gameId: state.gameId, gameName: gameLabel(), gameVersion: state.gameVersion, storage: storageSummary(), baselineInventory: state.baselineInventory ? { contract: "koei.mod-manager.inventory/v1", pathCount: state.baselineInventory.paths.length } : null },
    compatibility: { source: "manifest-declared", selectedGameAndBuildChecked: true, workshopVersionRangesSupported: true, independentlyVerified: false },
    mods: state.mods.map((mod) => ({ id: mod.id, name: mod.name, version: mod.version, gameId: mod.gameId, gameVersion: mod.gameVersion, compatibleGameVersion: mod.compatibleGameVersion || mod.gameVersion, platform: mod.platform || "Windows PC", manifestFormat: mod.manifestFormat || "koei-mod-sandbox.v1", dependencies: mod.dependencies || [], valid: mod.valid, files: (mod.files || []).map((file) => ({ source: file.source, target: file.target })) })),
    plan: { ready: plan.ok, fileCount: plan.fileCount, validationIssues: plan.validationIssues, conflicts: plan.conflicts, changes: plan.changes },
    compatibilityWarnings: plan.compatibilityWarnings,
    safety: { codeExecuted: false, gameInstallationRead: false, originalInstallationModified: false, exportIsConfirmedZipDownloadOnly: true },
  };
}

function workshopBrief() {
  const issues = state.mods.flatMap((mod) => (mod.validationErrors || []).map((item) => ({ modId: mod.id, code: item.code, message: item.message })));
  return {
    ...buildHandoff("koei.mod-sandbox.workshop-brief/v1"),
    supportedWorkshopInput: { manifest: "mod.json", projectFolderImport: true, verifiedZipImport: false, verificationReportTrusted: false },
    requiredManifest: { schema_version: 1, mod_id: "unique-mod-id", name: "Display name", version: "1.0.0", author: "Author", description: "", game_id: state.gameId, game_version: state.gameVersion, platform: "Windows PC", license: "SPDX identifier or description", dependencies: [], replacements: [{ source_path: "assets/replacement.bin", target_path: "Data/replacement.bin", sha256: "<64 lowercase hexadecimal characters>", license: "SPDX identifier or description", attribution: "", rights_status: "creator-owned" }] },
    validationIssues: issues,
    compatibilityWarnings: currentPlan().compatibilityWarnings,
  };
}

function reportText() {
  return createAuditReport(currentPlan(), state.mods, state.gameId, state.gameVersion);
}

function troubleshootingCenterReport() {
  return createTroubleshootingCenterReport(currentPlan(), state.mods, state.gameId, state.gameVersion);
}

function managerComponentSnapshot() {
  const plan = currentPlan();
  const payload = {
    schema_version: 1,
    load_order: state.mods.map((mod) => mod.id),
    mods: state.mods.map((mod, index) => ({
      id: mod.id,
      name: mod.name,
      version: mod.version,
      enabled: false,
      priority: index,
      files: mod.files.map((file) => ({ source: file.source, target: file.target, sha256: file.sha256 })),
      manifest_valid: mod.valid,
    })),
    sandbox_preflight: { ready: plan.ok, conflicts: plan.conflicts, validation_issues: plan.validationIssues, compatibility_warnings: plan.compatibilityWarnings },
    dependencies: state.mods.map((mod) => ({ mod_id: mod.id, requires: mod.dependencies || [] })),
    safety: { code_executed: false, file_contents_included: false, auto_apply: false, requires_explicit_manager_review: true },
  };
  return buildProfileComponentSnapshot(state.gameId, state.gameVersion, payload);
}

function managerComponentSnapshotText() {
  return JSON.stringify(managerComponentSnapshot(), null, 2);
}

function renderIntegrations() {
  const managerList = $("#manager-list"); managerList.replaceChildren();
  const nioh2Manager = state.gameId === "nioh2_pc";
  $("#manager-profile-panel").classList.toggle("hidden", nioh2Manager);
  $("#manager-native-panel").classList.toggle("hidden", !nioh2Manager);
  $("#manager-summary-title").textContent = nioh2Manager ? "Nioh 2 package library handoff" : "Playthrough profile component preview";
  $("#manager-summary-copy").textContent = nioh2Manager
    ? "Create one ZIP with the Mod Manager's supported .ini and asset layout plus root koei-mod.json. The manager revalidates each imported ZIP and requires its own confirmation before any game file changes."
    : "Preview the bounded ProfileComponentSnapshot for Smart Playthrough Profiles. The JSON is inert profile data and does not directly import to or install through a Mod Manager.";
  for (const id of ["manager-download-component", "manager-copy-component", "manager-copy-component-secondary", "manager-download-component-secondary"]) {
    const button = $(`#${id}`);
    if (button) button.disabled = nioh2Manager;
  }
  $("#manager-count").textContent = digits(state.mods.length);
  if (!state.mods.length) managerList.append(textNode("div", "No staged mods to hand off yet.", "contract-copy"));
  for (let index = 0; index < state.mods.length; index++) {
    const mod = state.mods[index]; const row = document.createElement("div"); row.className = "handoff-row";
    row.append(textNode("span", ICONS[mod.tint ?? index % ICONS.length], `mod-tile ${COLOR_CLASSES[mod.tint ?? index % COLOR_CLASSES.length]}`));
    const copy = document.createElement("span"); copy.append(textNode("b", mod.name), textNode("small", `${mod.files.length} destinations · ${mod.gameVersion}`));
    row.append(copy, textNode("span", mod.valid ? "✓" : "!", "integration-arrow"));
    if (nioh2Manager && mod.gameId === "nioh2_pc") {
      const download = textNode("button", "Download manager ZIP", "button button-quiet button-small");
      download.type = "button";
      download.dataset.action = "download-manager-package";
      download.dataset.modId = mod.id;
      download.disabled = !mod.valid;
      row.append(download);
    }
    managerList.append(row);
  }
  try { $("#manager-component-payload").textContent = nioh2Manager ? "Nioh 2 uses the manager-compatible ZIP package route above; it is not a registered save-profile component." : managerComponentSnapshotText(); }
  catch (error) { $("#manager-component-payload").textContent = error.message; }

  const plan = currentPlan();
  const issueList = $("#workshop-issues"); issueList.replaceChildren();
  const issues = [
    ...state.mods.flatMap((mod) => (mod.validationErrors || []).map((item) => `${mod.name}: ${item.message}`)),
    ...plan.validationIssues.map((item) => item.message),
  ];
  const warnings = plan.compatibilityWarnings.map((item) => item.message);
  if (!issues.length && !warnings.length) issueList.append(textNode("div", state.mods.length ? "Current manifests match the selected game profile and contain safe paths." : "Add a mod folder to run manifest validation.", `issue-item ${state.mods.length ? "ok" : ""}`));
  else {
    for (const issue of issues.slice(0, 20)) issueList.append(textNode("div", issue, "issue-item"));
    for (const warning of warnings.slice(0, Math.max(0, 20 - issues.length))) issueList.append(textNode("div", `Warning: ${warning}`, "issue-item warning"));
  }

  const summary = $("#troubleshoot-summary"); summary.replaceChildren();
  [
    ["Staged mods", state.mods.length, false],
    ["Planned paths", plan.fileCount, false],
    ["Manifest or compatibility errors", issues.length, issues.length > 0],
    ["Dependency warnings", warnings.length, false],
    ["Destination conflicts", plan.conflicts.length, plan.conflicts.length > 0],
  ].forEach(([label, value, issue]) => {
    const row = document.createElement("div"); row.append(textNode("span", "", `summary-dot${issue ? " issue" : ""}`), textNode("span", label), textNode("b", value)); summary.append(row);
  });
}

function render() {
  const plan = currentPlan();
  const nioh2Manager = state.gameId === "nioh2_pc";
  $("#game-select").value = state.gameId;
  $("#game-build").value = state.gameVersion;
  $("#side-game-name").textContent = gameLabel();
  $("#side-game-mark").textContent = gameMark();
  $("#demo-badge").textContent = state.demo ? "DEMO DATA" : "LOCAL FILES";
  $("#export-button").disabled = nioh2Manager;
  $("#export-button").title = nioh2Manager ? "Use the dedicated Nioh 2 Mod Manager ZIP handoff." : "Prepare a generic staging ZIP after explicit confirmation.";
  $("#metric-mods").textContent = digits(state.mods.length);
  $("#metric-mods-note").textContent = `${state.mods.filter((mod) => mod.valid).length} manifests matched`;
  $("#metric-changes").textContent = digits(plan.fileCount);
  $("#metric-changes-note").textContent = "Across staged destinations";
  $("#metric-conflicts").textContent = digits(plan.conflicts.length);
  $("#metric-conflicts-note").textContent = plan.conflicts.length ? "Resolve before export" : "No destination collisions";
  $("#workspace-state").textContent = state.demo ? "Sample workspace isolated" : `${state.mods.length} per-mod namespace${state.mods.length === 1 ? "" : "s"} isolated`;
  $("#workspace-updated").textContent = state.demo ? "· inert sample payloads" : storageSummary().includes("indexeddb") ? "· IndexedDB, namespaced by mod ID" : "· browser tab memory only";
  renderModRows(plan);
  renderChanges(plan);
  renderGate(plan);
  renderIntegrations();
}

function toast(message, { error = false, title = "" } = {}) {
  const region = $("#toast-region");
  const item = document.createElement("div"); item.className = `toast${error ? " error" : ""}`;
  if (title) item.append(textNode("strong", title));
  item.append(textNode("span", message)); region.append(item);
  setTimeout(() => item.remove(), 4200);
}

function dialogOpen(id) {
  const dialog = $(id);
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}

function routeTo(route) {
  state.route = route;
  $$(".route-view").forEach((view) => view.classList.toggle("active", view.dataset.view === route));
  $$(".nav-item[data-route]").forEach((item) => {
    const active = item.dataset.route === route;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openExportDialog() {
  if (state.gameId === "nioh2_pc") {
    toast("Use Mod Manager to download a package that matches its Nioh 2 importer.", { error: true, title: "Manager package handoff" });
    routeTo("manager");
    return;
  }
  const plan = currentPlan();
  if (!plan.ok || state.mods.some((mod) => !mod.valid)) {
    toast("Resolve manifest, profile, and destination checks before preparing a package.", { error: true, title: "Export is blocked" });
    if (plan.conflicts.length) $("#conflict-banner").scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  const summary = $("#export-summary"); summary.replaceChildren();
  [[state.mods.length, "MODS"], [plan.fileCount, "DESTINATIONS"], ["ZIP", "DOWNLOAD"]].forEach(([value, label]) => {
    const item = document.createElement("div"); item.append(textNode("b", value), textNode("span", label)); summary.append(item);
  });
  $("#export-confirm-checkbox").checked = false;
  $("#confirm-export").disabled = true;
  dialogOpen("#export-dialog");
}

function downloadBlob(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a"); link.href = url; link.download = fileName; link.hidden = true;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

async function exportPackage() {
  const plan = currentPlan();
  if (!$("#export-confirm-checkbox").checked) return;
  if (!plan.ok || state.mods.some((mod) => !mod.valid)) {
    $("#export-dialog").close();
    toast("The workspace changed; rerun validation before exporting.", { error: true });
    return;
  }
  const installManifest = {
    contract: "koei.mod-sandbox.install-manifest/v1",
    selectedGame: { id: state.gameId, name: gameLabel(), gameVersion: state.gameVersion },
    compatibility: { source: "manifest-declared exact match", independentlyVerified: false },
    createdAt: new Date().toISOString(),
    package: state.mods.map((mod) => ({ id: mod.id, name: mod.name, version: mod.version, gameVersion: mod.gameVersion, files: mod.files.map((file) => ({ source: file.source, target: file.target, sha256: file.sha256 })) })),
    safety: { codeExecuted: false, originalGameInstallationModified: false, requiresSeparateDeploymentReview: true },
  };
  const entries = [{ path: ".koei-mod-sandbox/install-manifest.json", data: JSON.stringify(installManifest, null, 2), system: true }];
  try {
    for (const mod of state.mods) {
      for (const file of mod.files) {
        const payload = mod.payloads.get(file.source);
        if (!payload) throw new Error(`Staged payload is missing: ${file.source}`);
        entries.push({ path: file.target, data: payload });
      }
    }
    const archive = await createZipBlob(entries);
    const slug = `${state.gameId}-${state.gameVersion}`.toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "game";
    downloadBlob(archive, `koei-mod-stage-${slug}.zip`);
    $("#export-dialog").close();
    toast("The staging ZIP is ready. No original game files were changed.", { title: "Package downloaded" });
  } catch (error) {
    $("#export-dialog").close();
    toast(error.message || "Package creation failed.", { error: true, title: "Export blocked" });
  }
}

async function downloadNioh2ManagerPackage(modId) {
  const mod = state.mods.find((item) => item.id === modId);
  if (!mod || mod.gameId !== "nioh2_pc" || !mod.valid) {
    toast("Select a validated Nioh 2 mod package first.", { error: true, title: "Manager export blocked" });
    return;
  }
  try {
    const archive = await createNioh2ManagerPackageBlob(mod);
    const slug = mod.id.toLowerCase().replace(/[^a-z0-9._-]+/g, "-").slice(0, 48) || "nioh2-mod";
    downloadBlob(archive, `nioh2-manager-${slug}.zip`);
    toast("The ZIP is ready for import into the Mod Manager library. It does not install or change game files.", { title: "Manager package ready" });
  } catch (error) {
    toast(error.message || "Package creation failed.", { error: true, title: "Manager export blocked" });
  }
}

function startDownloadReport() {
  const report = new Blob([reportText()], { type: "application/json;charset=utf-8" });
  downloadBlob(report, `koei-mod-sandbox-audit-${state.gameId}.json`);
  toast("AI-readable audit report downloaded. Mod file contents are not included.", { title: "Audit report ready" });
}

function startDownloadTroubleshootingReport() {
  const report = troubleshootingCenterReport();
  downloadBlob(new Blob([JSON.stringify(report, null, 2)], { type: "application/json;charset=utf-8" }), `koei-game-troubleshooting-${state.gameId}.json`);
  toast("Troubleshooting Center schema report downloaded. It covers sandbox preflight only; installation checks remain unchecked.", { title: "Troubleshooting report ready" });
}

async function copyText(content) {
  try {
    await navigator.clipboard.writeText(content);
    toast("Handoff copied as JSON. No mod file contents were included.", { title: "Handoff ready" });
    return true;
  } catch {
    toast("Clipboard access is unavailable here. Use the visible JSON preview or download the audit report.", { error: true, title: "Copy unavailable" });
    return false;
  }
}

async function sendHandoff(contract) {
  const payload = contract === "koei.mod-sandbox.workshop-brief/v1" ? workshopBrief() : contract === "koei.mod-sandbox.troubleshooting-report/v1" ? JSON.parse(reportText()) : buildHandoff(contract || "koei.mod-sandbox.manager-handoff/v1");
  state.lastHandoff = payload;
  const serialized = JSON.stringify(payload, null, 2);
  if (new TextEncoder().encode(serialized).byteLength > LIMITS.manifestBytes) {
    toast("This JSON handoff exceeds the 256 KiB contract limit.", { error: true, title: "Handoff refused" });
    return;
  }
  window.dispatchEvent(new CustomEvent("koei:mod-sandbox:handoff", { detail: payload }));
  if (window.location.origin && window.location.origin !== "null") {
    window.postMessage({ type: payload.contract, payload }, window.location.origin);
  }
  await copyText(serialized);
}

async function sendTroubleshootingReport() {
  const payload = troubleshootingCenterReport();
  const serialized = JSON.stringify(payload, null, 2);
  if (new TextEncoder().encode(serialized).byteLength > LIMITS.manifestBytes) {
    toast("This Troubleshooting Center report exceeds the 256 KiB contract limit.", { error: true, title: "Handoff refused" });
    return;
  }
  state.lastHandoff = payload;
  window.dispatchEvent(new CustomEvent("koei:game-troubleshooting:report", { detail: payload }));
  if (window.location.origin && window.location.origin !== "null") {
    window.postMessage({ type: "koei-game-troubleshooting", payload }, window.location.origin);
  }
  await copyText(serialized);
}

async function copyManagerComponentSnapshot() {
  try {
    const payload = managerComponentSnapshot();
    const serialized = JSON.stringify(payload, null, 2);
    window.dispatchEvent(new CustomEvent("koei:profile-component-snapshot", { detail: payload }));
    if (window.location.origin && window.location.origin !== "null") window.postMessage(payload, window.location.origin);
    await copyText(serialized);
  } catch (error) { toast(error.message, { error: true, title: "Snapshot refused" }); }
}

function downloadManagerComponentSnapshot() {
  try {
    const serialized = managerComponentSnapshotText();
    downloadBlob(new Blob([serialized], { type: "application/json;charset=utf-8" }), `mod-manager-component-${state.gameId}.json`);
    toast("The Mod Manager component snapshot is ready for explicit import and review.", { title: "Snapshot downloaded" });
  } catch (error) { toast(error.message, { error: true, title: "Snapshot refused" }); }
}

function normalizedUploadFiles(fileList) {
  const raw = [...fileList];
  const sourcePaths = raw.map((file) => file.webkitRelativePath || file.name);
  const normalizedPaths = normalizeFolderPaths(sourcePaths);
  return raw.map((file, index) => ({ file, path: normalizedPaths[index], size: file.size, type: file.type }));
}

async function calculateSha256(file) {
  if (!globalThis.crypto?.subtle || typeof file.arrayBuffer !== "function") throw new Error("This browser cannot verify declared SHA-256 hashes.");
  if (file.size > LIMITS.hashBytes) throw new Error("SHA-256 verification is limited to files up to 64 MiB.");
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function importFolderUnlocked(fileList) {
  const files = normalizedUploadFiles(fileList);
  if (!files.length) return;
  if (files.length > LIMITS.fileCount) {
    toast(`A folder can contain at most ${LIMITS.fileCount.toLocaleString()} files.`, { error: true, title: "Import blocked" });
    return;
  }
  const manifests = files.filter((entry) => MANIFEST_NAMES.has(entry.path.split("/").at(-1).toLowerCase()));
  if (manifests.length !== 1) {
    toast(manifests.length ? "Add exactly one mod-manifest.json, koei-mod.json, manifest.json, or Workshop mod.json to each folder." : "This folder has no supported JSON manifest.", { error: true, title: "Manifest required" });
    return;
  }
  const manifestFile = manifests[0].file;
  if (manifestFile.size > LIMITS.manifestBytes) {
    toast("Manifest exceeds the 256 KiB size limit.", { error: true, title: "Manifest too large" });
    return;
  }
  let manifest;
  try { manifest = parseManifest(await manifestFile.text()); }
  catch (error) { toast(error.message, { error: true, title: "Manifest rejected" }); return; }
  const nativeWorkshopManifest = "mod_id" in manifest || "replacements" in manifest || "schema_version" in manifest;
  if (nativeWorkshopManifest && manifestFile.path !== "mod.json") {
    toast("Workshop projects must place mod.json at the selected project folder root.", { error: true, title: "Workshop manifest location" });
    return;
  }

  const totalSize = files.reduce((total, entry) => total + entry.size, 0);
  if (files.some((entry) => entry.size > LIMITS.fileBytes) || totalSize > LIMITS.fileBytes) {
    toast("The folder exceeds the 256 MiB file or total size limit.", { error: true, title: "Import too large" });
    return;
  }
  const inventory = files.map(({ path, size, file }) => ({ path, size, file }));
  const preflight = validateMod(manifest, state.gameId, undefined, state.gameVersion);
  if (!preflight.ok) {
    toast(preflight.errors.slice(0, 3).map((item) => item.message).join(" "), { error: true, title: "Manifest needs attention" });
    return;
  }
  try {
    for (const descriptor of preflight.mod.files) {
      if (!descriptor.sha256) continue;
      const item = inventory.find((entry) => entry.path.toLocaleLowerCase("en-US") === descriptor.source.toLocaleLowerCase("en-US"));
      if (item) item.sha256 = await calculateSha256(item.file);
    }
  } catch (error) {
    toast(error.message, { error: true, title: "Hash verification unavailable" });
    return;
  }
  const result = validateMod(manifest, state.gameId, inventory, state.gameVersion);
  if (!result.ok) {
    toast(result.errors.slice(0, 3).map((item) => item.message).join(" "), { error: true, title: "Manifest needs attention" });
    return;
  }
  if (state.mods.some((mod) => mod.id.toLowerCase() === result.mod.id.toLowerCase())) {
    toast(`The mod ID ${result.mod.id} is already staged. Remove the existing package before importing it again.`, { error: true, title: "Duplicate mod ID" });
    return;
  }
  const filesByPath = new Map(files.map((entry) => [entry.path.toLocaleLowerCase("en-US"), entry.file]));
  const payloads = new Map(result.mod.files.map((entry) => [entry.source, filesByPath.get(entry.source.toLocaleLowerCase("en-US"))]));
  const mod = {
    ...result.mod,
    manifest,
    inventory,
    payloads,
    storageKey: `workspaces/${state.gameId}/${encodeURIComponent(state.gameVersion)}/${result.mod.id}`,
    valid: true,
    validationErrors: [],
    tint: state.mods.length % COLOR_CLASSES.length,
    demoFixture: false,
  };
  const isPersisted = await saveStagedMod(mod);
  mod.storageBackend = isPersisted ? "indexeddb" : "memory";
  state.persistence = mod.storageBackend;
  state.mods.push(mod);
  state.demo = false;
  render();
    toast(state.persistence === "indexeddb" ? `${mod.name} is staged in IndexedDB under its own mod-ID namespace.` : `${mod.name} is staged in a per-mod memory namespace in this tab.`, { title: "Mod added" });
}

async function importFolder(fileList) {
  const started = await runExclusiveImport(() => importFolderUnlocked(fileList));
  if (!started) {
    toast("Wait for the current folder import to finish before starting another.", { error: true, title: "Import already running" });
  }
}

async function importManagerInventory(file) {
  if (!file) return;
  if (file.size > LIMITS.manifestBytes) {
    toast("Inventory exceeds the 256 KiB size limit.", { error: true, title: "Inventory rejected" });
    return;
  }
  let inventory;
  try { inventory = parseManifest(await file.text()); }
  catch (error) { toast(error.message, { error: true, title: "Inventory rejected" }); return; }
  if (inventory.contract !== "koei.mod-manager.inventory/v1") {
    toast("Expected contract koei.mod-manager.inventory/v1.", { error: true, title: "Inventory contract mismatch" });
    return;
  }
  if (inventory.gameId !== state.gameId || inventory.gameVersion !== state.gameVersion) {
    toast("Inventory game ID and build/profile must exactly match the selected workspace.", { error: true, title: "Inventory profile mismatch" });
    return;
  }
  if (!Array.isArray(inventory.files) || inventory.files.length > LIMITS.filesPerManifest) {
    toast(`Inventory files must be an array with at most ${LIMITS.filesPerManifest.toLocaleString()} paths.`, { error: true, title: "Inventory rejected" });
    return;
  }
  const paths = [];
  const seen = new Set();
  try {
    for (const item of inventory.files) {
      const raw = typeof item === "string" ? item : item?.path ?? item?.target;
      const path = sanitizeRelativePath(raw);
      const key = path.toLocaleLowerCase("en-US");
      if (seen.has(key)) throw new Error(`Duplicate inventory path: ${path}`);
      seen.add(key); paths.push(path);
    }
  } catch (error) {
    toast(error.message, { error: true, title: "Unsafe inventory path" });
    return;
  }
  state.baselineInventory = { gameId: inventory.gameId, gameVersion: inventory.gameVersion, paths, sourceName: file.name };
  render();
  toast(`${paths.length} destination paths imported as read-only metadata. No game files were opened.`, { title: "Mod Manager inventory loaded" });
}

async function newWorkspace() {
  if (state.mods.some((mod) => !mod.demoFixture) && !window.confirm("Clear the staged browser workspace and its saved mod namespaces?")) return;
  await clearStagedProfile(state.gameId, state.gameVersion);
  state.mods = [];
  state.baselineInventory = null;
  state.demo = false;
  state.persistence = "indexeddb";
  render();
  toast("A new empty browser workspace is ready.", { title: "Workspace cleared" });
}

async function resetDemoWorkspace() {
  if (state.mods.some((mod) => !mod.demoFixture) && !window.confirm("Clear saved mod namespaces and load the demo workspace?")) return;
  await clearStagedProfile(state.gameId, state.gameVersion);
  loadDemo();
}

function focusConflicts() {
  const first = $("#conflict-banner");
  if (!first.classList.contains("hidden")) first.scrollIntoView({ behavior: "smooth", block: "center" });
}

document.addEventListener("click", async (event) => {
  const routeButton = event.target.closest("[data-route]");
  if (routeButton) { routeTo(routeButton.dataset.route); return; }
  const actionButton = event.target.closest("[data-action]");
  if (!actionButton) return;
  const action = actionButton.dataset.action;
  if (action === "add-mod") $("#folder-input").click();
  else if (action === "reset-demo") resetDemoWorkspace();
  else if (action === "new-workspace") newWorkspace();
  else if (action === "show-safety") dialogOpen("#safety-dialog");
  else if (action === "open-export") openExportDialog();
  else if (action === "download-report") startDownloadReport();
  else if (action === "download-troubleshooting-report") startDownloadTroubleshootingReport();
  else if (action === "copy-troubleshooting-report") sendTroubleshootingReport();
  else if (action === "focus-conflicts") focusConflicts();
  else if (action === "copy-handoff") sendHandoff("koei.mod-sandbox.manager-handoff/v1");
  else if (action === "copy-workshop-handoff") sendHandoff("koei.mod-sandbox.workshop-brief/v1");
  else if (action === "component-snapshot") copyManagerComponentSnapshot();
  else if (action === "download-component-snapshot") downloadManagerComponentSnapshot();
  else if (action === "download-manager-package") await downloadNioh2ManagerPackage(actionButton.dataset.modId);
  else if (action === "remove-mod") {
    const removed = state.mods.find((mod) => mod.id === actionButton.dataset.modId);
    if (removed && !removed.demoFixture && !(await removeStagedMod(removed.storageKey))) {
      toast("The saved namespace could not be removed from browser storage.", { error: true, title: "Removal incomplete" });
      return;
    }
    state.mods = state.mods.filter((mod) => mod.id !== actionButton.dataset.modId);
    state.demo = false;
    render();
    toast("Package removed from its isolated browser namespace.", { title: "Mod removed" });
  }
});

$("#folder-input").addEventListener("change", async (event) => {
  try { await importFolder(event.currentTarget.files); }
  catch { toast("This folder could not be read. Choose a standard folder with a JSON manifest.", { error: true, title: "Import failed" }); }
  finally { event.currentTarget.value = ""; }
});

$("#manager-inventory-input").addEventListener("change", async (event) => {
  try { await importManagerInventory(event.currentTarget.files?.[0]); }
  catch { toast("Inventory could not be read.", { error: true, title: "Import failed" }); }
  finally { event.currentTarget.value = ""; }
});

$("#game-select").addEventListener("change", (event) => {
  void switchWorkspaceProfile(event.currentTarget.value, $("#game-build").value);
});

$("#game-build").addEventListener("change", (event) => {
  void switchWorkspaceProfile($("#game-select").value, event.currentTarget.value);
});

$("#export-confirm-checkbox").addEventListener("change", (event) => { $("#confirm-export").disabled = !event.currentTarget.checked; });
$("#confirm-export").addEventListener("click", exportPackage);

// Other same-origin Koei Tecmo tools can observe handoffs through this window event
// or the corresponding postMessage contract. No inbound message is auto-staged.
window.addEventListener("message", (event) => {
  if (!window.location.origin || window.location.origin === "null" || event.origin !== window.location.origin) return;
  const message = event.data;
  if (!message || typeof message !== "object" || typeof message.type !== "string") return;
  if (["koei.mod-manager.workspace-request/v1", "koei.mod-workshop.validation-request/v1", "koei.troubleshooting.report-request/v1"].includes(message.type)) {
    if (message.type.includes("troubleshooting")) {
      event.source?.postMessage({ type: "koei-game-troubleshooting", payload: troubleshootingCenterReport() }, event.origin);
      return;
    }
    const contract = message.type.includes("workshop") ? "koei.mod-sandbox.workshop-brief/v1" : "koei.mod-sandbox.manager-handoff/v1";
    const payload = contract.includes("workshop") ? workshopBrief() : buildHandoff(contract);
    event.source?.postMessage({ type: payload.contract, payload }, event.origin);
  }
});

async function initialize() {
  fillGameOptions();
  let stored = [];
  try { stored = await loadStagedMods(); } catch { stored = []; }
  if (stored.length) {
    state.gameId = stored[0].gameId;
    state.gameVersion = stored[0].gameVersion;
    state.mods = await Promise.all(stored.filter((item) => item.gameId === state.gameId && item.gameVersion === state.gameVersion).map((item, index) => savedItemToMod(item, index, state.gameId, state.gameVersion)));
    state.demo = false;
    state.persistence = "indexeddb";
    render();
  } else loadDemo();
}

void initialize();
