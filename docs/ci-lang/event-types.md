# Event Types

Here is a short run-down of the available triggers and their field types:

## All Events

Every event has the following fields:

**`sha`**: The SHA of the commit that this workflow is running for.

**`provider`**: The Git provider we are running for (either `github` or `gitlab`).

**`repository_url`**: The URL of the repository that the workflow is running for.

## `git.push`

**`author`**: Username of the commit author.

**`message`**: The commit message of the most recent commit that was pushed.

**`committed_on`**: An ISO 8601 datetime of when the commit was authored.

**`ref`**: The full git ref pointing to the commit (ie, `/refs/heads/main`).

**`branch`**: The short-name of the branch which was pushed to (ie, `main`).

## `issue.open`

**`id`**: Platform-dependant ID for the issue.

**`title`**: Title of the issue.

**`submitted_by`**: Username of the user who opened the issue.

**`is_locked`**: Whether or not the issue is locked.

**`opened_at`**: ISO 8601 datetime of when the issue was opened.

**`body`**: Body of the issue.

## `issue.close`

Everything in `issue.open`, and:

**`opened_at`**: ISO 8601 datetime of when the issue was closed.
