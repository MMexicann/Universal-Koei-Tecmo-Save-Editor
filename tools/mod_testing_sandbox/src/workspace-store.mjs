import { LIMITS, normalizeModManifest, sanitizeRelativePath } from "./sandbox-core.mjs";

const DATABASE = "koei-mod-testing-sandbox";
const VERSION = 1;
const STORE = "staged";
const memoryFallback = new Map();

function openDatabase() {
  if (!globalThis.indexedDB) return Promise.resolve(null);
  return new Promise((resolve) => {
    let request;
    try { request = indexedDB.open(DATABASE, VERSION); }
    catch { resolve(null); return; }
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "key" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(null);
    request.onblocked = () => resolve(null);
  });
}

function asBlob(payload) {
  if (payload instanceof Blob) return payload;
  if (payload instanceof Uint8Array) return new Blob([payload]);
  if (payload instanceof ArrayBuffer) return new Blob([payload]);
  if (ArrayBuffer.isView(payload)) return new Blob([new Uint8Array(payload.buffer, payload.byteOffset, payload.byteLength)]);
  return null;
}

/** Save each mod under an independent workspace/game/build/mod-id key prefix. */
export async function saveStagedMod(mod) {
  const prefix = mod.storageKey;
  const metadata = {
    key: `${prefix}/\u0000manifest`,
    kind: "manifest",
    storageKey: prefix,
    manifest: mod.manifest,
    gameId: mod.gameId,
    gameVersion: mod.gameVersion,
    id: mod.id,
    name: mod.name,
    version: mod.version,
    author: mod.author,
    description: mod.description,
    valid: mod.valid,
    validationErrors: mod.validationErrors || [],
    storageBackend: "indexeddb",
    tint: mod.tint || 0,
    files: mod.files.map((file) => ({ ...file })),
    inventory: mod.files.map((file) => ({ path: file.source, sha256: file.sha256, size: mod.payloads.get(file.source)?.size || mod.payloads.get(file.source)?.byteLength || 0 })),
    storedAt: new Date().toISOString(),
  };
  const payloadEntries = mod.files.map((file) => ({
    key: `${prefix}/${file.source}`,
    kind: "payload",
    storageKey: prefix,
    path: file.source,
    data: asBlob(mod.payloads.get(file.source)),
  }));
  if (payloadEntries.some((entry) => !entry.data)) return false;
  const db = await openDatabase();
  if (!db) {
    metadata.storageBackend = "memory";
    memoryFallback.set(prefix, { metadata, payloadEntries });
    return false;
  }
  const cacheInMemory = () => {
    metadata.storageBackend = "memory";
    memoryFallback.set(prefix, { metadata, payloadEntries });
  };
  return new Promise((resolve) => {
    let transaction;
    try { transaction = db.transaction(STORE, "readwrite"); }
    catch { db.close(); cacheInMemory(); resolve(false); return; }
    const store = transaction.objectStore(STORE);
    store.put(metadata);
    for (const entry of payloadEntries) store.put(entry);
    transaction.oncomplete = () => { db.close(); memoryFallback.delete(prefix); resolve(true); };
    transaction.onerror = () => { db.close(); cacheInMemory(); resolve(false); };
    transaction.onabort = () => { db.close(); cacheInMemory(); resolve(false); };
  });
}

export async function loadStagedMods() {
  const db = await openDatabase();
  const records = db ? await new Promise((resolve) => {
    let transaction;
    try { transaction = db.transaction(STORE, "readonly"); }
    catch { db.close(); resolve([]); return; }
    const request = transaction.objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => resolve([]);
    transaction.oncomplete = () => db.close();
  }) : [];
  const allRecords = [...records];
  for (const cached of memoryFallback.values()) allRecords.push(cached.metadata, ...cached.payloadEntries);
  const payloadByKey = new Map(allRecords.filter((item) => item.kind === "payload").map((item) => [item.key, item.data]));
  const metadataByNamespace = new Map();
  for (const item of allRecords) if (item.kind === "manifest") metadataByNamespace.set(item.storageKey, item);
  return Promise.all([...metadataByNamespace.values()].map(async (item) => {
    const payloads = new Map(item.files.map((file) => [file.source, payloadByKey.get(`${item.storageKey}/${file.source}`)]));
    const inventory = await verifyStoredDigests({
      ...item,
      payloads,
      inventory: item.inventory.filter((entry) => payloads.has(entry.path) && payloads.get(entry.path) != null).map((entry) => ({ ...entry, file: payloads.get(entry.path) })),
    });
    return { ...item, payloads, inventory, demoFixture: false };
  }));
}

