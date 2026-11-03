import {KEY_NAMES} from './keys.js';

export class EditorError extends Error {
  constructor(message, path = '', blockId = null) {
    super(message);
    this.path = path;
    this.blockId = blockId;
  }
}

export function validateProject(project) {
  const fail = (message, path) => { throw new EditorError(message, path); };
  const object = (value, keys, path) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) fail('Ожидается объект', path);
    const extra = Object.keys(value).filter(key => !keys.includes(key));
    if (extra.length) fail(`Неподдерживаемые поля: ${extra.join(', ')}`, path);
  };
  const integer = (value, min, max, path) => {
    if (!Number.isInteger(value) || value < min || value > max) fail(`Ожидается целое число ${min}…${max}`, path);
  };
  object(project, ['format', 'name', 'variables', 'events'], '');
  if (!['zxblocks/v1', 'zxblocks/v2'].includes(project.format)) fail('Поддерживается zxblocks/v1 или zxblocks/v2', 'format');
  if (project.name !== undefined && typeof project.name !== 'string') fail('Имя проекта должно быть строкой', 'name');
  const variables = project.variables === undefined ? [] : project.variables;
  if (!Array.isArray(variables)) fail('Переменные должны быть массивом', 'variables');
  const names = new Set();
  variables.forEach((variable, index) => {
    const path = `variables[${index}]`;
    object(variable, ['name', 'initial'], path);
    if (typeof variable.name !== 'string' || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(variable.name)) fail('Имя переменной: латинские буквы, цифры и _', `${path}.name`);
    if (names.has(variable.name.toUpperCase())) fail('Имя переменной уже используется', `${path}.name`);
    names.add(variable.name.toUpperCase());
    integer(variable.initial === undefined ? 0 : variable.initial, 0, 255, `${path}.initial`);
  });
  const ref = (name, path) => {
    if (typeof name !== 'string' || !names.has(name.toUpperCase())) fail(`Неизвестная переменная: ${String(name)}`, path);
  };
  const expression = (value, path) => {
    if (typeof value === 'number') integer(value, 0, 255, path);
    else if (value && typeof value === 'object' && Object.hasOwn(value, 'key')) {
      object(value, ['key'], path);
      if (project.format !== 'zxblocks/v2') fail('Клавиатура требует zxblocks/v2. Выберите v2 в формате проекта.', path);
      if (!KEY_NAMES.includes(value.key)) fail('Неизвестная физическая клавиша', path);
    } else { object(value, ['var'], path); ref(value.var, path); }
  };
  const events = project.events === undefined ? {} : project.events;
  object(events, ['start', 'frame'], 'events');
  let count = 0;
  const actions = (list, path, depth = 0) => {
    if (!Array.isArray(list)) fail('Ожидается список действий', path);
    if (depth > 16) fail('Максимальная вложенность — 16', path);
    list.forEach((action, index) => {
      const at = `${path}[${index}]`;
      if (++count > 4096) fail('Максимум 4096 действий', at);
      if (!action || typeof action !== 'object') fail('Ожидается действие', at);
      switch (action.op) {
        case 'set':
          object(action, ['op', 'var', 'value'], at); ref(action.var, at); expression(action.value, `${at}.value`); break;
        case 'change':
          object(action, ['op', 'var', 'by'], at); ref(action.var, at); integer(action.by, -255, 255, `${at}.by`); break;
        case 'call':
          object(action, ['op', 'name', 'arg'], at);
          if (action.name !== 'set_border') fail('Поддерживается только set_border', at);
          expression(action.arg, `${at}.arg`); break;
        case 'if':
          object(action, ['op', 'condition', 'then', 'else'], at);
          object(action.condition, ['var', 'op', 'value'], `${at}.condition`);
          ref(action.condition.var, `${at}.condition`);
          if (!['eq', 'ne', 'lt', 'ge'].includes(action.condition.op)) fail('Сравнение: eq, ne, lt или ge', `${at}.condition`);
          integer(action.condition.value, 0, 255, `${at}.condition.value`);
          actions(action.then === undefined ? [] : action.then, `${at}.then`, depth + 1);
          actions(action.else === undefined ? [] : action.else, `${at}.else`, depth + 1); break;
        default: fail(`Неподдерживаемое действие: ${String(action.op)}`, at);
      }
    });
  };
  for (const event of ['start', 'frame']) actions(events[event] === undefined ? [] : events[event], `events.${event}`);
  return project;
}
