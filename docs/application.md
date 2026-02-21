# Application Module

Custom application/form system where admins create questionnaires, users submit answers via DM, and reviewers approve or deny submissions with interactive buttons.

## Concepts

**Forms** are named questionnaires owned by a guild. Each has ordered questions, a review channel, approval/denial thresholds, and optional custom messages. A form is "ready" once a review channel is assigned.

**Templates** are reusable question sets. Three built-in templates are seeded at startup (Guild Membership, Staff/Moderator, Event Sign-Up). Guilds can save their own forms as custom templates.

**Submissions** are created when a user completes an `/apply` conversation. The bot posts a review embed in the form's review channel with Approve, Deny, and Message buttons.

**Manager role** is an optional guild-wide role that grants non-admins permission to manage forms and review submissions.

## Flows

### Form Creation

1. Admin runs `/application create <name>`
2. Bot starts a DM conversation collecting questions one by one
3. Admin reacts with a cross mark to finish
4. Form is saved to the database

### User Submission

1. User runs `/apply <form_name>` (autocomplete shows only ready forms)
2. Bot walks the user through each question via DM
3. After answering all questions, the user sees a review summary
4. User confirms (check mark) or cancels (cross mark)
5. On confirm, the bot posts a review embed in the form's review channel

### Review

1. Reviewers click **Approve** or **Deny** on the review embed
2. Deny opens a modal for an optional reason; the reason is stored and shown in the review embed
3. When the required threshold is reached, the submission status changes; Approve and Deny are disabled
4. The **Message** button remains active so reviewers can notify the applicant at any time
5. After a decision the Message field is pre-filled with the configured approval or denial message (if set); successfully sending that post-decision message disables the button to prevent duplicate notifications

## Commands

### Admin Commands (`/application ...`)

#### `/application create <name>`

Create a new application form via DM conversation.

| Parameter | Type  | Description           |
| --------- | ----- | --------------------- |
| `name`    | `str` | Name for the new form |

#### `/application delete <name>`

Delete a form and all its submissions.

