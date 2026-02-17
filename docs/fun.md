# Fun Module

Entertainment commands with no external dependencies or database usage. All commands only require the bot to have `send_messages` permission.

## Commands

### `/roll [dice]`

Roll a die with N sides.

| Parameter | Type  | Default | Description     |
| --------- | ----- | ------- | --------------- |
| `dice`    | `int` | `6`     | Number of sides |

Returns a random number between 1 and N.

### `/choose <choices>`

Pick a random item from a comma-separated list.

| Parameter | Type  | Description                                              |
| --------- | ----- | -------------------------------------------------------- |
| `choices` | `str` | Comma-separated options (e.g., `"pizza, burger, sushi"`) |

### `/8ball <question>`

Magic 8-ball. The question **must** end with `?` or the bot refuses to answer.

| Parameter  | Type  | Description                              |
| ---------- | ----- | ---------------------------------------- |
| `question` | `str` | Your yes/no question (must end with `?`) |

Draws from 20 responses split across positive, neutral, and negative outcomes.

### `/hug <user> [intensity]`

Hug another server member with varying levels of enthusiasm.

| Parameter   | Type     | Default      | Description                |
| ----------- | -------- | ------------ | -------------------------- |
| `user`      | `Member` | _(required)_ | Who to hug                 |
| `intensity` | `int`    | random       | 0-4 scale of hug intensity |

**Intensity levels:**

- **0** — `(>._.)>` shy sideways hug
- **1** — `(## ^.^ ##)` blushing hug
- **2** — `(>^-^)> <(^-^<)` mutual hug
- **3** — `ʕっ•ᴥ•ʔっ` bear hug
- **4** — `(づ ̄ ³ ̄)づ` full embrace

### `/leet <intensity> <text>`

Convert text to 1337-speak at varying intensities.

| Parameter   | Type  | Description                           |
| ----------- | ----- | ------------------------------------- |
| `intensity` | `int` | 1-5, how aggressive the conversion is |
| `text`      | `str` | Text to convert                       |

Higher intensity levels replace more characters. Level 5 applies all substitutions (a->4, e->3, t->7, o->0, s->5, i->1, etc.).

### `/roti [num]`

Display a Rule of the Internet.

| Parameter | Type  | Default | Description                            |
| --------- | ----- | ------- | -------------------------------------- |
| `num`     | `int` | random  | Specific rule number (1-63, with gaps) |

43 rules are stored, numbered non-sequentially (matching the canonical internet rules list).

### `/say <text>`

The bot repeats whatever you type.

| Parameter | Type  | Description  |
| --------- | ----- | ------------ |
| `text`    | `str` | Text to echo |
