"""
Resources - Context for the AI to understand tables and definitions
"""

DEFINITIONS = """# Quester Definitions

## Questers (All Questers)
Users who completed quests in ANY of these categories:
- gameplay (or contains 'gameplay')
- post (or contains 'post') 
- engage (or contains 'engage')

SQL filter:
```sql
LEFT JOIN UNNEST(q.quest_category) AS category
WHERE category LIKE '%gameplay%' 
   OR category LIKE '%post%' 
   OR category LIKE '%engage%'
```

## Game Questers / Gameplay Questers
Users who completed quests with ONLY gameplay category:
```sql
LEFT JOIN UNNEST(q.quest_category) AS category
WHERE category LIKE '%gameplay%'
```

## Bot Detection
Use `mod_imx.sybil_score` table with `bot_score = 1` to identify bots:
```sql
LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id
-- Bot: s.bot_score = 1
-- Not bot: s.bot_score IS NULL OR s.bot_score < 1
```

## Required Filters (Always Apply)
```sql
AND v.is_front_end_cohort = TRUE
AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
AND g.plan_name != 'Maintenance'
```

- `is_front_end_cohort = TRUE` - Only count front-end users
- Exclude employees
- Exclude Guild of Guardians and Gods Unchained
- Exclude Maintenance tier games (only include active: Core, Boost, Ultra Boost)
- Do NOT filter out bots - show bot % separately using sybil_score

## Time Comparisons
Always cast DATE to TIMESTAMP:
```sql
WHERE e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY))
```

## Week Definition
Weeks start **Monday** and end **Sunday** (UTC):
```sql
DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) as week_start
```

**Important**: Convert TIMESTAMP to DATE before truncating!

For week-on-week comparison (last 2 COMPLETE weeks, excludes current incomplete week):
```sql
WITH weekly_data AS (
  SELECT 
    g.game_name,
    DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) as week_start,
    COUNT(DISTINCT e.visitor_id) as questers
  FROM `app_immutable_play.event` e
  ...
  WHERE 
    e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 21 DAY))
    AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))  -- EXCLUDE current week
  GROUP BY g.game_name, week_start
),
last_week AS (
  SELECT * FROM weekly_data 
  WHERE week_start = DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 7 DAY)
),
prev_week AS (
  SELECT * FROM weekly_data 
  WHERE week_start = DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 14 DAY)
)
SELECT 
  COALESCE(l.game_name, p.game_name) as game_name,
  COALESCE(l.questers, 0) as last_week,
  COALESCE(p.questers, 0) as prev_week,
  COALESCE(l.questers, 0) - COALESCE(p.questers, 0) as change
FROM last_week l
FULL OUTER JOIN prev_week p ON l.game_name = p.game_name
```

**Important**: Always exclude current incomplete week by filtering `event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))`

## Counting
Always use COUNT(DISTINCT visitor_id) to avoid duplicates.

## IMPORTANT: Overall vs Per-Game Totals
**Overall gameplay questers should NEVER be the sum of individual game totals.**

Users can quest across multiple games, so:
- Overall total = COUNT(DISTINCT visitor_id) across ALL games = unique users
- Per-game totals will sum to MORE than the overall total

Always calculate overall total separately using a distinct count across all games, NOT by summing per-game rows."""


TABLES = """# Tables

## ⚠️ COST WARNING
The `event` table has 700M+ rows. ALWAYS filter on `event_ts`!

---

## app_immutable_play.event
Quest completions. **ALWAYS FILTER event_ts!**

| Column | Type | Description |
|--------|------|-------------|
| visitor_id | INTEGER | User ID |
| quest_id | INTEGER | Quest ID |
| event_ts | TIMESTAMP | When event occurred **(ALWAYS FILTER)** |
| game_id | STRING | Game UUID |

## app_immutable_play.quest  
Quest definitions.

| Column | Type | Description |
|--------|------|-------------|
| quest_id | INTEGER | Quest ID |
| quest_name | STRING | Quest name |
| quest_category | ARRAY<STRING> | Categories (MUST UNNEST) |
| game_id | STRING | Game UUID |
| create_ts | TIMESTAMP | Created date |
| valid_from | TIMESTAMP | Start date |
| valid_to | TIMESTAMP | End date |

## app_immutable_play.visitor
User profiles.

| Column | Type | Description |
|--------|------|-------------|
| visitor_id | INTEGER | User ID |
| user_id | STRING | Auth ID (joins to sybil_score) |
| is_bot | BOOLEAN | Bot flag |
| is_immutable_employee | BOOLEAN | Employee flag |

## app_immutable_play.game
Game metadata.

| Column | Type | Description |
|--------|------|-------------|
| game_id | STRING | Game UUID |
| game_name | STRING | Human-readable name |

## mod_imx.sybil_score
Sybil/bot detection scores.

| Column | Type | Description |
|--------|------|-------------|
| user_id | STRING | Auth ID (joins to visitor.user_id) |
| bot_score | FLOAT | 1 = bot, <1 = not bot |
| primary_flag | STRING | Reason for flag |

**Bot filter**: WHERE bot_score = 1

## app_immutable_play.sweepstake_visitor
Rewards participation.

| Column | Type | Description |
|--------|------|-------------|
| visitor_id | INTEGER | User ID |
| sweepstake_name | STRING | e.g. "Weekly Draw 41" |
| has_redeemed | BOOLEAN | Entered sweepstake |"""


