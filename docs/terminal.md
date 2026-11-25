# Terminal interface

```bash
pip install "isoline[tui]"
isoline tui
```

A full-screen interface over the same engines as the command line. Pick a mode, type, press Enter.
Network work runs in the background, so the screen never freezes; a failed lookup shows the reason
on screen instead of a traceback.

| Mode | Key | Input | Runs |
|---|---|---|---|
| Fundamental | F2 | `AAPL` or `INFY.NS` | scores, quality, growth, red flags (`isoline scan`) |
| Valuation | F3 | `AAPL 0.09 0.07` (ticker, discount, growth; the last two optional) | DCF with scenarios and sensitivity (`isoline value`) |
| Compare | F4 | `AAPL MSFT` | side-by-side comparison (`isoline compare`) |
| Screening | F5 | `IT` or `Banking` | Piotroski and leverage screen (`isoline screen`) |

Each mode runs a different workflow, not a relabelled one. The session list on the left keeps what you
ran; select an entry to put it back in the input box.

## Keys

| Key | Action |
|---|---|
| Ctrl+K | command palette (search every action) |
| Ctrl+N | new analysis (focus the input) |
| F2 to F5 | choose mode |
| F1 | help |
| Ctrl+L | clear output |
| Ctrl+Q | quit |

## Notes

- Reports, exports and watchlists stay in the command line for now (`--export`, `--report`).
- The interface is tested headlessly with Textual's test pilot; it has not been exercised on every
  terminal emulator. If colours look wrong, try Windows Terminal, iTerm2 or a recent GNOME Terminal.
