// Screenshot only reviewed generated previews in an ephemeral, offline browser context.
const fs=require('node:fs');
const {chromium}=require('playwright-core');
const {check,root,local,id,hash,read,fresh,sourceCheck,safeError}=require('./common.cjs');
(async()=>{
  const dir=root(process.argv[2]);
  const themes=(process.argv[3]||'').split(',').filter(Boolean).map(id);
  check(themes.length>0&&themes.length<=3,'choose_one_to_three_themes');
  check(process.env.CHROME_PATH&&fs.existsSync(process.env.CHROME_PATH),'set_CHROME_PATH_to_trusted_browser');
  sourceCheck(dir);
  for(const theme of themes){
    const report=read(dir,'previews/'+theme+'-render.json');
    const markup=fs.readFileSync(local(dir,'previews/'+theme+'-preview.html'),'utf8');
    check(hash(markup)===report.preview_sha256,'preview_changed');
    check(hash(fs.readFileSync(local(dir,'previews/'+theme+'.html')))===report.html_sha256,'html_changed');
    check(!fs.existsSync(local(dir,'previews/'+theme+'-390.png')),'screenshot_already_exists');
    const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,chromiumSandbox:true});
    try{
      const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:2,javaScriptEnabled:false,serviceWorkers:'block',acceptDownloads:false});
      await context.route('**/*',r=>r.abort());
      const page=await context.newPage();
      await page.setContent(markup,{waitUntil:'load',timeout:15000});
      const stats=await page.evaluate(()=>({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,broken:[...document.images].filter(i=>!i.complete||!i.naturalWidth).length}));
      const passed=stats.width<=390&&stats.broken===0&&stats.height<=30000;
      fresh(dir,'previews/'+theme+'-capture.json',JSON.stringify({...stats,passed,html_sha256:report.html_sha256,preview_sha256:report.preview_sha256,visual_verified:false},null,2));
      check(passed,'capture_failed_broken_image_overflow_or_too_tall');
      await page.screenshot({path:local(dir,'previews/'+theme+'-390.png'),fullPage:true,timeout:15000});
    }finally{await browser.close();}
  }
  console.log('capture_checks_passed; screenshots still need human visual inspection');
})().catch(e=>{safeError(e);process.exitCode=2;});
