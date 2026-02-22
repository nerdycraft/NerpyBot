# Application Module

Custom application/form system where admins create questionnaires, users submit answers via DM, and reviewers approve or deny submissions with interactive buttons.

## Concepts

**Forms** are named questionnaires owned by a guild. Each has ordered questions, a review channel, approval/denial thresholds, and optional custom messages. A form is "ready" once a review channel is assigned.

**Apply button** is a persistent embed with an "Apply" button posted in a designated channel. Users click this button to start the DM application flow.

**Templates** are reusable question sets. Five built-in templates are seeded at startup (Guild Membership, Staff/Moderator, Partnership / Collaboration, Volunteer, Community Access). Guilds can save their own forms as custom templates.

**Submissions** are created when a user completes an application conversation (started via the Apply button). The bot posts a review embed in the form's review channel with Approve, Deny, and Message buttons.

**Manager role** is an optional guild-wide role that grants non-admins permission to manage forms and review submissions.

## Flows

### Form Creation

1. Admin runs `/application create <name> <review-channel> [channel] [description]`
2. Bot starts a DM conversation collecting questions one by one
3. Admin reacts with a cross mark to finish
4. Form is saved to the database
5. If `channel` was provided and the form is ready, an Apply button embed is posted in that channel

### User Submission

1. User clicks the Apply button in the designated channel
2. Bot walks the user through each question via DM
3. After answering all questions, the user sees a review summary
4. User confirms (check mark) or cancels (cross mark)
5. On confirm, the bot posts a review embed in the form's review channel

### Review

1. Reviewers click **Vote** on the review embed, then pick Approve or Deny from a dropdown
2. Both options open a modal for a required review note; the note is posted to a thread on the review embed
3. When the required threshold is reached, the submission status changes; Vote and Edit Vote are disabled
4. **Edit Vote** lets a reviewer change their existing vote before a decision is reached
5. The **Message** button remains active so reviewers can notify the applicant at any time
6. After a decision the Message field is pre-filled with the configured approval or denial message (if set); successfully sending that post-decision message disables the button to prevent duplicate notifications
7. **Override** (admin/manager only) lets a decided application be flipped APPROVED↔DENIED

## Commands

### Admin Commands (`/application ...`)

#### `/application create <name> <review-channel> [channel] [description] [description-message] [approvals] [denials] [approval-message] [denial-message]`

Create a new application form via DM conversation. The review channel is required at creation time.

| Parameter             | Type          | Description                                                     |
| --------------------- | ------------- | --------------------------------------------------------------- |
| `name`                | `str`         | Name for the new form                                           |
| `review-channel`      | `TextChannel` | Channel where submission reviews are posted                     |
| `channel`             | `TextChannel` | Channel where an Apply button message will be posted            |
| `description`         | `str`         | Custom text shown on the Apply button embed                     |
| `description-message` | `str`         | Message ID or link whose text becomes the description (deleted) |
| `approvals`           | `int` >= 1    | Number of approvals required (default: 1)                       |
| `denials`             | `int` >= 1    | Number of denials required (default: 1)                         |
| `approval_message`    | `str`         | Custom DM message sent to applicant on approval                 |
| `denial_message`      | `str`         | Custom DM message sent to applicant on denial                   |

#### `/application delete <name>`

Delete a form and all its submissions. If an Apply button message exists, it is also deleted.

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

#### `/application settings <name> [review-channel] [channel] [description] [description-message] [approvals] [denials] [approval-message] [denial-message]`

Configure form thresholds, channels, and custom messages.

| Parameter             | Type          | Description                                                     |
| --------------------- | ------------- | --------------------------------------------------------------- |
| `name`                | `str`         | Form name (autocomplete)                                        |
| `review-channel`      | `TextChannel` | New review channel                                              |
| `channel`             | `TextChannel` | Channel where the Apply button will be posted                   |
| `description`         | `str`         | Description shown on the Apply button embed                     |
| `description-message` | `str`         | Message ID or link whose text becomes the description (deleted) |
| `approvals`           | `int` >= 1    | Required approval votes                                         |
| `denials`             | `int` >= 1    | Required denial votes                                           |
| `approval_message`    | `str`         | Custom DM message on approval                                   |
| `denial_message`      | `str`         | Custom DM message on denial                                     |

