// Run against an offline preview or an isolated studio --registry test path.
// Requires Node 22+ and Chromium. Saves review images in the ignored artifacts/.
import {spawn, execFileSync, spawnSync} from 'node:child_process';
import {mkdtempSync, readFileSync, existsSync, mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';

const url=process.argv[2];
if(!url)throw new Error('Usage: node scripts/browser-smoke.mjs PREVIEW_URL [--save-test]');
const executable=process.env.CHROME_BIN || ['chromium','chromium-browser','google-chrome','google-chrome-stable'].find(name=>spawnSync(name,['--version'],{stdio:'ignore'}).status===0);
if(!executable)throw new Error('Install Chromium/Chrome or set CHROME_BIN');
const profile=mkdtempSync(join(tmpdir(),'niri-fragments-browser-'));
const browser=spawn(executable,['--headless=new','--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let ws;
try{
 for(let i=0;i<100&&!existsSync(join(profile,'DevToolsActivePort'));i++)await sleep(100);
 const port=readFileSync(join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];
 const tabs=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 ws=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 let sequence=0;const pending=new Map();
 ws.onmessage=event=>{const message=JSON.parse(event.data);const p=pending.get(message.id);if(p){pending.delete(message.id);message.error?p.reject(new Error(JSON.stringify(message.error))):p.resolve(message.result);}};
 const rpc=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const r=await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 await rpc('Emulation.setDeviceMetricsOverride',{width:1380,height:1120,deviceScaleFactor:1,mobile:false});
 await rpc('Page.navigate',{url});
 for(let i=0;i<100;i++){if(await evaluate('document.documentElement.dataset.shaderStatus'))break;await sleep(100);}
 assert.equal(await evaluate('document.documentElement.dataset.shaderStatus'),'ready',await evaluate("byId('error').textContent"));
 const expected=JSON.parse(execFileSync('python3',['-c','import hashlib,json;from niri_fragments.effects import PRESETS,shader;print(json.dumps({k:hashlib.sha256(shader(v,False).encode()).hexdigest() for k,v in PRESETS.items()}))'],{encoding:'utf8'}));
 const sample=()=>evaluate(`(()=>{const canvas=byId('stage'),gl=canvas.getContext('webgl');const pixels=new Uint8Array(canvas.width*canvas.height*4);gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let alpha=0,x=0,y=0,occupied=0;for(let i=0;i<pixels.length;i+=4){const a=pixels[i+3];if(a){const px=(i/4)%canvas.width,py=canvas.height-1-Math.floor(i/4/canvas.width);alpha+=a;x+=px*a;y+=py*a;occupied++;}}return {occupied,alpha,cx:alpha?x/alpha:0,cy:alpha?y/alpha:0,error:gl.getError()};})()`);
 const setProgress=async value=>{await evaluate(`byId('progress').value=${Math.round(value*1000)};byId('progress').dispatchEvent(new Event('input'))`);};
 const results={};mkdirSync('artifacts',{recursive:true});
 for(const name of Object.keys(expected)){
  await evaluate(`byId('preset').value=${JSON.stringify(name)};byId('preset').dispatchEvent(new Event('change'))`);
  assert.equal(await evaluate('document.documentElement.dataset.shaderStatus'),'ready',name);
  assert.equal(createHash('sha256').update(await evaluate('shaderFor(parameters,false)')).digest('hex'),expected[name],name+' export matches Python');
  await setProgress(0);const start=await sample();assert.equal(start.occupied,600*380,name+' reconstructs all pixels');
  await setProgress(.45);const middle=await sample();assert(middle.occupied>0&&middle.occupied<start.occupied,name+' intermediate fragments');assert.equal(middle.error,0);
  if(['balanced','explosion','implosion','earth','black-hole','vortex','space'].includes(name)){
   const capture=await rpc('Page.captureScreenshot',{format:'png'});writeFileSync(resolve('artifacts',name+'.png'),Buffer.from(capture.data,'base64'));
  }
  await setProgress(1);const end=await sample();assert.equal(end.occupied,0,name+' disappears completely');
  results[name]={start,middle,end};
 }
 assert(results.earth.middle.cy>results.balanced.middle.cy+25,'Earth moves downward');
 assert(results.updraft.middle.cy<results.balanced.middle.cy-20,'Updraft moves upward');
 assert(results['black-hole'].middle.occupied<results.balanced.middle.occupied/2,'Black hole contracts');
 // Check extreme controls through the real UI, then save only if explicitly requested.
 await evaluate("byId('preset').value='vortex';byId('preset').dispatchEvent(new Event('change'))");
 for(const [id,value] of Object.entries({particles:4096,gravity_strength:3,spin:720,swirl:360,dispersion:1,stagger:.4}))
  await evaluate(`byId(${JSON.stringify(id)}).value=${JSON.stringify(value)};byId(${JSON.stringify(id)}).dispatchEvent(new Event('input'))`);
 await setProgress(.5);assert.equal((await sample()).error,0);assert.equal(await evaluate('document.documentElement.dataset.shaderStatus'),'ready');
 // Exercise the real resize shader, two texture inputs and stable endpoints.
 const resizeExpected=JSON.parse(execFileSync('python3',['-c','import hashlib,json;from niri_fragments.effects import PRESETS,resize_shader;print(json.dumps({k:hashlib.sha256(resize_shader(v).encode()).hexdigest() for k,v in PRESETS.items()}))'],{encoding:'utf8'}));
 await evaluate("document.querySelector('[data-mode=resize]').click()");
 for(const name of Object.keys(resizeExpected)){
  await evaluate(`byId('preset').value=${JSON.stringify(name)};byId('preset').dispatchEvent(new Event('change'))`);
  assert.equal(createHash('sha256').update(await evaluate('shaderFor(parameters,false,true)')).digest('hex'),resizeExpected[name],name+' resize export parity');
  await setProgress(0);assert.equal((await sample()).occupied,600*380,name+' resize starts intact');
  await setProgress(.5);const middle=await sample();assert(middle.occupied>0&&middle.occupied<700*410,name+' resize breaks into pieces');assert.equal(middle.error,0);
  await setProgress(1);assert.equal((await sample()).occupied,800*440,name+' resize ends intact');
 }
 const pixel=()=>evaluate(`(()=>{const gl=byId('stage').getContext('webgl'),p=new Uint8Array(4);gl.readPixels(500,200,1,1,gl.RGBA,gl.UNSIGNED_BYTE,p);return Array.from(p);})()`);
 await setProgress(0);const oldPixel=await pixel();await setProgress(1);assert.notDeepEqual(await pixel(),oldPixel,'resize switches to the new texture contents');
 await setProgress(.5);const resizeCapture=await rpc('Page.captureScreenshot',{format:'png'});writeFileSync('artifacts/resize.png',Buffer.from(resizeCapture.data,'base64'));
 // Opt-in resize styles retain endpoints and preserve more content than full breakup.
 await evaluate("byId('preset').value='balanced';byId('preset').dispatchEvent(new Event('change'))");
 const resizeModes={};
 for(const name of ['full','edge','soft']){
  await evaluate(`byId('resize_mode').value=${JSON.stringify(name)};byId('resize_mode').dispatchEvent(new Event('input'))`);
  assert.equal(await evaluate('parameters.resize'),false,'choosing a resize style is not opt-in');
  await setProgress(0);assert.equal((await sample()).occupied,600*380);
  await setProgress(.5);resizeModes[name]=await sample();assert.equal(resizeModes[name].error,0);
  if(name==='edge')assert(await evaluate(`(()=>{const gl=byId('stage').getContext('webgl'),data=new Uint8Array(40*40*4);gl.readPixels(480,360,40,40,gl.RGBA,gl.UNSIGNED_BYTE,data);for(let i=3;i<data.length;i+=4)if(data[i]!==255)return false;return true;})()`),'edge mode keeps central content intact');
  await setProgress(1);assert.equal((await sample()).occupied,800*440);
 }
 assert(resizeModes.edge.alpha>resizeModes.full.alpha,'edge mode retains more content');
 assert(resizeModes.soft.alpha>resizeModes.full.alpha,'soft mode retains more content');
 // Both textured windows must exchange positions intact, with a visible
 // intermediate stream. The movement prototype must remain labelled as such.
 await evaluate("byId('preset').value='balanced';byId('preset').dispatchEvent(new Event('change'));document.querySelector('[data-mode=swap]').click()");
 assert.equal(await evaluate("byId('concept-note').hidden"),false);
 const sameImage=(a,b,message)=>{let delta=0;for(let i=0;i<a.length;i++)delta=Math.max(delta,Math.abs(a[i]-b[i]));assert(delta<=2,message+' (Canvas resampling tolerance 2/255, got '+delta+')');};
 const columns=()=>evaluate(`(()=>{const c=byId('motion-stage').getContext('2d');return [65,555].map(x=>Array.from(c.getImageData(x,250,380,240).data));})()`);
 await setProgress(0);const before=await columns();
 await setProgress(.5);const during=await columns();assert.notDeepEqual(during,before,'swap has intermediate fragments');
 const swapCapture=await rpc('Page.captureScreenshot',{format:'png'});writeFileSync('artifacts/swap.png',Buffer.from(swapCapture.data,'base64'));
 await setProgress(1);const after=await columns();sameImage(after[0],before[1],'second window arrives intact');sameImage(after[1],before[0],'first window arrives intact');
 await evaluate("document.querySelector('[data-mode=move]').click()");
 await setProgress(0);const moveBefore=await columns();await setProgress(1);const moveAfter=await columns();
 sameImage(moveAfter[1],moveBefore[0],'move arrives intact');
 await evaluate("document.querySelector('[data-mode=effect]').click()");
 // Import through the real file input; failed imports leave the editor untouched.
 const importFile=async(text)=>evaluate(`(async()=>{const transfer=new DataTransfer();transfer.items.add(new File([${JSON.stringify(text)}],'preset.json',{type:'application/json'}));byId('import-file').files=transfer.files;await byId('import-file').onchange();return {effect:effectDocument(),error:byId('error').textContent,status:byId('status').textContent};})()`);
 const importedDoc={schema:1,name:'Imported Exact',effect:{gravity:'up',gravity_strength:.833,open_ms:723,release:'right',origin_x:.123,resize_mode:'edge'}};
 let imported=await importFile(JSON.stringify(importedDoc));assert.equal(imported.error,'');assert.equal(imported.effect.name,importedDoc.name);assert.equal(imported.effect.effect.gravity_strength,.833);assert.equal(imported.effect.effect.resize,false);
 await evaluate("byId('spin').dispatchEvent(new Event('input'))");assert.equal(await evaluate('parameters.gravity_strength'),.833,'unrelated edits preserve imported precision');assert.equal(await evaluate('parameters.open_ms'),723);
 const saved=await evaluate('effectDocument()');
 for(const invalid of ['{broken',JSON.stringify({schema:true,name:'Bad',effect:{}}),JSON.stringify({schema:1,name:'Bad',effect:{gravity:'typo'}}),JSON.stringify({schema:1,name:'Bad',effect:{shader:'injection'}}),JSON.stringify({schema:1,name:'Bad',effect:{resize:1}}),' '.repeat(16385)]){
  const result=await importFile(invalid);assert.match(result.error,/Import failed/);assert.deepEqual(result.effect,saved);
 }
 imported=await importFile(JSON.stringify({schema:1,name:'Resize import',effect:{resize:true,resize_mode:'soft'}}));assert.equal(imported.error,'');assert.equal(imported.effect.effect.resize,true);
 await importFile(JSON.stringify({schema:1,name:'Legacy import',effect:{}}));assert.equal(await evaluate('parameters.resize'),false);
 if(process.argv.includes('--save-test')){
  await evaluate("byId('name').value='Browser Smoke Test';byId('save').click()");
  for(let i=0;i<100;i++){if(await evaluate("!byId('save').disabled"))break;await sleep(100);}
  assert.equal(await evaluate("byId('error').textContent"),'');assert.match(await evaluate("byId('status').textContent"),/^Saved Fragments/);
 }
 writeFileSync('artifacts/browser-checks.json',JSON.stringify(results,null,2)+'\n');
 console.log(`PASS: ${Object.keys(expected).length} WebGL-rendered presets, exact endpoints, motion, shader parity, extreme controls, three resize styles, texture transitions, intact move/swap endpoints, valid/invalid JSON imports and exact imported values`+(process.argv.includes('--save-test')?', and save to isolated registry.':'.'));
}finally{
 ws?.close();if(browser.exitCode===null){const exited=new Promise(resolve=>browser.once('exit',resolve));browser.kill('SIGTERM');await exited;}
 rmSync(profile,{recursive:true,force:true});
}
