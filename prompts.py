"""
Prompts - Pre-defined analysis workflows
"""


def register(mcp):
    """Register all prompts with the MCP server"""
    
    @mcp.prompt()
    def questers_report() -> str:
        """
        Standard weekly gameplay questers report.
        Use this whenever asked about "questers".
        """
        return """Generate a weekly gameplay questers report.

## Required Filters (ALWAYS APPLY)
- v.is_front_end_cohort = TRUE
- Exclude employees (is_immutable_employee = FALSE)
- Exclude 'Guild of Guardians' and 'Gods Unchained'
- Exclude Maintenance tier (plan_name != 'Maintenance')
- Compare last 2 COMPLETE weeks (Mon-Sun UTC) - exclude current week

## Required Output

### 1. Overall Total
Total distinct gameplay questers (users can quest across multiple games).
**NEVER sum per-game totals** - calculate overall separately.

### 2. Per-Game Breakdown
| Game | Tier | AM | Curr Questers | Prev Questers | WoW | WoW% | # Quests (Curr/Prev) | Bot% |
|------|------|-----|---------------|---------------|-----|------|----------------------|------|

### 3. Analysis
For games with significant changes, explain WHY:
- Quest availability change?
- High bot % (sybils)?
- New game launch?

## Instructions
1. Read resources for definitions and required filters
2. Query overall distinct gameplay questers (last 2 complete weeks)
3. Query per-game breakdown with gameplay questers, # quests, bot %
4. Always filter event_ts
5. Explain reasons for any significant WoW changes"""


    @mcp.prompt()
    def weekly_quester_report(weeks: int = 4) -> str:
        """
        Weekly trends report over multiple weeks.
        
        Args:
            weeks: Number of weeks to analyze (default: 4)
        """
        return f"""Generate a weekly quester report for the last {weeks} weeks.

## Required Output

### 1. Weekly Totals
Total gameplay questers per week across all games

### 2. Per-Game Weekly Breakdown
| Game | Week 1 | Week 2 | Week 3 | Week 4 | Trend | Reason |
|------|--------|--------|--------|--------|-------|--------|

### 3. Bot Analysis
Bot % per game using mod_imx.sybil_score (bot_score = 1)

### 4. Quest Availability
Number of gameplay quests available per game each week

## Instructions
1. Read resources for definitions (gameplay questers = gameplay category only)
2. Query weekly gameplay questers by game
   - Always filter event_ts
   - Filter quest_category LIKE '%gameplay%'
3. Calculate bot % from sybil_score
4. Count available quests per week
5. Identify reasons for changes"""


    @mcp.prompt()
    def investigate_game(game_name: str) -> str:
        """
        Deep dive into a specific game's quester trends.
        
        Args:
            game_name: The game to investigate
        """
        return f"""Investigate gameplay questers for {game_name}.

## Required Filters (ALWAYS APPLY)
- v.is_front_end_cohort = TRUE
- Exclude employees
- Compare last 2 complete weeks (Mon-Sun UTC)

## Required Output

### 1. Current State (Last Complete Week)
- Total gameplay questers
- Bot % (from sybil_score where bot_score = 1)
- Available gameplay quests

### 2. Trend (Last 4 Complete Weeks)
| Week | Questers | Bot % | Quests Available |
|------|----------|-------|------------------|

### 3. Root Cause Analysis
Why did questers go up or down?
- Quest availability changes?
- Bot/sybil activity (bot_score = 1)?
- Quest expiration (valid_to)?
- New quests launched?

### 4. Recommendations
What actions to take?

## Instructions
1. Read resources for table schemas and required filters
2. Filter to game_name = '{game_name}'
3. Always filter event_ts
4. Join sybil_score on user_id to get bot %
5. Check quest valid_from/valid_to for availability"""


    @mcp.prompt()
    def bot_analysis() -> str:
        """
        Analyze bot/sybil activity across active games.
        """
        return """Analyze bot activity across all active games (last complete week).

## Required Filters (ALWAYS APPLY)
- v.is_front_end_cohort = TRUE
- Exclude employees
- Exclude GoG, GU
- Exclude Maintenance tier
- Use last complete week (Mon-Sun UTC)

## Required Output

### 1. Overall Bot Stats
- Total gameplay questers vs bot questers
- Overall bot %

### 2. Per-Game Bot Breakdown
| Game | Tier | Total Questers | Bot Questers | Bot % |
|------|------|---------------|--------------|-------|

### 3. High-Risk Games
Games with bot % > 50%

## Instructions
1. Read resources for sybil_score table and required filters
2. Query last complete week of gameplay questers
3. Join mod_imx.sybil_score on visitor.user_id = sybil_score.user_id
4. Bot = bot_score = 1
5. Group by game and calculate bot %"""


    @mcp.prompt()
    def quest_farming_analysis() -> str:
        """
        Identify over-farmed quests and under-incentivized real players.
        Use for reward rebalancing recommendations.
        """
        return """Analyze quest farming patterns to identify:
1. Which quests are over-farmed by bots?
2. Where are real players under-incentivized?

## Required Filters (ALWAYS APPLY)
- v.is_front_end_cohort = TRUE
- Exclude employees
- Exclude GoG, GU, Maintenance tier
- Use last complete week

## Required Output

### 1. Quest Farming Summary
| Quest | Game | Completions | Unique Users | Bot % | Completions/User | Risk |
|-------|------|-------------|--------------|-------|------------------|------|

Risk levels:
- 🔴 HIGH: Bot% ≥80% OR Completions/User >10
- 🟡 MEDIUM: Bot% 60-79% OR Completions/User 5-10
- 🟢 LOW: Bot% <60% AND Completions/User <5

### 2. Bot Density vs Human Density
| Game | Human Users | Bot Users | Human Completions | Bot Completions | Bot Efficiency |
|------|-------------|-----------|-------------------|-----------------|----------------|

Bot Efficiency = Bot Completions per Bot User vs Human Completions per Human User
High efficiency = bots farming more aggressively than humans

### 3. Under-Incentivized Quests (Real Players)
Quests with LOW bot% but ALSO low completions - real players not engaging
| Quest | Game | Human Users | Completions/Human | Issue |
|-------|------|-------------|-------------------|-------|

### 4. Suggested Reward Rebalancing
| Quest | Current State | Recommendation |
|-------|---------------|----------------|
| High bot%, high completions | Over-farmed | Reduce rewards OR add verification |
| Low bot%, low completions | Under-incentivized | Increase rewards OR improve UX |
| High completions/user | Grindable | Add cooldowns OR diminishing returns |

## Instructions
1. Query all quests with completions, unique users, bot %
2. Calculate completions per user (farming indicator)
3. Separate bot vs human metrics
4. Flag high-risk quests for rebalancing"""


    @mcp.prompt()
    def metric_decomposition() -> str:
        """
        Decompose WoW quester delta into driver attributions.
        Use instead of "Questers is down 3%" to show WHY.
        """
        return """Generate a metric decomposition model for WoW quester changes.

## Purpose
Instead of: "Questers is down 3% WoW"
Build: Driver attribution showing WHY with non-overlapping buckets.

## The Model
```
Total Δ = [New Games] + [Discontinued Games] + [Continuing Games]
```

Each game falls into EXACTLY ONE bucket. No double-counting.

## Required Output

### 1. Headline
Total questers delta with direction and %

### 2. Decomposition Table
| Bucket | User Δ | Bot Δ | Human Δ | % of Total |
|--------|--------|-------|---------|------------|
| New Games | +X | +X | +X | X% |
| Discontinued | -X | -X | -X | -X% |
| Continuing Games | ±X | ±X | ±X | X% |

### 3. Bucket Details
For each bucket, list the games with their user/bot breakdown.

### 4. Summary
```
  + New Games:        +X,XXX  (X% of change)
      └─ Game A: +X,XXX (X% bots)
  
  - Discontinued:     -X,XXX  (-X% of change)
      └─ Game B: -X,XXX
  
  ± Continuing Games: ±X,XXX  (X% of change)
      Growth: Game C +X,XXX
      Decline: Game D -X,XXX
  
  ─────────────────────────────
  = Total:            ±X,XXX
```

## Instructions
1. Query per-game WoW totals with bot breakdown
2. Categorize each game into exactly one bucket:
   - New Games: prev_users = 0, curr_users > 0
   - Discontinued: prev_users > 0, curr_users = 0
   - Continuing: prev_users > 0, curr_users > 0
3. Sum each bucket's contribution
4. Show quality split (human vs bot) for each
5. Verify sum ≈ total delta (may differ slightly due to multi-game users)"""


    @mcp.prompt()
    def compare_periods(start1: str, end1: str, start2: str, end2: str) -> str:
        """
        Compare quester activity between two time periods.
        
        Args:
            start1: First period start (YYYY-MM-DD)
            end1: First period end (YYYY-MM-DD)
            start2: Second period start (YYYY-MM-DD)
            end2: Second period end (YYYY-MM-DD)
        """
        return f"""Compare gameplay questers between two periods:
- Period 1: {start1} to {end1}
- Period 2: {start2} to {end2}

## Required Output

### 1. Summary
| Metric | Period 1 | Period 2 | Change |
|--------|----------|----------|--------|
| Total Questers | | | |
| Bot % | | | |
| Games Active | | | |

### 2. Per-Game Comparison
| Game | P1 Questers | P2 Questers | Change % | Reason |
|------|-------------|-------------|----------|--------|

## Instructions
1. Filter event_ts to each period
2. Filter gameplay category only
3. Calculate bot % from sybil_score
4. Compare and explain changes"""
