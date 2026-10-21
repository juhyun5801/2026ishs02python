'use strict';

// Run on macOS (locally or in GitHub Actions) so Mach-O permissions and signatures stay intact.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const project = path.resolve(__dirname, '..');
const pkg = require('../package.json');
if (process.platform !== 'darwin') {
  console.error('Mac packaging requires macOS. Use the Build festival desktop app workflow on GitHub.');
  process.exit(1);
}
const selected = process.argv.includes('--arm64') ? ['arm64'] : process.argv.includes('--x64') ? ['x64'] : ['arm64', 'x64'];
const run = (command, args) => execFileSync(command, args, {cwd:project, stdio:'inherit'});
for (const arch of selected) {
  run(process.execPath, [require.resolve('electron-builder/out/cli/cli.js'), '--mac', 'dir', '--' + arch, '--publish', 'never', '--config.mac.identity=null']);
  const out = path.join(project, 'dist');
  const appFolder = path.join(out, arch === 'arm64' ? 'mac-arm64' : 'mac', pkg.build.productName + '.app');
  if (!fs.existsSync(appFolder)) throw new Error('Mac app bundle is missing: ' + appFolder);
  // Local/ad-hoc signing verifies integrity on both CPU types without an Apple account.
  run('codesign', ['--force', '--deep', '--sign', '-', '--timestamp=none', appFolder]);
  run('codesign', ['--verify', '--deep', '--strict', appFolder]);
  const base = pkg.build.productName + '-' + pkg.version + '-' + arch;
  run('ditto', ['-c', '-k', '--sequesterRsrc', '--keepParent', appFolder, path.join(out, base + '-mac.zip')]);
  const stage = fs.mkdtempSync(path.join(os.tmpdir(), 'raibit-dmg-'));
  run('ditto', [appFolder, path.join(stage, pkg.build.productName + '.app')]);
  fs.symlinkSync('/Applications', path.join(stage, 'Applications'));
  run('hdiutil', ['create', '-volname', pkg.build.productName, '-srcfolder', stage, '-ov', '-format', 'UDZO', path.join(out, base + '.dmg')]);
  console.log('Created macOS ' + arch + ' app ZIP and DMG in dist/.');
}
