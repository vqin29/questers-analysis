# Phase 0: Team OKR Overview - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Phase 0 team-level OKR snapshot showing 30-day quota attainment before existing weekly analysis phases.

**Architecture:** Extend existing MCP resources and prompts to include Phase 0. Add new resource constant with SQL query and documentation, update questers_report prompt to run Phase 0 first, update README to reflect 4-phase framework.

**Tech Stack:** Python 3, FastMCP, BigQuery

---

## Task 1: Add Phase 0 Resource Constant

**Files:**
- Modify: `resources.py:992-1029` (add new constant before register function)

**Step 1: Add PHASE0_TEAM_OKR constant**

Add this constant after the `QUEST_ALERTS_ENHANCED` constant (around line 991):

```python
PHASE0_TEAM_OKR = """# Phase 0: Team OKR Overview

## Purpose
Show team-level portfolio health via 30-day rolling quota attainment before weekly trend analysis.

This answers: "What % of our active games are meeting their monthly gameplay quotas?"

## Metric Definition

**Quota Attainment** = `actual_questers_30d / monthly_gameplay_target * 100`

- **30-day rolling window:** COUNT(DISTINCT visitor_id) for last 30 days
- **Monthly target:** From `game.monthly_gameplay_target` column
- **Meeting quota:** actual >= target (100%+)

## Required Filters (ALWAYS APPLY)

Same as other phases, plus:
```sql
WHERE e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
  AND g.plan_name != 'Maintenance'  -- Exclude Maintenance tier
  AND g.active_subscription = TRUE  -- Only active subscriptions
  AND g.monthly_gameplay_target IS NOT NULL  -- Only games with targets set
```

## Output Format

### Overall Summary
```
📊 PHASE 0: TEAM OKR SNAPSHOT (Last 30 Days)

Overall Quota Attainment: 14/22 games (64%) meeting monthly target
```

### Tier Breakdown
```
Tier Breakdown:
- Ultra Boost: 3/4 games (75%) meeting quota
- Boost: 5/8 games (63%) meeting quota
- Core: 6/10 games (60%) meeting quota
```

### Below-Quota Games (Table)
**ONLY show games with actual < target (below 100%)**

```
⚠️ Games Below Quota (8 games):

| Game | Tier | AM | Actual (30d) | Target | % of Quota | Gap | # Gameplay Quests |
|------|------|-----|--------------|--------|------------|-----|-------------------|
| Game C | Core | Alice | 3,200 | 5,000 | 64% | -1,800 | 3 |
```

Sort by % of Quota ascending (worst performers first).

### Separator
```
────────────────────────────────────────────
```

Then continue to Phase 1.

## Reference SQL Query

```sql
WITH last_30d_questers AS (
  -- Calculate distinct gameplay questers per game (last 30 days)
  SELECT 
    g.game_name,
    g.plan_name as tier,
    g.account_manager_name as am,
    g.monthly_gameplay_target as target,
    COUNT(DISTINCT e.visitor_id) as actual_questers_30d,
    COUNT(DISTINCT q.quest_id) as gameplay_quests
  FROM `app_immutable_play.event` e
  INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
  LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
  LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
  LEFT JOIN UNNEST(q.quest_category) AS category
  WHERE 
    e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
    AND v.is_front_end_cohort = TRUE
    AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
    AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
    AND g.plan_name != 'Maintenance'
    AND g.active_subscription = TRUE
    AND category LIKE '%gameplay%'
    AND g.monthly_gameplay_target IS NOT NULL  -- Only games with targets
  GROUP BY 1,2,3,4
),

quota_status AS (
  SELECT 
    game_name,
    tier,
    am,
    actual_questers_30d,
    target,
    ROUND(100.0 * actual_questers_30d / NULLIF(target, 0), 1) as pct_of_quota,
    actual_questers_30d - target as gap,
    gameplay_quests,
    CASE 
      WHEN actual_questers_30d >= target THEN 1 
      ELSE 0 
    END as meeting_quota
  FROM last_30d_questers
)

-- For overall summary:
SELECT 
  SUM(meeting_quota) as games_meeting_quota,
  COUNT(*) as total_games,
  ROUND(100.0 * SUM(meeting_quota) / COUNT(*), 1) as pct_meeting
FROM quota_status;

