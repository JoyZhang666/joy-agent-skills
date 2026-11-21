# Multi-agent CRM • preview 0.1

This skill lets cooperating agents query and update organizations, contacts, products, sales stages, opportunities, actions and evidence. An eighth table stores audit entries. [Data model](DATA-MODEL.md) · [Machine-readable schema](schema.json) · [Agent handbook](SKILL.md)

## Start a synthetic workspace

Use Python 3.10 or later on one trusted coordinator host. Create a private working directory outside this package. On Windows choose a directory accessible only to the intended operating-system user. Keep the coordinator database, key files, mapping, request files and backups there. Use the full path to crm.py if your working directory differs from the skill directory.

```text
python crm.py --db workspace.sqlite init
python crm.py --db workspace.sqlite register operator-a --key-file operator-a.key
python crm.py --db workspace.sqlite register operator-b --key-file operator-b.key
```

Give each process its assigned actor and key file through CRM_ACTOR and CRM_KEY_FILE. Set CRM_SESSION to its actual session identifier. In PowerShell use `$env:CRM_ACTOR='operator-a'` and set the other two variables the same way. On POSIX use `export`. Only the operator runs init and register. Accounts with filesystem access to the coordinator can bypass the CLI, so keep the database and credentials on the trusted host. Each installation uses one coordinator for its Base. Remote agents need an existing authenticated way to invoke that host. Network transport and automatic background delivery are outside this preview.

```text
python crm.py --db workspace.sqlite handbook
python crm.py --db workspace.sqlite query organizations
python crm.py --db workspace.sqlite sync example.json --dry-run
```

In a fresh synthetic database use the following example.json.

```json
{"request_key":"example-create-1","kind":"organizations","id":"org-example","expected_version":0,"expected_hash":null,"fields":{"name":"Example Workshop"},"source_ref":"synthetic-example-1"}
```

For an authorized test, add `--authorization` followed by the approval reference in place of `--dry-run`. Read the row and its history by kind and ID. For subsequent updates, include only changed fields and the current record version and hash. Use another request key for each new intent. Independent processes share the same sequence of accepted requests. If the head is pending, other requests wait. Resume with the owning identity and original key; ambiguous remote effects require reconciliation and may need operator review.

## Feishu

Use a fresh, dedicated test Base, a signed-in user and the external vendor CLI. Initialize its tables and save the mapping outside the package, then initialize a separate coordinator database using `init --feishu-config MAPPING`. See the [Feishu setup guide](FEISHU.md) for the installed CLI requirements. The application actor in each audit and the vendor login used for API access are separate identities. Both data backends use the same business schema.

Keep backups of the database and its matched remote mapping; losing the coordinator loses request ownership, queue state and local audit indexing. This preview serializes cooperating writers. Direct edits or a second coordinator connected to the same Base can race with the application.

## Hosting choices

| Agents | Where commands run | Availability |
|---|---|---|
| Several agents on one computer | Each uses its own registered identity and session on the same local coordinator. SQLite-only mode works offline. | Active while the computer is running. No rented server is needed. |
| Agents on multiple computers | Choose one workstation as the coordinator. Remote users invoke the CLI on it through a separately managed authenticated connection. Keep the SQLite file on that machine's local disk. | The workstation and its connection must be available. Pending intents already enqueued survive a restart. A disconnected client must retain its intent and revalidate before submission. |
| An always-on hosted machine | Install the same CLI on a trusted server and invoke it there. | Optional for longer availability. The server is still a single coordinator. |

For Feishu storage, the coordinator also needs network access to Feishu. Separate coordinators, independent local locks, a synced SQLite folder or direct user edits do not provide a shared FIFO guarantee. Provisioning remote access, failover and synchronization between disconnected writers are outside this release. Never grant untrusted agents unrestricted shell or filesystem access to the coordinator host.

License: MIT. See LICENSE.
