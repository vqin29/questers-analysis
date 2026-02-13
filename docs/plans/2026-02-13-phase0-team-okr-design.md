# Phase 0: Team OKR Overview - Design Document

**Date:** 2026-02-13  
**Author:** Vivian  
**Status:** Approved

---

## Overview

Add a new "Phase 0" to the existing 3-phase questers analysis framework. Phase 0 will provide a team-level OKR snapshot showing how active games are performing against their monthly gameplay quotas before diving into weekly trend analysis.

---

## Goals

1. **Portfolio health at-a-glance:** Show % of games meeting monthly quotas
2. **Focus on gaps:** Highlight only underperforming games to direct PM/CG attention
3. **Minimal disruption:** Integrate cleanly before existing Phase 1-3 workflow
4. **Context for investigation:** Include quest count and AM to help diagnose issues

---

## Requirements

### Functional Requirements

1. Calculate 30-day rolling gameplay questers per active game
2. Compare actual vs `monthly_gameplay_target` from game table
3. Show tier-level summary (Core, Boost, Ultra Boost)
4. Display detailed table for games below 100% quota only
5. Apply standard filters: active subscription, exclude Maintenance tier

### Data Requirements

**Source Tables:**
- `app_immutable_play.event` - Quest completions (filter event_ts to last 30 days)
- `app_immutable_play.visitor` - User profiles (apply standard filters)
- `app_immutable_play.quest` - Quest definitions (filter to gameplay category)
- `app_immutable_play.game` - Game metadata (source of `monthly_gameplay_target`)

**Required Filters (consistent with existing analysis):**
```sql
WHERE v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
  AND g.plan_name != 'Maintenance'  -- Exclude Maintenance tier
  AND g.active_subscription = TRUE  -- Only active subscriptions
  AND e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
```

### Non-Functional Requirements

- Query execution time: <30 seconds (consistent with existing Phase 1 queries)
- Works with existing BigQuery tool in MCP server
- Maintains visual consistency with existing phase outputs

---

## Design

### Output Structure

```
📊 PHASE 0: TEAM OKR SNAPSHOT (Last 30 Days)

Overall Quota Attainment: 14/22 games (64%) meeting monthly target

Tier Breakdown:
- Ultra Boost: 3/4 games (75%) meeting quota
- Boost: 5/8 games (63%) meeting quota
- Core: 6/10 games (60%) meeting quota

⚠️ Games Below Quota (8 games):

| Game | Tier | AM | Actual (30d) | Target | % of Quota | Gap | # Gameplay Quests |
|------|------|-----|--------------|--------|------------|-----|-------------------|
| Game C | Core | Alice | 3,200 | 5,000 | 64% | -1,800 | 3 |
| Game F | Boost | Bob | 4,500 | 8,000 | 56% | -3,500 | 5 |
| Game H | Ultra Boost | Carol | 8,000 | 12,000 | 67% | -4,000 | 2 |

────────────────────────────────────────────

📈 PHASE 1: WEEKLY TRENDS (Last 2 Complete Weeks)
[Existing Phase 1 continues...]
```

### SQL Query Structure

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
      WHEN actual_questers_30d >= target THEN TRUE 
      ELSE FALSE 
    END as meeting_quota
  FROM last_30d_questers
)

SELECT * FROM quota_status
ORDER BY pct_of_quota ASC, tier, game_name
```

### Presentation Logic

1. **Overall Summary:**
   - Count games meeting quota (actual >= target)
   - Calculate percentage: `meeting_quota_count / total_games * 100`

2. **Tier Breakdown:**
   - Group by tier (Core, Boost, Ultra Boost)
   - Show count and percentage for each tier

3. **Below-Quota Table:**
   - Filter to `meeting_quota = FALSE` (actual < target)
   - Sort by `pct_of_quota ASC` (worst performers first)
   - Include all relevant columns for context

---

## Integration Points

### 1. Resources (`resources.py`)

Add new constant:
```python
PHASE0_TEAM_OKR = """# Phase 0: Team OKR Overview

## Purpose
Show 30-day rolling quota attainment before weekly trend analysis.

## Metric
% of active games meeting their monthly gameplay quota (games.monthly_gameplay_target)

[Full documentation including SQL query]
"""
```

Register new resource:
```python
@mcp.resource("questers://context/phase0_team_okr")
def get_phase0_team_okr() -> str:
    return PHASE0_TEAM_OKR
```

### 2. Prompts (`prompts.py`)

**Update existing `questers_report()` prompt:**
- Add Phase 0 instructions at the top
- Update phase numbering references if needed

**Structure:**
```
## Phase 0: Team OKR Snapshot (ALWAYS RUN FIRST)
1. Read the questers://context/phase0_team_okr resource
2. Query 30-day gameplay questers with quotas
3. Present overall summary, tier breakdown, below-quota table
4. Separator line before Phase 1

## Phase 1: Present the Numbers
[Existing Phase 1 instructions...]
```

### 3. Documentation

**Update README.md:**
- Change "3-Phase Analysis Framework" to "4-Phase Analysis Framework"
- Add Phase 0 description
- Update feature list

---

## Error Handling

### Missing Quota Data
If a game has `monthly_gameplay_target = NULL`:
- Exclude from Phase 0 analysis
- Note in output: "X games excluded (no quota set)"

### Zero Questers
If a game has 0 questers in last 30 days:
- Include in below-quota table
- Show as "0%" of quota
- Flag as potential inactive game

### Query Performance
If query takes >30 seconds:
- Already filtering event_ts to 30 days (acceptable range)
- Pre-aggregation in CTE minimizes joins
- No bot_score join needed (not required for quota tracking)

---

## Future Enhancements (Out of Scope)

1. **Trend Analysis:** Show if game is improving/declining toward quota
2. **Projections:** Estimate if game will meet quota by month-end
3. **Bot Impact:** Show quota % excluding bot questers
4. **Historical Comparison:** Compare to previous month's attainment

---

## Testing Approach

1. **Data Validation:**
   - Verify 30-day window calculation
   - Confirm quota values match game table
   - Check filter application (active_subscription, no Maintenance)

2. **Edge Cases:**
   - Games with NULL quota
   - Games with 0 questers
   - New games with <30 days of data

3. **Integration:**
   - Run full questers_report prompt
   - Verify Phase 0 appears before Phase 1
   - Confirm visual formatting is clean

---

## Success Criteria

- [ ] Phase 0 query executes in <30 seconds
- [ ] Summary stats accurately reflect portfolio health
- [ ] Only below-quota games appear in detail table
- [ ] Filters match existing analysis standards
- [ ] Output integrates cleanly with existing Phase 1-3
- [ ] Documentation updated (README, resources, prompts)

---

## Rollout Plan

1. Add PHASE0_TEAM_OKR constant to resources.py
2. Register new resource in resources.py
3. Update questers_report() prompt in prompts.py
4. Update README.md with 4-phase framework
5. Test with sample query
6. Commit changes
