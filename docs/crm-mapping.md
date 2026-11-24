# CRM mapping status

Organization mapping is evidenced in discovery's CRM snapshot/import schema and existing importer. Assessment mapping is evidenced by orchestrator packages and CRM-sourced templates; automated writes are limited to the four AI fields documented by that project.

| CRM entity | Current status | Required next discovery |
|---|---|---|
| CRM Organization | Existing exact fields in `src/crm_import.py`; organization identity and links validated there. | Confirm inside Docker only if shared client changes. |
| CRM Assessment | Existing template/questions/link conventions read from live records by current workflow; local snapshots are not authority. | Capture actual server traceback/payload for known TypeError. |
| Contact | No verified mapping in workspace. | Fetch live DocType metadata; inspect relations, child tables and duplicate identity options. |
| Lead | No verified mapping in workspace. | Fetch live DocType metadata and configured statuses; determine actual Contact and Organization link semantics, notes/product fields/owner. |

Contact/Lead writes remain blocked until those live metadata checks complete. Proposed matching prioritizes exact CRM identity fields (verified email if present, otherwise carefully reviewed name plus organization/profile), checks organization relation, preserves human-owned populated values, and searches Leads before create. Ambiguous matches require review. Never infer a Lead-to-Contact field.
