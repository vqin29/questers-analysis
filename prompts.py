"""
Prompts - Pre-defined analysis workflows
"""


def register(mcp):
    """
    Register all prompts with the MCP server.
    
    Prompts registered:
    - questers_report - Full 4-phase weekly report (Phase 0 → 1 → 2 → 3)
    - metric_decomposition - WoW delta breakdown with driver attribution
    - investigate_game - Deep dive into specific game
    - bot_analysis - Bot activity across all games
    - quest_completions_breakdown - Simple quest completions (no alerts)
    - quest_farming_analysis - Quest farming and reward rebalancing
    """
    
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
2. Apply filters: ≥10 questers AND non_testing_quests > 0
3. Present overall summary: "X/Y games (Z%) meeting monthly target"
4. Present tier breakdown (Ultra Boost, Boost, Core)
5. Present table of games BELOW quota only (actual < target)
   - Include: Game, Tier, AM, Actual (30d), Target, % of Quota, Gap, # Gameplay Quests
   - Sort by % of Quota ascending (worst first)
6. Add separator line: `────────────────────────────────────────────`

### Time Window
Use last 30 days: `e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))`

### Additional Filters
- `HAVING COUNT(DISTINCT e.visitor_id) >= 10` (exclude low-activity/testing games)
- `WHERE non_testing_quests > 0` (exclude games with only testing quests)

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
(Note: Ensure game name is properly escaped in SQL to prevent injection)

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

## Phase 1: Present Current State

### 1. Current State (Last Complete Week)
- Total gameplay questers
- Bot % (from sybil_score where bot_score = 1)
- Available gameplay quests

### 2. Trend (Last 4 Complete Weeks)
| Week | Questers | Bot % | Quests Available |
|------|----------|-------|------------------|

## Phase 2: ASK for Hypotheses (MANDATORY)
After showing the trend, STOP and ask the user:

"Here's the trend for {game_name}. What do you think is driving this?

Possible angles to investigate:
- Quest-level breakdown (which specific quests gained/lost users?)
- Bot analysis (is the change driven by bots or real users?)
- Quest lifecycle (did quests expire or get added?)
- Farming detection (are specific quests being over-farmed?)
- User behavior (completions per user, repeat vs new users?)

Do you have a hypothesis, or would you like me to suggest one?"

**WAIT for user input before running investigation queries.**

## Phase 3: Targeted Investigation (after user responds)
Run queries based on user's hypothesis or chosen angle.

### Root Cause Analysis
Why did questers go up or down?
- Quest availability changes?
- Bot/sybil activity (bot_score = 1)?
- Quest expiration (valid_to)?
- New quests launched?

### Report Back and Iterate
Present findings and ask: "Does this explain it, or should we look at
something else?"

## Instructions
1. Read resources for table schemas and required filters
2. Filter to game_name = '{game_name}' (ensure game_name is properly escaped in SQL)
3. Always filter event_ts
4. Present numbers and trend FIRST
5. **ASK the user for hypotheses before investigating**

