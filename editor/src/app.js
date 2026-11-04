import {Blockly, toolbox} from './blocks.js';
import {exportProject, importProject, saveEditorState, loadEditorState, blockForPath} from './workspace.js';

const $ = id => document.getElementById(id);
const storageKey = 'zxblocks.editor.v1';
const workspace = Blockly.inject('workspace', {
  toolbox, media: 'media/', renderer: 'zelos', trashcan: true,
  grid: {spacing: 22, length: 2, colour: '#dde4ec', snap: false},
  zoom: {controls: true, wheel: true, startScale: .8, minScale: .35, maxScale: 1.5},
  move: {scrollbars: true, drag: true, wheel: true},
});
let metadata = {name: 'Новый проект', initials: {}};
let currentExport = null;
let assembly = '';
let artifacts = null;
let selectedTab = 'json';
let errorBlock = null;
let updateTimer;

function status(message, error = false, blockId = null) {
  $('status-text').textContent = message;
  $('status').classList.toggle('error', error);
  errorBlock = blockId;
  $('locate-error').hidden = !blockId;
}

function showOutput() {
  $('output').textContent = selectedTab === 'asm'
    ? assembly || 'Нажмите «Проверить ASM», «Собрать TAP/SNA» или «Запустить».'
    : currentExport ? JSON.stringify(currentExport.project, null, 2) : 'Подключите блоки и исправьте ошибку, чтобы получить JSON.';
  $('json-tab').setAttribute('aria-selected', String(selectedTab === 'json'));
  $('asm-tab').setAttribute('aria-selected', String(selectedTab === 'asm'));
  $('download-asm').disabled = !assembly;
  $('artifacts').hidden = !artifacts;
  if (artifacts) {
    $('download-tap').href = artifacts.tap;
    $('download-sna').href = artifacts.sna;
  } else {
    $('download-tap').removeAttribute('href');
    $('download-sna').removeAttribute('href');
  }
}

function download(value, filename, type = 'application/json') {
  const blob = new Blob([value], {type});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function showError(error, sourceMap = currentExport?.sourceMap ?? {}) {
  const id = error.blockId || blockForPath(sourceMap, error.path);
  status(error.message || 'Не удалось выполнить действие', true, id);
  if (id) workspace.getBlockById(id)?.setWarningText(error.message);
}

function renderVariables() {
  const variables = workspace.getVariableMap().getAllVariables();
  $('variables').replaceChildren();
  for (const variable of variables) {
    const id = variable.getId();
    const row = document.createElement('div'); row.className = 'variable-row';
    const name = document.createElement('input');
    name.value = variable.getName(); name.setAttribute('aria-label', 'Имя переменной');
    name.addEventListener('change', () => {
      const value = name.value.trim();
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(value) || variables.some(v => v.getId() !== id && v.getName().toUpperCase() === value.toUpperCase())) {
        name.value = variable.getName();
        status('Имя не изменено. Укажите уникальное имя: латинские буквы, цифры и _.', true); return;
      }
      workspace.getVariableMap().renameVariable(variable, value); refresh();
    });
    const initial = document.createElement('input');
    initial.type = 'number'; initial.min = '0'; initial.max = '255'; initial.step = '1';
    initial.value = metadata.initials[id] ?? 0; initial.setAttribute('aria-label', `Начальное значение ${variable.getName()}`);
    initial.addEventListener('change', () => {
      const value = initial.valueAsNumber;
      metadata.initials[id] = value; refresh();
    });
    const remove = document.createElement('button'); remove.textContent = '×';
    remove.setAttribute('aria-label', `Удалить переменную ${variable.getName()}`);
    remove.addEventListener('click', () => {
      const used = workspace.getAllBlocks(false).some(block => block.getField('VAR')?.getVariable()?.getId() === id);
      if (used) { status('Переменная используется в блоках. Сначала замените её в программе.', true); return; }
      workspace.getVariableMap().deleteVariable(variable); delete metadata.initials[id]; refresh();
    });
    row.append(name, initial, remove); $('variables').append(row);
  }
  if (!variables.length) {
    const empty = document.createElement('p'); empty.className = 'muted'; empty.textContent = 'Добавьте переменную кнопкой ＋'; $('variables').append(empty);
  }
}

function refresh() {
  const previousProject = JSON.stringify(currentExport?.project);
  workspace.getAllBlocks(false).forEach(block => block.setWarningText(null));
  $('block-count').textContent = `${workspace.getAllBlocks(false).length} блоков`;
  try {
    currentExport = exportProject(workspace, metadata);
    if (JSON.stringify(currentExport.project) !== previousProject) { assembly = ''; artifacts = null; }
    status('Проект готов к сборке. Изменения сохраняются в этом браузере.');
    try { localStorage.setItem(storageKey, JSON.stringify(saveEditorState(workspace, metadata))); }
    catch { status('Проект готов. Автосохранение недоступно — сохраните рабочее место в файл.'); }
  } catch (error) { currentExport = null; assembly = ''; artifacts = null; showError(error); }
  renderVariables(); showOutput();
}

function loadProject(project) {
  metadata = importProject(workspace, project);
  $('project-name').value = metadata.name;
  $('project-format').value = metadata.format;
  refresh();
}