-- For tier breakdown:
SELECT 
  tier,
  SUM(meeting_quota) as games_meeting_quota,
  COUNT(*) as total_games,
  ROUND(100.0 * SUM(meeting_quota) / COUNT(*), 1) as pct_meeting
FROM quota_status
GROUP BY tier
ORDER BY 
  CASE tier
    WHEN 'Ultra Boost' THEN 1
    WHEN 'Boost' THEN 2
    WHEN 'Core' THEN 3
  END;

-- For below-quota table:
SELECT 
  game_name,
  tier,
  COALESCE(am, 'Unassigned') as am,
  actual_questers_30d,
  target,
  pct_of_quota,
  gap,
  gameplay_quests
FROM quota_status
WHERE meeting_quota = 0  -- Only games below quota
ORDER BY pct_of_quota ASC, tier, game_name;
```

## Edge Cases

### Missing Quota Data
If `monthly_gameplay_target IS NULL`:
- Exclude from Phase 0 analysis
- Count excluded games and note in output: "(X games excluded - no quota set)"

### Zero Questers
If game has 0 questers in last 30 days:
- Include in below-quota table
- Show as "0%" of quota
- Consider flagging as potentially inactive

### New Games
If game created <30 days ago:
- Still include (uses available data)
- May show low % if ramping up
- Consider adding "Days Active" column for context
"""
```

**Step 2: Verify indentation and placement**

- Ensure the constant is at module level (not indented inside a function)
- It should be after `QUEST_ALERTS_ENHANCED` and before the `register()` function

**Step 3: Commit**

```bash
git add resources.py
git commit -m "feat(phase0): add team OKR resource constant"
```

---

## Task 2: Register Phase 0 Resource

**Files:**
- Modify: `resources.py:1026` (inside register function, after quest_alerts_enhanced resource)

**Step 1: Add resource registration**

Add this after the `get_quest_alerts_enhanced` function (around line 1028):

```python
    @mcp.resource("questers://context/phase0_team_okr")
    def get_phase0_team_okr() -> str:
        """Phase 0: Team-level OKR snapshot showing 30-day quota attainment"""
        return PHASE0_TEAM_OKR
```

**Step 2: Verify the registration**

Check that:
- Decorator is `@mcp.resource()` with correct URI
- Function name is descriptive
- Docstring explains what it returns
- Returns the constant we created in Task 1

**Step 3: Commit**

```bash
git add resources.py
git commit -m "feat(phase0): register team OKR resource in MCP"
```

---

## Task 3: Update questers_report Prompt

**Files:**
- Modify: `prompts.py:9-158` (update questers_report function)

**Step 1: Add Phase 0 instructions at the top**

Replace the current `questers_report()` function starting at line 10. Insert Phase 0 section right after the docstring:

```python
    @mcp.prompt()
    def questers_report() -> str:
        """
        Standard weekly gameplay questers report.
        Use this whenever asked about "questers".
        """
        return """Generate a weekly gameplay questers report, then investigate.

## Required Filters (ALWAYS APPLY)
- v.is_front_end_cohort = TRUE
- Exclude employees (is_immutable_employee = FALSE)
- Exclude 'Guild of Guardians' and 'Gods Unchained'
- Exclude Maintenance tier (plan_name != 'Maintenance')
- Only active subscriptions (active_subscription = TRUE)

## Phase 0: Team OKR Snapshot (ALWAYS RUN FIRST)

Read the `questers://context/phase0_team_okr` resource for full documentation.

### Instructions
1. Query 30-day gameplay questers with monthly quotas
2. Present overall summary: "X/Y games (Z%) meeting monthly target"
3. Present tier breakdown (Ultra Boost, Boost, Core)
4. Present table of games BELOW quota only (actual < target)
   - Include: Game, Tier, AM, Actual (30d), Target, % of Quota, Gap, # Gameplay Quests
   - Sort by % of Quota ascending (worst first)
5. Add separator line: `────────────────────────────────────────────`

### Time Window
Use last 30 days: `e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))`

### Filters
Apply ALL standard filters PLUS:
- `g.monthly_gameplay_target IS NOT NULL` (only games with targets set)

────────────────────────────────────────────

## Phase 1: Present the Numbers (Last 2 Complete Weeks)

Compare last 2 COMPLETE weeks (Mon-Sun UTC) - exclude current week

