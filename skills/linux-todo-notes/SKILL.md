---
name: linux-todo-notes
description: Add, find, edit, or complete tasks in the user's Linux desktop notes when asked to manage those notes or turn submitted text or a screenshot into a desktop checklist.
---

# Linux desktop notes

Use `linux-todo-notes` to access the shared local task database from any project. Run `linux-todo-notes --help` for commands. Create a note with `linux-todo-notes add 'title' --body 'description' --source 'original text'`, then add checklist entries with `linux-todo-notes item-add NOTE_ID 'task'`. Use `list` to find IDs and `item-update ITEM_ID --done 1` to complete a checklist entry. The desktop app refreshes from the same database.

Only record material the user submitted or asked to save. For screenshots, retain a reference to the original image in source when available, and record the interpreted text; do not invent unclear details. Reminder, due time and calendar integration are not yet implemented: do not claim a calendar event exists or a calendar was checked merely because a note was saved. Ask for confirmation before writing an actual calendar event, as required by the project. Never put personal task contents in the source repository.