ANALYSIS = """# Analysis Guide

## Standard Output Format
When asked about questers, always provide:

### 1. Overall Totals (by type)
| Type | Questers |
|------|----------|
| Gameplay | X |
| Social Post | X |
| Social Engage | X |
| **Total** | X |

### 2. Per-Game Breakdown
| Game | Gameplay | Social | Total | Bot % | Reason |
|------|----------|--------|-------|-------|--------|

Include:
- Gameplay questers (category LIKE '%gameplay%')
- Social questers (category LIKE '%post%' OR '%engage%')
- Bot % (from sybil_score where bot_score = 1)
- Reason for change (up/down)

## Why Gameplay Questers Go Up or Down

### Reasons for INCREASE
- More gameplay quests added
- New quest launch with high engagement
- Game entered rewards program
- Marketing campaign drove traffic

### Reasons for DECREASE  
- Fewer gameplay quests available
- Quests expired (valid_to passed)
- High bot % (sybils farming)
- Game left rewards program
- Poor quest design (low completion)

## Query: Overall Gameplay Questers (Last 2 Complete Weeks)
```sql
SELECT 
  DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) as week_start,
  COUNT(DISTINCT e.visitor_id) as gameplay_questers
FROM `app_immutable_play.event` e
INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
LEFT JOIN UNNEST(q.quest_category) AS category
WHERE 
  e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 21 DAY))
  AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
  AND g.plan_name != 'Maintenance'
  AND category LIKE '%gameplay%'
GROUP BY week_start
ORDER BY week_start DESC
```

## Quest Farming Detection

### Key Metrics
| Metric | Formula | Risk Threshold |
|--------|---------|----------------|
| Bot % | Bots / Total Users | ≥80% = High Risk |
| Completions/User | Total Completions / Unique Users | >10 = Grinding |
| Bot Efficiency | Bot Completions/Bot Users vs Human rate | >2x = Bot farming |

### Farming Indicators
1. **High Bot %**: Quest attracts sybils (easy to automate)
2. **High Completions/User**: Quest is grindable (repeatable for rewards)
3. **High Bot Efficiency**: Bots complete more per user than humans

### Reward Rebalancing Logic
| Current State | Recommendation |
|---------------|----------------|
| Bot% ≥80% | Add verification, reduce rewards, or discontinue |
| Completions/User >10 | Add cooldowns or diminishing returns |
| Low human engagement, low bot% | Increase rewards or improve quest UX |
| High human engagement, low bot% | Keep as-is (healthy quest) |

### Query: Quest Farming Analysis
```sql
SELECT 
  g.game_name,
  q.quest_name,
  COUNT(*) as completions,
  COUNT(DISTINCT e.visitor_id) as unique_users,
  COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) as bot_users,
  COUNT(DISTINCT CASE WHEN s.bot_score IS NULL OR s.bot_score < 1 THEN e.visitor_id END) as human_users,
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) / 
        NULLIF(COUNT(DISTINCT e.visitor_id), 0), 0) as bot_pct,
  ROUND(1.0 * COUNT(*) / NULLIF(COUNT(DISTINCT e.visitor_id), 0), 1) as completions_per_user
FROM `app_immutable_play.event` e
JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id
WHERE 
  e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 7 DAY))
  AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
  AND g.plan_name != 'Maintenance'
GROUP BY g.game_name, q.quest_name
ORDER BY bot_pct DESC, completions DESC
```

## Query: Per-Game Breakdown with WoW
```sql
SELECT 
  g.game_name,
  g.plan_name as tier,
  g.account_manager_name as am,
  COUNT(DISTINCT e.visitor_id) as gameplay_questers,
  COUNT(DISTINCT q.quest_id) as gameplay_quests,
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) / 
        NULLIF(COUNT(DISTINCT e.visitor_id), 0), 1) as bot_pct
FROM `app_immutable_play.event` e
INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
LEFT JOIN UNNEST(q.quest_category) AS category
LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id
WHERE 
  e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 7 DAY))
  AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
  AND g.plan_name != 'Maintenance'
  AND category LIKE '%gameplay%'
GROUP BY g.game_name, g.plan_name, g.account_manager_name
ORDER BY gameplay_questers DESC
```"""