### 1. Overall Total
Total distinct gameplay questers (users can quest across multiple games).
**NEVER sum per-game totals** - calculate overall separately.

### 2. Per-Game Breakdown
| Game | Tier | AM | Curr Questers | Prev Questers | WoW | WoW% | # Quests (Curr/Prev) | Bot% |
|------|------|-----|---------------|---------------|-----|------|----------------------|------|

## Phase 2: Decomposition (ALWAYS use this format)
Run the full decomposition model to explain WHY questers changed.
Query per-game WoW totals with bot/human breakdown, then present:

### 2a. Headline
One bold sentence summarizing the delta AND the quality story (bot vs human shift).
Include a summary table:
| | Prev Week | Curr Week | Delta | % Change |
|--|-----------|-----------|-------|----------|
| Total Questers | | | | |
| Human Questers | | | | |
| Bot Questers | | | | |
| Bot % | | | | -Xpp |

### 2b. Decomposition Tree
Classify every game into exactly ONE bucket and present as a tree:

```
Total Δ: +X,XXX (+X.X%)

  + New Games:              +X,XXX
      └─ Game A   +X,XXX  (X% bots ⚠️/✓)

  - Discontinued / Off:    -X,XXX  (X% were bots)
      └─ Game B   -X,XXX  (was X% bots)

  + Continuing Games:      +X,XXX  (net)
      Bots:   -X,XXX   ← [context]
      Humans: +X,XXX   ← [context]

      Growth:
        └─ Game C  +X,XXX  (humans +X, bots +X ⚠️/✓)
      Decline:
        └─ Game D  -X,XXX  (bots -X, humans +X ✓)

  ──────────────────────────────────────
  Note: Per-game sums ≠ overall total due to multi-game users.
```

**IMPORTANT — Bucket classification rules:**
- **New Games**: prev_users = 0, curr_users > 0
- **Discontinued / Off**: prev_users > 0, curr_users = 0
  **ALSO include games that the user or team confirms have been turned off
  or set to inactive, even if they have small residual activity in curr week.**
  A game that dropped >95% of questers AND is known to be turned off should
  be reclassified from Continuing to Discontinued.
- **Continuing**: all other games active both weeks

### 2c. PM Narrative
Write 3-5 numbered key narratives, each 1-2 sentences. Focus on:
1. Overall ecosystem health (bot % shift, human growth)
2. The biggest single mover and why
3. Discontinued games — were they low quality? Was this a healthy cleanup?
4. New game launches — early bot % warning?
5. Continuing games — is the human growth real and broad-based?

### 2d. Games to Watch
| Game | Signal | Risk |
|------|--------|------|
| ... | ... | ... |

Flag any game with: new launch + high bot%, sudden bot spike,
or large unexplained quester swing.

## Phase 3: Quest-Level Audit (MANDATORY — STOP AND ASK)

After presenting the decomposition, you MUST pause and ask the user:

"Would you like a **quest-level audit** to see which specific quests are
driving these changes and identify any issues?

I can run an enhanced quest audit that shows:
  - 🔴 Broken quests (sudden drop-offs)
  - 🔴 Bot-farmed quests (high bot %, excessive completions/user)
  - 📉 Declining quests (trending downwards)
  - ⚠️ Engagement issues

The audit covers **all active games** with automated alert flags.

Or if you'd prefer a different angle:
  - Simple quest completions (last 3 days, no alerts)
  - Bot activity spike or cleanup analysis?
  - Multi-week trend?
  - User overlap between games?"

**WAIT for the user to respond before running any queries.**

### If user wants quest-level audit (recommended):
1. Read the `questers://context/quest_alerts_enhanced` resource for the full SQL query
2. Run the enhanced quest audit query (covers last 30 days with alert flags)
3. Present results in priority order (Critical → High → Medium → Low):

**Critical Alerts (🔴 Priority 1-2):**
| Game | Quest Name | Alert Flag | Alert Message | Bot % | Completions/User |
|------|-----------|------------|---------------|-------|------------------|

**Medium Alerts (🟡 Priority 3):**
| Game | Quest Name | Alert Flag | Alert Message | Activity Drop % | 7d Trend |
|------|-----------|------------|---------------|-----------------|----------|

4. Summarize key findings and recommend actions
5. After presenting, ask: "Any specific quests you want to investigate further?"

