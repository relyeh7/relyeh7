# Zone Indicators MTF Signal Arrows Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a per-timeframe (M1/M5/M15/H1/H4/D1) buy/sell arrow row to each of the 3 existing Zone Indicators' panels, reusing each indicator's own detection engine — no new detection logic.

**Architecture:** One new file per indicator (`*_ZonesMTF.mqh`) that, on an `OnTimer` cadence, runs a throwaway instance of that indicator's own engine class against `CopyRates()`-fetched history for each of the 6 timeframes, then exposes a `Signal(tf_index)` the panel reads to draw a colored arrow cell. No indicator handles, no shared code between the 3 indicators (matches the established no-shared-engine-logic precedent).

**Tech Stack:** MQL5, same build/deploy tooling and EA test-runner pattern already in place.

**Design spec:** `docs/superpowers/specs/2026-09-23-zone-indicators-mtf-signals-design.md` — read this first.

**Repo layout note:** same as the base-suite plan — this plan runs inside the `zone-indicators` git worktree; paths below are relative to `Dev-Drive/` inside it, not the worktree's git toplevel.

---

### Task 1: SMC_ZonesInd MTF signal row

**Files:**
- Create: `ZoneIndicators/MQL5/Include/SMC_ZonesInd/SMC_ZonesMTF.mqh`
- Modify: `ZoneIndicators/MQL5/Include/SMC_ZonesInd/SMC_ZonesPanel.mqh`
- Modify: `ZoneIndicators/MQL5/Indicators/SMC_ZonesInd/SMC_ZonesInd.mq5`
- Modify: `ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/SMC_ZonesInd_TestRunner.mq5`

**Step 1: Dispatch the MQL5 Indicator Builder agent**

Give it, verbatim:
- The full design spec (`2026-09-23-zone-indicators-mtf-signals-design.md`), all sections.
- Read `SMC_ZonesEngine.mqh` directly — the engine class to reuse as-is, not modify.
- Explicit instruction: `SMC_ZonesMTF.mqh` defines `enum ENUM_ZI_MTF_SIGNAL {ZI_MTF_NONE, ZI_MTF_BUY, ZI_MTF_SELL}` and a `CSMCZonesMTFScanner` class with `ScanAll(symbol, lookback_bars)` and `Signal(tf_index)` (0..5 = M1,M5,M15,H1,H4,D1), per spec §3.
- `SMC_ZonesInd.mq5` gains (or extends) `OnTimer()`, firing `ScanAll()` every `InpMTFRefreshSeconds` (default 10, new input), and the panel reads `Signal()` for its 6 cells.
- `SMC_ZonesPanel.mqh` gains a new "MTF SIGNALS" row (6 cells, colored per spec §5) and a "Show MTF Row" checkbox toggle, independent of existing layer toggles.
- New input `InpMTFLookbackBars` (default 300).
- Test runner: 3 new asserts per spec §6 (signal classification correct on synthetic bars, A+ priority over normal zone, refresh-interval respected).
- Target: compile 0/0, all test-runner asserts (existing 53 + new ones) pass in the real headless Strategy Tester.

**Step 2: Verify compile output**

Run: `.\ZoneIndicators\tools\build.ps1 -Target SMC_ZonesInd`
Expected: `0 errors, 0 warnings`.

**Step 3: Run the headless test runner in Strategy Tester**

Expected: all assertions PASS, including the new MTF ones.

**Step 4: Fix any compile errors or failing asserts, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/MQL5/Include/SMC_ZonesInd ZoneIndicators/MQL5/Indicators/SMC_ZonesInd ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/SMC_ZonesInd_TestRunner.mq5
git commit -m "feat(zone-indicators): add MTF buy/sell signal row to SMC_ZonesInd panel"
```

---

### Task 2: CRT_ZonesInd MTF signal row

**Files:**
- Create: `ZoneIndicators/MQL5/Include/CRT_ZonesInd/CRT_ZonesMTF.mqh`
- Modify: `ZoneIndicators/MQL5/Include/CRT_ZonesInd/CRT_ZonesPanel.mqh`
- Modify: `ZoneIndicators/MQL5/Indicators/CRT_ZonesInd/CRT_ZonesInd.mq5`
- Modify: `ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/CRT_ZonesInd_TestRunner.mq5`

Same pattern as Task 1, targeting `CCRTZonesEngine` instead. Note: CRT's engine already has a live-reconfigurable range mode (`ResetRangeMode`) — the MTF scanner's throwaway engine instances must NOT share state with the main chart's engine instance; each per-timeframe scan gets its own fresh engine object, configured independently (e.g. same `InpRangeMode` input applied to each temporary scan instance, unless the design intent is for each timeframe to use its own natural session/daily boundary regardless of the main panel's live range-mode setting — if ambiguous, the builder should ask rather than guess).

**Step 1: Dispatch the MQL5 Indicator Builder agent** (same content shape as Task 1, adapted to CRT)

**Step 2: Verify compile output** — `.\ZoneIndicators\tools\build.ps1 -Target CRT_ZonesInd`, expect 0/0.

**Step 3: Run the headless test runner** — expect all PASS (60 existing + new).

**Step 4: Fix any issues, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/MQL5/Include/CRT_ZonesInd ZoneIndicators/MQL5/Indicators/CRT_ZonesInd ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/CRT_ZonesInd_TestRunner.mq5
git commit -m "feat(zone-indicators): add MTF buy/sell signal row to CRT_ZonesInd panel"
```

