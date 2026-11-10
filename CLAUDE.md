# Necron Turn Checklist

A personal, single-page web app for playing **Necrons in Warhammer 40,000 11th edition**. At the table it tells you, for the current turn (yours or your opponent's) and phase, what you are able to do: phase steps, army and detachment rules, enhancements, unit abilities, and every stratagem you can use right now, with a CP tracker.

Personal use only. Rules belong to Games Workshop; data comes from Wahapedia.

## Files

| Path | What it is |
|---|---|
| `index.html` | The whole app: HTML, CSS and JS in one file. No build step, no dependencies. |
| `tests/test_app.py` | Playwright smoke test with assertions (game flow, CP, limits, undo, Detachment Points, overview, saves, layout, data integrity). |
| `README.md` | Short deploy guide for GitHub Pages. Keep it short and direct. |
| `.nojekyll` | Empty. Tells GitHub Pages to serve files as they are, without Jekyll. |
| `.gitignore` | Ignores `.DS_Store`, `__pycache__/` and `.idea/`. |
| `CLAUDE.md` | This file. |

Open `index.html` in a browser to use it. The game is saved in that browser's `localStorage` only, so each device and each address (local file, GitHub Pages, artifact) has its own save.

**Deployment:** GitHub Pages, from branch `main`, folder `/ (root)` (steps in `README.md`). Every push to `main` redeploys.
- Repo: https://github.com/JosefKaplan/necron-checklist-11
- Live: https://josefkaplan.github.io/necron-checklist-11/ The site is public to anyone with the link; `<meta name="robots" content="noindex, nofollow">` in `index.html` keeps it out of search engines, so leave that tag in.

A copy is also published as a private claude.ai artifact: https://claude.ai/artifact/HRthWHdmsXPCL2ZEhD8zUp
That copy is separate: editing this file does not update it. To update it, open a Claude chat in the "Necrons 11th" project and ask for the artifact to be republished from this `index.html`.

## Hard rules for changes

1. **Keep it one self-contained static file.** GitHub Pages serves it as is, and the artifact copy blocks `fetch` and remote images (only inline code and Google Fonts load). No frameworks, no CDN scripts, no build tooling, no paths that assume the site lives at the domain root.
2. **Never paste rules text verbatim** from Wahapedia, Games Workshop or anywhere else. Every `when` / `target` / `effect` / `text` is a short summary in our own words. Keep numbers exact (CP, inches, dice, rolls).
3. **Keep IDs stable.** Stratagem, enhancement, unit and detachment `id`s are stored in saved games (`state.dets`, `state.enh`, `state.units`, `state.used`, `state.battle`…). Renaming one silently breaks saves. Add new IDs instead.
4. **Saved-state changes need a migration.** State is `v: 1`. Add new fields with defaults in `freshGame()` and backfill them in `migrate()`. `tests/test_app.py` checks that a v1 single-detachment save migrates.
5. **Be honest about uncertainty.** If a rule's exact timing or effect is not confirmed, set `verify: true`; the UI shows a "Check wording" tag. Remove the flag only after checking the full text.
6. Storage access stays wrapped in try/catch (`store.get/set`); the app must work without storage.
7. Run `python3 tests/test_app.py` after every change.

## How the code is organised (`<script>` in `index.html`)

Sections appear in this order. Find things by name, not line number.

- **Data**
  - `PHASES` (command, movement, shooting, charge, fight, end) and `WIN` (timing windows: `start`, `during`, `react`, `end`).
  - `CORE`: the 10 core stratagems. `Explosives` and `Smokescreen` have `keyword` set, which hides them from the Game tab and the overview (no Necron unit has EXPLOSIVES/GRENADES or SMOKE).
  - `DETACHMENTS`: 12 Necron detachments built with `D(id, name, rule, ruleReminders, enh, strats)`.
  - `DET_META`: Detachment Points, Unique tag and Force Dispositions per detachment, merged into `DETACHMENTS`.
  - `SIZES`: battle sizes with DP budget and Hyperphasing unit count.
  - `ARMY_RULE` (Reanimation Protocols), `STEPS` (core turn steps), `UNITS` (units with timed abilities).
- **State**: `freshGame()`, `migrate()`, `store` (localStorage key `necron-turn-checklist-v1`), `undoStack` (in memory).
- **Helpers**: `slotMatches` / `matches` (is an item active in this turn and phase?), `selDets`, `dpUsed`, `blockReason` (can this detachment still be added: DP budget and Unique tags), `armyProblems` (warnings for an already-selected army that breaks those rules, e.g. an old save), `stratPool`, `stratStatus` (once per phase / turn / round / battle), `timedReminders`, `fmt` (escapes text, styles CAPS keywords and `[ABILITIES]`), `dyn` (fills `{hyper}`).
- **Mutations**: always go through `mutate(fn)`, which snapshots for undo, saves and re-renders. `nextPhase`, `useStrat`, `toggleReminder`, `addLog`.
- **Rendering**: `render()` rebuilds `#tracker`, `#main`, `#tabbar` and `#sheet-root` from state.
  - Views: `renderGame`, `renderStrats` (which calls `renderOverview` or `renderStratCards`), `renderArmy`.
  - Pieces: `stratCard`, `renderSheet`, `renderTracker`.
- **Events**: one delegated `click` handler switches on `data-act`, plus delegated `change`, `submit` and `keydown` (Escape closes the sheet).

## Data model

Every timed item has `slots` and a window `w`.

- A **slot** is the string `"turn:phase"`.
  - turn is `mine`, `opp` or `any`.
  - phase is `command`, `movement`, `shooting`, `charge`, `fight`, `end` or `any`.
  - `any:any` means any phase of either turn. It is never shown in the End-of-turn step.
- **Reading 11th-edition WHEN lines:**
  - "Your opponent's Shooting phase or the Fight phase" becomes `["opp:shooting", "any:fight"]`.
  - "Fight phase." or "Command phase." without "your" means either player's phase, so `any:fight` / `any:command`.
- Window `w`: `start` (start of phase), `during`, `react` (just after something happens), `end`. Lists are sorted by window, then detachment before core, then CP.
- **Stratagem** `S(id, name, cp, type, slots, w, when, target, effect, extra)`.
  - `type` is one of: Battle Tactic, Strategic Ploy, Epic Deed, Wargear, Detachment (newer 3-stratagem detachments), Core.
  - `extra` can set `restr`, `limit` (`battle` / `turn` / `round`), `verify`, `keyword`.
- **Reminder** `R(id, name, slots, w, text, extra)`, used for detachment rule reminders, steps and units. A unit with `slots: null` is passive and shows under "Always on".
- **Enhancement** `E(id, name, who, text, extra)`. Give it `slots` and `w` only if it does something at a specific time; otherwise it is passive.
- **Detachment**: `rule` `{name, text}`, `ruleReminders` (timed parts of the rule), `enh`, `strats`, plus `dp`, `unique` and `fd` from `DET_META`.

### Common tasks

- **Fix or verify a rule:** edit its summary and slots in `CORE` / `DETACHMENTS` / `UNITS`, and drop `verify: true` once confirmed.
- **Add a unit ability:** add an `R("u-…", "Unit: Ability", slots, w, text, { limit })` to `UNITS`. It appears under Army > Units with timed abilities.
- **Add a detachment:**
  - Add a `D(...)` entry to `DETACHMENTS` and its `DET_META` line (DP, Unique tag, Force Disposition).
  - Use a new short id with prefixed child ids (for example `xx-name`).
  - It shows up everywhere automatically.
- **Another faction (e.g. Chaos Space Marines + Chaos Daemons):** the model is faction-agnostic, but `ARMY_RULE`, `UNITS`, the `WAHA` link and texts are Necron-specific. Prefer a copy of the app per faction over a faction switcher, unless asked.
- **Colours:** design tokens are in the `:root` block at the top of `<style>`, redefined for dark mode in two places (media query and `[data-theme="dark"]`). Keep all three blocks in sync. `--s1`, `--s2` and `--s3` colour the chosen detachments, in `DETACHMENTS` order (see `srcClass`).

## 11th-edition rules the app enforces

- Both players gain 1CP in each Command phase. The app adds yours when you tap **Next** into a Command phase (setting: Army > Game).
- Each stratagem once per phase. A unit can be targeted by only one stratagem per phase, shown as a reminder only (units aren't tracked). Battle-shocked units can't be targeted.
- **Detachment Points:**
  - Budget: Incursion 2 DP, Strike Force 3 DP. The Onslaught budget is unconfirmed, so the user sets it.
  - No detachment twice. No two detachments sharing a Unique tag:
    - DYNASTY: Awakened Dynasty, Hand of the Dynasty.
    - HYPERCRYPT: Hypercrypt Legion, The Phaeron's Armoury.
  - All chosen detachments' rules, enhancements and stratagems apply together.
- Hyperphasing unit count follows battle size (1 / 2 / 3), +1 with Dimensional Overseer.
- Reminders support limits `battle`, `turn` and `round` (e.g. Overlord's My Will Be Done is once per battle round).

## Verification status

On 10 November 2026, every entry was checked point by point against Wahapedia's live text:
- Army rule, all 12 detachment rules, the 42 enhancements (including the 4 Necrodermal Bindings), and all 63 detachment stratagems.
- The 10 core stratagems, the core turn steps, and the 10 unit abilities in `UNITS`.
- Wahapedia's own turn and phase icons on each stratagem matched the app's `slots`.

No entry is currently flagged `verify: true`.

**Details worth knowing:**
- Heroic Intervention's "Into the Fray" mode costs +1CP. The Use button takes the base 1CP, so add the extra yourself.
- Lord and Nemesor Zahndrekh are Legends datasheets on Wahapedia and are labelled "(Legends)".
- Resurrection Orb differs per unit: the Overlord resurrects its own unit, the Catacomb Command Barge one INFANTRY or MOUNTED unit within 6". `migrate()` adds `u-orb-ovl` once for saves that had the old combined `u-orb` ticked.

**How to re-verify after a rules update:**
1. Open the Wahapedia Necrons 11th page in Claude in Chrome.
2. Collect every `.str11Wrap` block. Each block holds:
   - `.str11Name`, `.str11CP` and `.str11Type` (detachment and type).
   - The turn, read from the class `str11ColorYour` / `str11ColorEnemy` / `str11ColorEither`.
   - The phase icons, read from the `.str11Icon` classes.
   - `.str11Text`, which holds WHEN / TARGET / EFFECT / RESTRICTIONS.
3. Detachment rules and enhancements are in the hidden `#wahMainContent > .clFl` sections, one per detachment.
4. Unit abilities are on `/factions/necrons/datasheets.html`. A Legends datasheet's container has the class `sLegendary`.
5. Tool output is small, so render the extracted text into the page and read it with `get_page_text`.

## Known gaps / next steps

- Not modelled:
  - Enhancement points (sources disagreed) and enhancement limits per battle size.
  - Boarding Actions detachments.
  - Per-unit tracking of the one-stratagem-per-unit rule.
  - Most unit abilities beyond the ones in `UNITS`.
- Onslaught DP budget unconfirmed.
- Data snapshot: Wahapedia Necrons 11th edition (rules v2.8.1, October 2026), verified 10 November 2026. Rules and balance updates change often, so re-verify after a balance dataslate or Munitorum Field Manual update.

## Testing

```bash
pip install playwright && python3 -m playwright install chromium   # once
python3 tests/test_app.py                                          # tests ./index.html
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" python3 tests/test_app.py   # use installed Chrome
```

The test runs a fresh browser profile at phone size (390×844, then 360×740), blocks Google Fonts, and stops at the first failing check. Add a check to it for every new feature.

## Sources

- Wahapedia, Necrons (11th edition): https://wahapedia.ru/wh40k11ed/factions/necrons
- Wahapedia data export (CSV, no API, attribution recommended): https://wahapedia.ru/wh40k11ed/the-rules/data-export
- Warhammer Community, Xenos Faction Packs (DP budgets): https://www.warhammer-community.com/en-gb/articles/fchkklcq/new40k-download-new-xenos-faction-packs-today/
