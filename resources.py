"""
Resources - Context for the AI to understand tables and definitions
"""
import os
from pathlib import Path

# Get the directory containing this file
_SCRIPT_DIR = Path(__file__).parent


def _load_sql(filename: str) -> str:
    """Load SQL content from a file"""
    sql_path = _SCRIPT_DIR / filename
    with open(sql_path, 'r') as f:
        return f.read().strip()

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

## Investigation Workflow (ALWAYS FOLLOW)

After presenting initial numbers, you MUST follow this workflow for any game
with a significant change (>20% WoW or >1,000 users absolute change):

### Step 1: Present the Numbers
Show the overall total and per-game breakdown as usual.

### Step 2: Flag Significant Movers
Clearly call out the top 3-5 games with the biggest changes (up AND down).
For each, state what you already know:
- Direction and magnitude of change
- Quest count change (if any)
- Bot % change (if any)

### Step 3: STOP AND ASK THE USER
Before investigating further, ALWAYS ask the user:
1. "Which of these do you want me to dig into?"
2. "Do you have any hypotheses for why [game] went up/down?"
3. "What would you like to see? e.g. quest-level breakdown, bot analysis,
   multi-week trend, farming detection, user overlap?"

Present these as options. Wait for user input before proceeding.

### Step 4: Investigate Based on User Direction
Once the user responds, run targeted queries based on their hypothesis:
- If they suspect quest changes → query quest valid_from/valid_to
- If they suspect bots → run farming analysis on that game
- If they want trends → pull 4-week history
- If they have a custom hypothesis → design a query to test it

### Step 5: Report Back and Iterate
Present findings and ask: "Does this answer your question, or do you want
to dig deeper into something else?"

**IMPORTANT:** Never just dump all analysis at once. The goal is a
conversation, not a monologue. Let the user guide the investigation.

## Common Hypotheses to Suggest

When a game goes UP, suggest investigating:
- Were new quests added? (check quest valid_from)
- Did bot % increase? (bots discovered the game)
- Was there a marketing push? (sudden spike pattern)
- Did another game's users migrate? (user overlap analysis)

When a game goes DOWN, suggest investigating:
- Did quests expire? (check quest valid_to)
- Were quests removed/paused? (quest count dropped)
- Did bot % drop? (sybil cleanup = "healthy" decline)
- Is the game in maintenance/sunset? (check plan_name changes)
- Did rewards change? (lower incentive)

## Why Gameplay Questers Go Up or Down

### Reasons for INCREASE
- More gameplay quests added
- New quest launch with high engagement
- Game entered rewards program
- Marketing campaign drove traffic
- Bot wave discovered the game

### Reasons for DECREASE  
- Fewer gameplay quests available
- Quests expired (valid_to passed)
- High bot % (sybils farming)
- Game left rewards program
- Poor quest design (low completion)
- Sybil cleanup (bots removed — this is a healthy decline)

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
This is the STANDARD format for Phase 2 analysis in all weekly reports.

## The Model

Decompose WoW delta into 3 MUTUALLY EXCLUSIVE buckets:

```
Total Δ = [New Games] + [Discontinued / Off] + [Continuing Games]
```

Each bucket is non-overlapping - a game falls into exactly ONE bucket.

## The Three Buckets

### Bucket 1: New Games
Games that launched this week (0 users prev week → N users curr week)

```sql
WHERE prev_users = 0 AND curr_users > 0
```

**Contribution:** +curr_users (all users are "new" to the ecosystem)

### Bucket 2: Discontinued / Turned Off
Games that stopped or were turned off.

**Default classification (data-driven):**
```sql
WHERE prev_users > 0 AND curr_users = 0
```

**Reclassification rule:** Games that are KNOWN to be turned off or set to
inactive should ALSO be classified as Discontinued, even if they have small
residual activity in the current week. Indicators:
- Game dropped >95% of questers (e.g. 25K → 500)
- Team confirms game was turned off / set to inactive
- Quest supply went to 0 or near-0

When in doubt, ASK the user: "Game X dropped from Y to Z — was this
turned off? Should I classify it as Discontinued?"

**Contribution:** -prev_users (all users "lost" from the ecosystem)

### Bucket 3: Continuing Games
Games active both weeks - shows their organic WoW change

```sql
WHERE prev_users > 0 AND curr_users > 0
```

**Contribution:** Σ(curr_users - prev_users) for each game

## Secondary Dimension: Quality Split (ALWAYS INCLUDE)

Within EVERY bucket, break down by:
- **Human users:** bot_score IS NULL OR bot_score < 1
- **Bot users:** bot_score = 1

This is critical for PM reporting — the headline number matters less than
whether the change is driven by real users or bots.

## Required Output Format

### 1. Headline
One bold sentence: the total delta AND the quality story.
Include summary table with Total / Human / Bot questers and Bot %.

