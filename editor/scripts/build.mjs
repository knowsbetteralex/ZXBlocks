import {build} from 'esbuild';
import {cp, mkdir} from 'node:fs/promises';

await mkdir('dist', {recursive: true});
await build({
  entryPoints: ['src/app.js'],
  bundle: true,
  outfile: 'dist/app.js',
  format: 'esm',
  target: 'es2022',
  sourcemap: true,
  legalComments: 'linked',
});
await cp('index.html', 'dist/index.html');
await cp('src/styles.css', 'dist/styles.css');
await cp('node_modules/blockly/media', 'dist/media', {recursive: true});
await cp('THIRD_PARTY_NOTICES.md', 'dist/THIRD_PARTY_NOTICES.md');
await cp('node_modules/blockly/LICENSE', 'dist/BLOCKLY_LICENSE');
await cp('../examples/border_cycle/project.json', 'dist/border_cycle.json');
await cp('../examples/keyboard_border/project.json', 'dist/keyboard_border.json');
await cp('../examples/arithmetic_border/project.json', 'dist/arithmetic_border.json');
console.log('Built editor/dist');
