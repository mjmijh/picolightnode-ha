---
name: git_workflow_merge_push
description: Wann und ob merge und push ohne Rückfrage erlaubt sind
type: feedback
---

Vor merge in main und push immer explizit auf Bestätigung warten.

**Why:** User möchte Fixes vor dem Merge testen können.

**How to apply:** Nach einem Commit auf einem Feature/Fix-Branch immer fragen "Soll ich jetzt mergen und pushen?" — nicht automatisch weitermachen.
