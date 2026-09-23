# Zone Indicators Suite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build three independent, bidirectional MQL5 indicators (SMC, Candle Range Theory, VWAP+volume) that detect buy/sell zones on any symbol/timeframe, each with a full interactive panel and alerts, deployed to demo terminal D4CE.

**Architecture:** Three standalone indicator projects under `H:\Dev-Drive\ZoneIndicators\`, sharing only a minimal `Common\ZI_Common.mqh` (zone struct + alert helper), each built from scratch by the **MQL5 Indicator Builder** agent grounded in patterns verified by the **MQL5 Article Miner** corpus (`series_catalog.md`) and the official MQL5 docs corpus.

**Tech Stack:** MQL5 (MetaEditor / metaeditor64 CLI), MT5 Strategy Tester (headless test runners), PowerShell build/deploy tooling (pattern from `GridFib_EA/tools/`).

**Design spec:** `docs/superpowers/specs/2026-09-22-zone-indicators-suite-design.md` — read this first for full rationale; this plan only restates what's needed to execute.

---

### Task 1: Project scaffolding + shared common module

**Files:**
- Create: `ZoneIndicators/Common/ZI_Common.mqh`
- Create: `ZoneIndicators/tools/compile.ps1`
- Create: `ZoneIndicators/tools/build.ps1`
- Create: `ZoneIndicators/tools/deploy.ps1`
- Create (empty, with `.gitkeep` or first real file in Task 3-5): `ZoneIndicators/SMC_ZonesInd/`, `ZoneIndicators/CRT_ZonesInd/`, `ZoneIndicators/VWAP_ZonesInd/`

**Step 1: Create folder structure**

```powershell
New-Item -ItemType Directory -Force -Path `
  "H:\Dev-Drive\ZoneIndicators\Common", `
  "H:\Dev-Drive\ZoneIndicators\SMC_ZonesInd\Tests", `
  "H:\Dev-Drive\ZoneIndicators\CRT_ZonesInd\Tests", `
  "H:\Dev-Drive\ZoneIndicators\VWAP_ZonesInd\Tests", `
  "H:\Dev-Drive\ZoneIndicators\tools", `
  "H:\Dev-Drive\ZoneIndicators\docs"
```

**Step 2: Write `ZI_Common.mqh`**

Contents (adapt exact MQL5 syntax against the docs corpus, but this is the
contract every engine/panel must use):

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

`ZI_Common.mqh` has no `OnCalculate`, so verify it via a throwaway one-line
test indicator that just `#include`s it and compiles 0/0. Delete the
throwaway file after confirming.

**Step 4: Write `tools/compile.ps1`, `tools/build.ps1`, `tools/deploy.ps1`**

Copy the pattern from `H:\Dev-Drive\GridFib_EA\tools\build.ps1` and
`deploy.ps1` (referenced in memory: `project_gridfib_ea` — these already
handle metaeditor64 compilation and demo-terminal-only deploy with the
prop-firm/D0E8 safeguard list). Adjust paths to point at
`ZoneIndicators\*\*.mq5` instead of `GridFib_EA\*`. Keep the same D0E8
exclusion safeguard — do not weaken it.

**Step 5: Commit**

```bash
git add ZoneIndicators/Common ZoneIndicators/tools
git commit -m "feat(zone-indicators): scaffold project structure and shared ZI_Common.mqh"
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
- Create: `ZoneIndicators/SMC_ZonesInd/SMC_ZonesInd.mq5`
- Create: `ZoneIndicators/SMC_ZonesInd/SMC_ZonesEngine.mqh`
- Create: `ZoneIndicators/SMC_ZonesInd/SMC_ZonesPanel.mqh`
- Create: `ZoneIndicators/SMC_ZonesInd/Tests/SMC_ZonesInd_TestRunner.mq5`

**Step 1: Dispatch the MQL5 Indicator Builder agent**

Give it, verbatim:
- Section 4.1 of the design spec (SMC bidirectional methodology table +
  confluence rule).
- Section 5 (data flow), Section 6 (panel spec), Section 7 (alerts),
  Section 8 (error-handling lessons) from the same spec.
- The contract of `ZI_Common.mqh` from Task 1 (must `#include` it, use
  `ZI_Zone`/`ZI_Alert`, not redefine its own).
- The mined patterns for OB/FVG/sweep from Task 2's `mined-patterns.md`.
- Explicit instruction: build engine + panel + main indicator + a
  `Tests/SMC_ZonesInd_TestRunner.mq5` headless test runner (pattern:
  `GridFib_EA/Tests/GridFib_TestRunner.mq5`) asserting zone detection,
  mitigation, panel toggle visibility, and alert-condition firing.
