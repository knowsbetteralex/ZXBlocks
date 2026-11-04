import {Blockly, toolbox} from './blocks.js';
import {exportProject, importProject, loadEditorState, saveDraft, loadDraft, blockForPath} from './workspace.js';
import {ProjectSession, recoveryKey, request} from './project-session.js';

const $ = id => document.getElementById(id);
let storage = null;
try { storage = window.localStorage; } catch { /* Filesystem saving remains available. */ }
const workspace = Blockly.inject('workspace', {
  toolbox, media: 'media/', renderer: 'zelos', trashcan: true,
  grid: {spacing: 22, length: 2, colour: '#dde4ec', snap: false},
  zoom: {controls: true, wheel: true, startScale: .8, minScale: .35, maxScale: 1.5},
  move: {scrollbars: true, drag: true, wheel: true},
});
let metadata = {name: 'Новый проект', format: 'zxblocks/v1', initials: {}};
let session = null;
let currentExport = null;
let assembly = '';
let assemblySource = '';
let builds = [];
let currentBuild = null;
let selectedTab = 'builds';
let errorBlock = null;
let updateTimer;
let saveTimer;
let loading = false;
let busy = true;
let newDocument = null;

const capture = () => saveDraft(workspace, metadata);
const programText = () => JSON.stringify(currentExport?.project);
const title = () => metadata.name.trim() || 'Без названия';
const filename = () => `${title().replace(/[<>:"/\\|?*\x00-\x1f]/g, '_')}-${session.id.slice(0, 8)}`;
function rememberActive() { try { storage?.setItem('zxblocks.activeProject.v1', session.id); } catch { /* Optional. */ } }

function status(message, error = false, blockId = null) {
  $('status-text').textContent = message;
  $('status').classList.toggle('error', error);
  errorBlock = blockId;
  $('locate-error').hidden = !blockId;
}

function showError(error, sourceMap = currentExport?.sourceMap ?? {}) {
  const candidate = error.blockId || blockForPath(sourceMap, error.path);
  const id = candidate && workspace.getBlockById(candidate) ? candidate : null;
  status(error.message === 'Failed to fetch' ? 'Нет связи с мастерской. Запустите zxblocks editor; черновик сохранён в браузере.' : error.message || 'Не удалось выполнить действие', true, id);
  if (id) workspace.getBlockById(id)?.setWarningText(error.message);
}

function showSaveState() {
  if (!session) return;
  $('project-picker').textContent = `${title()} ▾`;
  document.title = `${title()} — ZXBlocks`;
  $('save-state').textContent = session.error ? 'Не сохранено · нажмите «Сохранить» или создайте копию' :
    session.pending ? 'Сохраняем…' : session.dirty ? 'Есть изменения…' : 'Сохранено на компьютере';
  $('save-state').classList.toggle('save-error', Boolean(session.error));
}

function setBusy(value) {
  busy = value;
  document.querySelectorAll('[data-project-action], #project-picker, #import-file, #create-project').forEach(button => { button.disabled = value; });
  document.querySelectorAll('.run-build').forEach(button => { button.disabled = value; });
  for (const id of ['save', 'run', 'duplicate', 'export', 'export-layout', 'compile', 'build']) $(id).disabled = value || !session;
}

function download(value, name, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([value], {type}));
  const a = document.createElement('a');
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function showOutput() {
  for (const tab of ['builds', 'json', 'asm']) $(tab + '-tab').setAttribute('aria-selected', String(selectedTab === tab));
  $('builds-panel').hidden = selectedTab !== 'builds';
  $('output').hidden = selectedTab === 'builds';
  $('output').textContent = selectedTab === 'asm' ? assembly || 'Выберите «Проверить и показать ASM» в меню или запустите программу.' :
    currentExport ? JSON.stringify(currentExport.project, null, 2) : 'Черновик сохранён. Подключите блоки и исправьте ошибку, чтобы получить JSON программы.';
  $('download-asm').hidden = selectedTab !== 'asm';
  $('download-asm').disabled = !assembly;
  $('build-state').textContent = currentBuild && currentBuild.source === programText() ? `Собрана версия №${Number(currentBuild.number)}` :
    builds.some(build => build.status === 'success') ? 'Версия отличается от сборки' : 'Ещё не собран';
}

