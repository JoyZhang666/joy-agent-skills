# 证据与 SQ 数据格式

SQ 是本次研究的一个子问题，由任务计划决定名称和数量。核心研究可直接使用 Markdown 证据表；只有需要机械汇总时才准备以下 JSON。

每个原始文件为 UTF-8 JSON 对象，含 `sq_id`、`topic`、`summary`、`data_points`、`sources`。文件名以 `sq` 开头并以 `.json` 结尾。每个 SQ 的数据点 ID 唯一；来源可为 URL 字符串或含 `url`、`origin_id` 的对象。

```json
{
  "sq_id": "SQ-EVIDENCE",
  "topic": "供应商是否有可验证的直接客户",
  "summary": {"finding": "仅有公司自述", "gap": "缺直接量产文件"},
  "data_points": [{
    "id": "D1", "entity": "示例供应商甲", "as_of": "2026-10-01",
    "field": "客户关系", "value": "公司称为品牌乙提供材料",
    "period": "2026", "unit": null, "scope": "该法人主体",
    "relationship": "self-reported", "evidence_status": "self_reported",
    "source_url": "https://example.com/synthetic/company-profile",
    "source_locator": "虚构材料 S1 第2段",
    "origin_id": "S1"
  }],
  "sources": [{"url": "https://example.com/synthetic/company-profile", "origin_id": "S1"}]
}
```

这是完全虚构的格式示例，链接不是实际证据。

## 保存与核验

- 关键事实记录实体、资料日期/适用期间、指标、数值/文本、单位、范围、来源 URL 或本地材料位置。缺失可为 null，不填零。
- `evidence_status` 可写 unreviewed、self_reported、estimate、conflict、confirmed、unknown；它是输入声明，汇总程序不会证明它正确。确认要有实际读过的原文与定位，推断还应保留依据和计算方法。
- `origin_id` 标识原始出处。多篇转载同一通稿用同一 origin；程序只统计 URL 和输入声明，不能自动判断独立性。原文、访问日期、转载关系和来源冲突仍须研究者核对。
- 将结论与支持/反对数据点关联。一个合理建议可以在证据不足时是“先索取材料”，不必强行下合作结论。

## 兼容与脚本输出

`aggregate.py` 兼容 `research_subject` → `topic`，`fact/category` → `field`，`confidence` → `reported_confidence`。字典/列表型 summary 转为 JSON 文本供展示，原值仍保存在 raw_sq_data。旧字符串型数据点保留原文并标为待整理，不猜测证据。

输出 `aggregation.json`、`data.csv`、`status.md`。CSV 为 UTF-8 BOM，文本若可能被电子表格解释成公式，会加前置单引号；原始 JSON 不因此改变。汇总不做单位换算、来源真实性判断或信用评分。

必须用 `--expected-sq` 传实际计划 ID。每个文件的 sq_id 以显式值为准；旧格式仅在数据点中可唯一识别 SQ 前缀时推导，否则采用文件名大写。重复 SQ/DP ID 和结构错误会失败。空数据点文件不能充当完成项。缺少计划项时保存部分结果并返回 2；完整的技术汇总返回 0，**两者都不表示事实验证通过**。既有输出目录不会被覆盖。