### 2. Decomposition Tree
```
Total Δ: +X,XXX (+X.X%)

  + New Games:              +X,XXX
      └─ Game A   +X,XXX  (X% bots ⚠️/✓)

  - Discontinued / Off:    -X,XXX  (X% were bots)
      └─ Game B   -X,XXX  (was X% bots)

  + Continuing Games:      +X,XXX  (net)
      Bots:   -X,XXX   ← [context, e.g. "massive bot cleanup"]
      Humans: +X,XXX   ← [context, e.g. "strong organic growth"]

      Growth:
        └─ Game C  +X,XXX  (humans +X, bots +X ⚠️/✓)
      Decline:
        └─ Game D  -X,XXX  (bots -X, humans +X ✓)

  ──────────────────────────────────────
  Note: Per-game sums ≠ overall total due to multi-game users.
```

Use ⚠️ for concerning signals (high bot %, bot spike) and ✓ for healthy
signals (low bot %, human-driven growth). Use ✓✓ for standout healthy games.

### 3. PM Narrative
Write 3-5 numbered key takeaways, each 1-2 sentences. Always cover:
1. Overall ecosystem health (bot % shift, human growth direction)
2. The biggest single mover and what drove it
3. Discontinued/off games — were they low quality? Is this a healthy cleanup?
4. New launches — early bot % signal?
5. Continuing games — is human growth real and broad-based?

### 4. Games to Watch
| Game | Signal | Risk |
|------|--------|------|

Flag games with: new launch + high bot %, sudden bot spike on unchanged
quest supply, or large unexplained quester swing.

## Formula

```
Total Δ = New_Games + Discontinued_Games + Continuing_Games

Where:
- New_Games = Σ curr_users for games with prev_users = 0
- Discontinued_Games = -Σ prev_users for games with curr_users = 0 (or turned off)
- Continuing_Games = Σ (curr_users - prev_users) for remaining games
```

**Note:** Sum may not exactly equal Total Δ because users can play
multiple games across categories (counted once in total, but once per game).
Always note this caveat in the output.

## Interpretation Guide

| Primary Driver | Meaning | Action |
|----------------|---------|--------|
| New Games dominant | Growth from launches | Monitor quality (bot %) |
| Discontinued dominant | Losses from shutdowns | Review game lifecycle — was it healthy cleanup? |
| Continuing positive | Organic ecosystem growth | Healthy state |
| Continuing negative | Organic ecosystem decline | Investigate churn |
| Bot decline + Human growth | Quality improving | Highlight as positive for PM |

## Example Output

```
Total Δ: +3,022 (+5.4%)

  + New Games:              +12,843
      └─ Might and Magic: Fates   +12,530  (64% bots ⚠️)
      └─ Emoji Marble Dash          +313  (22% bots ✓)

  - Discontinued / Off:    -44,768  (76% were bots)
      └─ Plooshy Pile Up        -24,826  (was 74% bots)
      └─ Meta Toy DragonZ SAGA  -14,612  (was 72% bots)
      └─ Dalarnia Legends        -5,330  (was 95% bots)

  + Continuing Games:      +23,904  (net)
      Bots:   -5,317   ← ongoing bot cleanup
      Humans: +29,221   ← strong organic growth

      Growth:
        └─ Trillionaire Thugs ZW  +19,165  (humans +9.7K, bots +9.4K ⚠️)
        └─ Elumia                  +2,640  (bots -5.8K, humans +8.5K ✓✓)
      Decline:
        └─ Syndicate of Vigilantes -2,392  (bots -6.8K, humans +4.5K ✓)
        └─ Villains               -1,062  (bots -1.9K, humans +836 ✓)

  ──────────────────────────────────────
  Note: Per-game sums ≠ overall total due to multi-game users.
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


QUEST_COMPLETIONS = """# Quest-Level Completions Analysis (Phase 3)

## Purpose
Drill down from game-level quester counts to individual quest completions.
This answers: "Which specific quests are driving the change in questers?"

Use this after Phase 2 (decomposition) when the user wants quest-level granularity.

## Default Query: All Active Games (Last 3 Days)
Shows every quest with completions across all active non-Maintenance games.
Useful for spotting which quests are hot, dead, or anomalous.

```sql
SELECT
  g.game_name,
  q.quest_name,
  q.quest_id,
  COUNT(*) AS quest_completions,
  COUNT(DISTINCT e.visitor_id) AS unique_completers,
  ROUND(1.0 * COUNT(*) / NULLIF(COUNT(DISTINCT e.visitor_id), 0), 1) AS completions_per_user
FROM `app_immutable_play.event` e
INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
LEFT JOIN UNNEST(q.quest_category) AS category
WHERE
  e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
  AND g.plan_name != 'Maintenance'
  AND category LIKE '%gameplay%'