function renderBuilds() {
  $('build-list').replaceChildren();
  $('builds-panel').querySelector('.empty-state').hidden = builds.length > 0;
  for (const build of builds) {
    const item = document.createElement('article'); item.className = 'build-item';
    const heading = document.createElement('strong');
    const isCurrent = currentBuild?.number === build.number && currentBuild.source === programText();
    heading.textContent = `№${Number(build.number)} · ${build.status === 'success' ? isCurrent ? 'Текущая программа' : 'Собрана' : build.status === 'failed' ? 'Ошибка сборки' : 'Не завершена'}`;
    const time = document.createElement('p'); time.textContent = `${new Date(build.created_at).toLocaleString('ru-RU')}${build.code_size ? ` · ${build.code_size} байт` : ''}`;
    const links = document.createElement('div'); links.className = 'build-links';
    for (const suffix of ['sna', 'tap']) {
      if (!build.artifacts) break;
      const a = document.createElement('a'); a.href = build.artifacts[suffix]; a.textContent = `Скачать ${suffix.toUpperCase()}`; links.append(a);
    }
    const log = document.createElement('a'); log.href = build.log; log.textContent = 'Журнал'; links.append(log);
    if (build.status === 'success') {
      const run = document.createElement('button'); run.textContent = 'Запустить эту сборку'; run.className = 'run-build'; run.disabled = busy;
      run.addEventListener('click', () => runHistorical(build.number)); links.append(run);
    }
    item.append(heading, time, links);
    if (build.error) { const error = document.createElement('p'); error.className = 'build-error'; error.textContent = build.error; item.append(error); }
    $('build-list').append(item);
  }
}

async function loadBuilds(id = session?.id) {
  if (!id) return;
  const result = await request(`/api/projects/${id}/builds`);
  if (session?.id !== id) return;
  builds = result.builds;
  if (!currentBuild && currentExport) {
    const source = programText();
    const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(source)))].map(value => value.toString(16).padStart(2, '0')).join('');
    const matching = builds.find(build => build.status === 'success' && build.source_hash === hash);
    if (matching && session?.id === id) currentBuild = {number: matching.number, source};
  }
  if (session?.id === id) { renderBuilds(); showOutput(); }
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
        name.value = variable.getName(); status('Укажите уникальное имя: латинские буквы, цифры и _.', true); return;
      }
      workspace.getVariableMap().renameVariable(variable, value); refresh();
    });
    const initial = document.createElement('input');
    initial.type = 'number'; initial.min = '0'; initial.max = '255'; initial.step = '1';
    initial.value = Object.hasOwn(metadata.initials, id) ? metadata.initials[id] ?? '' : 0;
    initial.setAttribute('aria-label', `Начальное значение ${variable.getName()}`);
    initial.addEventListener('change', () => { metadata.initials[id] = Number.isNaN(initial.valueAsNumber) ? null : initial.valueAsNumber; refresh(); });
    const remove = document.createElement('button'); remove.textContent = '×'; remove.setAttribute('aria-label', `Удалить переменную ${variable.getName()}`);
    remove.addEventListener('click', () => {
      const used = workspace.getAllBlocks(false).some(block => block.getField('VAR')?.getVariable()?.getId() === id);
      if (used) { status('Переменная используется в блоках. Сначала замените её в программе.', true); return; }
      workspace.getVariableMap().deleteVariable(variable); delete metadata.initials[id]; refresh();
    });
    row.append(name, initial, remove); $('variables').append(row);
  }
  if (!variables.length) { const empty = document.createElement('p'); empty.className = 'muted'; empty.textContent = 'Добавьте переменную кнопкой ＋'; $('variables').append(empty); }
}

function scheduleSave() {
  if (loading || !session) return;
  session.remember();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => session?.save().catch(showError), 650);
}

function refresh() {
  if (loading) return;
  workspace.getAllBlocks(false).forEach(block => block.setWarningText(null));
  $('block-count').textContent = `${workspace.getAllBlocks(false).length} блоков`;
  try {
    currentExport = exportProject(workspace, metadata);
    metadata.format = currentExport.project.format;
    status('Готово к запуску. F5 — запустить, Ctrl+S — сохранить.');
  }
  catch (error) { currentExport = null; showError(error); }
  if (programText() !== assemblySource) assembly = '';
  renderVariables(); renderBuilds(); showOutput(); scheduleSave();
}