**SQL Safety Note:** When constructing queries, use BigQuery parameterized queries
or ensure game_name is properly escaped to prevent SQL injection.
Example: WHERE g.game_name = @game_name (parameterized)
6. Run targeted queries based on user direction
7. Join sybil_score on user_id to get bot %
8. Check quest valid_from/valid_to for availability"""


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
Total Δ = [New Games] + [Discontinued / Off] + [Continuing Games]
```

Each game falls into EXACTLY ONE bucket. No double-counting.

## Bucket Classification Rules
- **New Games**: prev_users = 0, curr_users > 0
- **Discontinued / Off**: prev_users > 0, curr_users = 0
  **ALSO include games confirmed as turned off or set to inactive, even if they
  have small residual activity in curr week.** A game that dropped >95% of
  questers AND is known to be turned off should be reclassified from Continuing
  to Discontinued. ASK the user if unsure.
- **Continuing**: all other games active both weeks

## Required Output (ALWAYS use this exact format)

### 1. Headline
One bold sentence: the delta AND the quality story (bot vs human shift).
Summary table:
| | Prev Week | Curr Week | Delta | % Change |
|--|-----------|-----------|-------|----------|
| Total Questers | | | | |
| Human Questers | | | | |
| Bot Questers | | | | |
| Bot % | | | | -Xpp |

### 2. Decomposition Tree
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

### 3. PM Narrative
Write 3-5 numbered key narratives, each 1-2 sentences. Focus on:
1. Overall ecosystem health (bot % shift, human growth)
2. The biggest single mover and why
3. Discontinued games — were they low quality? Healthy cleanup?
4. New game launches — early bot % warning?
5. Continuing games — is human growth real and broad-based?

### 4. Games to Watch
| Game | Signal | Risk |
|------|--------|------|
Flag any game with: new launch + high bot%, sudden bot spike,
or large unexplained quester swing.

## Instructions
1. Query overall totals with bot/human split (last 2 complete weeks)
2. Query per-game WoW totals with bot/human breakdown
3. Classify games into buckets (ask user about reclassification if needed)
4. Present full decomposition: headline, tree, PM narrative, games to watch
5. Verify bucket sum ≈ total delta (note multi-game user caveat)

## After Presenting Decomposition: ASK (MANDATORY)
After showing the decomposition, STOP and ask:

"Which of these would you like me to investigate further?
Do you have a hypothesis for why [biggest mover] changed?

I can run:
  - **Quest-level audit** (enhanced with automated alerts - identifies broken/farmed quests)
  - Bot vs human split (is this real growth or bot inflation?)
  - Multi-week trend (is this a one-off or sustained?)
  - User overlap (are users migrating between games?)"

**WAIT for user direction before investigating further.**

If user chooses quest-level audit, read `questers://context/quest_alerts_enhanced` resource."""


    @mcp.prompt()
    def quest_completions_breakdown(game_name: str = "") -> str:
        """
        Quest-level completions breakdown for active games (Phase 3).
        
        For detailed audit with alerts, use the enhanced version instead.
        This is a simpler view showing just completions without alert flags.
        
        Args:
            game_name: Optional game to filter to. Leave empty for all active games.
        """
        game_filter = f'for **{game_name}**' if game_name else 'across **all active non-Maintenance games**'
        enhanced_note = """
**Note:** For a more comprehensive audit with automated alert flags (broken quests,
bot farming, etc.), use the enhanced quest audit by reading the
`questers://context/quest_alerts_enhanced` resource instead.
"""
        game_specific_note = f"""
### Game-Specific Instructions
Since the user asked about {game_name}:
- Filter to g.game_name = '{game_name}' (ensure proper SQL escaping)
- Include bot % per quest (join sybil_score)
- Use the "Filtered Query: Specific Game" from the quest_completions resource

**SQL Safety:** Use parameterized queries (WHERE g.game_name = @game_name) or ensure
game_name is properly escaped to prevent SQL injection.
""" if game_name else """
### All-Games Instructions
- Show ALL active non-Maintenance games
- Group results by game
- Use the "Default Query: All Active Games" from the quest_completions resource
- Do NOT include bot % in the all-games view (too expensive) — save it for drill-down
"""
        return f"""{enhanced_note}

Show quest-level completions {game_filter} for the last 3 days.

## Required Filters (ALWAYS APPLY)
- v.is_front_end_cohort = TRUE
- Exclude employees (is_immutable_employee = FALSE)
- Exclude 'Guild of Guardians' and 'Gods Unchained'
- Exclude Maintenance tier (plan_name != 'Maintenance')
- Last 3 days: event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY))

## Steps
1. Read the `questers://context/quest_completions` resource for reference queries
2. Read the `questers://context/definitions` resource for standard filters
3. Run the appropriate query (all games or specific game)
4. Present results in the format specified by the resource
{game_specific_note}
## Output Format
For each game, show a table of quests sorted by completions descending:

| Quest Name | Completions (3d) | Unique Completers | Completions/User | Flag |
|-----------|-------------------|-------------------|------------------|------|

Flag any quests with:
- 🔴 Completions/User > 10 (possible farming)
- 🟡 Completions/User 5-10 (high engagement, monitor)
- 📈 Highest completions for the game
- 💀 0 completions (possibly expired/broken)

## After Presenting: ASK (MANDATORY)
"Any quests stand out? I can dig deeper into:
  - A specific quest's trend over time
  - Bot vs human breakdown for a quest
  - Whether a quest was recently added or is about to expire
  - Completions per user distribution (farming detection)"

**WAIT for user direction before investigating further.**"""


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