$('project-name').addEventListener('input', () => { metadata.name = $('project-name').value; refresh(); });
$('project-format').addEventListener('change', () => { metadata.format = $('project-format').value; refresh(); });
$('example').addEventListener('click', async () => {
  try { loadProject(await (await fetch('border_cycle.json')).json()); }
  catch (error) { showError(error); }
});
$('keyboard-example').addEventListener('click', async () => {
  try { loadProject(await (await fetch('keyboard_border.json')).json()); }
  catch (error) { showError(error); }
});
$('open').addEventListener('click', () => $('json-file').click());
$('open-layout').addEventListener('click', () => $('layout-file').click());
for (const [input, isLayout] of [[$('json-file'), false], [$('layout-file'), true]]) {
  input.addEventListener('change', async () => {
    const file = input.files[0];
    if (!file) return;
    try {
      if (file.size > 1024 * 1024) throw new Error('Файл должен быть не больше 1 МиБ');
      const data = JSON.parse(await file.text());
      if (isLayout) { metadata = loadEditorState(workspace, data); $('project-name').value = metadata.name; $('project-format').value = metadata.format; refresh(); }
      else loadProject(data);
    } catch (error) { showError(error); }
    input.value = '';
  });
}
$('export').addEventListener('click', () => {
  try { download(JSON.stringify(exportProject(workspace, metadata).project, null, 2) + '\n', 'project.json'); status('JSON программы сохранён. Его можно собрать через zxblocks build.'); }
  catch (error) { showError(error); }
});
$('save-layout').addEventListener('click', () => {
  try { download(JSON.stringify(saveEditorState(workspace, metadata), null, 2) + '\n', 'project.zxb-workspace.json'); status('Рабочее место сохранено вместе с расположением блоков.'); }
  catch (error) { showError(error); }
});
$('add-variable').addEventListener('click', () => {
  const map = workspace.getVariableMap();
  let index = 1;
  while (map.getVariable(`var_${index}`, 'u8')) index++;
  const variable = map.createVariable(`var_${index}`, 'u8');
  metadata.initials[variable.getId()] = 0; refresh();
});
$('fit').addEventListener('click', () => workspace.zoomToFit());
$('locate-error').addEventListener('click', () => {
  if (!errorBlock) return;
  workspace.getBlockById(errorBlock)?.select(); workspace.centerOnBlock(errorBlock);
});
$('json-tab').addEventListener('click', () => { selectedTab = 'json'; showOutput(); });
$('asm-tab').addEventListener('click', () => { selectedTab = 'asm'; showOutput(); });
$('download-asm').addEventListener('click', () => { if (assembly) download(assembly, 'project.asm', 'text/plain'); });
async function buildCurrentProject(action) {
  let snapshot;
  try {
    snapshot = exportProject(workspace, metadata);
    for (const id of ['compile', 'build', 'run']) $(id).disabled = true;
    status(action === 'run' ? 'Собираем текущую программу и открываем EmuZWin…' : 'Собираем текущую программу…');
    const response = await fetch(`/api/${action}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(snapshot.project)});
    const result = await response.json();
    if (!response.ok) { showError(result.error, snapshot.sourceMap); return; }
    if (JSON.stringify(exportProject(workspace, metadata).project) !== JSON.stringify(snapshot.project)) {
      status(result.launched ? 'Собранная версия открыта в EmuZWin. Блоки успели измениться — нажмите «Запустить» ещё раз.' : 'Программа изменилась во время сборки. Нажмите собрать ещё раз.'); return;
    }
    assembly = result.asm; artifacts = result.artifacts ?? artifacts; selectedTab = 'asm'; showOutput();
    status(result.launched ? 'Программа открыта в EmuZWin. Изменяйте блоки и нажимайте «Запустить» для новой сборки.' :
      result.artifacts ? `Готово: ${result.code_size} байт машинного кода. TAP и SNA доступны для скачивания.` : 'Готово: Z80 ASM собран. Для запуска нажмите «Запустить».');
  } catch (error) { showError(error.message === 'Failed to fetch' ? new Error('Нет связи с компилятором. Запустите zxblocks editor.') : error, snapshot?.sourceMap); }
  finally { for (const id of ['compile', 'build', 'run']) $(id).disabled = false; }
}
$('compile').addEventListener('click', () => buildCurrentProject('compile'));
$('build').addEventListener('click', () => buildCurrentProject('build'));
$('run').addEventListener('click', () => buildCurrentProject('run'));

workspace.addChangeListener(event => {
  if (event.isUiEvent) return;
  clearTimeout(updateTimer); updateTimer = setTimeout(refresh, 180);
});
new ResizeObserver(() => Blockly.svgResize(workspace)).observe($('workspace'));

try {
  let saved = null;
  try { saved = localStorage.getItem(storageKey); } catch { /* Editing also works without storage. */ }
  if (saved) {
    try { metadata = loadEditorState(workspace, JSON.parse(saved)); $('project-name').value = metadata.name; $('project-format').value = metadata.format; refresh(); }
    catch {
      // Keep the failed snapshot before a fresh example starts autosaving.
      try { localStorage.setItem(`${storageKey}.recovery`, saved); } catch { /* Storage may be unavailable. */ }
      loadProject(await (await fetch('border_cycle.json')).json());
      status('Не удалось восстановить рабочее место. Открыт пример бордюра.', true);
    }
  } else loadProject(await (await fetch('border_cycle.json')).json());
} catch (error) { showError(error); }
