import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {Blockly} from '../src/blocks.js';
import {importProject, exportProject, saveEditorState, loadEditorState, blockForPath} from '../src/workspace.js';
import {validateProject} from '../src/ir.js';

const example = JSON.parse(readFileSync(new URL('../../examples/border_cycle/project.json', import.meta.url)));
function withWorkspace(fn) {
  const workspace = new Blockly.Workspace();
  try { return fn(workspace); } finally { workspace.dispose(); }
}

test('border example round-trips exactly through real Blockly blocks', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const result = exportProject(workspace, metadata);
  assert.deepEqual(result.project, example);
  assert.ok(result.sourceMap['events.frame[1].then[0]']);
  assert.equal(workspace.getAllBlocks(false).length, 10);
}));

test('all unsigned comparisons, branches, deltas and expressions round-trip', () => withWorkspace(workspace => {
  const project = structuredClone(example);
  project.variables.push({name: 'other', initial: 255});
  project.events.frame = ['eq', 'ne', 'lt', 'ge'].map(op => ({op: 'if', condition: {var: 'counter', op, value: 255}, then: [{op: 'change', var: 'other', by: -255}], else: [{op: 'set', var: 'counter', value: {var: 'other'}}]}));
  project.events.frame.push({op: 'call', name: 'set_border', arg: 255});
  assert.deepEqual(exportProject(workspace, importProject(workspace, project)).project, project);
}));

test('renaming a Blockly variable updates every IR reference', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const map = workspace.getVariableMap();
  map.renameVariable(map.getVariable('counter', 'u8'), 'ticks');
  const project = exportProject(workspace, metadata).project;
  assert.equal(project.variables[0].name, 'ticks');
  assert.equal(project.events.frame[2].arg.var, 'ticks');
}));

test('editor positions survive save/load without entering semantic IR', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const event = workspace.getTopBlocks(false)[0];
  event.moveBy(125, 70);
  const position = event.getRelativeToSurfaceXY();
  const saved = saveEditorState(workspace, metadata);
  const restored = loadEditorState(workspace, saved);
  assert.deepEqual(exportProject(workspace, restored).project, example);
  assert.equal(workspace.getBlockById(event.id).getRelativeToSurfaceXY().x, position.x);
  assert.ok(!JSON.stringify(example).includes('workspace'));
}));

test('unknown or malformed IR is rejected without destroying the open workspace', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  for (const invalid of [null, {format: 'zxblocks/v99'}, {...example, assets: []},
    {...example, variables: null}, {...example, events: null},
    {...example, variables: [{name: 'x', initial: true}]}, {...example, variables: [{name: 'x', initial: null}]}]) {
    assert.throws(() => importProject(workspace, invalid));
    assert.deepEqual(exportProject(workspace, metadata).project, example);
  }
}));

test('minimal project stays free of undeclared Blockly variables', () => withWorkspace(workspace => {
  const project = exportProject(workspace, importProject(workspace, {format: 'zxblocks/v1'})).project;
  assert.deepEqual(project.variables, []);
  assert.deepEqual(project.events, {start: [], frame: []});
}));

test('tampered editor state is rejected before replacing the open project', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const state = saveEditorState(workspace, metadata);
  state.project.events.frame[0].by = 5;
  assert.throws(() => loadEditorState(workspace, state), /не совпадают/);
  assert.deepEqual(exportProject(workspace, metadata).project, example);
}));

test('disabled actions cannot silently disappear from export', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const block = workspace.getAllBlocks(false).find(block => block.type === 'zxb_change');
  block.setDisabledReason(true, 'MANUALLY_DISABLED');
  assert.throws(() => exportProject(workspace, metadata), error => error.blockId === block.id);
}));

test('duplicate events and detached blocks identify the offending block', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const extra = workspace.newBlock('zxb_event');
  assert.throws(() => exportProject(workspace, metadata), error => error.blockId === extra.id);
  extra.dispose();
  const detached = workspace.newBlock('zxb_byte');
  assert.throws(() => exportProject(workspace, metadata), error => error.blockId === detached.id);
}));

test('a disconnected value identifies its parent action', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const block = workspace.getAllBlocks(false).find(block => block.type === 'zxb_border');
  block.getInputTargetBlock('VALUE').dispose();
  assert.throws(() => exportProject(workspace, metadata), error => error.blockId === block.id);
}));

