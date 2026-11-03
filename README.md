# ZXBlocks

**ZXBlocks** — открытый экспериментальный конструктор программ для ZX Spectrum 48K: визуальные блоки на ПК → версионированный JSON IR → читаемый Z80 ASM → машинный код/TAP. Spectrum исполняет только скомпилированный результат.

> **Статус: bootstrap / pre-alpha.** Реализован минимальный Python-компилятор JSON IR, а не графический Scratch-редактор. Первый пример циклически меняет цвет бордюра. Визуальный редактор и библиотека игровых процедур — следующие этапы.

## Быстрый старт

Нужен Python 3.11+.

~~~powershell
git clone https://github.com/knowsbetteralex/ZXBlocks.git
cd ZXBlocks
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python -m zxblocks compile examples/border_cycle/project.json -o build/border_cycle.asm
~~~

Для сборки BIN и TAP установите sjasmplus: https://github.com/z00m128/sjasmplus/releases

~~~powershell
python -m zxblocks build examples/border_cycle/project.json -o build
~~~

Результаты: build/border_cycle.asm, build/border_cycle.bin, build/border_cycle.tap.

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
  компилируется в `build/border_cycle.asm`, `.bin` и `.tap`.
- **F5**, конфигурация `ZXBlocks: border_cycle (DeZog 48K)`, сначала выполняет
  сборку, затем создаёт `build/border_cycle.sna` и `.sld` и открывает встроенный
  симулятор DeZog в режиме Spectrum 48K. Выполнение остановлено на входе;
  повторное **F5** продолжает программу, **F10/F11** выполняют шаги.
- Для точек останова откройте `build/border_cycle.asm`, например процедуру
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
.venv\Scripts\python.exe -m zxblocks build examples/border_cycle/project.json -o build
sjasmplus --fullpath=rel --sld=build/border_cycle.sld tools/debug_border_cycle.asm
emuz build\border_cycle.sna
~~~

## Уже работает

- События start и frame.
- Переменные u8 (0–255), начальные значения.
- Блоки set, change, if (eq, ne, lt, ge), call set_border.
- Читаемая и детерминированная генерация ASM, валидация JSON.
- CODE TAP, юнит-тесты, GitHub Actions.

**Пока не реализованы:** визуальный редактор, анимации, игровые объекты, столкновения, BASIC-загрузчик, подсчёт T-states, другие типы чисел.

## Папки

| Путь | Назначение |
| --- | --- |
| src/zxblocks/ | Python-компилятор, CLI, упаковка TAP |
| examples/ | Проекты на JSON IR |
| tests/ | Регрессионные тесты |
| editor/ | Будущий веб-редактор Blockly |
| runtime/ | Будущие процедуры Z80 |
| docs/ | Архитектура, IR, этапы и решения |
| AGENTS.md | Инструкции для Codex |

Порядок чтения: [архитектура](docs/ARCHITECTURE.md), [формат блоков](docs/BLOCK_IR.md), [план](docs/ROADMAP.md), [совместная работа](CONTRIBUTING.md).

Главный принцип: **блоки описывают поведение, движок реализует механизм**. Генерируемые программы независимы от IDE. Идеи из [SpaceCan](https://github.com/knowsbetteralex/SpaceCan) можно переносить после анализа контрактов и лицензий.

## Лицензия

MIT для оригинального кода ZXBlocks. Лицензии сторонних библиотек и переносимых процедур рассматриваются отдельно.
