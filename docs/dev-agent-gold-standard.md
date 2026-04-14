# IRIS Dev Agent Gold Standard

This is the delivery contract for every Dev agent before a task can be considered complete.

## Required Flow

1. Understand the request and identify the exact files that need to change.
2. Read and edit real workspace files with `workspace_file`.
3. Inspect `status` and `diff` with `workspace_file` before committing.
4. Validate objectively:
   - Backend/Python: `workspace_file` with `action=validate_py_compile`.
   - Frontend/TypeScript/CSS: `workspace_file` with `action=npm_build`.
5. Commit with `github_commit` using local mode:
   - `repo_path`: repository root.
   - `file_paths`: exact changed files for the subtask.
   - `commit_message`: clear and verifiable.
   - `push=false` unless remote push is known to work.
6. Return `DELIVERY_EVIDENCE` with real files, validation, commit message, real SHA and push status.

## Rejection Rules

A delivery is rejected when:

- It does not include `DELIVERY_EVIDENCE`.
- It lists files that were not actually changed.
- Validation is missing or does not include a `passed` result.
- The commit SHA does not exist in the local Git repository.
- The listed files are not present in the commit.
- The agent claims success without using the workspace and commit tools.

## Live Artifact Visibility

When editing files, agents must pass `task_id`, `agent_id`, `agent_role` and `team` to `workspace_file`.
This emits:

- `FILE_CHANGED`
- `DIFF_PREVIEW`
- `CODE_ARTIFACT_UPDATED`

These events allow Agent Ops to show what code is being built while the task is running.