- Target: compile 0 errors / 0 warnings, all test-runner asserts pass.

**Step 2: Verify compile output**

Run: `.\ZoneIndicators\tools\compile.ps1 -Target SMC_ZonesInd`
Expected: `0 errors, 0 warnings` in the log for the indicator, its engine
header, its panel header, and the test runner.

**Step 3: Run the headless test runner in Strategy Tester**

Follow the same invocation pattern used for `GridFib_TestRunner.mq5` /
`Test_GridFib.mq5` (script-based or `.ini`-driven Strategy Tester run).
Expected: all assertions PASS (log tail shows assertion count and 0
failures).

**Step 4: Fix any compile errors or failing asserts, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/SMC_ZonesInd
git commit -m "feat(zone-indicators): add SMC_ZonesInd bidirectional order-block/FVG/sweep indicator"
```

---

### Task 4: Build CRT_ZonesInd (Candle Range Theory)

**Files:**
- Create: `ZoneIndicators/CRT_ZonesInd/CRT_ZonesInd.mq5`
- Create: `ZoneIndicators/CRT_ZonesInd/CRT_ZonesEngine.mqh`
- Create: `ZoneIndicators/CRT_ZonesInd/CRT_ZonesPanel.mqh`
- Create: `ZoneIndicators/CRT_ZonesInd/Tests/CRT_ZonesInd_TestRunner.mq5`

**Step 1: Dispatch the MQL5 Indicator Builder agent**

Same pattern as Task 3, but with:
- Design spec Section 4.2 (CRT methodology: reference range, manipulation
  sweep, distribution/reingreso confirmation, buy/sell zone rules, ATR/point
  strength filter).
- The CRT prompt maestro / transcribed book material already in memory
  (`project_candle_range_theory`) as additional grounding — have the
  builder agent consult it if the mined-patterns doc doesn't fully cover
  session-range sweep logic.
- Same `ZI_Common.mqh` contract, same panel/alert/error-handling sections
  (5-8) from the spec, same test-runner requirement.

**Step 2: Verify compile output**

Run: `.\ZoneIndicators\tools\compile.ps1 -Target CRT_ZonesInd`
Expected: `0 errors, 0 warnings`.

**Step 3: Run the headless test runner**

Expected: all assertions PASS.

**Step 4: Fix any issues, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/CRT_ZonesInd
git commit -m "feat(zone-indicators): add CRT_ZonesInd session-range sweep/reversal indicator"
```

---

### Task 5: Build VWAP_ZonesInd (VWAP + volume exhaustion)

**Files:**
- Create: `ZoneIndicators/VWAP_ZonesInd/VWAP_ZonesInd.mq5`
- Create: `ZoneIndicators/VWAP_ZonesInd/VWAP_ZonesEngine.mqh`
- Create: `ZoneIndicators/VWAP_ZonesInd/VWAP_ZonesPanel.mqh`
- Create: `ZoneIndicators/VWAP_ZonesInd/Tests/VWAP_ZonesInd_TestRunner.mq5`

**Step 1: Dispatch the MQL5 Indicator Builder agent**

Same pattern as Tasks 3-4, but with:
- Design spec Section 4.3 (VWAP + bands + volume-exhaustion methodology,
  including the `VOLUME_TICK` vs `VOLUME_REAL` fallback note).
- Explicit reminder: indicator handles for any internal `iMA`/`iStdDev`
  (if used instead of manual VWAP math) must be created once in `OnInit`
  and validated for `INVALID_HANDLE` — never created/released per tick
  (this is a previously-hit bug, see spec Section 8).
- Same `ZI_Common.mqh` contract, panel/alert/error-handling/testing
  requirements.

**Step 2: Verify compile output**

Run: `.\ZoneIndicators\tools\compile.ps1 -Target VWAP_ZonesInd`
Expected: `0 errors, 0 warnings`.

**Step 3: Run the headless test runner**

Expected: all assertions PASS.

**Step 4: Fix any issues, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/VWAP_ZonesInd
git commit -m "feat(zone-indicators): add VWAP_ZonesInd deviation-band volume-exhaustion indicator"
```

---

### Task 6: Full-suite build, deploy to D4CE, and documentation

**Files:**
- Modify: `ZoneIndicators/tools/build.ps1`, `ZoneIndicators/tools/deploy.ps1`
- Create: `Vault/Proyectos/ZoneIndicators.md`
- Modify: `Vault/Diario/2026-09-22.md` (create from template if absent)

**Step 1: Run the full build across all three indicators**

Run: `.\ZoneIndicators\tools\build.ps1` (no `-Target`, builds all three plus
`Common`)
Expected: `0 errors, 0 warnings` across all compile logs.

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
