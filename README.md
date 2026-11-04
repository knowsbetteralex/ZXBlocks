# ZXBlocks

**ZXBlocks** — открытый экспериментальный конструктор программ для ZX Spectrum 48K: визуальные блоки на ПК → версионированный JSON IR → читаемый Z80 ASM → машинный код/TAP. Spectrum исполняет только скомпилированный результат.

> **Статус: pre-alpha, M2 — клавиатура.** Работают Python-компилятор, локальный Blockly-редактор и версионированное чтение клавиш. Проекты v1 сохранены; новые клавиатурные выражения используют v2. Таймеры, процедуры и игровой runtime — следующие этапы. Браузерная приёмка M1 остаётся открытой в чеклисте.

## Быстрый старт

Нужен Python 3.11+.

~~~powershell
git clone https://github.com/knowsbetteralex/ZXBlocks.git
cd ZXBlocks
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python -m zxblocks compile examples/border_cycle/project.json -o build/examples/border_cycle/border_cycle.asm
~~~

Для сборки BIN и TAP установите sjasmplus: https://github.com/z00m128/sjasmplus/releases

~~~powershell
python -m zxblocks build examples/border_cycle/project.json
~~~

Результаты: `build/cli/border_cycle/border_cycle.asm`, `.bin`, `.tap`.
`-o` задаёт другую папку явно; сборки из VS Code находятся в `build/examples/`.

**Внимание:** пока создаётся CODE-only TAP, без BASIC-загрузчика и автозапуска. На Spectrum 48K выполните CLEAR 32767, затем LOAD "" CODE, затем RANDOMIZE USR 32768. Полученная программа не возвращается в BASIC.

## Сборка и отладка в VS Code

После создания `.venv` и установки проекта установите рекомендованные расширения
**DeZog** (`maziac.dezog`), **Z80 Assembly** (`imanolea.z80-asm`) и
**ASM Code Lens** (`maziac.asm-code-lens`);
`sjasmplus` должен быть доступен в PATH терминала VS Code.
Общие настройки находятся в `.vscode/` и используют Python из `.venv` без
предварительной активации окружения.
Файлы `.asm` и `.inc` связаны с языком Z80 Assembly, чтобы DeZog разрешал
устанавливать точки останова даже при других общих настройках ассемблера.

- **Ctrl+Shift+B** запускает `ZXBlocks: build`: JSON-пример `border_cycle`
  компилируется в `build/examples/border_cycle/border_cycle.asm`, `.bin` и `.tap`.
- **F5**, конфигурация `ZXBlocks: border_cycle (DeZog 48K)`, сначала выполняет
  сборку, затем создаёт SNA и SLD в `build/examples/border_cycle/` и открывает встроенный
  симулятор DeZog в режиме Spectrum 48K. Выполнение остановлено на входе;
  повторное **F5** продолжает программу, **F10/F11** выполняют шаги.
- Для точек останова откройте `build/examples/border_cycle/border_cycle.asm`, например процедуру
  `ZXB_ON_FRAME`. Сейчас отладка привязана к сгенерированному ASM, а не к JSON.
- Если `emuz` доступен в PATH, задача **Tasks: Run Task → ZXBlocks: run EmuZWin**
  пересобирает пример и открывает SNA в EmuZWin. Это отдельный запуск эмулятора;
  сеанс DeZog использует собственный симулятор.

Снимок SNA сразу запускает код с адреса 32768 и содержит подготовленные RAM,
системные переменные и стек ниже кода, как после `CLEAR 32767`. Его сборка
описана в `tools/debug_border_cycle.asm`; ROM в снимок не включается.
Все результаты сборки и временные файлы DeZog остаются в `build/`.

Эту же отладочную сборку можно выполнить из терминала в корне репозитория:

~~~powershell
.venv\Scripts\python.exe -m zxblocks build examples/border_cycle/project.json -o build/examples/border_cycle
sjasmplus --fullpath=rel --sld=build/examples/border_cycle/border_cycle.sld tools/debug_border_cycle.asm
emuz build\examples\border_cycle\border_cycle.sna
~~~

## Blockly-редактор

Для сборки редактора нужен Node.js 22+. Python CLI по-прежнему работает
самостоятельно, без Node.js и сторонних Python-библиотек.

~~~powershell
cd editor
npm ci
npm test
npm run build
cd ..
.venv\Scripts\python.exe -m zxblocks editor --open
~~~

Редактор доступен на **http://127.0.0.1:8765**. В VS Code после `npm ci`
можно запускать задачу **ZXBlocks: editor** — она пересоберёт редактор.
Сервер останавливается через Ctrl+C; другой порт задаётся `--port 8766`.
Если порт занят, остановите уже запущенный редактор или выберите другой порт.

Сверху — название текущего проекта и три кнопки:

- **Открыть** — список проектов и импорт JSON/рабочего места из файла.
- **Сохранить** / Ctrl+S — сохранить проект на компьютере вместе с блоками и
  масштабом. Есть автосохранение, в том числе незаконченных черновиков.
- **▶ Запустить** / F5 — собрать текущую программу и открыть SNA в EmuZWin.