---

### Task 3: VWAP_ZonesInd MTF signal row

**Files:**
- Create: `ZoneIndicators/MQL5/Include/VWAP_ZonesInd/VWAP_ZonesMTF.mqh`
- Modify: `ZoneIndicators/MQL5/Include/VWAP_ZonesInd/VWAP_ZonesPanel.mqh`
- Modify: `ZoneIndicators/MQL5/Indicators/VWAP_ZonesInd/VWAP_ZonesInd.mq5`
- Modify: `ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/VWAP_ZonesInd_TestRunner.mq5`

Same pattern as Tasks 1-2, targeting `CVWAPZonesEngine`. Note: VWAP resets its accumulators daily per-session — each per-timeframe scan's throwaway engine instance needs enough lookback (`InpMTFLookbackBars`, default 300) to cover at least one full session on the coarser timeframes (H4/D1) for a meaningful VWAP/band state; on D1 in particular, confirm with the spec's intent (session VWAP on a Daily chart is somewhat degenerate — if this is a real ambiguity, the builder should flag it rather than silently picking an interpretation).

**Step 1: Dispatch the MQL5 Indicator Builder agent** (same content shape, adapted to VWAP)

**Step 2: Verify compile output** — `.\ZoneIndicators\tools\build.ps1 -Target VWAP_ZonesInd`, expect 0/0.

**Step 3: Run the headless test runner** — expect all PASS (60 existing + new).

**Step 4: Fix any issues, re-run Steps 2-3**

**Step 5: Commit**

```bash
git add ZoneIndicators/MQL5/Include/VWAP_ZonesInd ZoneIndicators/MQL5/Indicators/VWAP_ZonesInd ZoneIndicators/MQL5/Experts/ZoneIndicators_Tests/VWAP_ZonesInd_TestRunner.mq5
git commit -m "feat(zone-indicators): add MTF buy/sell signal row to VWAP_ZonesInd panel"
```

---

### Task 4: Full-suite rebuild, redeploy, and documentation

**Files:**
- Modify: `Vault/Proyectos/ZoneIndicators.md` (external, not in this git repo — same convention as the base-suite plan's Task 6)
- Modify: `Vault/Diario/<today>.md`

**Step 1: Run the full build across all three indicators**

Run: `.\ZoneIndicators\tools\build.ps1` (no `-Target`)
Expected: `0 errors, 0 warnings` across all 6 compile targets.

**Step 2: Deploy the full bundle to demo terminal D4CE only**

Run: `.\ZoneIndicators\tools\deploy.ps1 -DataFolder D4CEFEDAF043B05DA80223FD698C7DF2`
D0E8 (or any other terminal) only if the user explicitly asks again — do not deploy there by default even though it was done once before for the base suite.

**Step 3: Update the Vault project note**

Append a new `## Sesión 2026-09-23` section to `Vault/Proyectos/ZoneIndicators.md` describing the MTF signal row addition, test results, and that the previous "pending manual validation" note now also covers the new MTF row (arrows visible, colors correct, toggle works).

**Step 4: Update the daily log**

Add a line to `Vault/Diario/<today>.md` linking `[[ZoneIndicators]]` if not already referencing today's work.

**Step 5: Commit**

```bash
git add ZoneIndicators/tools  # only if anything there needed changes (unlikely)
git commit -m "feat(zone-indicators): rebuild/redeploy full suite with MTF signal arrows"
```
(Skip the commit if `tools/*.ps1` needed no changes — say so instead, same convention as the base plan's Task 6.)

---

## Post-plan manual validation (user, not automated)

1. Open the D4CE demo terminal (or wherever the user is testing), reattach each of
   the 3 indicators (or just let the already-attached ones reload after
   recompiling).
2. Confirm the new MTF row appears in each panel, with 6 correctly colored
   cells (green/red/gray) that visually match what each indicator's own zones
   say on that timeframe.
3. Confirm the "Show MTF Row" toggle works independently of other layer toggles.
4. Confirm the row updates roughly every `InpMTFRefreshSeconds` (default 10s),
   not instantly and not never.