function documentFromFile(data) {
  if (data?.format === 'zxblocks/stored-project/v1') data = data.document;
  const scratch = new Blockly.Workspace();
  try {
    const properties = data?.format === 'zxblocks/editor/v2' ? loadDraft(scratch, data) :
      data?.format === 'zxblocks/editor/v1' ? loadEditorState(scratch, data) : importProject(scratch, data);
    const document = saveDraft(scratch, properties);
    if (data?.format === 'zxblocks/editor/v2') document.view = data.view ?? document.view;
    return document;
  } finally { scratch.dispose(); }
}

function adopt(record, document = record.document) {
  loading = true;
  clearTimeout(updateTimer); clearTimeout(saveTimer);
  try {
    metadata = loadDraft(workspace, document);
    $('project-name').value = metadata.name;
    assembly = ''; assemblySource = ''; builds = []; currentBuild = null;
    session = new ProjectSession(record, capture, {storage, changed: showSaveState});
    rememberActive();
  } finally { loading = false; }
  refresh();
}

async function saveCurrent() {
  clearTimeout(updateTimer); clearTimeout(saveTimer);
  if (session) { refresh(); clearTimeout(saveTimer); await session.save(); }
}

async function openProject(id) {
  if (busy) return;
  setBusy(true); $('open-error').textContent = '';
  try {
    let recovered = false;
    if (session?.id === id && session.conflict) {
      const document = capture();
      document.metadata.name = `${title().slice(0, 100)} — восстановлено`;
      if (document.project) document.project.name = document.metadata.name;
      await request('/api/projects', {document});
      recovered = true;
    } else await saveCurrent();
    const record = await request(`/api/projects/${id}`);
    adopt(record); $('open-dialog').close(); await loadBuilds();
    if (recovered) status('Открыта сохранённая версия. Ваш черновик сохранён отдельным проектом с пометкой «восстановлено».');
  } catch (error) { $('open-error').textContent = error.message; showError(error); }
  finally { setBusy(false); }
}

async function showProjects() {
  if (busy) return;
  $('project-menu').open = false;
  $('open-error').textContent = ''; $('project-list').textContent = 'Загружаем проекты…';
  $('open-dialog').showModal();
  try {
    const result = await request('/api/projects');
    $('project-list').replaceChildren();
    for (const project of result.projects) {
      const button = document.createElement('button'); button.className = 'project-card';
      const name = document.createElement('strong'); name.textContent = project.name;
      const hint = document.createElement('span'); hint.textContent = `${project.id === session?.id ? 'Открыт сейчас · ' : ''}${project.valid ? 'Готов к сборке' : 'Черновик'} · ${new Date(project.updated_at).toLocaleString('ru-RU')} · ${project.id.slice(0, 8)}`;
      button.append(name, hint); button.addEventListener('click', () => openProject(project.id)); $('project-list').append(button);
    }
    if (!result.projects.length) $('project-list').textContent = 'Проектов пока нет. Создайте новый через меню или импортируйте файл.';
  } catch (error) { $('open-error').textContent = error.message; }
}

function askName(document, duplicate = false) {
  newDocument = structuredClone(document);
  $('name-title').textContent = duplicate ? 'Создать копию проекта' : 'Новый проект';
  $('new-name').value = duplicate ? `${title().slice(0, 110)} — копия` : document.metadata.name;
  $('name-error').textContent = '';
  $('name-dialog').showModal(); $('new-name').select();
}

async function createProject(document, {copy = false} = {}) {
  // Copy is also the recovery route after a revision conflict; it never overwrites the original.
  if (!copy) await saveCurrent();
  const record = await request('/api/projects', {document});
  adopt(record); await loadBuilds();
}

