import * as BlocklyModule from 'blockly/core';
import * as RuModule from 'blockly/msg/ru';
import {KEY_NAMES} from './keys.js';

// Blockly exposes CommonJS in Node and ESM in browsers.
const unwrap = module => module.default ?? module;
const Blockly = unwrap(BlocklyModule);
Blockly.setLocale(unwrap(RuModule));

const variable = {type: 'field_variable', name: 'VAR', variable: 'counter', variableTypes: ['u8'], defaultType: 'u8'};
const byte = (name) => ({type: 'field_number', name, value: 0, min: 0, max: 255, precision: 1});

Blockly.common.defineBlocksWithJsonArray([
  {type: 'zxb_event', message0: '%1 %2', args0: [
    {type: 'field_dropdown', name: 'EVENT', options: [['Когда программа запускается', 'start'], ['Каждый кадр', 'frame']]},
    {type: 'input_statement', name: 'DO', check: 'Action'}], colour: 36},
  {type: 'zxb_set', message0: 'задать %1 значение %2', args0: [variable, {type: 'input_value', name: 'VALUE', check: 'Byte'}],
    previousStatement: 'Action', nextStatement: 'Action', colour: 212},
  {type: 'zxb_change', message0: 'изменить %1 на %2', args0: [variable,
    {type: 'field_number', name: 'DELTA', value: 1, min: -255, max: 255, precision: 1}],
    previousStatement: 'Action', nextStatement: 'Action', colour: 212},
  {type: 'zxb_if', message0: 'если %1 %2 %3', args0: [variable,
    {type: 'field_dropdown', name: 'CMP', options: [['=', 'eq'], ['≠', 'ne'], ['<', 'lt'], ['≥', 'ge']]}, byte('LIMIT')],
    message1: 'то %1', args1: [{type: 'input_statement', name: 'THEN', check: 'Action'}],
    message2: 'иначе %1', args2: [{type: 'input_statement', name: 'ELSE', check: 'Action'}],
    previousStatement: 'Action', nextStatement: 'Action', colour: 278},
  {type: 'zxb_border', message0: 'цвет бордюра %1', args0: [{type: 'input_value', name: 'VALUE', check: 'Byte'}],
    previousStatement: 'Action', nextStatement: 'Action', colour: 154},
  {type: 'zxb_byte', message0: '%1', args0: [byte('NUM')], output: 'Byte', colour: 212},
  {type: 'zxb_var', message0: '%1', args0: [variable], output: 'Byte', colour: 212},
  {type: 'zxb_key', message0: 'клавиша %1 нажата', args0: [
    {type: 'field_dropdown', name: 'KEY', options: KEY_NAMES.map(key => [key === 'SPACE' ? 'ПРОБЕЛ' : key, key])}],
    output: 'Byte', colour: 154, tooltip: 'zxblocks/v2: 1 — нажата, 0 — отпущена. Состояние фиксируется перед каждым кадром.'},
]);

export const toolbox = {kind: 'categoryToolbox', contents: [
  {kind: 'category', name: 'События', colour: '#c48227', contents: [{kind: 'block', type: 'zxb_event'}]},
  {kind: 'category', name: 'Переменные', colour: '#367fc4', contents: [
    {kind: 'block', type: 'zxb_set', inputs: {VALUE: {shadow: {type: 'zxb_byte'}}}},
    {kind: 'block', type: 'zxb_change'}, {kind: 'block', type: 'zxb_var'}, {kind: 'block', type: 'zxb_byte'}]},
  {kind: 'category', name: 'Условия', colour: '#945ac2', contents: [{kind: 'block', type: 'zxb_if'}]},
  {kind: 'category', name: 'Spectrum', colour: '#2b9873', contents: [
    {kind: 'block', type: 'zxb_border', inputs: {VALUE: {shadow: {type: 'zxb_byte'}}}},
    {kind: 'block', type: 'zxb_key', fields: {KEY: 'SPACE'}}]},
]};

export {Blockly};