/** Recalculate manifest-declared digests from restored payload bytes before validation. */
export async function verifyStoredDigests(item) {
  const inventory = (item.inventory || []).map((entry) => ({ ...entry }));
  const manifest = normalizeModManifest(item.manifest);
  const manifestFiles = Array.isArray(manifest?.files) ? manifest.files : [];
  for (const descriptor of manifestFiles) {
    const declared = descriptor && typeof descriptor === "object" && typeof descriptor.sha256 === "string"
      ? descriptor.sha256.toLowerCase()
      : null;
    if (!declared) continue;
    const source = typeof descriptor === "string" ? descriptor : descriptor.source ?? descriptor.path;
    if (typeof source !== "string") continue;
    let sourceKey;
    try { sourceKey = sanitizeRelativePath(source).toLocaleLowerCase("en-US"); } catch { continue; }
    const entry = inventory.find((candidate) => candidate.path?.normalize("NFC").toLocaleLowerCase("en-US") === sourceKey);
    if (!entry) continue;
    delete entry.sha256;
    const payload = item.payloads?.get(entry.path);
    const size = Number(payload?.size ?? payload?.byteLength ?? 0);
    if (!payload || !Number.isFinite(size) || size > LIMITS.hashBytes || !globalThis.crypto?.subtle) continue;
    try {
      const bytes = payload instanceof Blob ? await payload.arrayBuffer()
        : payload instanceof ArrayBuffer ? payload
          : ArrayBuffer.isView(payload) ? payload.buffer.slice(payload.byteOffset, payload.byteOffset + payload.byteLength)
            : null;
      if (!bytes || bytes.byteLength > LIMITS.hashBytes) continue;
      const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
      entry.sha256 = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
    } catch {
      // Leave the hash absent so validateMod fails closed as unverifiable.
    }
  }
  return inventory;
}

export async function removeStagedMod(storageKey) {
  const indexedDBAvailable = Boolean(globalThis.indexedDB);
  const db = await openDatabase();
  if (!db) {
    if (indexedDBAvailable) return false;
    return memoryFallback.delete(storageKey);
  }
  return new Promise((resolve) => {
    let transaction;
    try { transaction = db.transaction(STORE, "readwrite"); }
    catch { db.close(); resolve(false); return; }
    const store = transaction.objectStore(STORE);
    const request = store.getAllKeys();
    request.onsuccess = () => {
      for (const key of request.result) if (typeof key === "string" && key.startsWith(`${storageKey}/`)) store.delete(key);
    };
    transaction.oncomplete = () => { memoryFallback.delete(storageKey); db.close(); resolve(true); };
    transaction.onerror = () => { db.close(); resolve(false); };
    transaction.onabort = () => { db.close(); resolve(false); };
  });
}

export async function clearStagedMods() {
  const indexedDBAvailable = Boolean(globalThis.indexedDB);
  const db = await openDatabase();
  if (!db) {
    if (indexedDBAvailable) return false;
    memoryFallback.clear();
    return true;
  }
  return new Promise((resolve) => {
    let transaction;
    try { transaction = db.transaction(STORE, "readwrite"); }
    catch { db.close(); resolve(false); return; }
    transaction.objectStore(STORE).clear();
    transaction.oncomplete = () => { memoryFallback.clear(); db.close(); resolve(true); };
    transaction.onerror = () => { db.close(); resolve(false); };
    transaction.onabort = () => { db.close(); resolve(false); };
  });
}

/** Remove only the selected game/build workspace, preserving other profiles. */
export async function clearStagedProfile(gameId, gameVersion) {
  const prefix = `workspaces/${gameId}/${encodeURIComponent(gameVersion)}/`;
  const clearMemoryProfile = () => {
    for (const [storageKey, item] of memoryFallback) {
      if (item.metadata.gameId === gameId && item.metadata.gameVersion === gameVersion) memoryFallback.delete(storageKey);
    }
  };
  const indexedDBAvailable = Boolean(globalThis.indexedDB);
  const db = await openDatabase();
  if (!db) {
    if (indexedDBAvailable) return false;
    clearMemoryProfile();
    return true;
  }
  return new Promise((resolve) => {
    let transaction;
    try { transaction = db.transaction(STORE, "readwrite"); }
    catch { db.close(); resolve(false); return; }
    const store = transaction.objectStore(STORE);
    const request = store.getAllKeys();
    request.onsuccess = () => {
      for (const key of request.result) if (typeof key === "string" && key.startsWith(prefix)) store.delete(key);
    };
    transaction.oncomplete = () => { clearMemoryProfile(); db.close(); resolve(true); };
    transaction.onerror = () => { db.close(); resolve(false); };
    transaction.onabort = () => { db.close(); resolve(false); };
  });
}
