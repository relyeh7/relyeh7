# Zone Indicators Suite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build three independent, bidirectional MQL5 indicators (SMC, Candle Range Theory, VWAP+volume) that detect buy/sell zones on any symbol/timeframe, each with a full interactive panel and alerts, deployed to demo terminal D4CE.

**Architecture:** Three standalone indicator projects under `ZoneIndicators/MQL5/`, laid out in the same `Include/Indicators/Experts` convention already used by `GridFib_EA` (needed for MetaEditor's `/inc:` angle-bracket include resolution and for terminal deployment), sharing only a minimal `Include/ZoneIndicators/ZI_Common.mqh` (zone struct + alert helper). Each is built from scratch by the **MQL5 Indicator Builder** agent, grounded in patterns verified by the **MQL5 Article Miner** corpus (`series_catalog.md`) and the official MQL5 docs corpus.

**Tech Stack:** MQL5 (MetaEditor / metaeditor64 CLI), MT5 Strategy Tester (headless EA-based test runners), PowerShell build/deploy tooling (pattern from `GridFib_EA/tools/`).

**Design spec:** `docs/superpowers/specs/2026-09-22-zone-indicators-suite-design.md` — read this first for full rationale; this plan only restates what's needed to execute. Note: the spec's §3 folder diagram is superseded by the layout below — the flat layout in the spec doesn't support MQL5 angle-bracket include resolution the way this repo's established `GridFib_EA` pattern does; this plan's layout is the corrected, buildable one.

**Repo layout note (read before dispatching anyone):** this plan runs inside a git worktree whose toplevel is one directory above the actual project root. Every path below (`ZoneIndicators/...`, `docs/...`, `Vault/...`) is relative to `Dev-Drive/` inside the worktree, not the worktree's git toplevel. State this explicitly in every dispatch.

**Final folder layout (all tasks build toward this):**

```
ZoneIndicators/
├── MQL5/
│   ├── Include/
│   │   ├── ZoneIndicators/ZI_Common.mqh
│   │   ├── SMC_ZonesInd/SMC_ZonesEngine.mqh, SMC_ZonesPanel.mqh
│   │   ├── CRT_ZonesInd/CRT_ZonesEngine.mqh, CRT_ZonesPanel.mqh
│   │   └── VWAP_ZonesInd/VWAP_ZonesEngine.mqh, VWAP_ZonesPanel.mqh
│   ├── Indicators/
│   │   ├── SMC_ZonesInd/SMC_ZonesInd.mq5
│   │   ├── CRT_ZonesInd/CRT_ZonesInd.mq5
│   │   └── VWAP_ZonesInd/VWAP_ZonesInd.mq5
│   └── Experts/
│       └── ZoneIndicators_Tests/
│           ├── SMC_ZonesInd_TestRunner.mq5
│           ├── CRT_ZonesInd_TestRunner.mq5
│           └── VWAP_ZonesInd_TestRunner.mq5
├── tools/ (compile.ps1, build.ps1, deploy.ps1)
└── docs/ (mined-patterns.md)
```

Each indicator's main `.mq5` includes its own engine/panel via angle brackets
(`#include <SMC_ZonesInd\SMC_ZonesEngine.mqh>`), resolved at compile time
against `/inc:ZoneIndicators\MQL5` — exactly like `GridFib_EA`. The
TestRunner for each indicator is an **Expert Advisor**, not a script or the
indicator itself — MT5 Strategy Tester only executes EAs, so headless
testing of an indicator's engine logic requires an EA wrapper that
`#include`s the same engine header and runs assertions against it (this is
exactly the `GridFib_TestRunner.mq5` pattern, which is an EA under
`Experts/GridFib/`, not under `Indicators/`).

---

### Task 1: Project scaffolding + shared common module + build tooling

**Files:**
- Create: `ZoneIndicators/MQL5/Include/ZoneIndicators/ZI_Common.mqh`
- Create: `ZoneIndicators/tools/compile.ps1`
- Create: `ZoneIndicators/tools/build.ps1`
- Create: `ZoneIndicators/tools/deploy.ps1`
- Create empty (populated in Tasks 3-5): `ZoneIndicators/MQL5/Include/SMC_ZonesInd/`, `.../CRT_ZonesInd/`, `.../VWAP_ZonesInd/`, `ZoneIndicators/MQL5/Indicators/SMC_ZonesInd/`, `.../CRT_ZonesInd/`, `.../VWAP_ZonesInd/`, `ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/`

**Step 1: Create folder structure**

```powershell
New-Item -ItemType Directory -Force -Path `
  "ZoneIndicators\MQL5\Include\ZoneIndicators", `
  "ZoneIndicators\MQL5\Include\SMC_ZonesInd", `
  "ZoneIndicators\MQL5\Include\CRT_ZonesInd", `
  "ZoneIndicators\MQL5\Include\VWAP_ZonesInd", `
  "ZoneIndicators\MQL5\Indicators\SMC_ZonesInd", `
  "ZoneIndicators\MQL5\Indicators\CRT_ZonesInd", `
  "ZoneIndicators\MQL5\Indicators\VWAP_ZonesInd", `
  "ZoneIndicators\MQL5\Experts\ZoneIndicators_Tests", `
  "ZoneIndicators\tools", `
  "ZoneIndicators\docs"
```

Run this from the `Dev-Drive/` directory (see repo layout note above).

**Step 2: Write `ZI_Common.mqh`**

```mql5
//+------------------------------------------------------------------+
//| ZI_Common.mqh — shared types for the Zone Indicators suite       |
//+------------------------------------------------------------------+
#property strict

enum ENUM_ZI_TYPE { ZI_BUY, ZI_SELL };

struct ZI_Zone
{
   double     price_hi;
   double     price_lo;
   ENUM_ZI_TYPE type;
   int        strength;
   datetime   bar_time;
   bool       mitigated;
   string     label;
};

// Fires Alert()+SendNotification() with per-bar throttling.
// last_alert_bar_time is caller-owned state (one per zone-kind/direction).
void ZI_Alert(const string message, const bool push_enabled,
              const bool sound_enabled, datetime &last_alert_bar_time,
              const datetime current_bar_time)
{
   if(current_bar_time == last_alert_bar_time) return;
   last_alert_bar_time = current_bar_time;
   if(sound_enabled) Alert(message);
   if(push_enabled)  SendNotification(message);
}
```

**Step 3: Compile-check the header stand-alone**

Write a throwaway indicator at
`ZoneIndicators/MQL5/Indicators/SMC_ZonesInd/_ZI_CommonCheck.mq5` containing
only `#property strict`, `#include <ZoneIndicators\ZI_Common.mqh>`, an empty
`OnCalculate` returning `rates_total`. Compile it with `/inc:` pointed at
`ZoneIndicators\MQL5` (see Step 4). Confirm `0 errors, 0 warnings`, then
delete the throwaway file — it is not part of the deliverable.

**Step 4: Write `tools/compile.ps1`, `tools/build.ps1`, `tools/deploy.ps1`**

Port the pattern from `H:\Dev-Drive\GridFib_EA\tools\{compile,build,deploy}.ps1`
(read those three files directly — they are the working reference,
untracked in git but present on disk at that path) with these adaptations:

- `compile.ps1`: same shape as GridFib's (`-File <path>` mandatory param,
  `-MetaEditor` default path, `-AllowWarnings` switch), but `/inc:` must
  point at `ZoneIndicators\MQL5` (this project's own root), not GridFib's.
- `build.ps1`: GridFib's version hardcodes a hard-coded `$targets` array with
  no per-project filter — **this plan needs more**: add a `-Target
  <ProjectName>` optional string parameter. When given (e.g. `SMC_ZonesInd`),
  compile only the files whose path contains `\<ProjectName>\` or
  `<ProjectName>_TestRunner.mq5`; when omitted, compile everything (all 3
  indicators + their test runners + `Common`, matching GridFib's
  no-argument full-build behavior). This is required — Tasks 3-5 depend on
  `-Target` existing.
- `deploy.ps1`: same shape as GridFib's (`-DataFolder` defaulting to
  `D4CEFEDAF043B05DA80223FD698C7DF2`, hardcoded `$forbidden` list with the
  two prop-firm IDs, `-SkipBuild` switch). Adjust the `$map` array to this
  project's `Include/Indicators/Experts` subfolders instead of GridFib's.
  **Do not add D0E8 to any default or convenience list** — it must require
  an explicit, separately-requested change to even become deployable there.

**Step 5: Commit**

```bash
git add ZoneIndicators/MQL5/Include/ZoneIndicators ZoneIndicators/tools
git commit -m "feat(zone-indicators): scaffold project structure, shared ZI_Common.mqh, and build/deploy tooling"
```

---

### Task 2: Mine/confirm detection patterns from the corpus

**Files:**
- Create: `ZoneIndicators/docs/mined-patterns.md`

**Step 1: Dispatch the MQL5 Article Miner agent**

Prompt it with (adapt wording, keep intent):

> Necesito confirmar o minar patrones de código YA VERIFICADOS por
> compilación en el corpus de `H:\Dev-Drive\MQL5_Articles\` (usar
> `series_catalog.md` si ya existe una entrada aplicable, o minar una nueva
> si no) para tres técnicas: (1) detección de Order Blocks + Fair Value Gaps
> + liquidity sweep de máximos/mínimos iguales, (2) sweep de rango de sesión
> con reingreso (Candle Range Theory / manipulación-distribución), (3) VWAP
> de sesión con bandas de desviación estándar + detección de agotamiento de
> volumen. Para cada una, entrega: la referencia al artículo/sección de
> docs, el snippet de código ya compilado como prueba, y notas de
> adaptación necesarias para un indicador bidireccional (compra Y venta).
> No construyas el indicador final — solo confirma/extrae los patrones.

**Step 2: Save the agent's findings**

Write the miner's output to `ZoneIndicators/docs/mined-patterns.md` — this
becomes the grounding reference for Tasks 3-5.

**Step 3: Commit**

```bash
git add ZoneIndicators/docs/mined-patterns.md
git commit -m "docs(zone-indicators): record mined/verified detection patterns for SMC, CRT, VWAP"
```

---

### Task 3: Build SMC_ZonesInd (SMC bidireccional)

**Files:**
- Create: `ZoneIndicators/MQL5/Indicators/SMC_ZonesInd/SMC_ZonesInd.mq5`
- Create: `ZoneIndicators/MQL5/Include/SMC_ZonesInd/SMC_ZonesEngine.mqh`
- Create: `ZoneIndicators/MQL5/Include/SMC_ZonesInd/SMC_ZonesPanel.mqh`
- Create: `ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/SMC_ZonesInd_TestRunner.mq5`

**Step 1: Dispatch the MQL5 Indicator Builder agent**

Give it, verbatim:
- Section 4.1 of the design spec (SMC bidirectional methodology table +
  confluence rule).
- Section 5 (data flow), Section 6 (panel spec), Section 7 (alerts),
  Section 8 (error-handling lessons) from the same spec.
- The folder layout and include convention from this plan's header (angle
  bracket includes resolved against `ZoneIndicators\MQL5`).
- The contract of `ZI_Common.mqh` from Task 1 (`#include
  <ZoneIndicators\ZI_Common.mqh>`, use `ZI_Zone`/`ZI_Alert`, do not redefine).
- The mined patterns for OB/FVG/sweep from Task 2's `mined-patterns.md`.
- Explicit instruction: build engine header + panel header + main indicator
  `.mq5` + an EA-based `SMC_ZonesInd_TestRunner.mq5` under
  `Experts/ZoneIndicators_Tests/` (pattern:
  `GridFib_EA/Experts/GridFib/GridFib_TestRunner.mq5` — read it directly as
  reference) asserting zone detection, mitigation, panel toggle visibility,
  and alert-condition firing, runnable headless in Strategy Tester.
- Target: compile 0 errors / 0 warnings, all test-runner asserts pass.

**Step 2: Verify compile output**

Run: `.\ZoneIndicators\tools\build.ps1 -Target SMC_ZonesInd`
Expected: `0 errors, 0 warnings` in the log for the indicator, its engine
header, its panel header, and the test runner.

**Step 3: Run the headless test runner in Strategy Tester**

Follow the same invocation pattern used for `GridFib_TestRunner.mq5`
(`.ini`-driven headless Strategy Tester run against the EA). Expected: all
assertions PASS (log tail shows assertion count and 0 failures).

**Step 4: Fix any compile errors or failing asserts, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/MQL5/Indicators/SMC_ZonesInd ZoneIndicators/MQL5/Include/SMC_ZonesInd ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/SMC_ZonesInd_TestRunner.mq5
git commit -m "feat(zone-indicators): add SMC_ZonesInd bidirectional order-block/FVG/sweep indicator"
```

---

### Task 4: Build CRT_ZonesInd (Candle Range Theory)

**Files:**
- Create: `ZoneIndicators/MQL5/Indicators/CRT_ZonesInd/CRT_ZonesInd.mq5`
- Create: `ZoneIndicators/MQL5/Include/CRT_ZonesInd/CRT_ZonesEngine.mqh`
- Create: `ZoneIndicators/MQL5/Include/CRT_ZonesInd/CRT_ZonesPanel.mqh`
- Create: `ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/CRT_ZonesInd_TestRunner.mq5`

**Step 1: Dispatch the MQL5 Indicator Builder agent**

Same pattern as Task 3 (folder layout, include convention, `ZI_Common.mqh`
contract, EA-based test-runner requirement under
`Experts/ZoneIndicators_Tests/`), but with:
- Design spec Section 4.2 (CRT methodology: reference range, manipulation
  sweep, distribution/reingreso confirmation, buy/sell zone rules, ATR/point
  strength filter).
- The CRT prompt maestro / transcribed book material already in memory
  (`project_candle_range_theory`) as additional grounding — have the
  builder agent consult it if the mined-patterns doc doesn't fully cover
  session-range sweep logic.
- Same panel/alert/error-handling sections (5-8) from the spec.

**Step 2: Verify compile output**

Run: `.\ZoneIndicators\tools\build.ps1 -Target CRT_ZonesInd`
Expected: `0 errors, 0 warnings`.

**Step 3: Run the headless test runner**

Expected: all assertions PASS.

**Step 4: Fix any issues, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/MQL5/Indicators/CRT_ZonesInd ZoneIndicators/MQL5/Include/CRT_ZonesInd ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/CRT_ZonesInd_TestRunner.mq5
git commit -m "feat(zone-indicators): add CRT_ZonesInd session-range sweep/reversal indicator"
```

---

### Task 5: Build VWAP_ZonesInd (VWAP + volume exhaustion)

**Files:**
- Create: `ZoneIndicators/MQL5/Indicators/VWAP_ZonesInd/VWAP_ZonesInd.mq5`
- Create: `ZoneIndicators/MQL5/Include/VWAP_ZonesInd/VWAP_ZonesEngine.mqh`
- Create: `ZoneIndicators/MQL5/Include/VWAP_ZonesInd/VWAP_ZonesPanel.mqh`
- Create: `ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/VWAP_ZonesInd_TestRunner.mq5`

**Step 1: Dispatch the MQL5 Indicator Builder agent**

Same pattern as Tasks 3-4 (folder layout, include convention,
`ZI_Common.mqh` contract, EA-based test-runner requirement), but with:
- Design spec Section 4.3 (VWAP + bands + volume-exhaustion methodology,
  including the `VOLUME_TICK` vs `VOLUME_REAL` fallback note).
- Explicit reminder: indicator handles for any internal `iMA`/`iStdDev`
  (if used instead of manual VWAP math) must be created once in `OnInit`
  and validated for `INVALID_HANDLE` — never created/released per tick
  (this is a previously-hit bug, see spec Section 8).
- Same panel/alert/error-handling/testing requirements.

**Step 2: Verify compile output**

Run: `.\ZoneIndicators\tools\build.ps1 -Target VWAP_ZonesInd`
Expected: `0 errors, 0 warnings`.

**Step 3: Run the headless test runner**

Expected: all assertions PASS.

**Step 4: Fix any issues, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/MQL5/Indicators/VWAP_ZonesInd ZoneIndicators/MQL5/Include/VWAP_ZonesInd ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/VWAP_ZonesInd_TestRunner.mq5
git commit -m "feat(zone-indicators): add VWAP_ZonesInd deviation-band volume-exhaustion indicator"
```

---

### Task 6: Full-suite build, deploy to D4CE, and documentation

**Files:**
- Modify: `ZoneIndicators/tools/build.ps1`, `ZoneIndicators/tools/deploy.ps1` (only if Tasks 3-5 surfaced gaps — see Step 1)
- Create: `Vault/Proyectos/ZoneIndicators.md`
- Modify: `Vault/Diario/2026-09-22.md` (create from template if absent)

**Step 1: Run the full build across all three indicators**

Run: `.\ZoneIndicators\tools\build.ps1` (no `-Target`, builds all three plus
`Common`)
Expected: `0 errors, 0 warnings` across all compile logs. If this reveals a
gap in `build.ps1`/`deploy.ps1` (e.g. a target missed by the `-Target`
filter logic from Task 1), fix it here and note the fix in the commit
message.

**Step 2: Deploy the full bundle to demo terminal D4CE only**

Run: `.\ZoneIndicators\tools\deploy.ps1 -DataFolder D4CEFEDAF043B05DA80223FD698C7DF2`
(same demo terminal ID used for GridFib/SMC deployments per
`reference_mt5_terminals` memory). Confirm the script's forbidden-list still
blocks the two prop-firm terminal IDs and does **not** touch D0E8.

**Step 3: Write the Obsidian project note**

Create `Vault/Proyectos/ZoneIndicators.md` from
`Vault/Plantillas/Plantilla-Proyecto.md`, summarizing: the three indicators,
their methodologies, panel/alert features, test results, and the pending
next step (user must attach each indicator on a demo chart and visually
validate zone drawing before any further step).

**Step 4: Update the daily log**

Add a line to `Vault/Diario/2026-09-22.md` linking `[[ZoneIndicators]]`.

**Step 5: Commit**

```bash
git add ZoneIndicators/tools
git commit -m "feat(zone-indicators): finalize build/deploy tooling for full suite, deploy to D4CE demo"
```

(Vault files are outside the git repo per project convention — commit only
if they happen to be tracked; otherwise just write them.)

**Step 6: Store the durable lesson(s) in Memanto, if any new invariant was hit**

Only if Tasks 3-5 surfaced a genuinely new MQL5 gotcha (not already covered
by the existing memories referenced in Section 8 of the spec) — run
`memanto remember` with `--type learning`, full metadata flags, following
the `memanto-memory` skill schema. Do not store routine build/test activity.

---

## Post-plan manual validation (user, not automated)

1. Open the D4CE demo terminal, attach each of the three indicators to a
   chart (any symbol/timeframe).
2. Visually confirm zones draw correctly and the panel toggles work.
3. Confirm alerts fire (push/sound) when a zone forms.
4. Only after this manual check, decide whether any indicator should also
   go to a real-money terminal — that requires a fresh, explicit request.
