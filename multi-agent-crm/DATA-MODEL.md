# CRM data model

Schema version 1 defines seven business tables and a system audit table. Installers can inspect [schema.json](schema.json) to see every field, type, required flag and link target. No seed data is required. An installation supplies its own organizations, product catalog and stage vocabulary.

## Tables and relationships

| Table | One row represents | Required fields | Other fields |
|---|---|---|---|
| organizations | A distinct business organization | name | — |
| contacts | A person associated with one organization | name, organization | — |
| products | An item or service in the catalog | name | description |
| stages | A reusable stage in the sales process | name, position | — |
| opportunities | A potential deal with one organization at one stage | name, organization, stage | contacts, products, sources, estimated_amount, currency, target_date |
| actions | A task associated with one opportunity | name, opportunity | owner, due_date, status, sources |
| sources | An evidence reference | name, reference | locator |
| audit | An accepted change to a business record | request_key, actor, session, table_name, record_id, version_after, hash_after, authorization | version_before, hash_before, source_ref |

A required `ref` references exactly one existing row in its target table. Multiple contacts may share one organization. Multiple actions may belong to one opportunity. A `refs` field represents zero or more distinct IDs. Two opportunities can reference the same product or contact. One source can support several deals and actions.

## Record identity and field values

A business row has a table-scoped stable ID, record version, content hash and typed business fields. Keep the ID when a person or organization changes its displayed name. Use the current version and hash returned by a live query when preparing an update. Concurrent edits require a fresh read and review. Retries of the same authorized request reuse its original request key.

Text values are strings. Dates represent calendar dates in YYYY-MM-DD format. Stage position is an integer used for display order. Deal estimates are numeric values in the separately named currency. Supply a currency code with any estimate and keep different currencies separate in totals. Omit unknown optional values. Use source.reference to identify the original material and source.locator for a page, section or other precise location.

The audit table is maintained by the write service. Its record pointer consists of table_name and record_id. Version and hash fields identify the change. The actor, session, authorization reference and source reference document its origin. Authorization references are review identifiers and must contain no credentials.

## Synthetic example

Create an organization with ID `org-example` and name `Example Workshop`, then create a stage with ID `stage-review`, name `Review` and position `1`. The business fields for a corresponding opportunity can then be represented as:

```json
{
  "name": "Sample assembly review",
  "organization": "org-example",
  "stage": "stage-review"
}
```

This fragment illustrates the field payload. The skill and client guide describe the complete request envelope and authorization steps.
