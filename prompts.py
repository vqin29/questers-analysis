"""
Prompts - Pre-defined analysis workflows

## Standard Query Patterns (ALWAYS FOLLOW)

When users ask about specific topics, automatically run the appropriate phase(s):

1. **Gameplay OKR / Quota Attainment** - User asks "what is the gameplay OKR?", "OKR?", "quota?", "gameplay OKR numbers?", etc.
   → IMMEDIATELY run Phase 0 query (phase0_team_okr.sql) - DO NOT just explain the definition
   → Execute the SQL and present ACTUAL NUMBERS:
     * Overall: X/Y games meeting quota (Z% meeting)
     * Tier breakdown table with performance by subscription tier
     * Games below quota with detailed gap analysis
   → User wants live data, not definitions
   
2. **Questers WoW / Questers Performance / Weekly Trends** - User asks "questers WoW?", "questers performance?", "weekly performance?", "how did questers change?", etc.
   → ALWAYS run BOTH Phase 1 AND Phase 2 (REQUIRED):
   
   **Phase 1** (phase1_weekly_trends.sql):
   - Query 1: Overall questers trend (last 2-3 complete weeks) with WoW %
   - Query 2: Per-game breakdown with questers, bot %, and # of quests available
   
   **Phase 2** (phase2_decomposition.sql):
   - Decomposition showing what's DRIVING the change
   - Buckets: New Games, Discontinued Games, Continuing Games (with human/bot split)
   
   → Output must include:
     - Overall WoW trend and % change
     - Decomposition breakdown by bucket
     - Game-level detail: questers, bot %, quests available (week-over-week)
     - New game launches AND discontinued/churned games
"""

# Common filters used across all prompts
COMMON_FILTERS = """- v.is_front_end_cohort = TRUE
- Exclude employees (is_immutable_employee = FALSE)
- Exclude 'Guild of Guardians' and 'Gods Unchained'
- Exclude Maintenance tier (plan_name != 'Maintenance')
- Always filter event_ts"""


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
        return f"""Generate a 4-phase gameplay questers report.

## Required Filters
{COMMON_FILTERS}
- Only active subscriptions (active_subscription = TRUE)

## Phase 0: Team OKR Snapshot
Read `questers://sql/phase0_team_okr` and run query.
Present: Overall (X/Y games meeting quota), Tier breakdown, Games below quota table.

────────────────────────────────────────────

## Phase 1: Present Numbers (Last 2 Complete Weeks)
1. Overall total gameplay questers (distinct across all games)
2. Per-game table: Game | Tier | AM | Curr | Prev | WoW | WoW% | Quests | Bot%

## Phase 2: Decomposition
Classify games into buckets and present tree:
- **New Games**: prev=0, curr>0
- **Discontinued/Off**: prev>0, curr=0 (or confirmed turned off)
- **Continuing**: active both weeks

### Format:
```
Total Δ: +X,XXX (+X.X%)
  + New Games: +X,XXX
  - Discontinued: -X,XXX
  + Continuing: +X,XXX (net)
      Bots: -X | Humans: +X
```

Then write 3-5 numbered PM narratives covering ecosystem health, biggest mover, quality signals.

## Phase 3: Quest-Level Audit (ASK FIRST)
Pause and ask: "Want quest-level audit with automated alerts? Or different angle?"

**If yes:** Read `questers://sql/phase3_quest_alerts` and present by priority.

## Phase 4: Investigate
Based on user direction, run targeted follow-ups."""


    @mcp.prompt()
    def weekly_quester_report(weeks: int = 4) -> str:
        """
        Weekly trends report over multiple weeks.
        
        Args:
            weeks: Number of weeks to analyze (default: 4)
        """
        return f"""Generate weekly quester report for last {weeks} weeks.

## Output
1. Weekly totals (gameplay questers across all games)
2. Per-game table: Game | Week 1 | Week 2 | Week 3 | Week 4 | Trend | Reason
3. Bot % per game per week
4. Quest availability per game per week"""


    @mcp.prompt()
    def investigate_game(game_name: str) -> str:
        """
        Deep dive into a specific game's quester trends.
        
        Args:
            game_name: The game to investigate
        """
        return f"""Investigate gameplay questers for {game_name}.

## Required Filters
{COMMON_FILTERS}

## Phase 1: Present Trend
Show last 4 complete weeks:
| Week | Questers | Bot % | Quests Available |

## Phase 2: ASK for Hypotheses (MANDATORY)
Stop and ask: "What's driving this? Possible angles:
- Quest-level breakdown
- Bot analysis
- Quest lifecycle (added/expired)
- Farming detection"

**WAIT for user input.**

## Phase 3: Investigate
Run targeted queries based on user hypothesis. Report back and iterate.

**SQL Safety:** Use parameterized queries (WHERE g.game_name = @game_name)."""


    @mcp.prompt()
    def bot_analysis() -> str:
        """
        Analyze bot/sybil activity across active games.
        """
        return f"""Analyze bot activity across active games (last complete week).

## Required Filters
{COMMON_FILTERS}

## Output
1. Overall: Total questers vs bot questers, overall bot %
2. Per-game table: Game | Tier | Total | Bots | Bot%
3. High-risk games (bot% >50%)

Join mod_imx.sybil_score on user_id, where bot_score = 1."""


    @mcp.prompt()
    def quest_farming_analysis() -> str:
        """
        Identify over-farmed quests and under-incentivized real players.
        Use for reward rebalancing recommendations.
        """
        return f"""Analyze quest farming patterns (last complete week).

## Required Filters
{COMMON_FILTERS}

## Output
1. Quest Farming Summary: Quest | Game | Completions | Users | Bot% | Comp/User | Risk
   - 🔴 HIGH: Bot% ≥80% OR Comp/User >10
   - 🟡 MEDIUM: Bot% 60-79% OR Comp/User 5-10

2. Bot Efficiency: Compare bot vs human completions per user

3. Under-Incentivized: Low bot%, low completions (real players not engaging)

4. Rebalancing Recommendations based on patterns"""




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
        game_note = f"Filter to g.game_name = @game_name (parameterized). Include bot % per quest." if game_name else "Show all games grouped, no bot % (too expensive)."
        
        return f"""**Note:** For comprehensive audit with alerts, use `questers://sql/phase3_quest_alerts`.

Show quest-level completions {game_filter} (last 3 days).

## Required Filters
{COMMON_FILTERS}
- Last 3 days: event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY))

{game_note}

## Output
Table per game: Quest Name | Completions (3d) | Unique Completers | Comp/User | Flag

Flags: 🔴 >10 comp/user, 🟡 5-10, 📈 highest, 💀 zero

After presenting, ASK: "Any quests stand out? Want to dig deeper?" **WAIT for user.**"""


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
        return f"""Compare gameplay questers:
- Period 1: {start1} to {end1}
- Period 2: {start2} to {end2}

## Output
1. Summary: Metric | P1 | P2 | Change (Total Questers, Bot %, Games Active)
2. Per-game: Game | P1 Questers | P2 Questers | Change % | Reason"""