async function buildCurrentProject(action) {
  if (busy || !session) return;
  setBusy(true);
  const id = session.id;
  let snapshot;
  try {
    await saveCurrent(); snapshot = exportProject(workspace, metadata);
    status(action === 'run' ? 'Готовим текущую программу и открываем EmuZWin…' : 'Собираем текущую программу…');
    const result = await request(action === 'compile' ? '/api/compile' : `/api/projects/${id}/${action}`,
      action === 'compile' ? snapshot.project : {project: snapshot.project});
    const source = JSON.stringify(snapshot.project);
    if (result.build) { currentBuild = {number: result.build.number, source}; await loadBuilds(id); }
    if (source === programText()) { assembly = result.asm; assemblySource = source; }
    selectedTab = action === 'compile' ? 'asm' : 'builds'; renderBuilds(); showOutput();
    status(source !== programText() ? 'Собранная версия готова. Блоки изменились — запустите текущую программу ещё раз.' :
      result.launched ? `Программа открыта в EmuZWin.${result.reused ? ' Использована готовая сборка.' : ''}` :
        result.build ? `Сборка №${Number(result.build.number)} готова. Скачайте SNA или TAP в панели «Сборки».` : 'ASM готов. Для запуска нажмите «Запустить».');
  } catch (error) { showError(error, snapshot?.sourceMap); await loadBuilds(id).catch(() => {}); }
  finally { setBusy(false); }
}

async function runHistorical(number) {
  if (busy) return;
  setBusy(true);
  try { await request(`/api/projects/${session.id}/builds/${number}/run`, {}); status(`Сборка №${Number(number)} открыта в EmuZWin.`); }
  catch (error) { showError(error); }
  finally { setBusy(false); }
}

$('project-name').addEventListener('input', () => { metadata.name = $('project-name').value; refresh(); });
$('open').addEventListener('click', showProjects);
$('project-picker').addEventListener('click', showProjects);
$('save').addEventListener('click', () => saveCurrent().then(() => {
  if (currentExport) status('Проект и расположение блоков сохранены на компьютере.');
  else status('Черновик сохранён. Исправьте ошибку в блоках перед запуском.', true, errorBlock);
}).catch(showError));
$('import-file').addEventListener('click', () => $('project-file').click());
$('project-file').addEventListener('change', async () => {
  const file = $('project-file').files[0];
  if (!file) return;
  setBusy(true);
  try {
    if (file.size > 1024 * 1024) throw new Error('Файл должен быть не больше 1 МиБ');
    const document = documentFromFile(JSON.parse(await file.text()));
    await createProject(document); $('open-dialog').close(); status('Файл импортирован как отдельный проект. Исходный файл остаётся на месте.');
  } catch (error) { $('open-error').textContent = error.message; showError(error); }
  finally { $('project-file').value = ''; setBusy(false); }
});
$('new').addEventListener('click', () => askName(documentFromFile({format: 'zxblocks/v1', name: 'Новый проект'})));
$('duplicate').addEventListener('click', () => askName(capture(), true));
for (const [button, path] of [['example', 'border_cycle.json'], ['keyboard-example', 'keyboard_border.json']]) {
  $(button).addEventListener('click', async () => {
    try { askName(documentFromFile(await (await fetch(path)).json())); }
    catch (error) { showError(error); }
  });
}
$('name-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  const name = $('new-name').value.trim(); if (!name) return;
  setBusy(true);
  try {
    const document = structuredClone(newDocument); document.metadata.name = name; if (document.project) document.project.name = name;
    await createProject(document, {copy: $('name-title').textContent.startsWith('Создать копию')});
    $('name-dialog').close(); status('Проект создан и сохранён. Он доступен через «Открыть».');
  } catch (error) { $('name-error').textContent = error.message; }
  finally { setBusy(false); }
});
document.querySelectorAll('.close-dialog').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('.menu-items button').forEach(button => button.addEventListener('click', () => { $('project-menu').open = false; }));
document.addEventListener('pointerdown', event => { if (!$('project-menu').contains(event.target)) $('project-menu').open = false; });
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') $('project-menu').open = false;
  if (event.target.closest('dialog')) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); if (!busy) $('save').click(); }
  if (event.key === 'F5' && !event.ctrlKey && !event.shiftKey) { event.preventDefault(); if (!busy) buildCurrentProject('run'); }
});
$('export').addEventListener('click', () => {
  try { download(JSON.stringify(exportProject(workspace, metadata).project, null, 2) + '\n', `${filename()}.json`); status('JSON для компилятора экспортирован.'); }
  catch (error) { showError(error); }
});
$('export-layout').addEventListener('click', () => { download(JSON.stringify(capture(), null, 2) + '\n', `${filename()}.zxb-workspace.json`); status('Проект с блоками экспортирован. Его можно импортировать в другой мастерской.'); });
$('add-variable').addEventListener('click', () => {
  const map = workspace.getVariableMap(); let index = 1;
  while (map.getVariable(`var_${index}`, 'u8')) index++;
  const variable = map.createVariable(`var_${index}`, 'u8'); metadata.initials[variable.getId()] = 0; refresh();
});
$('fit').addEventListener('click', () => workspace.zoomToFit());
$('locate-error').addEventListener('click', () => { if (errorBlock) { workspace.getBlockById(errorBlock)?.select(); workspace.centerOnBlock(errorBlock); } });
for (const tab of ['builds', 'json', 'asm']) $(tab + '-tab').addEventListener('click', () => { selectedTab = tab; showOutput(); });
$('download-asm').addEventListener('click', () => { if (assembly) download(assembly, `${filename()}.asm`, 'text/plain'); });
for (const action of ['compile', 'build', 'run']) $(action).addEventListener('click', () => buildCurrentProject(action));
workspace.addChangeListener(event => {
  if (loading) return;
  if (event.isUiEvent) { if (event.type === Blockly.Events.VIEWPORT_CHANGE) scheduleSave(); return; }
  clearTimeout(updateTimer); updateTimer = setTimeout(refresh, 180);
});
new ResizeObserver(() => Blockly.svgResize(workspace)).observe($('workspace'));
window.addEventListener('beforeunload', event => { if (session?.dirty) { session.remember(); event.preventDefault(); event.returnValue = ''; } });

