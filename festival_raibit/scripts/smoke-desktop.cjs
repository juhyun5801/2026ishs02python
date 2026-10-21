'use strict';

// Validate the actual packaged app with a fresh, temporary profile. Never use event records.
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const pkg = require('../package.json');
const exe = path.resolve(process.argv[2]);
const exercise = process.argv.includes('--exercise');
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'raibit-release-test-'));
const port = 9234;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let child, socket, serial = 0, log = '';
const pending = new Map();
const guard = setTimeout(() => { console.error('Packaged app test timed out'); if (child) child.kill(); process.exit(1); }, 75000);

async function evaluate(expression) {
  const id = ++serial;
  const promise = new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
  socket.send(JSON.stringify({id, method:'Runtime.evaluate', params:{expression, awaitPromise:true, returnByValue:true}}));
  const result = await promise;
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

(async () => {
  assert.ok(fs.existsSync(exe), 'Packaged executable missing');
  child = spawn(exe, ['--windowed', '--user-data-dir=' + profile, '--remote-debugging-port=' + port], {stdio:['ignore','pipe','pipe']});
  child.stdout.on('data', c => { log = (log + c).slice(-6000); });
  child.stderr.on('data', c => { log = (log + c).slice(-6000); });
  child.on('error', error => { log += error.message; });
  let page;
  for (let i = 0; i < 120; i++) {
    try { page = (await (await fetch('http://127.0.0.1:' + port + '/json')).json()).find(p => p.type === 'page' && p.url.includes('index.html')); } catch (_) {}
    if (page) break;
    if (child.exitCode !== null) throw new Error('App exited before ready: ' + log);
    await sleep(250);
  }
  assert.ok(page, 'App did not open: ' + log);
  assert.ok(page.url.includes('app.asar'), 'Must test packaged app');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, {once:true});
    socket.addEventListener('error', reject, {once:true});
  });
  socket.addEventListener('message', event => {
    const data = JSON.parse(event.data), q = pending.get(data.id);
    if (!q) return;
    pending.delete(data.id);
    if (data.error) q.reject(new Error(data.error.message)); else q.resolve(data.result);
  });
  let state;
  for (let i = 0; i < 50; i++) {
    try { state = await evaluate('api.getState()'); } catch (_) {}
    if (state) break;
    await sleep(100);
  }
  assert.ok(state, 'Preload API must be ready');
  assert.strictEqual(state.version, pkg.version);
  assert.strictEqual(state.sim, false, 'First launch must use hardware mode');
  assert.deepStrictEqual([state.settings.score.ref,state.settings.score.top,state.settings.score.curve,state.settings.soundVolume], [35,3000,0.6,34]);
  assert.strictEqual(state.settings.gaugeSound, true);
  assert.strictEqual(state.recordsTotal, 0);
  await evaluate(`window.__testErrors=[];window.addEventListener('error',e=>window.__testErrors.push(e.message));`);
  const duration = await evaluate(`new Promise((resolve,reject)=>{const a=new Audio('sounds/score-fanfare.wav');a.onloadedmetadata=()=>resolve(a.duration);a.onerror=()=>reject(new Error('Missing fanfare'));a.load();})`);
  assert.ok(Math.abs(duration - 1.85) < 0.01);
  await evaluate(`window.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyD',ctrlKey:true,bubbles:true}))`);
  assert.strictEqual(await evaluate(`!document.getElementById('admin').hidden`), true);
  await evaluate(`document.getElementById('btn-page2').click()`);
  await sleep(300);
  assert.strictEqual(await evaluate(`!document.getElementById('diag').hidden`), true);
  await evaluate(`document.getElementById('btn-page1').click();document.getElementById('btn-page3').click()`);
  await sleep(200);
  assert.deepStrictEqual(await evaluate(`['sc-ref','sc-top','s-volume'].map(id=>Number(document.getElementById(id).value))`), [35,3000,34]);
  assert.strictEqual(await evaluate(`document.getElementById('s-sound').checked`), true);
  assert.strictEqual(await evaluate(`document.body.innerText.includes('미리 듣기')`), false);
  assert.strictEqual(await evaluate(`!!document.getElementById('s-awake')`), false);
  await evaluate(`document.getElementById('s-sound').checked=false;document.getElementById('s-sound').dispatchEvent(new Event('change',{bubbles:true}))`);
  await sleep(150);
  assert.strictEqual((await evaluate('api.getState()')).settings.gaugeSound, false);
  await evaluate(`document.getElementById('s-sound').checked=true;document.getElementById('s-sound').dispatchEvent(new Event('change',{bubbles:true}))`);
  if (exercise) {
    // CI Mac hosts have no sensors attached. Exercise measurement without mixing a real source.
    assert.strictEqual(state.ports.spikerbox.connected, false);
    await evaluate(`Object.defineProperty(document,'hidden',{get:()=>false});window.__fanPlays=0;const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(this.src.includes('score-fanfare.wav'))window.__fanPlays++;return play.call(this)};const update=GaugeSound.prototype.update;GaugeSound.prototype.update=function(o){update.call(this,o);window.__voice=this.voice;}`);
    await evaluate(`api.setSim(true)`);
    await evaluate(`api.simKey('a',true)`);
    await sleep(900);
    await evaluate(`api.start()`);
    await sleep(1000);
    assert.strictEqual(await evaluate(`!!window.__voice && window.__voice.ctx.state==='running'`), true);
    await sleep(4600);
    state = await evaluate(`api.getState()`);
    assert.strictEqual(state.game.phase, 'result');
    assert.ok(state.game.p1.score > 0);
    assert.strictEqual(await evaluate(`window.__fanPlays`), 1);
    await evaluate(`api.setSim(false)`);
  }
  assert.deepStrictEqual(await evaluate('window.__testErrors'), []);
  console.log('PACKAGED APP VERIFIED ' + JSON.stringify({platform:process.platform,arch:process.arch,version:pkg.version,ref:35,referenceScore:3000,volume:34,fanfareSeconds:duration,pages:3,measurement:exercise}));
  // Quit request closes the socket; don't await a response from a terminated app.
  socket.send(JSON.stringify({id:++serial,method:'Runtime.evaluate',params:{expression:'api.quit()'}}));
  await sleep(600);
})().catch(error => {
  console.error(error.stack);
  process.exitCode = 1;
}).finally(() => {
  clearTimeout(guard);
  if (socket) socket.close();
  if (child && child.exitCode === null) child.kill();
});