| Parameter | Type  | Description                                 |
| --------- | ----- | ------------------------------------------- |
| `name`    | `str` | Form name (autocomplete from guild's forms) |

#### `/application list`

List all forms for this server with question count and readiness status.

#### `/application edit <name>`

Edit a form's questions via DM conversation (add, remove, reorder).

| Parameter | Type  | Description                                 |
| --------- | ----- | ------------------------------------------- |
| `name`    | `str` | Form name (autocomplete from guild's forms) |

#### `/application channel <name> <channel>`

Set the review channel where submission embeds are posted.

| Parameter | Type          | Description                                 |
| --------- | ------------- | ------------------------------------------- |
| `name`    | `str`         | Form name (autocomplete from guild's forms) |
| `channel` | `TextChannel` | Channel to send review embeds to            |

#### `/application settings <name> [approvals] [denials] [approval_message] [denial_message]`

Configure form thresholds and custom messages.

| Parameter          | Type       | Description                              |
| ------------------ | ---------- | ---------------------------------------- |
| `name`             | `str`      | Form name (autocomplete)                 |
| `approvals`        | `int` >= 1 | Required approval votes (optional)       |
| `denials`          | `int` >= 1 | Required denial votes (optional)         |
| `approval_message` | `str`      | Custom DM message on approval (optional) |
| `denial_message`   | `str`      | Custom DM message on denial (optional)   |

#### `/application export <name>`

Export a form as JSON, sent as a file attachment via DM.

| Parameter | Type  | Description                                 |
| --------- | ----- | ------------------------------------------- |
| `name`    | `str` | Form name (autocomplete from guild's forms) |

#### `/application import`

Import a form from a JSON file. The bot DMs the user and waits 120 seconds for a file upload.

### Template Commands (`/application template ...`)

#### `/application template list`

Show all available templates (built-in + guild custom).

#### `/application template use <template> <name>`

Create a new form from a template.

| Parameter  | Type  | Description                  |
| ---------- | ----- | ---------------------------- |
| `template` | `str` | Template name (autocomplete) |
| `name`     | `str` | Name for the new form        |

#### `/application template save <form> <template_name>`

Save an existing form as a guild template.

| Parameter       | Type  | Description                     |
| --------------- | ----- | ------------------------------- |
| `form`          | `str` | Source form name (autocomplete) |
| `template_name` | `str` | Name for the new template       |

#### `/application template delete <template_name>`

Delete a guild custom template. Built-in templates cannot be deleted.

| Parameter       | Type  | Description                                        |
| --------------- | ----- | -------------------------------------------------- |
| `template_name` | `str` | Template name (autocomplete, guild templates only) |

### Manager Role Commands (`/application managerole ...`)

Requires `administrator` permission.

#### `/application managerole set <role>`

Set the guild's application manager role.

| Parameter | Type   | Description                                |
| --------- | ------ | ------------------------------------------ |
| `role`    | `Role` | Role that can manage forms and review apps |

#### `/application managerole remove`

Remove the manager role configuration.

### User Command

#### `/apply <form>`

Submit an application via DM. This is a top-level command (not under `/application`). Autocomplete only shows forms that have a review channel configured.

| Parameter | Type  | Description                     |
| --------- | ----- | ------------------------------- |
| `form`    | `str` | Form to apply to (autocomplete) |

## Import/Export JSON Format

```json
{
  "name": "Form Name",
  "required_approvals": 1,
  "required_denials": 1,
  "approval_message": "Welcome!",
  "denial_message": null,
  "questions": [
    { "text": "Question text here", "order": 1 },
    { "text": "Another question", "order": 2 }
  ]
}
```

Guild/channel IDs are intentionally excluded so forms are portable across servers.

## Permission Model

- **Admin commands** require `administrator` permission OR the guild's manager role
- **Manager role commands** (`set`/`remove`) require `administrator` only
- **Review buttons** (approve/deny/message) require `administrator` or the manager role
- **`/apply`** is available to all guild members
- **Bot permissions** needed: `send_messages`, `embed_links`

## Database Models

### `ApplicationGuildConfig`

| Column        | Type            | Purpose                  |
| ------------- | --------------- | ------------------------ |
| GuildId       | BigInteger (PK) | Discord guild ID         |
| ManagerRoleId | BigInteger      | Optional manager role ID |

### `ApplicationForm`

| Column            | Type         | Purpose                             |
| ----------------- | ------------ | ----------------------------------- |
| Id                | Integer (PK) | Auto-increment                      |
| GuildId           | BigInteger   | Discord guild ID                    |
| Name              | Unicode(100) | Form name                           |
| ReviewChannelId   | BigInteger   | Channel for review embeds           |
| RequiredApprovals | Integer      | Votes needed to approve (default 1) |
| RequiredDenials   | Integer      | Votes needed to deny (default 1)    |
| ApprovalMessage   | UnicodeText  | Custom DM on approval               |
| DenialMessage     | UnicodeText  | Custom DM on denial                 |

**Indexes:** `ApplicationForm_GuildId`, `ApplicationForm_Name_GuildId` (unique)

### `ApplicationQuestion`

| Column       | Type         | Purpose           |
| ------------ | ------------ | ----------------- |
| Id           | Integer (PK) | Auto-increment    |
| FormId       | Integer (FK) | Parent form       |
| QuestionText | UnicodeText  | The question text |
| SortOrder    | Integer      | Display order     |

### `ApplicationSubmission`

| Column             | Type         | Purpose                                                   |
| ------------------ | ------------ | --------------------------------------------------------- |
| Id                 | Integer (PK) | Auto-increment                                            |
| FormId             | Integer (FK) | Parent form                                               |
| GuildId            | BigInteger   | Discord guild ID                                          |
| UserId             | BigInteger   | Applicant's Discord ID                                    |
| UserName           | Unicode(50)  | Applicant's username                                      |
| Status             | String(10)   | `pending`, `approved`, or `denied`                        |
| SubmittedAt        | DateTime     | Submission timestamp (UTC)                                |
| ReviewMessageId    | BigInteger   | Message ID of the review embed                            |
| DecisionReason     | UnicodeText  | Reason provided on denial (shown in the review embed)     |
| ApplicantNotified  | Boolean      | True once a reviewer successfully DMs the applicant post-decision; disables the Message button |

**Indexes:** `ApplicationSubmission_GuildId`, `ApplicationSubmission_FormId`

### `ApplicationAnswer`

| Column       | Type         | Purpose           |
| ------------ | ------------ | ----------------- |
| Id           | Integer (PK) | Auto-increment    |
| SubmissionId | Integer (FK) | Parent submission |
| QuestionId   | Integer (FK) | Answered question |
| AnswerText   | UnicodeText  | User's answer     |

### `ApplicationVote`

| Column       | Type         | Purpose               |
| ------------ | ------------ | --------------------- |
| Id           | Integer (PK) | Auto-increment        |
| SubmissionId | Integer (FK) | Parent submission     |
| UserId       | BigInteger   | Reviewer's Discord ID |
| Vote         | String(10)   | `approve` or `deny`   |

**Indexes:** `ApplicationVote_SubmissionId`, `ApplicationVote_SubmissionId_UserId` (unique — one vote per reviewer)

### `ApplicationTemplate`

| Column    | Type         | Purpose                      |
| --------- | ------------ | ---------------------------- |
| Id        | Integer (PK) | Auto-increment               |
| GuildId   | BigInteger   | Guild ID (null for built-in) |
| Name      | Unicode(100) | Template name                |
| IsBuiltIn | Boolean      | True for seeded templates    |

### `ApplicationTemplateQuestion`

| Column       | Type         | Purpose           |
| ------------ | ------------ | ----------------- |
| Id           | Integer (PK) | Auto-increment    |
| TemplateId   | Integer (FK) | Parent template   |
| QuestionText | UnicodeText  | The question text |
| SortOrder    | Integer      | Display order     |

## Conversation Flows

Three `Conversation` subclasses in `modules/conversations/application.py`:

- **ApplicationCreateConversation** — `INIT` -> `COLLECT` (loop) -> `DONE`. Collects questions via text, finishes on cross-mark reaction.
- **ApplicationEditConversation** — `INIT` shows the current questions with reaction menu (add/remove/reorder/done). Each action transitions through its own confirm state, then returns to `INIT`.
- **ApplicationSubmitConversation** — `INIT` -> `question_0` ... `question_N` -> `CONFIRM` -> `SUBMIT`/`CANCELLED`. Tracks `last_activity` for timeout detection.

## Persistent Review View

`ApplicationReviewView` in `modules/views/application.py` uses `timeout=None` and fixed `custom_id` strings so buttons survive bot restarts. Registered in `bot.py:setup_hook()` with `self.add_view()`.

## Built-In Templates

Seeded on cog load (idempotent):

- **Guild Membership** — 6 questions about the applicant's background and availability
- **Staff / Moderator** — 6 questions about moderation experience and availability
- **Event Sign-Up** — 5 questions about the applicant's character and scheduling