async function start() {
  setBusy(true);
  try {
    const {projects} = await request('/api/projects');
    let active;
    try { active = storage?.getItem('zxblocks.activeProject.v1'); } catch { /* Optional. */ }
    const id = projects.find(project => project.id === active)?.id ?? projects[0]?.id;
    let legacy = null;
    try { if (!storage?.getItem('zxblocks.editor.v1.migratedProject')) legacy = storage?.getItem('zxblocks.editor.v1'); } catch { /* Optional. */ }
    let migrated = false;
    if (legacy) {
      let document;
      try { document = documentFromFile(JSON.parse(legacy)); }
      catch { /* Original data is retained; a saved project can still open. */ }
      if (document) {
        const record = await request('/api/projects', {document});
        adopt(record); migrated = true;
        try { storage?.setItem('zxblocks.editor.v1.migratedProject', record.id); } catch { /* Optional. */ }
        status('Прежнее автосохранение перенесено в отдельный проект.');
      }
    }
    if (migrated) { /* Already opened the migrated project. */ }
    else if (id) {
      const record = await request(`/api/projects/${id}`);
      let recovery = null;
      try { recovery = JSON.parse(storage?.getItem(recoveryKey(id)) ?? 'null'); } catch { /* Preserve damaged recovery for manual inspection. */ }
      if (recovery && JSON.stringify(recovery.document) !== JSON.stringify(record.document)) {
        // Validate first. A stale browser draft becomes a separate copy, never an overwrite.
        let document;
        try { document = documentFromFile(recovery.document); }
        catch (error) {
          // Keep an unreadable recovery under another key before normal autosaving.
          try { storage?.setItem(`${recoveryKey(id)}.unreadable`, JSON.stringify(recovery)); } catch { /* Optional. */ }
          adopt(record); status(`Не удалось восстановить черновик: ${error.message}. Открыта сохранённая версия.`, true);
          await loadBuilds(); return;
        }
        if (recovery.revision !== record.revision) {
          document.metadata.name = `${document.metadata.name.slice(0, 100)} — восстановлено`;
          if (document.project) document.project.name = document.metadata.name;
          adopt(await request('/api/projects', {document}));
          try { storage?.removeItem(recoveryKey(id)); } catch { /* Optional. */ }
          status('Черновик из браузера восстановлен отдельным проектом. Сохранённая версия доступна через «Открыть».');
        } else { adopt(record, document); status('Восстановлены последние изменения из браузера.'); }
      } else adopt(record);
    } else {
      const document = documentFromFile(await (await fetch('border_cycle.json')).json());
      adopt(await request('/api/projects', {document}));
      if (legacy) status('Прежнее автосохранение прочитать не удалось; оно сохранено в браузере. Открыт новый пример.', true);
    }
    await loadBuilds();
  } catch (error) { showError(error); }
  finally { setBusy(false); }
}
await start();
