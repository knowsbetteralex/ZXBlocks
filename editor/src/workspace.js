import {Blockly} from './blocks.js';
import {EditorError, validateProject} from './ir.js';

function variableState(name, variables) {
  const variable = variables.find(v => v.name.toUpperCase() === name.toUpperCase());
  return {id: variable.id};
}

export function importProject(workspace, input) {
  const project = validateProject(input); // Validate before touching the open workspace.
  const variables = (project.variables ?? []).map((v, index) => ({name: v.name, type: 'u8', id: `zxb_var_${index}`}));
  const expression = value => typeof value === 'number'
    ? {type: 'zxb_byte', fields: {NUM: value}}
    : Object.hasOwn(value, 'key') ? {type: 'zxb_key', fields: {KEY: value.key}}
    : {type: 'zxb_var', fields: {VAR: variableState(value.var, variables)}};
  const chain = actions => {
    let first = null;
    let last = null;
    for (const action of actions) {
      let block;
      if (action.op === 'set') block = {type: 'zxb_set', fields: {VAR: variableState(action.var, variables)}, inputs: {VALUE: {block: expression(action.value)}}};
      if (action.op === 'change') block = {type: 'zxb_change', fields: {VAR: variableState(action.var, variables), DELTA: action.by}};
      if (action.op === 'call') block = {type: 'zxb_border', inputs: {VALUE: {block: expression(action.arg)}}};
      if (action.op === 'if') {
        block = {type: 'zxb_if', fields: {VAR: variableState(action.condition.var, variables), CMP: action.condition.op, LIMIT: action.condition.value}, inputs: {}};
        if (action.then?.length) block.inputs.THEN = {block: chain(action.then)};
        if (action.else?.length) block.inputs.ELSE = {block: chain(action.else)};
      }
      if (last) last.next = {block};
      else first = block;
      last = block;
    }
    return first;
  };
  const blocks = ['start', 'frame'].map((event, index) => {
    const block = {type: 'zxb_event', x: 40 + index * 430, y: 40, fields: {EVENT: event}};
    const body = chain(project.events?.[event] ?? []);
    if (body) block.inputs = {DO: {block: body}};
    return block;
  });
  Blockly.serialization.workspaces.load({variables, blocks: {languageVersion: 0, blocks}}, workspace);
  return {format: project.format, name: project.name ?? 'Новый проект', initials: Object.fromEntries(variables.map((v, i) => [v.id, project.variables[i].initial ?? 0]))};
}

export function exportProject(workspace, metadata) {
  const sourceMap = {};
  const visited = new Set();
  const fail = (message, block) => { throw new EditorError(message, '', block?.id); };
  const variableName = block => {
    const variable = block.getField('VAR').getVariable();
    if (!variable) fail('Выберите переменную', block);
    return variable.getName();
  };
  const expression = (block, path, parent) => {
    if (!block) fail('Подключите число или переменную', parent);
    visited.add(block.id); sourceMap[path] = block.id;
    if (block.type === 'zxb_byte') return Number(block.getFieldValue('NUM'));
    if (block.type === 'zxb_var') return {var: variableName(block)};
    if (block.type === 'zxb_key') return {key: block.getFieldValue('KEY')};
    fail('Ожидается байтовое значение', block);
  };
  let count = 0;
  const chain = (block, path, depth = 0) => {
    if (depth > 16) fail('Максимальная вложенность — 16', block);
    const actions = [];
    for (; block; block = block.getNextBlock()) {
      if (++count > 4096) fail('Максимум 4096 действий', block);
      visited.add(block.id);
      const at = `${path}[${actions.length}]`;
      sourceMap[at] = block.id;
      let action;
      if (block.type === 'zxb_set') action = {op: 'set', var: variableName(block), value: expression(block.getInputTargetBlock('VALUE'), `${at}.value`, block)};
      else if (block.type === 'zxb_change') action = {op: 'change', var: variableName(block), by: Number(block.getFieldValue('DELTA'))};
      else if (block.type === 'zxb_border') action = {op: 'call', name: 'set_border', arg: expression(block.getInputTargetBlock('VALUE'), `${at}.arg`, block)};
      else if (block.type === 'zxb_if') {
        action = {op: 'if', condition: {var: variableName(block), op: block.getFieldValue('CMP'), value: Number(block.getFieldValue('LIMIT'))}, then: chain(block.getInputTargetBlock('THEN'), `${at}.then`, depth + 1)};
        const otherwise = chain(block.getInputTargetBlock('ELSE'), `${at}.else`, depth + 1);
        if (otherwise.length) action.else = otherwise;
      } else fail('Этот блок не поддерживается', block);
      actions.push(action);
    }
    return actions;
  };
  const events = {start: [], frame: []};
  const eventNames = new Set();
  for (const block of workspace.getTopBlocks(false)) {
    if (block.type !== 'zxb_event') fail('Подключите блок к событию', block);
    const event = block.getFieldValue('EVENT');
    if (eventNames.has(event)) fail('Оставьте одно событие каждого типа', block);
    eventNames.add(event); visited.add(block.id); sourceMap[`events.${event}`] = block.id;
    events[event] = chain(block.getInputTargetBlock('DO'), `events.${event}`);
  }
  for (const block of workspace.getAllBlocks(false)) {
    if (!block.isEnabled()) fail('Отключённые блоки не поддерживаются', block);
    if (!visited.has(block.id)) fail('Подключите блок к событию', block);
  }
  const variables = workspace.getVariableMap().getAllVariables().map(variable => ({name: variable.getName(), initial: metadata.initials[variable.getId()] ?? 0}));
  const project = {format: metadata.format ?? 'zxblocks/v1', name: metadata.name, variables, events};
  try { validateProject(project); }
  catch (error) { error.blockId ??= blockForPath(sourceMap, error.path); throw error; }
  return {project, sourceMap};
}

export function saveEditorState(workspace, metadata) {
  return {format: 'zxblocks/editor/v1', project: exportProject(workspace, metadata).project,
    workspace: Blockly.serialization.workspaces.save(workspace), initials: {...metadata.initials}};
}

export function loadEditorState(workspace, state) {
  if (state?.format !== 'zxblocks/editor/v1') throw new EditorError('Неизвестный формат рабочего места');
  validateProject(state.project);
  const scratch = new Blockly.Workspace();
  const metadata = {format: state.project.format, name: state.project.name, initials: state.initials ?? {}};
  try {
    Blockly.serialization.workspaces.load(state.workspace, scratch);
    if (JSON.stringify(exportProject(scratch, metadata).project) !== JSON.stringify(state.project)) throw new EditorError('Блоки рабочего места не совпадают с проектом');
  } finally { scratch.dispose(); }
  Blockly.serialization.workspaces.load(state.workspace, workspace);
  return metadata;
}

export function blockForPath(sourceMap, path) {
  while (path) {
    if (sourceMap[path]) return sourceMap[path];
    const parent = path.replace(/(?:\.[^.\[\]]+|\[\d+\])$/, '');
    if (parent === path) return null;
    path = parent;
  }
  return null;
}
