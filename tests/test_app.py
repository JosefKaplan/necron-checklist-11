#!/usr/bin/env python3
"""Smoke test for the Necron Turn Checklist (index.html).

Setup once:   pip install playwright && python3 -m playwright install chromium
Run:          python3 tests/test_app.py            (tests ../index.html)
              python3 tests/test_app.py path/to/index.html
Use a local Chrome instead of Playwright's Chromium:  CHROME_PATH=/path/to/chrome python3 tests/test_app.py

Exits non-zero on the first failed check and prints which one.
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PAGE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (HERE.parent / "index.html")
URL = PAGE.as_uri()
KEY = "necron-turn-checklist-v1"

passed = 0


def check(name, cond, detail=""):
    global passed
    if not cond:
        print(f"FAIL  {name}  {detail}")
        sys.exit(1)
    passed += 1
    print(f"ok    {name}")


def state(pg):
    return pg.evaluate("({round: state.round, turn: state.turn, phase: state.phase, cp: state.cp})")


def names(pg, sel=".strat h3"):
    return pg.eval_on_selector_all(sel, "els => els.map(e => e.textContent.trim())")


CELL = """([phase, col]) => {
  const sec = [...document.querySelectorAll('.ov-phase')].find(x => x.getAttribute('aria-label') === phase);
  const c = sec.querySelectorAll('.ov-cell')[col === 'mine' ? 0 : 1];
  return [...c.querySelectorAll('.ov-item .nm')].map(x => x.textContent);
}"""

DATA_CHECK = r"""() => {
  const T = ['mine', 'opp', 'any'], P = ['command', 'movement', 'shooting', 'charge', 'fight', 'end', 'any'];
  const all = [...CORE, ...DETACHMENTS.flatMap(d => [...d.strats, ...d.ruleReminders, ...d.enh]), ...STEPS, ...UNITS, ARMY_RULE];
  const seen = new Set(), problems = [];
  all.forEach(it => {
    if (seen.has(it.id)) problems.push('duplicate id ' + it.id);
    seen.add(it.id);
    (it.slots || []).forEach(s => { const [t, p] = s.split(':'); if (!T.includes(t) || !P.includes(p)) problems.push(it.id + ' bad slot ' + s); });
    if (it.slots && !WIN[it.w]) problems.push(it.id + ' bad window ' + it.w);
  });
  DETACHMENTS.forEach(d => { if (!(d.dp >= 1 && d.dp <= 3)) problems.push(d.id + ' missing DP'); });
  return { count: all.length, problems };
}"""


def main():
    errors = []
    with sync_playwright() as p:
        launch = {"executable_path": os.environ["CHROME_PATH"]} if os.environ.get("CHROME_PATH") else {}
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.route("**/fonts.googleapis.com/**", lambda r: r.abort())
        ctx.route("**/fonts.gstatic.com/**", lambda r: r.abort())
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and "ERR_FAILED" not in m.text and errors.append(m.text))
        pg.goto(URL)
        pg.wait_for_timeout(150)

        # --- data integrity -------------------------------------------------
        d = pg.evaluate(DATA_CHECK)
        check("data: ids unique, slots and windows valid", not d["problems"], d["problems"])
        check("page asks search engines not to index it (public GitHub Pages site)",
              "noindex" in (pg.get_attribute("meta[name=robots]", "content") or ""))
        icons = pg.evaluate("""() => Promise.all(['icon', 'apple-touch-icon'].map(rel => {
          const href = document.querySelector(`link[rel="${rel}"]`)?.href || '';
          return new Promise(done => {
            const img = new Image();
            img.onload = () => done({ rel, inline: href.startsWith('data:image/'), width: img.naturalWidth });
            img.onerror = () => done({ rel, inline: href.startsWith('data:image/'), width: 0 });
            img.src = href;
          });
        }))""")
        check("tab and home-screen icons are inline images that load",
              all(i["inline"] and i["width"] > 0 for i in icons), icons)

        # --- game flow, CP and limits ---------------------------------------
        check("starts in round 1, your Command phase, 1CP",
              state(pg) == {"round": 1, "turn": "mine", "phase": "command", "cp": 1}, state(pg))
        pg.click("[data-act=use][data-id=core-bravery]")
        check("using Insane Bravery costs 1CP", state(pg)["cp"] == 0)
        check("used stratagem is blocked for the phase",
              pg.inner_text(".strat:has(h3:text('Insane Bravery')) .use") == "Used this phase")
        for _ in range(6):
            pg.click("[data-act=next]")
        check("Next after End of turn goes to opponent's Command phase and adds 1CP",
              state(pg) == {"round": 1, "turn": "opp", "phase": "command", "cp": 1}, state(pg))
        pg.click("[data-act=next]"); pg.click("[data-act=next]")
        opp_shoot = names(pg)
        check("opponent's Shooting phase lists Awakened Dynasty reactions",
              "Protocol of the Undying Legions" in opp_shoot and "Protocol of the Vengeful Stars" in opp_shoot, opp_shoot)
        pg.click("[data-act=use][data-id=ad-undying]")
        check("using a stratagem in the opponent's turn costs CP", state(pg)["cp"] == 0)
        pg.click("[data-act=undo]")
        check("undo refunds the CP", state(pg)["cp"] == 1)
        for _ in range(4):
            pg.click("[data-act=next]")
        check("round 2 starts in your Command phase with +1CP",
              state(pg) == {"round": 2, "turn": "mine", "phase": "command", "cp": 2}, state(pg))
        check("once-per-battle stratagem stays blocked next round",
              pg.inner_text(".strat:has(h3:text('Insane Bravery')) .use") == "Used this battle")

        # --- detachments and Detachment Points ------------------------------
        pg.click("[data-act=view][data-view=army]")
        check("Hand of the Dynasty can't join Awakened Dynasty (both Unique: DYNASTY)",
              pg.is_disabled("#det-hand") and "DYNASTY" in pg.inner_text("label[for=det-hand] .why"))
        pg.uncheck("#det-awakened"); pg.check("#det-canoptek"); pg.check("#det-hand")
        check("Canoptek Court + Hand of the Dynasty = 3/3 DP",
              pg.evaluate("[state.dets, dpUsed()]") == [["canoptek", "hand"], 3])
        check("a 2 DP detachment is now blocked with a reason",
              pg.is_disabled("#det-cursed") and "DP" in pg.inner_text("label[for=det-cursed] .why"))
        pg.click("[data-act=size][data-size=incursion]")
        check("Incursion sets 2 DP and warns when over budget",
              pg.evaluate("state.settings.dp") == 2 and pg.query_selector(".overline") is not None)
        pg.click("[data-act=size][data-size=strike]")
        pg.uncheck("#det-canoptek"); pg.check("#det-hypercrypt"); pg.check("#enh-e-overseer")
        check("The Phaeron's Armoury can't join Hypercrypt Legion (both Unique: HYPERCRYPT)",
              pg.is_disabled("#det-phaeron") and "HYPERCRYPT" in pg.inner_text("label[for=det-phaeron] .why"))
        pg.click("[data-act=turn][data-turn=opp]"); pg.click("[data-act=phase][data-phase=end]")
        check("Hyperphasing shows 2 units at Strike Force +1 for Dimensional Overseer",
              any("up to 3" in t for t in names(pg, ".check .txt")))
        pg.click("[data-act=turn][data-turn=mine]"); pg.click("[data-act=phase][data-phase=command]")
        cmd = names(pg)
        check("stratagems from both detachments are merged",
              "Reanimation Crypts" in cmd and "Dominance Protocols" in cmd, cmd)

        # --- stratagems tab: overview and full cards ------------------------
        pg.click("[data-act=view][data-view=strats]")
        pg.click("[data-act=smode][data-mode=overview]")
        check("overview puts Nanosaturation in the opponent's Shooting phase",
              "Nanosaturation" in pg.evaluate(CELL, ["Shooting", "opp"]))
        check("overview puts Counteroffensive only in the opponent's Fight phase",
              "Counteroffensive" in pg.evaluate(CELL, ["Fight", "opp"]) and "Counteroffensive" not in pg.evaluate(CELL, ["Fight", "mine"]))
        check("keyword-gated core stratagems are not in the overview", "Explosives" not in pg.inner_text("main"))
        pg.click(".ov-item[data-id=hd-nano]")
        check("tapping an entry opens its card", pg.inner_text(".sheet .strat h3") == "Nanosaturation")
        pg.keyboard.press("Escape")
        check("Escape closes the card", pg.query_selector(".sheet") is None)
        pg.click("[data-act=smode][data-mode=cards]")
        check("full cards list all 10 core stratagems",
              any(h.startswith("Core stratagems 10") for h in names(pg, "main h2")), names(pg, "main h2"))

        # --- layout ----------------------------------------------------------
        pg.set_viewport_size({"width": 360, "height": 740})
        for view in ("game", "strats", "army"):
            pg.evaluate(f"state.view = '{view}'; render()")
            wide = pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            check(f"no sideways scrolling at 360px ({view})", not wide)

        # --- saved games ------------------------------------------------------
        pg.reload(); pg.wait_for_timeout(100)
        check("game survives a reload", pg.evaluate("state.dets") == ["hand", "hypercrypt"])
        pg.evaluate(f"""() => {{ const s = JSON.parse(JSON.stringify(state)); delete s.dets; s.det = 'obeisance';
            s.settings = {{ first: 'mine', autoCP: true }}; localStorage.setItem('{KEY}', JSON.stringify(s)); }}""")
        pg.reload(); pg.wait_for_timeout(100)
        check("old single-detachment saves are migrated",
              pg.evaluate("[state.dets, state.settings.dp]") == [["obeisance"], 3])

        # --- consistency fixes ----------------------------------------------
        pg.evaluate("state.dets = ['canoptek']; state.enh = ['e-tesla']; state.turn = 'mine'; state.phase = 'charge'; state.view = 'game'; render()")
        check("Tesla Weave also shows in your own Charge phase (enemy Heroic Intervention)",
              any("Metalodermal Tesla Weave" in t for t in names(pg, ".check .src")))
        pg.evaluate("state.dets = ['hypercrypt', 'phaeron']; state.enh = []; save()")
        pg.reload(); pg.wait_for_timeout(100)
        warn = pg.inner_text(".ctx") if pg.query_selector(".ctx .overline") else ""
        check("an illegal combination from an old save is flagged in the Game tab", "HYPERCRYPT" in warn, warn)

        browser.close()

    check("no JavaScript errors", not errors, errors)
    print(f"\n{passed} checks passed")


if __name__ == "__main__":
    main()
