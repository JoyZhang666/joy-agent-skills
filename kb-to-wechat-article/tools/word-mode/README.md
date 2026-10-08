# Word / PDF 本地转换工具

给使用者：将文稿交给 AI，说“保持原文，先检查能否转换”，它应按 [Word 模式](../../references/word-layout-mode.md) 带你选择。下面命令供 AI 或熟悉终端的人执行，不要求小白猜路径。

所有文章放在 Skill 之外的私人工作文件夹。AI 应把示例换成用户选定的实际位置并展示；路径加引号。输出目录必须全新，失败保留现场，换新目录修复重试，不覆盖文章。

## 普通 DOCX → 可编辑 HTML 与预览

解析需要 Python 3.10+，仅标准库。渲染另需 Node.js 22.12+、本目录锁定依赖，以及已安装的可信 Chrome/Edge。

1. 用户选择此功能后，在本目录运行 `npm ci --ignore-scripts --no-audit --no-fund`。需要网络下载，只安装到本目录，不全局安装、不执行安装钩子、不下载浏览器。不需要全局文颜 CLI、`wenyan login`、WENYAN_MD_ROOT 或 CHROMIUM_REQUIRE。
2. 回 Skill 根目录。以下仅为示例：父目录 `private-work` 应先建立，文章目录尚不存在；AI 需换成用户实际路径。

```powershell
python tools/word-mode/prepare.py --input "input/article.docx" --article-dir "private-work/article-001"
node tools/word-mode/render.mjs "private-work/article-001" original
```

`original` 不套主题，只保留解析器支持的格式，不是所有 Word 字体/页式。用户想改风格时再选择已安装的文颜主题，如 `default`；一次最多三款，逗号分隔。未知主题停止。

3. AI 定位已安装浏览器，将其完整可执行文件路径设置到当前进程的 CHROME_PATH，不写系统环境、不复用个人登录资料：

```powershell
$env:CHROME_PATH = "此处替换为已确认的浏览器可执行文件完整路径"
node tools/word-mode/capture.cjs "private-work/article-001" original
```

生成 previews 下的正文 HTML、嵌入图片的 `original-preview.html`、`original-390.png`、render/capture JSON。断图、横向溢出或过高会失败。Agent 实际看图，再请用户确认；程序通过不是视觉验收。

截图失败先检查浏览器路径和主机权限，不通过关闭浏览器沙箱解决。宿主不允许启动时，说明截图未完成，打开本地预览人工检查，不伪造验收。临时浏览器关闭页面脚本、阻断页面请求，这不等于完整 OS 隔离。

## 复杂 Word → PDF 整页图片

先按 [保真补救指南](../../references/word-fidelity.md) 确认最终视图、导出并核对 PDF；用户选择页图后才转换。不需要 Node 或文颜。

由 AI 在用户确认的独立 Python 环境中安装固定依赖，使用该环境的 Python：

```powershell
python -m pip install -r tools/word-mode/requirements-pdf.txt
python tools/word-mode/pdf-pages.py --input "input/article.pdf" --article-dir "private-work/article-pages-001" --confirm-local-export
```

确认参数代表用户已确认来源与页面，不是程序证明 PDF 来自 Word。输出 source.pdf、`pages/page-0001.png` 等整页图、article.html、manifest.json。只有 `status=complete` 才生成完成；失败留下 incomplete，不能上传。

默认 144 DPI（72–200），最多 30 MiB、30 页、单边 8192 像素、单页 1600 万像素、合计 1 亿像素。拒绝加密/交互表单。超限回编辑器分章导出并保留页码，不丢页或静默降质。页图不是无损 Word；手机字太小就调整 Word 手机版字号/页面宽度再导出。

## 入草稿箱与边界

两条路线先交本地文件。Word 多图自动上传尚未提供，按 [人工入草稿箱](../../references/word-fidelity.md#把页面图片放进公众号草稿箱) 在后台按序插图、手机预览、保存并确认。普通 DOCX HTML 可作文字排版参考，图片须逐张上传，本地 src 不能直接在微信使用。

旧 `publish-guarded.mjs` 明确退出，不读账号、不联网；SKIP_COVER=1 不会启用上传。原有 scripts/push_guarded.py 只适用普通单图稿，不能拿来发 Word 多图。真实微信未测试，不能把本地渲染称为全流程验收。

## 维护者验证

本目录：`node --test test-local.cjs`。浏览器两例仅在设置 CHROME_PATH 时运行，否则跳过。Skill 根目录：`python -B -m unittest discover -s tests -v`。PDF 加密夹具额外需要 pypdf（仅测试）；缺少时该例跳过。

见 [依赖地图](../../references/dependency-map.md) 与 [许可](../../THIRD-PARTY-NOTICES.md)。
