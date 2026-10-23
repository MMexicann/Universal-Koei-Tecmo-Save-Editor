/** Exercise the actual trusted folder-import handler with browser-like File data. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { createHash, webcrypto } from "node:crypto";
import { LIMITS, parseManifest, normalizeFolderPaths, validateMod, createWorkshopValidationRecord } from "../src/sandbox-core.mjs";

async function inputChangeHandler(selector, backendName, backend) {
  const source = await readFile(new URL("../src/main.mjs", import.meta.url), "utf8");
  const begin = source.indexOf(`$("${selector}").addEventListener("change",`);
  const end = source.indexOf("\n});", begin) + "\n});".length;
  assert.ok(begin >= 0 && end > begin, "actual browser input listener must be present");
  let listener;
  const notices = [];
  const context = {
    $: (selected) => {
      assert.equal(selected, selector);
      return { addEventListener: (type, handler) => {
        assert.equal(type, "change");
        listener = handler;
      } };
    },
    [backendName]: backend,
    toast: (...args) => notices.push(args),
  };
  vm.runInNewContext(source.slice(begin, end), context);
  return { listener, notices };
}

for (const [selector, backendName] of [["#folder-input", "importFolder"],
                                     ["#manager-inventory-input", "importManagerInventory"]]) {
  test(`${selector} cleanup survives native currentTarget expiration after await`, async () => {
    for (const rejected of [false, true]) {
      const files = [{ name: "owned-procedural-input" }];
      const input = { files, value: "chosen input" };
      let release, captured;
      const gate = new Promise((resolve) => { release = resolve; });
      const { listener, notices } = await inputChangeHandler(selector, backendName, async (value) => {
        captured = value;
        await gate;
        if (rejected) throw new Error("procedural input rejection");
      });
      let currentTarget = input;
      const event = { get currentTarget() { return currentTarget; } };
      const pending = listener(event);
      // Browser dispatch clears currentTarget before an awaited File/IndexedDB
      // operation completes; the selected input element remains alive.
      currentTarget = null;
      release();
      await assert.doesNotReject(pending);
      assert.equal(input.value, "");
      assert.equal(captured, selector === "#folder-input" ? files : files[0]);
      assert.equal(notices.length, rejected ? 1 : 0);
      assert.equal(files[0].name, "owned-procedural-input");
    }
  });
}

async function importHandler() {
  const source = await readFile(new URL("../src/main.mjs", import.meta.url), "utf8");
  const begin = source.indexOf("function normalizedUploadFiles(");
  const end = source.indexOf("\nasync function importFolder(", begin);
  assert.ok(begin >= 0 && end > begin, "actual folder handler must be present");
  const state = { gameId: "wolong", gameVersion: "1.5.0", mods: [], demo: false };
  const saved = [];
  const notices = [];
  const context = { LIMITS, parseManifest, normalizeFolderPaths, validateMod, createWorkshopValidationRecord, state,
    crypto: webcrypto, COLOR_CLASSES: ["gold"],
    MANIFEST_NAMES: new Set(["mod-manifest.json", "manifest.json", "mod.json"]),
    toast: (message, options) => notices.push({ message, ...options }),
    saveStagedMod: async (mod) => { saved.push(mod); return false; }, render: () => {},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(begin, end) + "\nglobalThis.runImport = importFolderUnlocked;", context);
  return { run: context.runImport, state, saved, notices };
}

function uploaded(bytes, path) {
  return Object.assign(new Blob([bytes]), { name: path.split("/").at(-1), webkitRelativePath: path });
}

function workshopFiles(prefix = "project/") {
  const bytes = "synthetic owned replacement";
  const manifest = { schema_version: 1, mod_id: "workshop-ui", name: "Workshop UI",
    version: "1.0.0", author: "Fixture", description: "", game_id: "wolong",
    game_version: ">=1.0.0,<2.0.0", platform: "Windows PC", license: "MIT", dependencies: [],
    replacements: [{ source_path: "replacements/skin.bin", target_path: "Data/Skin.bin",
      sha256: createHash("sha256").update(bytes).digest("hex"), license: "MIT",
      attribution: "Fixture", rights_status: "creator-owned" }],
  };
  return [uploaded(JSON.stringify(manifest), `${prefix}mod.json`), uploaded(bytes, `${prefix}replacements/skin.bin`)];
}

test("native Workshop root manifest reaches actual folder-handler storage with verified bytes", async () => {
  const handler = await importHandler();
  await handler.run(workshopFiles());
  assert.equal(handler.saved.length, 1, JSON.stringify(handler.notices));
  assert.equal(handler.state.mods.length, 1);
  assert.equal(handler.saved[0].manifestFormat, "koei-mod-workshop.v1");
  assert.equal(handler.saved[0].gameVersion, "1.5.0");
  assert.equal(await handler.saved[0].payloads.get("replacements/skin.bin").text(), "synthetic owned replacement");
});

test("native Workshop nested manifest is refused by actual folder handler", async () => {
  const handler = await importHandler();
  const files = workshopFiles("project/nested/");
  files.push(uploaded("unrelated", "project/readme.txt"));
  await handler.run(files);
  assert.equal(handler.saved.length, 0);
  assert.equal(handler.state.mods.length, 0);
  assert.equal(handler.notices.at(-1).title, "Workshop manifest location");
});

test("ordinary Sandbox manifest reaches actual folder handler without Workshop classification", async () => {
  const handler = await importHandler();
  const manifest = { schemaVersion: 1, id: "ordinary-ui", name: "Ordinary UI", version: "1.0.0",
    gameId: "wolong", gameVersion: "1.5.0", files: [{ source: "data/skin.bin", target: "Data/Skin.bin" }] };
  await handler.run([uploaded(JSON.stringify(manifest), "project/mod-manifest.json"), uploaded("inert", "project/data/skin.bin")]);
  assert.equal(handler.saved.length, 1, JSON.stringify(handler.notices));
  assert.equal(handler.saved[0].manifestFormat, "koei-mod-sandbox.v1");
});

test("profile switch during actual folder reading cannot import into the newly selected profile", async () => {
  const handler = await importHandler();
  const files = workshopFiles();
  const realText = files[0].text.bind(files[0]);
  let release;
  files[0].text = async () => { await new Promise((resolve) => { release = resolve; }); return realText(); };
  const pending = handler.run(files);
  handler.state.gameId = "dw8xl";
  handler.state.gameVersion = "new-build";
  release();
  await pending;
  assert.equal(handler.saved.length, 0);
  assert.equal(handler.state.mods.length, 0);
  assert.equal(handler.notices.at(-1).title, "Profile changed");
});
