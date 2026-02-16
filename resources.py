"""
Resources - Context for the AI to understand tables and definitions
"""
from pathlib import Path

# Get the directory containing this file
_SCRIPT_DIR = Path(__file__).parent


def _load_sql(filename: str) -> str:
    """Load SQL content from a file"""
    sql_path = _SCRIPT_DIR / filename
    try:
        with open(sql_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Required SQL file not found: {sql_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to load SQL file {filename}: {e}")

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

For WoW comparison, always exclude current incomplete week:
```sql
event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
```

See `phase1_weekly_trends.sql` and `phase2_decomposition.sql` for complete examples.

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

## Standard Query Patterns (ALWAYS FOLLOW)

When users ask about specific topics, automatically run the appropriate phase(s):

### 1. Gameplay OKR Questions
User asks: "What is the gameplay OKR?" / "How are games doing against quota?" / "OKR status?" / "quota attainment"
→ **Run Phase 0** (phase0_team_okr.sql)
→ Show: Overall quota attainment, tier breakdown, games below quota

### 2. Questers WoW / Week-over-Week / Performance Questions  
User asks: "What about questers WoW?" / "Weekly performance?" / "How did questers change?" / "Questers performance?" / any question about questers trends
→ **Run BOTH Phase 1 AND Phase 2** (REQUIRED - NOT OPTIONAL):
  
  **Phase 1** (phase1_weekly_trends.sql) - Run ALL 3 queries:
  - Query 1: Overall gameplay questers (last 2-3 complete weeks) showing WoW trend
  - Query 2: Per-game breakdown showing questers, quests available, bot % for last week
  - Query 3: Quest farming analysis (optional, show if relevant)
  
  **Phase 2** (phase2_decomposition.sql):
  - Decomposition into New Games, Discontinued Games, and Continuing Games with human/bot split
  - Shows what's DRIVING the WoW change (not just the headline number)
  
→ **Output MUST include**:
  1. Overall WoW trend (total questers by week with % change)
  2. Decomposition breakdown (New/Discontinued/Continuing buckets with impact)
  3. Game-level table: Game | Questers | Bot % | Quests Available (week-over-week comparison)
  4. New game launches (games that went from 0 to N questers)
  5. Discontinued/churned games (games that went from N to 0 questers or turned off)
  6. Key insights about quality (human vs bot growth)

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

## Investigation Workflow

1. **Present numbers first** - Overall + per-game breakdown
2. **Flag top movers** - Top 3-5 games with biggest changes
3. **STOP and ASK** - Let user choose what to investigate
4. **Run targeted queries** - Based on user hypothesis
5. **Iterate** - Report back and ask if they want more

**Key principle:** Don't dump all analysis at once. Make it a conversation.

## Reference SQL Queries

See `phase1_weekly_trends.sql` for complete SQL queries including:
- Overall Gameplay Questers (Last 2 Complete Weeks)
- Per-Game Breakdown with WoW
- Quest Farming Analysis

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
| High human engagement, low bot% | Keep as-is (healthy quest) |"""


DECOMPOSITION = """# Metric Decomposition Model

## Purpose
Replace "Questers is down 3%" with driver attribution showing WHY.
This is the STANDARD format for Phase 2 analysis in all weekly reports.

## Reference SQL Query

See `phase2_decomposition.sql` for the complete WoW decomposition query that classifies
games into buckets and calculates human/bot splits.

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

Use ⚠️ for concerning signals (high bot %, bot spike) and ✓ for healthy signals."""


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

## Reference SQL Queries

See `phase3_quest_completions.sql` for complete SQL queries including:
- All Active Games - Quest Completions (Last 3 Days)
- Specific Game with Bot % Breakdown (Last 3 Days)

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


def _get_phase1_weekly_trends_content() -> str:
    """Phase 1: Weekly trends SQL"""
    return _load_sql('phase1_weekly_trends.sql')


def _get_phase2_decomposition_content() -> str:
    """Phase 2: WoW decomposition SQL"""
    return _load_sql('phase2_decomposition.sql')


def _get_phase3_quest_completions_content() -> str:
    """Phase 3: Quest completions SQL"""
    return _load_sql('phase3_quest_completions.sql')


def _get_phase0_team_okr_content() -> str:
    """Phase 0: Team OKR with 30-day quota attainment"""
    sql_query = _load_sql('phase0_team_okr.sql')
    
    return f"""# Phase 0: Team OKR Overview

Shows % of active games meeting monthly gameplay quotas (30-day rolling).

## Metric
**Quota Attainment** = `actual_questers_30d / monthly_gameplay_target * 100`

## Filters
- Games with ≥10 questers in last 30 days
- At least 1 non-testing gameplay quest
- Has `monthly_gameplay_target` set

## Output Format
1. Overall: "X/Y games (Z%) meeting quota"
2. Tier breakdown (Ultra Boost, Boost, Core)
3. Table of games BELOW quota (<100%), sorted by % ascending

## SQL Query
```sql
{sql_query}
```"""


# Cache the content so we don't read from file multiple times
PHASE0_TEAM_OKR = _get_phase0_team_okr_content()
PHASE1_WEEKLY_TRENDS_SQL = _get_phase1_weekly_trends_content()
PHASE2_DECOMPOSITION_SQL = _get_phase2_decomposition_content()
PHASE3_QUEST_COMPLETIONS_SQL = _get_phase3_quest_completions_content()


def _get_quest_alerts_enhanced_content() -> str:
    """Phase 3: Quest audit with automated alert flags"""
    sql_query = _load_sql('phase3_quest_alerts.sql')
    
    return f"""# Quest Alerts Dashboard (Phase 3)

Identifies problematic quests: broken, bot-farmed, declining, engagement issues.

## Alert Priority
- 🔴 **Critical (1-2)**: Bot% ≥80%, farming >20x/user, possibly broken
- 🟡 **Medium (3)**: Bot% 70-80%, farming 10-20x, major drops >70%
- ⚠️ **Low (4)**: Low activity, no recent completions

## Time Windows
- 48h: Rapid anomaly detection
- 7d: Trend analysis
- 30d: Bot % baseline

## SQL Query
```sql
{sql_query}
```"""


# Cache the content so we don't read from file multiple times
QUEST_ALERTS_ENHANCED = _get_quest_alerts_enhanced_content()


def register(mcp):
    """
    Register all resources with the MCP server.
    
    Resources registered:
    - questers://context/definitions - Core definitions (gameplay questers, bot detection, filters)
    - questers://context/tables - BigQuery table schemas
    - questers://context/analysis - Analysis patterns
    - questers://context/decomposition - Metric decomposition model
    - questers://context/farming - Quest farming detection
    - questers://context/quest_completions - Quest-level completions analysis
    - questers://sql/phase0_team_okr - Phase 0 SQL: Team-level quota attainment
    - questers://sql/phase1_weekly_trends - Phase 1 SQL: Weekly trends and farming analysis
    - questers://sql/phase2_decomposition - Phase 2 SQL: WoW driver attribution
    - questers://sql/phase3_quest_completions - Phase 3 SQL: Quest-level drill-down
    - questers://sql/phase3_quest_alerts - Phase 3 SQL: Quest audit with automated alerts
    """
    
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
    
    # SQL References - Provide complete queries with documentation
    @mcp.resource("questers://sql/phase0_team_okr")
    def get_phase0_sql() -> str:
        """Phase 0 SQL: Team-level OKR snapshot showing 30-day quota attainment"""
        return PHASE0_TEAM_OKR
    
    @mcp.resource("questers://sql/phase1_weekly_trends")
    def get_phase1_sql() -> str:
        """Phase 1 SQL: Weekly trends and quest farming analysis"""
        return PHASE1_WEEKLY_TRENDS_SQL
    
    @mcp.resource("questers://sql/phase2_decomposition")
    def get_phase2_sql() -> str:
        """Phase 2 SQL: WoW driver attribution with bucket classification"""
        return PHASE2_DECOMPOSITION_SQL
    
    @mcp.resource("questers://sql/phase3_quest_completions")
    def get_phase3_completions_sql() -> str:
        """Phase 3 SQL: Quest-level completions drill-down"""
        return PHASE3_QUEST_COMPLETIONS_SQL
    
    @mcp.resource("questers://sql/phase3_quest_alerts")
    def get_phase3_alerts_sql() -> str:
        """Phase 3 SQL: Enhanced quest audit system with automated alert flags"""
        return QUEST_ALERTS_ENHANCED