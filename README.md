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
