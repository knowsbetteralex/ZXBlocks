import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {Blockly} from '../src/blocks.js';
import {validateProject} from '../src/ir.js';
import {importProject, exportProject, saveDraft, loadDraft, blockForPath} from '../src/workspace.js';

const example = JSON.parse(readFileSync(new URL('../../examples/arithmetic_border/project.json', import.meta.url)));
const binary = (op, left, right) => ({op, left, right});
const minimal = value => ({format: 'zxblocks/v3', name: 'Expressions', variables: [{name: 'x', initial: 0}],
  events: {start: [], frame: [{op: 'set', var: 'x', value}]}});
function withWorkspace(fn) {
  const workspace = new Blockly.Workspace();
  try { return fn(workspace); } finally { workspace.dispose(); }
}

test('v3 arithmetic, comparisons and keyboard round-trip and preserve workspace state', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  assert.deepEqual(exportProject(workspace, metadata).project, example);
  const expression = workspace.getAllBlocks(false).find(block => block.type === 'zxb_arithmetic');
  expression.setCollapsed(true);
  const saved = saveDraft(workspace, metadata);
  const restored = loadDraft(workspace, saved);
  assert.equal(restored.format, 'zxblocks/v3');
  assert.equal(workspace.getBlockById(expression.id).isCollapsed(), true);
  assert.deepEqual(exportProject(workspace, restored).project, example);
}));

test('nested arithmetic and new comparisons automatically select v3 from older projects', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, {format: 'zxblocks/v1', name: 'Legacy'});
  const event = workspace.getTopBlocks(false).find(block => block.getFieldValue('EVENT') === 'frame');
  const condition = workspace.newBlock('zxb_compare_if'); condition.setFieldValue('le', 'CMP');
  event.getInput('DO').connection.connect(condition.previousConnection);
  for (const input of ['LEFT', 'RIGHT']) condition.getInput(input).connection.connect(workspace.newBlock('zxb_byte').outputConnection);
  let result = exportProject(workspace, metadata);
  assert.equal(result.project.format, 'zxblocks/v3');
  assert.deepEqual(result.project.events.frame[0].condition, {left: 0, op: 'le', right: 0});
  assert.equal(saveDraft(workspace, metadata).metadata.format, 'zxblocks/v3');
  const restored = loadDraft(workspace, saveDraft(workspace, metadata));
  assert.equal(restored.format, 'zxblocks/v3');
  const restoredCondition = workspace.getBlockById(condition.id);
  const math = workspace.newBlock('zxb_arithmetic'); math.setFieldValue('sub', 'OP');
  restoredCondition.getInputTargetBlock('LEFT').dispose();
  restoredCondition.getInput('LEFT').connection.connect(math.outputConnection);
  for (const input of ['LEFT', 'RIGHT']) math.getInput(input).connection.connect(workspace.newBlock('zxb_byte').outputConnection);
  result = exportProject(workspace, restored);
  assert.deepEqual(result.project.events.frame[0].condition.left, binary('sub', 0, 0));
}));

test('all six expression comparisons preserve both branches', () => withWorkspace(workspace => {
  const project = minimal(0);
  project.events.frame = ['eq', 'ne', 'lt', 'le', 'gt', 'ge'].map(op => ({op: 'if',
    condition: {left: binary('add', {var: 'x'}, 1), op, right: binary('sub', 0, {key: 'SPACE'})},
    then: [{op: 'set', var: 'x', value: 255}], else: [{op: 'set', var: 'x', value: 0}]}));
  assert.deepEqual(exportProject(workspace, importProject(workspace, project)).project, project);
}));

test('incomplete arithmetic survives draft restore and points to its missing input', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, minimal(binary('sub', 1, binary('add', 2, 3))));
  const inner = workspace.getAllBlocks(false).find(block => block.type === 'zxb_arithmetic' && block.getFieldValue('OP') === 'add');
  inner.getInputTargetBlock('RIGHT').dispose();
  assert.throws(() => exportProject(workspace, metadata), error => error.blockId === inner.id);
  const saved = saveDraft(workspace, metadata); assert.equal(saved.project, null);
  const restored = loadDraft(workspace, saved);
  assert.equal(workspace.getBlockById(inner.id).getInputTargetBlock('RIGHT'), null);
  assert.throws(() => exportProject(workspace, restored), error => error.blockId === inner.id);
}));

test('malformed arithmetic and unsupported formats never replace the open project', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, example);
  for (const invalid of [minimal(binary('mul', 1, 2)), minimal(binary('add', 1, null)),
    minimal({...binary('sub', 1, 2), extra: 0}), {...minimal(binary('add', 1, 2)), format: 'zxblocks/v1'},
    {...minimal(binary('sub', 1, 2)), format: 'zxblocks/v2'}]) {
    assert.throws(() => importProject(workspace, invalid));
    assert.deepEqual(exportProject(workspace, metadata).project, example);
  }
}));

test('expression depth and global node limits are enforced independently of actions', () => withWorkspace(workspace => {
  let expression = 1;
  for (let i = 0; i < 16; i++) expression = binary('add', 0, expression);
  const metadata = importProject(workspace, minimal(expression));
  assert.deepEqual(exportProject(workspace, metadata).project, minimal(expression));
  assert.throws(() => validateProject(minimal(binary('sub', expression, 0))), /16/);
  const project = minimal(0);
  project.events.start = [{op: 'set', var: 'x', value: 0}];
  project.events.frame = Array.from({length: 2048}, () => ({op: 'if', condition: {left: 0, op: 'eq', right: 0}}));
  assert.throws(() => validateProject(project), /4096/);
}));

test('nested expression diagnostics resolve to the precise arithmetic block', () => withWorkspace(workspace => {
  const metadata = importProject(workspace, minimal(binary('add', 1, binary('sub', 2, 3))));
  const result = exportProject(workspace, metadata);
  const id = blockForPath(result.sourceMap, 'events.frame[0].value.right.left');
  assert.equal(workspace.getBlockById(id).type, 'zxb_byte');
  const parent = blockForPath(result.sourceMap, 'events.frame[0].value.right.op');
  assert.equal(workspace.getBlockById(parent).getFieldValue('OP'), 'sub');
}));

test('real Blockly arithmetic export generates identical Python assembly and simulation', () => withWorkspace(workspace => {
  const exported = exportProject(workspace, importProject(workspace, example)).project;
  const python = process.env.ZXBLOCKS_PYTHON || (process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python');
  const script = 'import json,sys; from zxblocks import compile_project; from zxblocks.simulator import Simulator; a,b=json.load(sys.stdin); assert compile_project(a)==compile_project(b); x,y=Simulator(a),Simulator(b); assert [x.step(["SPACE"]) for _ in range(30)]==[y.step(["SPACE"]) for _ in range(30)]';
  const child = spawnSync(python, ['-c', script], {input: JSON.stringify([example, exported]), encoding: 'utf8', cwd: fileURLToPath(new URL('..', import.meta.url))});
  assert.equal(child.status, 0, child.stderr || child.error?.message);
}));
