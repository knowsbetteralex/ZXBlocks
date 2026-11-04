import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {Blockly} from '../src/blocks.js';
import {importProject, exportProject, saveDraft, loadDraft} from '../src/workspace.js';
import {ProjectSession, recoveryKey} from '../src/project-session.js';

const example = JSON.parse(readFileSync(new URL('../../examples/border_cycle/project.json', import.meta.url)));

function connectKeyboard(workspace) {
  const border = workspace.getAllBlocks(false).find(block => block.type === 'zxb_border');
  border.getInputTargetBlock('VALUE').dispose();
  const key = workspace.newBlock('zxb_key');
  border.getInput('VALUE').connection.connect(key.outputConnection);
  return {border, key};
}

test('automatic keyboard capability is saved consistently and restored without a format selector', () => {
  const workspace = new Blockly.Workspace();
  try {
    const metadata = importProject(workspace, example);
    connectKeyboard(workspace);
    const saved = saveDraft(workspace, metadata);
    assert.equal(saved.metadata.format, 'zxblocks/v2');
    assert.equal(saved.project.format, 'zxblocks/v2');
    const restored = loadDraft(workspace, saved);
    assert.equal(restored.format, 'zxblocks/v2');
    assert.deepEqual(exportProject(workspace, restored).project, saved.project);
    const tampered = structuredClone(saved); tampered.metadata.format = 'zxblocks/v1';
    assert.throws(() => loadDraft(workspace, tampered), /не совпадают/);
    assert.deepEqual(exportProject(workspace, restored).project, saved.project);
  } finally { workspace.dispose(); }
});

test('a detached keyboard draft is retained and enables the capability only when connected', () => {
  const workspace = new Blockly.Workspace();
  try {
    const metadata = importProject(workspace, example);
    const key = workspace.newBlock('zxb_key');
    const saved = saveDraft(workspace, metadata);
    assert.equal(saved.metadata.format, 'zxblocks/v1');
    assert.equal(saved.project, null);
    const restored = loadDraft(workspace, saved);
    assert.ok(workspace.getBlockById(key.id));
    const border = workspace.getAllBlocks(false).find(block => block.type === 'zxb_border');
    border.getInputTargetBlock('VALUE').dispose();
    border.getInput('VALUE').connection.connect(workspace.getBlockById(key.id).outputConnection);
    assert.equal(exportProject(workspace, restored).project.format, 'zxblocks/v2');
  } finally { workspace.dispose(); }
});

