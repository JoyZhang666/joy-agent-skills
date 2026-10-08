// Synthetic local tests. Browser cases run only with an explicitly selected CHROME_PATH.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const {JSDOM}=require('jsdom');
const common=require('./common.cjs');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jC1kAAAAASUVORK5CYII=','base64');
function fixture(t){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'word-tools-test-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  fs.mkdirSync(path.join(dir,'media'));
  const source=Buffer.from('synthetic retained source, not a real document');
  const markup='<div id="wenyan"><p data-pid="p0001">Sample<br>text<img src="media/image0001.png" data-source-image="media/image0001.png"></p></div>';
  const files={'source.docx':source,'source.html':markup,'media/image0001.png':png,
    'source-paragraphs.json':JSON.stringify([{pid:'p0001',tag:'p',text:'Sample\ntext',images:['media/image0001.png']}]),
    'source-check.json':JSON.stringify({source_sha256:common.hash(source),source_html_sha256:common.hash(markup),images:[{file:'media/image0001.png',sha256:common.hash(png)}]})};
  for(const [n,b] of Object.entries(files))fs.writeFileSync(path.join(dir,n),b);
  return dir;
}
function run(script,dir,theme){
  const env={};for(const k of ['SystemRoot','WINDIR','PATH','TEMP','TMP','TMPDIR','CHROME_PATH'])if(process.env[k])env[k]=process.env[k];
  return spawnSync(process.execPath,[path.join(__dirname,script),dir,theme],{encoding:'utf8',env,timeout:60000});
}
test('article boundary and theme traversal are rejected',t=>{
  const dir=fixture(t);assert.throws(()=>common.local(dir,'../outside'));
  assert.throws(()=>common.id('../theme'));assert.throws(()=>common.id('CON'));
});
test('source text, order, local image identity and active content are guarded',t=>{
  const dir=fixture(t),original=fs.readFileSync(path.join(dir,'source.html'),'utf8');
  common.inspect(JSDOM,original,dir);
  for(const changed of [original.replace('Sample','Changed'),original.replace('media/image0001.png','https://example.com/x.png'),original.replace('<p','<script>bad</script><p')])assert.throws(()=>common.inspect(JSDOM,changed,dir));
  fs.appendFileSync(path.join(dir,'media/image0001.png'),'changed');assert.throws(()=>common.inspect(JSDOM,original,dir));
});
test('render uses the selected directory and refuses overwrite',t=>{
  const dir=fixture(t),other=fixture(t);const a=run('render.mjs',dir,'original');assert.equal(a.status,0,a.stderr);
  assert.equal(fs.existsSync(path.join(other,'previews')),false);
  const output=fs.readFileSync(path.join(dir,'previews/original.html'));
  const b=run('render.mjs',dir,'original');assert.notEqual(b.status,0);assert.deepEqual(fs.readFileSync(path.join(dir,'previews/original.html')),output);
});
test('changed source HTML and missing theme fail before success',t=>{
  const dir=fixture(t);fs.appendFileSync(path.join(dir,'source.html'),'changed');
  assert.notEqual(run('render.mjs',dir,'original').status,0);
  const clean=fixture(t);assert.notEqual(run('render.mjs',clean,'does-not-exist').status,0);
});
test('legacy publisher cannot send or bypass cover requirements',t=>{
  const dir=fixture(t);const result=run('publish-guarded.mjs',dir,'original');assert.equal(result.status,2);
  assert.equal(fs.existsSync(path.join(dir,'push-receipt.json')),false);
});
test('real browser writes a verified screenshot',{skip:!process.env.CHROME_PATH},t=>{
  const dir=fixture(t);assert.equal(run('render.mjs',dir,'original').status,0);
  const result=run('capture.cjs',dir,'original');assert.equal(result.status,0,result.stderr);
  assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'previews/original-capture.json'))).passed,true);
  assert.ok(fs.statSync(path.join(dir,'previews/original-390.png')).size>0);
});
test('broken preview image produces failure, never success',{skip:!process.env.CHROME_PATH},t=>{
  const dir=fixture(t);assert.equal(run('render.mjs',dir,'original').status,0);
  const file=path.join(dir,'previews/original-preview.html');
  const broken=fs.readFileSync(file,'utf8').replace(/data:image\/png;base64,[^\"]+/,'data:image/png;base64,broken');fs.writeFileSync(file,broken);
  const reportFile=path.join(dir,'previews/original-render.json'),report=JSON.parse(fs.readFileSync(reportFile));report.preview_sha256=common.hash(broken);fs.writeFileSync(reportFile,JSON.stringify(report));
  const result=run('capture.cjs',dir,'original');assert.notEqual(result.status,0);
  assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'previews/original-capture.json'))).passed,false);
  assert.equal(fs.existsSync(path.join(dir,'previews/original-390.png')),false);
});