В **Меню** находятся создание и копирование проекта, создание из примеров,
экспорт, сборка TAP/SNA без запуска, просмотр ASM и показ всех блоков.
Примеры открываются новыми проектами. При переключении работа сохраняется;
при следующем входе открывается последний проект. Прежнее автосохранение
браузера переносится в отдельный проект.

Панель **Сборки** показывает только результаты текущего проекта, скачивание
TAP/SNA и журнал. Повторный запуск неизменённой программы использует готовую
проверенную сборку. Нужны `sjasmplus` и `emuz` в PATH сервера редактора.

**Меню → Экспорт → Проект с блоками** создаёт переносимую копию всего рабочего
места. **JSON для компилятора** экспортирует только `zxblocks/v1` или
`zxblocks/v2` для `zxblocks compile/build/run` и требует исправить ошибки схемы.
Подробнее: [редактор](editor/README.md), [проекты и структура файлов](docs/PROJECTS.md).

Любой сохранённый проект можно также собрать и запустить одной командой:

~~~powershell
.venv\Scripts\python.exe -m zxblocks run examples/keyboard_border/project.json
~~~

Замените путь на свой JSON. Команда создаёт `project.asm`, `.bin`, `.tap`,
`.sna`, `.sld` и копию JSON в `build/cli/keyboard_border/`, затем открывает SNA через `emuz`.
`-o build/my_run` меняет папку результата; `--emulator` и `--assembler` задают
исполняемые файлы для запуска из CLI. Исходный проект остаётся на месте.
Проекты редактора хранятся в `projects/<id>/`, их пронумерованные сборки — в
`build/projects/<id>/<номер>/`, отдельно исходники, готовые файлы и отладка.
Папки примеров не перезаписываются. TAP по-прежнему
CODE-only, а SNA сразу открывает программу с адреса 32768.

## Клавиатура и проверка логики (v2)

В редакторе выберите **Меню → Создать из примера → Бордюр с клавиатурой**. Он создаёт проект v2: пробел
нажат — жёлтый бордюр, отпущен — синий. Блок **клавиша … нажата** возвращает
0 или 1. Для своего проекта сначала явно выберите **v2 · клавиатура**.
Обычные проекты v1 продолжают собираться без изменения результата.

~~~powershell
.venv\Scripts\python.exe -m zxblocks build examples/keyboard_border/project.json -o build/examples/keyboard_border
.venv\Scripts\python.exe -m zxblocks simulate examples/keyboard_border/project.json --inputs examples/keyboard_border/inputs.json
~~~

`simulate` проверяет логику на ПК и не является эмулятором Spectrum. Для
явного обновления существующего JSON есть `zxblocks upgrade input.json -o output.json`.
Спецификация: [zxblocks/v2](docs/BLOCK_IR_V2.md).

Для отладки выберите конфигурацию **ZXBlocks: keyboard_border (DeZog 48K)**
и нажмите F5. Задача **ZXBlocks: run keyboard in EmuZWin** открывает новый
снимок в `emuz`. Для ручной сборки снимка и запуска:

~~~powershell
sjasmplus --fullpath=rel --sld=build/examples/keyboard_border/keyboard_border.sld tools/debug_keyboard_border.asm
emuz build\examples\keyboard_border\keyboard_border.sna
~~~

## Уже работает

- События start и frame.
- Переменные u8 (0–255), начальные значения.
- Блоки set, change, if (eq, ne, lt, ge), call set_border.
- Читаемая и детерминированная генерация ASM, валидация JSON.
- CODE TAP, юнит-тесты, GitHub Actions.
- Локальный Blockly-редактор, импорт/экспорт IR, переменные, сохранение рабочего места.
- Компиляция из редактора через Python и привязка ошибок действий к блокам.
- Клавиатура в v2, явная миграция, Python-модель логики и тесты собранного Z80-кода.

**Пока не реализованы:** таймеры и процедуры в IR, анимации, игровые объекты, столкновения, BASIC-загрузчик, измерение T-states в Spectrum, другие типы чисел.

## Папки

| Путь | Назначение |
| --- | --- |
| src/zxblocks/ | Python-компилятор, CLI, упаковка TAP |
| examples/ | Проекты на JSON IR |
| projects/ | Локальные пользовательские проекты редактора, вне Git |
| build/ | Сборки по проектам, примеры, проверки и отладочные данные |
| tests/ | Регрессионные тесты |
| editor/ | Локальный Blockly-редактор и тесты переноса IR |
| runtime/ | Будущие процедуры Z80 |
| docs/ | Архитектура, IR, этапы и решения |
| AGENTS.md | Инструкции для Codex |

Порядок чтения: [архитектура](docs/ARCHITECTURE.md), [формат блоков](docs/BLOCK_IR.md), [план](docs/ROADMAP.md), [совместная работа](CONTRIBUTING.md).

Главный принцип: **блоки описывают поведение, движок реализует механизм**. Генерируемые программы независимы от IDE. Идеи из [SpaceCan](https://github.com/knowsbetteralex/SpaceCan) можно переносить после анализа контрактов и лицензий.

## Лицензия

MIT для оригинального кода ZXBlocks. Лицензии сторонних библиотек и переносимых процедур рассматриваются отдельно.