test('IR guards mirror compiler depth and action limits', () => {
  const project = structuredClone(example);
  project.events.frame = Array.from({length: 4097}, () => ({op: 'change', var: 'counter', by: 0}));
  assert.throws(() => validateProject(project), /4096/);
  let body = [];
  for (let i = 0; i < 17; i++) body = [{op: 'if', condition: {var: 'counter', op: 'eq', value: 0}, then: body}];
  project.events.frame = body;
  assert.throws(() => validateProject(project), /16/);
});

test('compiler diagnostic paths resolve to nested blocks', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const {sourceMap} = exportProject(workspace, metadata);
  assert.equal(blockForPath(sourceMap, 'events.frame[1].then[0].value'), sourceMap['events.frame[1].then[0].value']);
  assert.equal(blockForPath(sourceMap, 'events.frame[1].condition.value'), sourceMap['events.frame[1]']);
  assert.equal(blockForPath(sourceMap, 'variables[0].name'), null);
}));

test('editor export and hand-written IR compile to identical Z80 ASM', () => withWorkspace(workspace => {
  const result = exportProject(workspace, importProject(workspace, example)).project;
  const script = 'import json,sys; from zxblocks import compile_project; a,b=json.load(sys.stdin); assert compile_project(a)==compile_project(b); print("ASM identical")';
  const python = process.env.ZXBLOCKS_PYTHON || (process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python');
  const child = spawnSync(python, ['-c', script], {input: JSON.stringify([example, result]), encoding: 'utf8', cwd: fileURLToPath(new URL('..', import.meta.url))});
  assert.equal(child.status, 0, child.stderr || child.error?.message);
  assert.match(child.stdout, /ASM identical/);
}));

test('v2 keyboard project and editor layout round-trip without downgrading', () => withWorkspace(workspace => {
  const project = JSON.parse(readFileSync(new URL('../../examples/keyboard_border/project.json', import.meta.url)));
  const metadata = importProject(workspace, project);
  assert.deepEqual(exportProject(workspace, metadata).project, project);
  assert.ok(workspace.getAllBlocks(false).some(block => block.type === 'zxb_key'));
  const restored = loadEditorState(workspace, saveEditorState(workspace, metadata));
  assert.equal(restored.format, 'zxblocks/v2');
  assert.deepEqual(exportProject(workspace, restored).project, project);
}));

test('connected key blocks automatically enable v2 while malformed v1 imports stay rejected', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  const border = workspace.getAllBlocks(false).find(block => block.type === 'zxb_border');
  border.getInputTargetBlock('VALUE').dispose();
  const key = workspace.newBlock('zxb_key');
  border.getInput('VALUE').connection.connect(key.outputConnection);
  const result = exportProject(workspace, metadata);
  assert.equal(result.project.format, 'zxblocks/v2');
  assert.deepEqual(result.capabilities, ['keyboard']);
  assert.equal(result.sourceMap['events.frame[2].arg'], key.id);
  const invalidInput = {...result.project, format: 'zxblocks/v1'};
  assert.throws(() => importProject(workspace, invalidInput), /v2/);
  assert.deepEqual(exportProject(workspace, metadata).project, result.project);
}));

test('physical key vocabulary matches the Python compiler and every key round-trips', () => withWorkspace(workspace => {
  const project = JSON.parse(readFileSync(new URL('../../examples/keyboard_border/project.json', import.meta.url)));
  const metadata = importProject(workspace, project);
  const block = workspace.getAllBlocks(false).find(block => block.type === 'zxb_key');
  const keys = block.getField('KEY').getOptions(false).map(option => option[1]);
  for (const key of keys) {
    block.setFieldValue(key, 'KEY');
    assert.equal(exportProject(workspace, metadata).project.events.frame[0].value.key, key);
  }
  const python = process.env.ZXBLOCKS_PYTHON || (process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python');
  const child = spawnSync(python, ['-c', 'import json; from zxblocks.keyboard import KEY_MATRIX; print(json.dumps(list(KEY_MATRIX)))'], {encoding: 'utf8', cwd: fileURLToPath(new URL('..', import.meta.url))});
  assert.equal(child.status, 0, child.stderr);
  assert.deepEqual(keys, JSON.parse(child.stdout));
}));
