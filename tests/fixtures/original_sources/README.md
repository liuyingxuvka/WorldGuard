# Original-source development seeds

These small text fixtures are copied byte for byte from the Round 14 handoff:
`Temp` commit `792424ad9a3dbd2c1afd23acbf9af611daef738b`,
`handoffs/2026-11-05-第14轮-下一轮开发/附件/技能原型/WorldGuard/`.

- `batch1`: the original public `seeds/`.
- `batch2`: the now-public `新种子/seeds/` (`public`, `new`, `heldout` are historical names).
- `batch3`: `第三批种子/seeds/`; the three known-limit cases record limitations, not claimed catches.

`manifest.json` records every original relative path and SHA-256. No generated outputs or raw AI sessions are included.
The source sidecars are test inputs: tests merge their `texts`, `aliases`, `tables`, `decimal` and `values` into the
native contract or mesh before checking it. The production reader has no dependency on this directory or seed IDs.
