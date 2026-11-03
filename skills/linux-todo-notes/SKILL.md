---
name: linux-todo-notes
description: Add, find, edit, or complete tasks in the user's Linux desktop notes when asked to manage those notes or turn submitted text or a screenshot into a desktop checklist.
---

# Linux desktop notes

Use `linux-todo-notes` to access the shared local task database from any project. Run `linux-todo-notes --help` for commands. Create a note with `linux-todo-notes add 'title' --body 'description' --source 'original text'`, then add checklist entries with `linux-todo-notes item-add NOTE_ID 'task'`. Use `list` to find IDs and `item-update ITEM_ID --done 1` to complete a checklist entry. The desktop app refreshes from the same database.

Only record material the user submitted or asked to save. For screenshots, retain a reference to the original image in source when available, and record the interpreted text; do not invent unclear details. Store reminder, execution start/end and deadline separately with `update --reminder-at ... --start-at ... --end-at ... --due-at ...` using ISO 8601 timestamps with timezone. A note save does not create an event. When the user requests scheduling, read the latest calendar and propose suitable times; write only after confirmation. Before changing an existing arrangement, inspect `list` for its calendar and event IDs and update that event rather than creating a duplicate. After an actual successful calendar write, record its IDs with `calendar-write NOTE_ID success --calendar-id ID --event-id ID`; on failure use `calendar-write NOTE_ID failed`. Only after successfully fetching and comparing the relevant calendar record `calendar-check NOTE_ID success`; use `failed` on failure. These commands record results; they do not access the calendar themselves. Never put personal task contents in the source repository.
