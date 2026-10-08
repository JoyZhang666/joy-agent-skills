# 依赖地图

基础写作只需能读 Skill 的 AI。安装前确认用户要用的功能；开发者电脑上存在不等于已随包交付。

| 分类 | 内容 | 如何取得 |
|---|---|---|
| 随包 | SKILL、README、references、prompts、workflows | 说明和可读流程；JSON 不是运行引擎 |
| 随包 | scripts/、tools/*.py、根 requirements.txt | 原有检查与普通单图草稿守卫 |
| 随包 | tools/word-mode/prepare.py、common.cjs、render.mjs、capture.cjs | DOCX 建档、检查、渲染及截图 |
| 随包 | tools/word-mode/mobile-copy.py、pdf-pages.py、requirements-pdf.txt | 110 mm 手机版 DOCX 副本与 PDF 页图后备 |
| 随包 | Word 工具的 package.json、package-lock.json | 固定版本；选用后按锁文件 npm ci，锁文件不是依赖代码 |
| 随包但不上传 | tools/word-mode/publish-guarded.mjs | 旧入口提示并退出，Word 多图自动上传未提供 |
| 随包 | templates/theme-library-template.json | 空白台账，复制到私人工作目录；不是 CSS，不含已验收主题 |
| 随包 | tests/、tools/word-mode/test-local.cjs | 虚构输入维护测试 |
| 按需安装 | Python 3.10+ | 用 Python 脚本时才需要 |
| 按需安装 | Node 22.12+、@wenyan-md/core 3.0.12、jsdom 27.4.0、playwright-core 1.62.1 | DOCX 渲染，按锁文件安装；xmldom 覆盖固定为 0.9.12 |
| 用户提供 | 已安装的可信 Chrome/Edge | CHROME_PATH 指向可执行文件，不自动下载或使用登录配置 |
| 按需安装 | pypdfium2 5.13.0、Pillow 12.3.0 | 仅 PDF 页图路线 |
| 仅测试可选 | pypdf | 加密测试夹具，没有则对应测试跳过 |
| 用户提供 | 原编辑器、字体、确认的 PDF | 不随包分发；不同编辑器导出可能重排，需要核对 |
| 可选服务 | 知识库、图片工具、公众号账号 | 分别授权；人工后台交稿无需 API 密钥 |
| 运行时生成 | source.docx、source.html、source-check.json、source-paragraphs.json、media/、previews/ | DOCX 工具在用户文章目录生成 |
| 运行时生成 | source.docx、mobile.docx、mobile-layout.json | 手机版副本工具生成；仅 Python 标准库，不启动 Office |
| 运行时生成 | source.pdf、pages/、previews/、article.html、preview.html、mobile-check.json、manifest.json | PDF 工具生成；complete 仅指生成，自动检查和手机目检分别核对 |
| 用户文章记录 | article.md、workflow-state.json、封面、收据、主题台账 | 私人工作目录，不上传开源仓库 |
| 非必需历史资料 | 作者上一篇文章、旧目录、私人知识体系 | 不依赖、不交付，不要求新用户找作者机器 |

命令见 [Word 工具](../tools/word-mode/README.md)。不打包 node_modules、pip 缓存、原始 ZIP、内部审计或私人来源记录。