When `channel` is changed, the old Apply button message is deleted and a new one is posted in the new channel. When only `description` is changed, the existing Apply button message is edited in-place.

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

#### `/application template use <template> <name> <review-channel> [channel] [description] [description-message]`

Create a new form from a template.

| Parameter             | Type          | Description                                                     |
| --------------------- | ------------- | --------------------------------------------------------------- |
| `template`            | `str`         | Template name (autocomplete)                                    |
| `name`                | `str`         | Name for the new form                                           |
| `review-channel`      | `TextChannel` | Channel where submission reviews are posted                     |
| `channel`             | `TextChannel` | Channel where an Apply button message will be posted            |
| `description`         | `str`         | Custom text shown on the Apply button embed                     |
| `description-message` | `str`         | Message ID or link whose text becomes the description (deleted) |

#### `/application template save <form> <template_name>`

Save an existing form as a guild template.

| Parameter       | Type  | Description                     |
| --------------- | ----- | ------------------------------- |
| `form`          | `str` | Source form name (autocomplete) |
| `template_name` | `str` | Name for the new template       |

#### `/application template create <name> [approval-message] [denial-message]`

Create a new guild template via DM conversation. The bot walks you through adding questions one by one.

| Parameter          | Type  | Description                                                   |
| ------------------ | ----- | ------------------------------------------------------------- |
| `name`             | `str` | Name for the new template                                     |
| `approval_message` | `str` | Default approval message for forms created from this template |
| `denial_message`   | `str` | Default denial message for forms created from this template   |

#### `/application template edit-messages <template_name> [approval-message] [denial-message]`

Update the default approval/denial messages on a custom template. Built-in templates cannot be edited.

| Parameter          | Type  | Description                                        |
| ------------------ | ----- | -------------------------------------------------- |
| `template_name`    | `str` | Template name (autocomplete, guild templates only) |
| `approval_message` | `str` | New default approval message                       |
| `denial_message`   | `str` | New default denial message                         |

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

### Reviewer Role Commands (`/application reviewerrole ...`)

Requires `administrator` permission.

#### `/application reviewerrole set <role>`

Set the guild's application reviewer role. Reviewers can vote on applications but cannot manage forms or override decisions.

| Parameter | Type   | Description                        |
| --------- | ------ | ---------------------------------- |
| `role`    | `Role` | Role that can vote on applications |

#### `/application reviewerrole remove`

Remove the reviewer role configuration.

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
- **Manager/Reviewer role commands** (`set`/`remove`) require `administrator` only
- **Review buttons** (Vote, Edit Vote, Message) require `administrator`, the manager role, or the reviewer role
- **Override button** requires `administrator` or the manager role (reviewers cannot override)
- **Apply button** is available to all guild members
- **Bot permissions** needed: `send_messages`, `embed_links`

## Database Models

### `ApplicationGuildConfig`

| Column         | Type            | Purpose                   |
| -------------- | --------------- | ------------------------- |
| GuildId        | BigInteger (PK) | Discord guild ID          |
| ManagerRoleId  | BigInteger      | Optional manager role ID  |
| ReviewerRoleId | BigInteger      | Optional reviewer role ID |

### `ApplicationForm`

| Column            | Type         | Purpose                                        |
| ----------------- | ------------ | ---------------------------------------------- |
| Id                | Integer (PK) | Auto-increment                                 |
| GuildId           | BigInteger   | Discord guild ID                               |
| Name              | Unicode(100) | Form name                                      |
| ReviewChannelId   | BigInteger   | Channel for review embeds                      |
| RequiredApprovals | Integer      | Votes needed to approve (default 1)            |
| RequiredDenials   | Integer      | Votes needed to deny (default 1)               |
| ApprovalMessage   | UnicodeText  | Custom DM on approval                          |
| DenialMessage     | UnicodeText  | Custom DM on denial                            |
| ApplyChannelId    | BigInteger   | Channel where the Apply button embed is posted |
| ApplyMessageId    | BigInteger   | Message ID of the posted Apply button embed    |
| ApplyDescription  | UnicodeText  | Custom description on the Apply button embed   |

