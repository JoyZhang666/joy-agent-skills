# 来源与第三方许可

本项目正文与脚本由 JoyZhang666 整理开发，以 MIT 开源。下述第三方权利分别保留；本项目的许可不替代外部工具的许可。

## humanizer：中文表达检查的参考

`references/humanizer-zh-rules.md` 参考 [blader/humanizer](https://github.com/blader/humanizer) 的识别与润色思路，按中文事实保护、用户风格和可选检查场景整理；未打包完整上游 Skill。保守保留上游 MIT 许可全文如下（2026-10-08 从上游 LICENSE 核对）：

```text
MIT License

Copyright (c) 2025 Siqi Chen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 可选外部工具

- [文颜 CLI](https://github.com/caol64/wenyan-cli)：排版与公众号草稿接口，Apache-2.0；本包不包含其代码或主题。接口文档核对时上游 package.json 为 2.0.12；不代表本包已完成该版本真实微信联调。
- [得到大脑](https://www.biji.com/)：可选用户素材来源；不包含其客户端、凭据或用户笔记。命令以官方 CLI 当前帮助为准。
- [Codex Skills](https://developers.openai.com/codex/skills/) / [OpenClaw Skills](https://docs.openclaw.ai/tools/skills)：安装位置参考，宿主配置不同须现场确认。

新增图片、字体、CSS、引用和用户素材时，应各自核查来源及可公开范围；本包不授予这些材料的再分发权。