test('removing the last keyboard block removes keyboard runtime without downgrading a saved document', () => {
  const workspace = new Blockly.Workspace();
  try {
    const metadata = importProject(workspace, example);
    connectKeyboard(workspace);
    const saved = saveDraft(workspace, metadata);
    const restored = loadDraft(workspace, saved);
    const border = workspace.getAllBlocks(false).find(block => block.type === 'zxb_border');
    border.getInputTargetBlock('VALUE').dispose();
    const number = workspace.newBlock('zxb_byte');
    border.getInput('VALUE').connection.connect(number.outputConnection);
    const result = exportProject(workspace, restored);
    assert.equal(result.project.format, 'zxblocks/v2');
    assert.deepEqual(result.capabilities, []);
    const python = process.env.ZXBLOCKS_PYTHON || (process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python');
    const script = 'import json,sys; from zxblocks import compile_project; keyed,plain=json.load(sys.stdin); assert "ZXB_RT_KEY_POLL" in compile_project(keyed); assert "ZXB_RT_KEY_POLL" not in compile_project(plain); legacy=dict(plain,format="zxblocks/v1"); assert compile_project(plain)==compile_project(legacy)';
    const child = spawnSync(python, ['-c', script], {input: JSON.stringify([saved.project, result.project]), encoding: 'utf8', cwd: fileURLToPath(new URL('..', import.meta.url))});
    assert.equal(child.status, 0, child.stderr || child.error?.message);
  } finally { workspace.dispose(); }
});

test('A → B → A restores unfinished blocks, IDs, positions and initial values', () => {
  const workspace = new Blockly.Workspace();
  try {
    const metadata = importProject(workspace, example);
    const border = workspace.getAllBlocks(false).find(block => block.type === 'zxb_border');
    border.getInputTargetBlock('VALUE').dispose();
    const loose = workspace.newBlock('zxb_byte'); loose.setFieldValue(23, 'NUM'); loose.moveBy(245, 123);
    const saved = saveDraft(workspace, metadata);
    assert.equal(saved.project, null);
    importProject(workspace, {format: 'zxblocks/v2', name: 'Project B'});
    const restored = loadDraft(workspace, saved);
    assert.deepEqual(restored, metadata);
    assert.equal(workspace.getBlockById(loose.id).getFieldValue('NUM'), 23);
    assert.equal(workspace.getBlockById(loose.id).getRelativeToSurfaceXY().x, 245);
    assert.equal(workspace.getBlockById(border.id).getInputTargetBlock('VALUE'), null);
    assert.throws(() => exportProject(workspace, restored));
    assert.deepEqual(saveDraft(workspace, restored), saved);
  } finally { workspace.dispose(); }
});

test('valid draft preserves IR and viewport independently, invalid initials remain drafts', () => {
  const workspace = new Blockly.Workspace();
  try {
    const metadata = importProject(workspace, example);
    const saved = saveDraft(workspace, metadata); saved.view = {scale: .65, scrollX: -150, scrollY: 25};
    const restored = loadDraft(workspace, saved);
    assert.deepEqual(exportProject(workspace, restored).project, example);
    assert.ok(!Object.hasOwn(saved.project, 'view'));
    metadata.initials[Object.keys(metadata.initials)[0]] = null;
    assert.equal(saveDraft(workspace, metadata).project, null);
    assert.equal(loadDraft(workspace, saveDraft(workspace, metadata)).initials.zxb_var_0, null);
  } finally { workspace.dispose(); }
});

test('damaged draft imports leave the open project intact', () => {
  const workspace = new Blockly.Workspace();
  try {
    const metadata = importProject(workspace, example);
    for (const mutate of [
      draft => { draft.project.events.frame[0].by = 12; },
      draft => { draft.workspace.blocks.blocks[0].type = 'unknown'; draft.project = null; },
      draft => { draft.metadata.format = 'zxblocks/v99'; },
      draft => { draft.view.scale = 0; },
      draft => { draft.extra = 1; },
    ]) {
      const draft = saveDraft(workspace, metadata); mutate(draft);
      assert.throws(() => loadDraft(workspace, draft));
      assert.deepEqual(exportProject(workspace, metadata).project, example);
    }
  } finally { workspace.dispose(); }
});

const memory = () => {
  const values = new Map();
  return {getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key)};
};

test('save serializes revisions and also saves edits made during the first write', async () => {
  let document = {value: 1};
  const calls = [];
  let finish;
  const storage = memory();
  const session = new ProjectSession({id: 'a', revision: 1, document: {value: 0}}, () => structuredClone(document), {
    storage, send: async (path, body) => {
      calls.push(body);
      if (calls.length === 1) await new Promise(resolve => { finish = resolve; });
      return {revision: body.revision + 1};
    },
  });
  const first = session.save();
  document = {value: 2}; session.remember();
  const second = session.save();
  assert.equal(calls.length, 1);
  assert.deepEqual(JSON.parse(storage.getItem(recoveryKey('a'))).document, document);
  finish(); await Promise.all([first, second]);
  assert.deepEqual(calls.map(body => [body.revision, body.document.value]), [[1, 1], [2, 2]]);
  assert.equal(session.revision, 3); assert.equal(session.dirty, false);
  assert.equal(storage.getItem(recoveryKey('a')), undefined);
});

test('offline draft is retained, retry succeeds; conflicts never overwrite another tab', async () => {
  const storage = memory(); let fail = true;
  const session = new ProjectSession({id: 'b', revision: 4, document: {}}, () => ({draft: true}), {
    storage, send: async () => { if (fail) throw new Error('Offline'); return {revision: 5}; },
  });
  await assert.rejects(session.save(), /Offline/);
  assert.equal(session.revision, 4); assert.ok(storage.getItem(recoveryKey('b')));
  fail = false; await session.save(); assert.equal(session.revision, 5);
  let calls = 0;
  const conflict = new ProjectSession({id: 'c', revision: 1, document: {}}, () => ({draft: true}), {
    storage, send: async () => { calls++; throw Object.assign(new Error('Conflict'), {status: 409}); },
  });
  await assert.rejects(conflict.save(), /Conflict/);
  await assert.rejects(conflict.save(), /другой вкладке/);
  assert.equal(calls, 1); assert.ok(storage.getItem(recoveryKey('c')));
});