**Indexes:** `ApplicationForm_GuildId`, `ApplicationForm_Name_GuildId` (unique)

### `ApplicationQuestion`

| Column       | Type         | Purpose           |
| ------------ | ------------ | ----------------- |
| Id           | Integer (PK) | Auto-increment    |
| FormId       | Integer (FK) | Parent form       |
| QuestionText | UnicodeText  | The question text |
| SortOrder    | Integer      | Display order     |

### `ApplicationSubmission`

| Column            | Type         | Purpose                                                                                        |
| ----------------- | ------------ | ---------------------------------------------------------------------------------------------- |
| Id                | Integer (PK) | Auto-increment                                                                                 |
| FormId            | Integer (FK) | Parent form                                                                                    |
| GuildId           | BigInteger   | Discord guild ID                                                                               |
| UserId            | BigInteger   | Applicant's Discord ID                                                                         |
| UserName          | Unicode(50)  | Applicant's username                                                                           |
| Status            | String(10)   | `pending`, `approved`, or `denied`                                                             |
| SubmittedAt       | DateTime     | Submission timestamp (UTC)                                                                     |
| ReviewMessageId   | BigInteger   | Message ID of the review embed                                                                 |
| DecisionReason    | UnicodeText  | Reason provided on denial (shown in the review embed)                                          |
| ApplicantNotified | Boolean      | True once a reviewer successfully DMs the applicant post-decision; disables the Message button |

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

| Column          | Type         | Purpose                      |
| --------------- | ------------ | ---------------------------- |
| Id              | Integer (PK) | Auto-increment               |
| GuildId         | BigInteger   | Guild ID (null for built-in) |
| Name            | Unicode(100) | Template name                |
| IsBuiltIn       | Boolean      | True for seeded templates    |
| ApprovalMessage | UnicodeText  | Default approval message     |
| DenialMessage   | UnicodeText  | Default denial message       |

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

## Apply Button

When a form has an `ApplyChannelId` configured, the bot posts an embed with a persistent "Apply" button in that channel. This gives users a discoverable way to start an application without knowing the `/apply` command.

### Lifecycle

- **Posted** when a form becomes "ready" (has questions, a review channel, and an apply channel). This happens after `/application create`, `/application template use`, or `/application settings` when the apply channel is set.
- **Reposted** when `channel` is changed via `/application settings` — the old message is deleted and a new one is posted in the new channel.
- **Edited** when only `description` is changed via `/application settings` — the existing message is updated in-place.
- **Deleted** when the form is deleted via `/application delete`.

### Embed Content

The embed title is the form name. The description is either the custom `ApplyDescription` or the default text "Click the button below to apply!". Below the embed sits a green "Apply" button.

### Button Behaviour

When a user clicks the button:

1. The bot looks up the form via the message ID
2. Validates the form is still ready and the user hasn't already applied
3. Starts an `ApplicationSubmitConversation` via DM
4. Sends an ephemeral "Check your DMs!" confirmation

## Persistent Views

`ApplicationReviewView` and `ApplicationApplyView` in `modules/views/application.py` use `timeout=None` and fixed `custom_id` strings so buttons survive bot restarts. Both are registered in `bot.py:setup_hook()` with `self.add_view()`.

## Built-In Templates

Seeded on cog load (idempotent):

- **Guild Membership** — 6 questions about the applicant's background and availability
- **Staff / Moderator** — 6 questions about moderation experience and availability
- **Partnership / Collaboration** — 5 questions: Tell us about your community or project — what do you do? / How many active members or participants do you have? / What kind of collaboration are you looking for? / What value would this partnership bring to both communities? / Who is the primary point of contact, and how can we reach them?
- **Volunteer** — 5 questions: What areas or tasks are you most interested in volunteering for? / How many hours per week can you commit? / Do you have any relevant skills or experience? / What timezone are you in, and when are you typically available? / Why do you want to volunteer with us?
- **Community Access** — 4 questions: Which channel or area are you requesting access to, and why? / How long have you been a member of this server? / Have you read and agreed to the server rules? / How do you plan to use this access?
