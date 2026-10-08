// Local Word artifacts only. Never import account configuration.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
class Stop extends Error {}
function check(ok, code) { if (!ok) throw new Stop(code); }
function noLinks(p) {
  for (let q = path.resolve(p); ; q = path.dirname(q)) {
    if (fs.existsSync(q)) check(!fs.lstatSync(q).isSymbolicLink(), 'linked_path');
    if (q === path.dirname(q)) break;
  }
}
function root(value) {
  check(typeof value === 'string' && value.length > 0, 'missing_article_dir');
  noLinks(value); const p = fs.realpathSync(value);
  check(fs.statSync(p).isDirectory(), 'not_article_dir'); return p;
}
function local(dir, name) {
  check(typeof name === 'string' && name.length > 0 && !path.isAbsolute(name) && !name.includes(':') && !name.split(/[\\/]/).includes('..'), 'outside_article_dir');
  const p = path.resolve(dir, name); check(p.startsWith(dir + path.sep), 'outside_article_dir'); noLinks(p); return p;
}
function id(value) {
  check(/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(value) && !/^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i.test(value), 'invalid_theme_id'); return value;
}
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const read = (dir, name) => JSON.parse(fs.readFileSync(local(dir, name), 'utf8'));
function fresh(dir, name, content) {
  const p = local(dir, name); fs.mkdirSync(path.dirname(p), {recursive:true}); fs.writeFileSync(p, content, {flag:'wx'});
}
function sourceCheck(dir) {
  const meta = read(dir, 'source-check.json');
  check(meta.source_sha256 === hash(fs.readFileSync(local(dir, 'source.docx'))), 'source_changed');
  for (const image of meta.images) {
    const name = image.file.startsWith('media/') ? image.file : 'media/' + image.file;
    check(image.sha256 === hash(fs.readFileSync(local(dir, name))), 'image_changed');
  }
  return meta;
}
function inspect(JSDOM, markup, dir) {
  const dom = new JSDOM(markup); // No runScripts/resources: no source code or remote fetch.
  const document = dom.window.document;
  const roots = document.querySelectorAll('#wenyan'); check(roots.length === 1, 'missing_or_duplicate_root');
  const root = roots[0];
  const tags = new Set(['DIV','SECTION','P','H1','H2','H3','H4','H5','H6','SPAN','STRONG','B','EM','I','U','BR','IMG']);
  for (const el of [root, ...root.querySelectorAll('*')]) {
    check(tags.has(el.tagName), 'unsupported_html_tag');
    for (const a of el.attributes) {
      check(['id','class','style','data-pid','data-source-image','src','alt','width','height'].includes(a.name), 'unsupported_html_attribute');
      if (a.name === 'style') check(!/url\s*\(|@|expression\s*\(|\\|\/\*/i.test(a.value), 'external_or_active_css');
      if (a.name === 'src') check(el.tagName === 'IMG', 'unexpected_source');
    }
  }
  check(document.body.children.length === 1 && document.body.firstElementChild === root, 'extra_body_content');
  check(!document.querySelector('script,iframe,object,embed,link,style,base,meta'), 'active_document_content');
  const paraText = e => { const c=e.cloneNode(true);for(const br of c.querySelectorAll('br')) br.replaceWith('\n');return c.textContent; };
  const paras = [...root.querySelectorAll('[data-pid]')].map(e => ({
    pid:e.dataset.pid, tag:e.tagName.toLowerCase(), text:paraText(e),
    images:[...e.querySelectorAll('img')].map(i => i.getAttribute('data-source-image'))
  }));
  const expected = read(dir, 'source-paragraphs.json');
  check(JSON.stringify(paras) === JSON.stringify(expected), 'paragraphs_changed');
  const walker=document.createTreeWalker(root,4);
  for(let t=walker.nextNode();t;t=walker.nextNode()) check(!t.textContent.trim()||t.parentElement.closest('[data-pid]'),'untracked_text');
  const allowed = new Set(sourceCheck(dir).images.map(x => x.file.startsWith('media/') ? x.file : 'media/' + x.file));
  for (const img of root.querySelectorAll('img')) {
    const src = img.getAttribute('src'); check(allowed.has(src) && img.dataset.sourceImage === src, 'untracked_image');
    local(dir, src);
  }
  check(root.querySelectorAll('img').length === expected.reduce((n,p)=>n+p.images.length,0), 'image_count_changed');
  return {dom, root};
}
function safeError(e) { console.error(e instanceof Stop ? e.message : 'word_tool_failed_' + e.name); }
module.exports = {Stop,check,noLinks,root,local,id,hash,read,fresh,sourceCheck,inspect,safeError};
