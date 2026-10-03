// Deterministic recordings of Studio's real shaders and its labelled concepts.
// Node 22+, Chromium and FFmpeg. No desktop capture or live preset changes.
import {spawn, execFileSync} from 'node:child_process';
import {mkdtempSync, readFileSync, existsSync, mkdirSync, writeFileSync, rmSync, statSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';

const root=resolve(fileURLToPath(new URL('..',import.meta.url)));
process.chdir(root);
mkdirSync(join(root,'artifacts'),{recursive:true});
const scratch=mkdtempSync(join(root,'artifacts/readme-gifs-'));
const preview=join(scratch,'preview.html');
execFileSync('python3',['-m','niri_fragments','preview','--output',preview]);
const profile=mkdtempSync(join(tmpdir(),'fragments-gifs-'));
const browser=spawn('chromium',['--headless=new','--no-sandbox','--disable-dev-shm-usage',
 '--use-angle=swiftshader','--enable-unsafe-swiftshader','--remote-debugging-port=0',
 '--user-data-dir='+profile,'about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let ws;
try{
 for(let i=0;i<100&&!existsSync(join(profile,'DevToolsActivePort'));i++)await sleep(100);
 const port=readFileSync(join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];
 const tabs=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 ws=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 let sequence=0;const pending=new Map();
 ws.onmessage=event=>{const message=JSON.parse(event.data),p=pending.get(message.id);if(p){pending.delete(message.id);message.error?p.reject(new Error(JSON.stringify(message.error))):p.resolve(message.result);}};
 const rpc=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const r=await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 await rpc('Emulation.setDeviceMetricsOverride',{width:720,height:616,deviceScaleFactor:1,mobile:false});
 await rpc('Page.navigate',{url:pathToFileURL(preview).href});
 for(let i=0;i<100;i++){if(await evaluate('document.documentElement.dataset.shaderStatus'))break;await sleep(100);}
 assert.equal(await evaluate('document.documentElement.dataset.shaderStatus'),'ready');
 // Capture-only layout: keep the actual canvas and synthetic window textures.
 await evaluate(`(()=>{
  const style=document.createElement('style');style.textContent=
   'html,body{width:720px;height:616px;margin:0;padding:0;overflow:hidden;background:#10151e}header,body>p,aside,.tabs,.controls,#concept-note,#caption,#status,main>small,#error{display:none!important}.layout{display:block;margin:0 14px}canvas{width:690px;height:524px;max-height:none;min-height:0;border-radius:12px}canvas[hidden]{display:none}#gif-heading{height:53px;padding:18px 22px 0;box-sizing:border-box;font-size:18px;font-weight:600;color:#dfedf5}#gif-note{padding:10px 22px;font-size:12px;color:#93b5c5;display:block!important}';
  document.head.append(style);
  const heading=document.createElement('div');heading.id='gif-heading';document.body.prepend(heading);
  const note=document.createElement('div');note.id='gif-note';document.body.append(note);
 })()`);
 const presets=JSON.parse(execFileSync('python3',['-c','import json;from niri_fragments.effects import describe_presets;print(json.dumps(describe_presets()))'],{encoding:'utf8'}));
 const out=join(root,'docs/gifs');mkdirSync(out,{recursive:true});
 const specs=[
  {name:'opening',preset:'explosion',mode:'effect',title:'OPEN · Reconstruction',direction:'open'},
  {name:'closing',preset:'explosion',mode:'effect',title:'CLOSE · Explosion',direction:'close'},
  {name:'resize',preset:'balanced',mode:'resize',title:'RESIZE · Opt-in fragments',direction:'round'},
  {name:'move-concept',preset:'balanced',mode:'move',title:'MOVE · Studio design concept',direction:'round'},
  {name:'swap-concept',preset:'balanced',mode:'swap',title:'SWAP · Studio design concept',direction:'round'},
  ...Object.keys(presets).map(preset=>({name:'preset-'+preset,preset,mode:'effect',title:preset.replaceAll('-',' ').toUpperCase(),direction:'round',small:true}))
 ];
 const manifest=[];
 for(const spec of specs){
  const directory=join(scratch,spec.name);mkdirSync(directory);
  const effect=presets[spec.preset],concept=['move','swap'].includes(spec.mode);
  // Show actual preset durations, sampled at 20 fps; a hold separates endpoints.
  const forward=spec.mode==='resize'?effect.resize_ms:concept?1100:effect.close_ms;
  const backward=spec.mode==='resize'?effect.resize_ms:concept?1100:effect.open_ms;
  const pause=450,fps=20;
  const duration=spec.direction==='round'?pause*3+forward+backward:pause*2+(spec.direction==='open'?backward:forward);
  const note=concept?'Synthetic windows · design preview, not installed movement':spec.mode==='resize'?'Real resize shader · disabled by default':'Real open/close shader · '+spec.preset+' preset · synthetic window';
  await evaluate(`byId('preset').value=${JSON.stringify(spec.preset)};byId('preset').dispatchEvent(new Event('change'));document.querySelector('[data-mode=${spec.mode}]').click();byId('gif-heading').textContent=${JSON.stringify(spec.title)};byId('gif-note').textContent=${JSON.stringify(note)};`);
  const count=Math.ceil(duration*fps/1000);
  for(let frame=0;frame<count;frame++){
   const t=frame*1000/fps;
   let p;
   if(spec.direction==='open')p=1-Math.max(0,Math.min(1,(t-pause)/backward));
   else if(spec.direction==='close')p=Math.max(0,Math.min(1,(t-pause)/forward));
   else if(t<pause+forward)p=Math.max(0,Math.min(1,(t-pause)/forward));
   else p=1-Math.max(0,Math.min(1,(t-2*pause-forward)/backward));
   await evaluate(`byId('progress').value=${Math.round(p*1000)};byId('progress').dispatchEvent(new Event('input'));`);
   const capture=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
   writeFileSync(join(directory,String(frame).padStart(4,'0')+'.png'),Buffer.from(capture.data,'base64'));
  }
  const target=join(out,spec.name+'.gif'),width=spec.small?360:640;
  execFileSync('ffmpeg',['-v','error','-y','-framerate',String(fps),'-i',join(directory,'%04d.png'),
   '-filter_complex',`scale=${width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`,
   '-loop','0',target]);
  assert(statSync(target).size>1000);
  manifest.push({file:'docs/gifs/'+spec.name+'.gif',preset:spec.preset,mode:spec.mode,frames:count,fps,bytes:statSync(target).size});
  console.log(`Rendered ${spec.name}: ${count} frames, ${Math.round(statSync(target).size/1024)} KiB`);
 }
 writeFileSync(join(out,'manifest.json'),JSON.stringify({renderer:'Studio WebGL shaders / labelled Canvas movement concepts',fps:20,clips:manifest},null,2)+'\n');
 console.log('Frame sources: '+scratch);
}finally{
 ws?.close();if(browser.exitCode===null){const exited=new Promise(resolve=>browser.once('exit',resolve));browser.kill('SIGTERM');await exited;}
 rmSync(profile,{recursive:true,force:true});
}
