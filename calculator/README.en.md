# calculator · Calculator ∞ Alchemia

A terminal-style calculator (MVC + cryptography easter eggs) with **zero
external dependencies** and **mouse-only** interaction.

## Run

```bash
python main.py
python -m calculator      # equivalent
```

Standard library only: `tkinter`, `hashlib`, `secrets`, `base64`.

## Architecture

Previously a single 858-line `calculator.py`. Now split into a package with
strictly one-way dependencies:

```
app ──> controller ──> model ──> engine / crypto / easter_eggs
             │            └────────> config
             └──> view ──> config / snapshot
```

```
calculator/              # the package
├── config.py        limits / theme / keypad layouts (single source of truth)
├── snapshot.py      the Model → View data contract
├── engine/          tokenizer → parser (shunting-yard) → evaluator
├── crypto.py        ciphers, digests, key & salt generation (uses `secrets`)
├── easter_eggs.py   easter-egg table (multiple values per key, rotating)
├── model.py         state machine, no tkinter import
├── view.py          pure rendering, no model import
├── controller.py    wiring + side effects
└── app.py           composition root
main.py              entry point
tests/               77 unit tests + GUI smoke tests
```

Model and View share **no import relationship** — the Model emits a `Snapshot`
and the View consumes it. The Controller never touches layout constants; it
only registers a single `on_press(token)` callback.

### Why the entry point is `main.py`, not `calculator.py`

A package named `calculator/` **shadows** a same-named `calculator.py`
(packages take precedence over modules), so an entry script called
`calculator.py` could never be imported. Hence the entry script is
`main.py` while the package keeps the name `calculator`.

## Features

- Arithmetic with parentheses, precedence, unary minus. Behaviour is
  **identical to the previous `eval`-based implementation** (verified against
  10 expressions, zero differences).
- Cryptography panel: press `#`, pick a mode, type on the letter keypad,
  press `EXE`. Supports caesar / hash / key / xor / vig / rot13 / b64 /
  salt / pwd. On the letter keypad, `_` stands for a space.
- Easter eggs: special combinations; hitting the same key repeatedly
  **rotates** through its values (`128` → `aes-128` → `md5` → `nonce`).
- Interaction easter eggs: same key 3× clears, backspace 3× quits,
  equals 3× shuffles the keypad.

## Tests

```bash
PYTHONPATH=".:./tests" python -m unittest discover -s tests -p "test_*.py"
```

77 tests: engine 17 / crypto 26 / model 25 / GUI smoke 9. The core layers
(config, engine, crypto, easter_eggs, model, snapshot) do **not** import
tkinter, so the suite runs on a GUI-less interpreter (GUI smoke tests skip).

## Bugs fixed during the refactor

| Bug | Evidence | Fix |
|---|---|---|
| `SPECIAL_COMBOS` duplicate keys silently overwritten | 68 entries, only 58 effective; docs said `128→aes-128`, actual was `nonce` | value tuples with rotation, nothing lost |
| `eval()` allow-list permitted `**` | `9**9**9` passed validation → could freeze the UI | three-stage engine; `**` rejected at the lexer, plus result-magnitude guard |
| Cryptography 100% unreachable | no `#` key, no letter keys — 17 of 18 letter eggs and all 9 modes unreachable | `#` key + switchable letter keypad; all 9 modes verified working |
| Layering violations | View signature referenced `CalculatorModel`; Controller iterated the View's `BUTTON_TOKENS` | `Snapshot` contract; single callback registration |
| Keys generated with `random` | Mersenne Twister is not cryptographically secure | switched to `secrets` |
| No tests at all | — | 77 added |

## License

MIT · Copyright (c) 2026 siwpan