GROUP BY g.game_name, q.quest_name, q.quest_id
ORDER BY g.game_name, quest_completions DESC
```

## Filtered Query: Specific Game (Last 3 Days, with Bot %)
When the user asks about a specific game, include bot % per quest.

```sql
SELECT
  g.game_name,
  q.quest_name,
  q.quest_id,
  COUNT(*) AS quest_completions,
  COUNT(DISTINCT e.visitor_id) AS unique_completers,
  COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) AS bot_completers,
  COUNT(DISTINCT CASE WHEN s.bot_score IS NULL OR s.bot_score < 1 THEN e.visitor_id END) AS human_completers,
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) /
        NULLIF(COUNT(DISTINCT e.visitor_id), 0), 1) AS bot_pct,
  ROUND(1.0 * COUNT(*) / NULLIF(COUNT(DISTINCT e.visitor_id), 0), 1) AS completions_per_user
FROM `app_immutable_play.event` e
INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
LEFT JOIN UNNEST(q.quest_category) AS category
LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id
WHERE
  e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name = '{game_name}'  -- Replace with actual game name
  AND g.plan_name != 'Maintenance'
  AND category LIKE '%gameplay%'
GROUP BY g.game_name, q.quest_name, q.quest_id
ORDER BY quest_completions DESC
```

## Presentation Format

### All Games View
Group results by game, showing each game's quests sorted by completions:

```
🎮 Game A (Tier: Core, AM: Name)
| Quest Name          | Completions (3d) | Unique Completers | Comp/User |
|---------------------|------------------|--------------------|-----------|
| Quest Alpha         | 12,340           | 5,200              | 2.4       |
| Quest Beta          | 8,100            | 4,800              | 1.7       |
| Quest Gamma         | 230              | 180                | 1.3       |

🎮 Game B (Tier: Boost, AM: Name)
| Quest Name          | Completions (3d) | Unique Completers | Comp/User |
|---------------------|------------------|--------------------|-----------|
| ...                 | ...              | ...                | ...       |
```

### Specific Game View (includes bot %)
| Quest Name | Completions | Unique Completers | Bot % | Human Completers | Comp/User | Flag |
|-----------|-------------|-------------------|-------|------------------|-----------|------|

## Flags & Anomalies
- 🔴 **Completions/User > 10**: Possible farming / grinding
- 🟡 **Completions/User 5-10**: High engagement, monitor
- ⚠️ **Bot % > 60%**: High bot activity on this quest
- 📈 **Top quest by completions**: Driving game's quester numbers
- 💀 **0 completions**: Quest may be expired or broken

## Follow-Up Questions to Ask
After presenting quest-level data, ask:
"Any quests stand out? I can dig deeper into:
  - A specific quest's completion trend over time
  - Bot vs human breakdown for any quest
  - Whether a quest was recently added or is about to expire
  - Completions per user distribution (farming detection)"
"""


def _get_phase0_team_okr_content() -> str:
    """Generate Phase 0 Team OKR documentation with SQL loaded from file"""
    sql_query = _load_sql('phase0_team_okr.sql')
    
    return f"""# Phase 0: Team OKR Overview

## Purpose
Show team-level portfolio health via 30-day rolling quota attainment before weekly trend analysis.

This answers: "What % of our active games are meeting their monthly gameplay quotas?"

## Metric Definition

**Quota Attainment** = `actual_questers_30d / monthly_gameplay_target * 100`

- **30-day rolling window:** COUNT(DISTINCT visitor_id) for last 30 days
- **Monthly target:** From `game.monthly_gameplay_target` column
- **Meeting quota:** actual >= target (100%+)

## Required Filters (ALWAYS APPLY)

Same as other phases, plus additional filters:
```sql
WHERE e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
  AND g.plan_name != 'Maintenance'  -- Exclude Maintenance tier
  AND g.active_subscription = TRUE  -- Only active subscriptions
  AND g.monthly_gameplay_target IS NOT NULL  -- Only games with targets set