DECOMPOSITION = """# Metric Decomposition Model

## Purpose
Replace "Questers is down 3%" with driver attribution showing WHY.

## The Model

Decompose WoW delta into 3 MUTUALLY EXCLUSIVE buckets:

```
Total Δ = [New Games] + [Discontinued Games] + [Continuing Games]
```

Each bucket is non-overlapping - a game falls into exactly ONE bucket.

## The Three Buckets

### Bucket 1: New Games
Games that launched this week (0 users prev week → N users curr week)

```sql
WHERE prev_users = 0 AND curr_users > 0
```

**Contribution:** +curr_users (all users are "new" to the ecosystem)

### Bucket 2: Discontinued Games  
Games that stopped this week (N users prev week → 0 users curr week)

```sql
WHERE prev_users > 0 AND curr_users = 0
```

**Contribution:** -prev_users (all users "lost" from the ecosystem)

### Bucket 3: Continuing Games
Games active both weeks - shows their organic WoW change

```sql
WHERE prev_users > 0 AND curr_users > 0
```

**Contribution:** Σ(curr_users - prev_users) for each game

## Secondary Dimension: Quality Split

Within each bucket, break down by:
- **Human users:** bot_score IS NULL OR bot_score < 1
- **Bot users:** bot_score = 1

## Formula

```
Total Δ = New_Games + Discontinued_Games + Continuing_Games

Where:
- New_Games = Σ curr_users for games with prev_users = 0
- Discontinued_Games = -Σ prev_users for games with curr_users = 0
- Continuing_Games = Σ (curr_users - prev_users) for games with both > 0
```

**Note:** Sum may not exactly equal Total Δ because users can play 
multiple games across categories (counted once in total, but once per game).

## Interpretation Guide

| Primary Driver | Meaning | Action |
|----------------|---------|--------|
| New Games dominant | Growth from launches | Monitor quality (bot %) |
| Discontinued dominant | Losses from shutdowns | Review game lifecycle |
| Continuing positive | Organic ecosystem growth | Healthy state |
| Continuing negative | Organic ecosystem decline | Investigate churn |

## Example Output

```
Total Δ: +7,808 (+16.4%)

  + New Games:        +17,172  (+220%)
      └─ Elowyn: +12,164 (85% bots) ⚠️
      └─ Trillionaire Thugs: +5,008 (7% bots) ✓

  - Discontinued:     -5,724   (-73%)
      └─ Spider Tanks: -5,723

  ± Continuing Games: -4,992   (-64%)
      Growth: Plooshy +9K, Chainers +6K
      Decline: Treeverse -11K, Basejump -9K

  ─────────────────────────────
  = Total:            +7,808
```"""


FARMING = """# Quest Farming Analysis

## Purpose
Internal tool for Customer Growth to answer:
- "Which quests are over-farmed?"
- "Where are real players under-incentivized?"

## Key Metrics

### 1. Bot Density
```
Bot % = (Users with bot_score=1) / (Total Users) * 100
```
- 🔴 ≥80%: High risk, likely automated
- 🟡 60-79%: Medium risk, monitor
- 🟢 <60%: Acceptable

### 2. Farming Intensity
```
Completions/User = Total Completions / Unique Users
```
- >10: Excessive grinding (add cooldowns)
- 5-10: High engagement (monitor)
- <5: Normal engagement

### 3. Bot Efficiency
```
Bot Efficiency = (Bot Completions / Bot Users) / (Human Completions / Human Users)
```
- >2x: Bots farming more aggressively than humans
- 1-2x: Similar rates
- <1x: Humans more engaged (healthy)

## Reward ROI Analysis

### Over-Farmed Quests (Bad ROI)
| Signal | Meaning |
|--------|---------|
| High bot %, high completions | Rewards going to bots |
| High completions/user | Grindable, rewards concentrated |
| Bot efficiency >2x | Bots optimizing better than humans |

**Action**: Reduce rewards, add verification, or discontinue

### Under-Incentivized Quests (Missed Opportunity)
| Signal | Meaning |
|--------|---------|
| Low bot %, low completions | Real players not engaging |
| Low completions/user | Quest too hard or not rewarding |
| Quest requires real gameplay | Good design but low participation |

**Action**: Increase rewards, simplify requirements, improve UX

## Suggested Rebalancing Framework

| Quest Profile | Bot % | Completions/User | Recommendation |
|---------------|-------|------------------|----------------|
| Bot Farm | ≥80% | Any | Discontinue or add verification |
| Grind Farm | Any | >10 | Add cooldowns, diminishing returns |
| Healthy High | <60% | 3-10 | Keep as-is, successful quest |
| Under-engaged | <40% | <2 | Increase rewards or visibility |
| Ghost Quest | Any | <1 | Review quest design, may discontinue |

## Categories to Watch
- `in_game` quests with high bot %: Likely automated gameplay
- Quests with >20 completions/user: Infinite grinding
- New quests with immediate high bot %: Exploit found"""


def register(mcp):
    """Register all resources with the MCP server"""
    
    @mcp.resource("questers://context/definitions")
    def get_definitions() -> str:
        """Core definitions for quester analysis"""
        return DEFINITIONS
    
    @mcp.resource("questers://context/tables")
    def get_tables() -> str:
        """Table schemas for quester analysis"""
        return TABLES
    
    @mcp.resource("questers://context/analysis")
    def get_analysis() -> str:
        """Analysis patterns for investigating trends"""
        return ANALYSIS
    
    @mcp.resource("questers://context/farming")
    def get_farming() -> str:
        """Quest farming detection and reward rebalancing"""
        return FARMING
    
    @mcp.resource("questers://context/decomposition")
    def get_decomposition() -> str:
        """Metric decomposition model for driver attribution"""
        return DECOMPOSITION
