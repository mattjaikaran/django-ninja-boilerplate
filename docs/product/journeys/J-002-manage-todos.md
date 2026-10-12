---
id: J-002
title: Manage todos
actor: Signed-in user
status: building
steps:
  - id: S1
    title: Create a todo
    story: As a signed-in user, I want to add a todo, so that I remember the task.
    features: [F-010]
    acceptance:
      - The new todo appears at the top of my list.
      - An empty title shows a validation error.
  - id: S2
    title: Find a todo
    story: As a signed-in user, I want to search and filter my todos, so that I find a task fast.
    features: [F-011]
    acceptance:
      - A search term shows only matching todos.
      - The completed and pending filters show only todos in that state.
  - id: S3
    title: Edit and complete a todo
    story: As a signed-in user, I want to edit a todo and mark it complete, so that my list stays current.
    features: [F-010]
    acceptance:
      - A changed title persists after a page reload.
      - A completed todo moves to the completed filter.
  - id: S4
    title: Delete a todo
    story: As a signed-in user, I want to delete a todo, so that my list holds only real tasks.
    features: [F-010]
    acceptance:
      - The deleted todo leaves the list and does not come back on reload.
---

## Goal

A signed-in user creates, finds, edits, completes, and deletes todos.

## Context

- The list calls `GET /api/todos/`. Search calls `GET /api/todos/search`
  with `q`, `priority`, and `completed`. The filters call
  `GET /api/todos/completed` and `GET /api/todos/pending`.
- Create calls `POST /api/todos/`. Edit and complete call
  `PUT /api/todos/{todo_id}`. Delete calls `DELETE /api/todos/{todo_id}`.
- Todos are scoped to the signed-in user. Another user's todo returns 404.

## Notes

Start from J-001 S2 (signed in) with a fresh account so the list is empty.