GROUP BY ...
HAVING COUNT(DISTINCT e.visitor_id) >= 10  -- Exclude games with <10 questers (testing/inactive)
```

**Additional filter for testing quests:**
- Exclude games where ALL gameplay quests have "testing" in their category
- Only count `non_testing_quests > 0`

## Output Format

### Overall Summary
```
📊 PHASE 0: TEAM OKR SNAPSHOT (Last 30 Days)
Filtered: Games with ≥10 questers AND at least 1 non-testing gameplay quest

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
{sql_query}
```

## Edge Cases

### Missing Quota Data
If `monthly_gameplay_target IS NULL`:
- Exclude from Phase 0 analysis
- Count excluded games and note in output: "(X games excluded - no quota set)"

### Low Activity Games
If game has <10 questers in last 30 days:
- Exclude from Phase 0 (likely testing/inactive)
- These games won't count toward total denominator

### Testing Quests Only
If game only has quests with "testing" category:
- Exclude from Phase 0 (not production-ready)
- Check `non_testing_quests > 0` filter

### New Games
If game created <30 days ago:
- Still include (uses available data)
- May show low % if ramping up
"""


# Cache the content so we don't read from file multiple times
PHASE0_TEAM_OKR = _get_phase0_team_okr_content()


def _get_quest_alerts_enhanced_content() -> str:
    """Generate Quest Alerts Enhanced documentation with SQL loaded from file"""
    sql_query = _load_sql('quest_alerts_enhanced.sql')
    
    return f"""# Quest Alerts Dashboard - Enhanced (Phase 3 Reference)

This is the **complete implementation** of the Phase 3 quest audit system with automated alert flags.

## Purpose
Identify problematic quests at scale:
- 🔴 Broken quests (sudden drop-offs)
- 🔴 Bot-farmed quests (high bot %, excessive completions/user)
- 📉 Declining quests (trending downwards)
- ⚠️ Engagement issues

## Alert Severity

### 🔴 Critical (Priority 1-2)
- **Critical bot rate** ≥90%
- **High bot rate** 80-90%
- **Excessive farming** >20 completions/user (with 10+ users)
- **No completions in 7d** (but had activity 7-14d ago) → Likely broken
- **Possibly broken** 0 completions in 48h (but had 5+ prev 48h)

### 🟡 Medium (Priority 3)
- **Elevated bot rate** 70-80%
- **High farming** 10-20 completions/user
- **Major activity drop** >70% user decline (48h window)
- **Trending downwards** >25% completion decline (7d)

### ⚠️ Low (Priority 4)
- **Low recent activity** <5 users in 48h (was 20+)
- **No recent completions** >48h since last completion

## Time Windows Strategy

| Window | Comparison | Purpose | Detection Speed |
|--------|-----------|---------|-----------------|
| **48h** | Current vs 48-96h ago | Rapid anomaly detection | 1-2 days |
| **7d** | Current vs 7-14d ago | Trend analysis | 1 week |
| **30d** | Overall baseline | Bot % and patterns | 1 month |

## Key Metrics

| Metric | Formula | Detects |
|--------|---------|---------|
| `bot_rate_pct` | `bot_users / total_users * 100` | Bot concentration |
| `completions_per_user` | `total_completions / distinct_users` | Farming/grinding |
| `activity_drop_pct` | `(users_prev_48h - users_48h) / users_prev_48h * 100` | Rapid drops |
| `completions_7d_drop_pct` | `(completions_prev_7d - completions_7d) / completions_prev_7d * 100` | Trends |

## Full SQL Query

```sql
{sql_query}
```

## Usage Notes

1. **Filter to problems only** - Uncomment WHERE clause at end to show only alerts
2. **By Account Manager** - Use for AM-specific reports
3. **By Game** - Add `WHERE game_name = 'GameName'` to drill into specific game
4. **Export to CSV** - For sharing with AMs or PMs

## Example Alerts Explained

| Alert | What It Means | Action |
|-------|---------------|--------|
| 🔴 CRITICAL BOT RATE (96%) | Almost all users are bots | Urgent: Review quest design, reduce rewards |
| 🔴 EXCESSIVE FARMING (42.3x/user) | Users completing quest 40+ times | Add cooldowns or caps |
| ⚠️ NO COMPLETIONS LAST 7D | Quest had activity, now 0 | Check if quest is broken |
| 📉 TRENDING DOWNWARDS (34%) | Completions dropping steadily | Investigate cause, may be broken |
| ⚠️ POSSIBLY BROKEN | Sudden drop to 0 in 48h | Technical issue likely |

## When to Use

- After Phase 2 decomposition shows large WoW changes
- When investigating specific game's decline/growth
- Weekly quest health audit for all games
- When PM/CG asks "Why did this game's questers drop?"
"""


# Cache the content so we don't read from file multiple times
QUEST_ALERTS_ENHANCED = _get_quest_alerts_enhanced_content()


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
    
    @mcp.resource("questers://context/quest_completions")
    def get_quest_completions() -> str:
        """Quest-level completions analysis for Phase 3 drill-down"""
        return QUEST_COMPLETIONS
    
    @mcp.resource("questers://context/phase0_team_okr")
    def get_phase0_team_okr() -> str:
        """Phase 0: Team-level OKR snapshot showing 30-day quota attainment"""
        return PHASE0_TEAM_OKR
    
    @mcp.resource("questers://context/quest_alerts_enhanced")
    def get_quest_alerts_enhanced() -> str:
        """Enhanced quest audit system with automated alert flags (Phase 3 reference)"""
        return QUEST_ALERTS_ENHANCED