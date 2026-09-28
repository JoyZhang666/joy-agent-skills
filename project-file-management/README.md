![项目文件管理：本地索引 · 便于交接](../assets/brand/project-file-management.svg)

# 项目文件管理 · Project File Management

**日常管理 · 本地索引 · 便于交接**

| 你提供什么 | 得到什么 |
|---|---|
| 你授权整理的工作区或项目目录，以及整理目标。 | 工作区索引、项目登记与交接记录；本地辅助工具提供检查结果。 |

**先准备：**辅助工具需 Python 3.10+，仅标准库；不要求外部业务 API。移动、删除等操作另按明确授权处理。

[第一次使用 Skill](../docs/start-here.md) · [作业指导书](references/项目文件管理作业指导书.md) · [返回全部作品](../README.md)

<details>
<summary>看一个虚构示例</summary>

> 虚构项目“阅读小助手”｜入口：README.md｜状态：草稿｜下一步：核对示例输入。

仅示意输入或输出的形式，不是真实用户资料或运行结果。

</details>

---

版本：v1.1.2 · 许可证：[MIT](LICENSE)

把散落的项目文件组织成可定位、可交接、可验证的工作区。适合新建项目、接入已有项目，以及让人和 Agent 接续工作。

本包包含一份作业指导书、空白模板、虚构示例工作区、Skill 入口和一个 Python 辅助工具。所有示例均为教学内容，身份与环境字段由使用者自行填写。

## 从哪里开始

- 了解完整方法：[项目文件管理作业指导书](references/项目文件管理作业指导书.md)。
- 交给 Agent 使用：[SKILL.md](SKILL.md)。是否自动发现 Skill 取决于所用平台；也可以明确要求 Agent 先阅读该文件。
- 复用文档结构：[工作区模板](assets/templates/workspace/)、[项目模板](assets/templates/project/)、[可选模板](assets/templates/optional/)。
- 看文件如何配合：[虚构示例工作区](assets/example-workspace/README.md)。

先审阅目标工作区已有规则，再复制需要的模板；填写占位符并校正链接。不要用模板直接覆盖既有 AGENTS.md 或已填写的项目资料。

## 工具使用

需要 Python 3.10 或以上，只使用标准库，无需安装第三方依赖。阅读 Markdown 和模板不需要 Python。

在本目录中，可只读检查包内示例：

```sh
python scripts/workspace_admin.py audit --root assets/example-workspace
```

对实际工作区操作时，把 `<workspace-root>` 替换为自己指定的目录：

```sh
python scripts/workspace_admin.py audit --root "<workspace-root>"
python scripts/workspace_admin.py index --root "<workspace-root>"
```

- `audit`：只读核对项目登记、入口文件、路径和索引一致性。
- `index`：先验证登记，再生成 `PROJECTS.md`；拒绝覆盖不带本工具生成标记的手工索引。
- 工具不会迁移、重命名或删除文件，也不进行联网、上传或遥测。

练习写入操作前，先把整个示例工作区复制到独立目录。检查通过只代表工具覆盖的文件结构条件满足，不代表真实业务已经验收。

## 隐私与分享

本目录只包含可复用说明、脚本、空白模板和明确标注的虚构案例。填写后的身份字段、真实项目登记、原始输入、运行日志、账号凭据及机器路径需要另行保管，分享前重新审查。

工具在出错时可能输出使用者的文件路径；不要未经检查就公开运行日志。模板中的留白和演示日期属于教学内容，不代表作者的私人资料。

## 版本与许可

本次公开保留 v1.1.2 原包内 28 个文件的内容，新增本说明及 MIT 许可证；源目录外的内部验收记录和历史审查材料不随仓库发布。模板和虚构案例中的演示版本号保留原意，不代表本包版本。

本作品采用 [MIT 许可证](LICENSE)，公开署名为 JoyZhang666。许可适用于本目录的说明、模板、示例及脚本。
