// Prepared Word HTML -> local Wenyan previews. No publishing or global CLI lookup.
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
import {createWenyanCore, registerAllBuiltInThemes, getTheme} from '@wenyan-md/core';
import common from './common.cjs';
const {check, root, local, id, hash, read, fresh, inspect, safeError} = common;
try {
  const dir=root(process.argv[2]);
  const themes=(process.argv[3] || '').split(',').filter(Boolean).map(id);
  check(themes.length>0 && themes.length<=3 && new Set(themes).size===themes.length,'choose_one_to_three_themes');
  const source=fs.readFileSync(local(dir,'source.html'),'utf8');
  const expected=read(dir,'source-check.json');
  check(expected.source_html_sha256===hash(source),'source_html_changed');
  registerAllBuiltInThemes();
  const core=await createWenyanCore({isWechat:false,isConvertMathJax:false,mermaid:false});
  for (const theme of themes) {
    check(theme==='original' || getTheme(theme),'theme_not_installed');
    const {root:element}=inspect(JSDOM,source,dir);
    const before=[...element.querySelectorAll('[data-pid]')].map(e=>e.style.textAlign);
    const result=theme==='original' ? element.outerHTML : await core.applyStylesWithTheme(element,{themeId:theme,isMacStyle:false,isAddFootnote:false});
    const {root:styled}=inspect(JSDOM,result,dir);
    [...styled.querySelectorAll('[data-pid]')].forEach((el,i)=>{el.style.whiteSpace='pre-wrap';if(!el.textContent&&!el.querySelector('img')) el.style.minHeight='1em';if(before[i]) el.style.textAlign=before[i];});
    for (const img of styled.querySelectorAll('img')) {img.style.maxWidth='100%';img.style.height='auto';}
    const final=styled.outerHTML;inspect(JSDOM,final,dir);
    fresh(dir,'previews/'+theme+'.html',final);
    // Embed verified images as data URLs; preview needs no file URL or media copy.
    const {root:preview}=inspect(JSDOM,final,dir);
    for (const img of preview.querySelectorAll('img')) {
      const bytes=fs.readFileSync(local(dir,img.getAttribute('src')));
      const type=bytes[0]===0x89?'image/png':'image/jpeg';
      img.setAttribute('src','data:'+type+';base64,'+bytes.toString('base64'));
    }
    const page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:16px;background:white}*{box-sizing:border-box}</style></head><body>'+preview.outerHTML+'</body></html>';
    fresh(dir,'previews/'+theme+'-preview.html',page);
    fresh(dir,'previews/'+theme+'-render.json',JSON.stringify({source_sha256:expected.source_sha256,html_sha256:hash(final),preview_sha256:hash(page),paragraphs_exact:true,images_exact:true,visual_verified:false},null,2));
  }
  console.log('local_render_complete; visual inspection and user confirmation still required');
} catch(e) {safeError(e);process.exitCode=2;}