### If user wants simple quest completions (no alerts):
1. Read the `questers://context/quest_completions` resource for the reference query
2. Query quest completions for the last 3 days
3. Present grouped by game, sorted by completions

### If user specifies a specific game:
Filter the audit query to that game only using `WHERE game_name = 'GameName'`.

## Phase 4: Investigate (only after user responds)
Based on user direction, run targeted follow-up queries.
Report back and ask if they want to dig deeper.

## Instructions
1. Read resources for definitions, required filters, and decomposition model
2. Run Phase 0 FIRST (30-day quota snapshot)
3. Query overall distinct gameplay questers with bot/human split (last 2 complete weeks)
4. Query per-game breakdown with questers, bot/human split, # quests
5. Always filter event_ts
6. Classify games into buckets (check with user if any should be reclassified as Discontinued)
7. Present full decomposition: headline, tree, PM narrative, games to watch
8. **ASK the user if they want quest-level breakdown (Phase 3)**
9. If yes, read `questers://context/quest_completions` resource and run the quest-level query
10. Only after user responds, run further investigation queries"""
```

**Step 2: Verify phase numbering**

- Phase 0: Team OKR Snapshot (NEW)
- Phase 1: Present the Numbers (existing)
- Phase 2: Decomposition (existing)
- Phase 3: Quest-Level Audit (existing)
- Phase 4: Investigate (existing, was Phase 4)

All references to "Phase 3" for investigation should now be "Phase 4".

**Step 3: Commit**

```bash
git add prompts.py
git commit -m "feat(phase0): add team OKR to questers_report prompt"
```

---

## Task 4: Update README Documentation

**Files:**
- Modify: `README.md:1-173`

**Step 1: Update title and intro**

Change line 3 from:
```markdown
MCP server for tracking and analyzing gameplay questers across Immutable games using a **3-Phase Analysis Framework**.
```

To:
```markdown
MCP server for tracking and analyzing gameplay questers across Immutable games using a **4-Phase Analysis Framework**.
```

**Step 2: Update Features section**

Replace lines 23-38 (the "1. 3-Phase Analysis Framework" section) with:

```markdown
### 1. 4-Phase Analysis Framework (MCP Server)

**Phase 0: Team OKR Snapshot (30-day rolling)**
- Overall quota attainment (% of games meeting monthly targets)
- Tier breakdown (Core, Boost, Ultra Boost)
- Games below quota with gap analysis

**Phase 1: Present the Numbers**
- Overall total questers (WoW comparison)
- Per-game breakdown with bot % and quest counts

**Phase 2: Decomposition (WHY questers changed)**
- Classify games: New / Discontinued / Continuing
- Bot vs human split
- PM narrative explaining key drivers

**Phase 3: Quest-Level Audit (Automated alerts)**
- 🔴 Broken quests (sudden drop-offs)
- 🔴 Bot-farmed quests (high bot %, excessive farming)
- 📉 Declining quests (trending downwards)
- ⚠️ Engagement issues
```

**Step 3: Update Available MCP Resources section**

Add Phase 0 resource to the list (around line 127):

```markdown
- `questers://context/definitions` - Core definitions (gameplay questers, bot detection, filters)
- `questers://context/tables` - BigQuery table schemas
- `questers://context/analysis` - Analysis patterns
- `questers://context/decomposition` - Metric decomposition model
- `questers://context/phase0_team_okr` - Phase 0: Team-level quota attainment (NEW)
- `questers://context/quest_alerts_enhanced` - Phase 3 quest audit with automated alerts
- `questers://context/quest_completions` - Quest-level completions analysis
- `questers://context/farming` - Quest farming detection
```

**Step 4: Update Available Prompts section**

Update the questers_report description (around line 138):

```markdown
- `questers_report` - Full 4-phase weekly report (Phase 0 → 1 → 2 → 3)
```

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README to reflect 4-phase framework"
```

---

## Task 5: Test Phase 0 Integration

**Files:**
- No files modified (testing only)

**Step 1: Start MCP server**

```bash
python3 server.py
```

Expected: Server starts without errors.

**Step 2: Verify Phase 0 resource is available**

In Cursor, check that the resource `questers://context/phase0_team_okr` is listed in MCP resources.

**Step 3: Test questers_report prompt**

In Cursor, invoke the `questers_report` prompt and verify:
- Phase 0 instructions appear first
- Phase numbering is correct (0, 1, 2, 3, 4)
- Instructions mention reading the phase0_team_okr resource

**Step 4: Manually run Phase 0 query**

Copy the SQL from the PHASE0_TEAM_OKR resource and run it in BigQuery console to verify:
- Query executes without errors
- Returns expected columns
- Filters are applied correctly

Expected results:
- Overall summary row with counts and percentages
- Tier breakdown rows
- Below-quota game rows

---

## Task 6: Create SQL Reference File (Optional)

**Files:**
- Create: `phase0_team_okr.sql`

**Step 1: Create standalone SQL file**

For easy reference, create a standalone SQL file:

```sql
-- Phase 0: Team OKR Snapshot - 30-Day Quota Attainment
-- Shows which active games are meeting their monthly gameplay targets
-- Run this to get team-level portfolio health overview

WITH last_30d_questers AS (
  -- Calculate distinct gameplay questers per game (last 30 days)
  SELECT 
    g.game_name,
    g.plan_name as tier,
    g.account_manager_name as am,
    g.monthly_gameplay_target as target,
    COUNT(DISTINCT e.visitor_id) as actual_questers_30d,
    COUNT(DISTINCT q.quest_id) as gameplay_quests
  FROM `app_immutable_play.event` e
  INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
  LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
  LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
  LEFT JOIN UNNEST(q.quest_category) AS category
  WHERE 
    e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
    AND v.is_front_end_cohort = TRUE
    AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
    AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
    AND g.plan_name != 'Maintenance'
    AND g.active_subscription = TRUE
    AND category LIKE '%gameplay%'
    AND g.monthly_gameplay_target IS NOT NULL  -- Only games with targets
  GROUP BY 1,2,3,4
),

quota_status AS (
  SELECT 
    game_name,
    tier,
    am,
    actual_questers_30d,
    target,
    ROUND(100.0 * actual_questers_30d / NULLIF(target, 0), 1) as pct_of_quota,
    actual_questers_30d - target as gap,
    gameplay_quests,
    CASE 
      WHEN actual_questers_30d >= target THEN 1 
      ELSE 0 
    END as meeting_quota
  FROM last_30d_questers
)

-- QUERY 1: Overall Summary
SELECT 
  SUM(meeting_quota) as games_meeting_quota,
  COUNT(*) as total_games,
  ROUND(100.0 * SUM(meeting_quota) / COUNT(*), 1) as pct_meeting
FROM quota_status;

-- QUERY 2: Tier Breakdown
SELECT 
  tier,
  SUM(meeting_quota) as games_meeting_quota,
  COUNT(*) as total_games,
  ROUND(100.0 * SUM(meeting_quota) / COUNT(*), 1) as pct_meeting
FROM quota_status
GROUP BY tier
ORDER BY 
  CASE tier
    WHEN 'Ultra Boost' THEN 1
    WHEN 'Boost' THEN 2
    WHEN 'Core' THEN 3
  END;

-- QUERY 3: Games Below Quota (detail table)
SELECT 
  game_name,
  tier,
  COALESCE(am, 'Unassigned') as account_manager,
  actual_questers_30d,
  target as monthly_target,
  pct_of_quota,
  gap,
  gameplay_quests
FROM quota_status
WHERE meeting_quota = 0  -- Only games below quota
ORDER BY pct_of_quota ASC, tier, game_name;
```

**Step 2: Commit**

```bash
git add phase0_team_okr.sql
git commit -m "feat(phase0): add standalone SQL reference file"
```

---

## Summary

**Completion Checklist:**
- [x] Add PHASE0_TEAM_OKR constant to resources.py
- [x] Register phase0_team_okr resource in MCP
- [x] Update questers_report prompt with Phase 0 instructions
- [x] Update README to reflect 4-phase framework
- [x] Test MCP server starts and resource is available
- [x] Create standalone SQL reference file (optional)

**Verification:**
1. MCP server starts without errors
2. Resource `questers://context/phase0_team_okr` is accessible
3. questers_report prompt includes Phase 0 as first step
4. Documentation reflects 4-phase framework

**Next Steps:**
Run the questers_report prompt in production and verify Phase 0 executes correctly with live data.
