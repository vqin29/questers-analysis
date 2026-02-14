# Questers MCP Server

MCP server for tracking and analyzing gameplay questers across Immutable games using a **4-Phase Analysis Framework**.

## Quick Start

### Run MCP Server
```bash
python3 server.py
```

The server exposes resources (context), prompts (analysis workflows), and SQL queries for Phase 0-3 analysis.

## Project Structure

### SQL Files (All phases consolidated)
```
├── phase0_team_okr.sql          # Phase 0: 30-day quota attainment
├── phase1_weekly_trends.sql     # Phase 1: Weekly WoW trends and farming
├── phase2_decomposition.sql     # Phase 2: Driver attribution (New/Discontinued/Continuing)
├── phase3_quest_completions.sql # Phase 3: Quest-level drill-down
└── phase3_quest_alerts.sql      # Phase 3: Automated quest health alerts
```

All SQL queries are externalized for easier testing, maintenance, and version control.

## Features

### 1. 4-Phase Analysis Framework (MCP Server)

**Phase 0: Team OKR Snapshot (30-day rolling)**
- Overall quota attainment (% of games meeting monthly targets)
- Tier breakdown (Core, Boost, Ultra Boost)
- Games below quota with gap analysis
- Filtered: ≥10 questers AND non-testing quests only

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

### 2. Quest Health Monitoring

**Quest Alerts Dashboard (Phase 3)**
Identifies problematic quests at scale:
- Bot % per quest
- Completions per user (grinding indicator)
- Activity drops (48h and 7d windows)
- Automated alert flags and priority levels

## Required Filters (Always Applied)

```sql
AND v.is_front_end_cohort = TRUE
AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
AND g.plan_name != 'Maintenance'
```

## Key Definitions

| Term | Definition |
|------|------------|
| **Gameplay Questers** | Users completing quests with `gameplay` category |
| **Bot** | User with `sybil_score.bot_score = 1` |
| **Week** | Monday 00:00 UTC to Sunday 23:59 UTC |
| **Active Games** | Non-maintenance tier (Core, Boost, Ultra Boost) |

## Files

| File | Purpose |
|------|---------|
| `server.py` | MCP server entry point |
| `prompts.py` | Analysis prompts (Phase 0-3 workflows) |
| `resources.py` | Context and definitions (loads SQL from files) |
| `tools.py` | BigQuery query tool |
| `phase0_team_okr.sql` | Phase 0 SQL query (Team OKR snapshot) |
| `phase3_quest_alerts.sql` | Phase 3 SQL query (Quest audit with alerts) |
| `requirements.txt` | Python dependencies |

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Authenticate with Google Cloud:
```bash
gcloud auth application-default login
```

3. Run the MCP server:
```bash
python3 server.py
```

## MCP Server Usage

Add to `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "questers": {
      "command": "python3",
      "args": ["/path/to/server.py"]
    }
  }
}
```

## Available MCP Resources

The server exposes context resources that can be integrated into other MCP servers:

- `questers://context/definitions` - Core definitions (gameplay questers, bot detection, filters)
- `questers://context/tables` - BigQuery table schemas
- `questers://context/analysis` - Analysis patterns
- `questers://context/decomposition` - Metric decomposition model
- `questers://context/phase0_team_okr` - Phase 0: Team-level quota attainment (30-day rolling)
- `questers://sql/phase3_quest_alerts` - Phase 3 quest audit with automated alerts
- `questers://context/quest_completions` - Quest-level completions analysis
- `questers://context/farming` - Quest farming detection

## Available Prompts

- `questers_report` - Full 4-phase weekly report (Phase 0 → 1 → 2 → 3)
- `metric_decomposition` - WoW delta breakdown with driver attribution
- `investigate_game` - Deep dive into specific game
- `bot_analysis` - Bot activity across all games
- `quest_completions_breakdown` - Simple quest completions (no alerts)
- `quest_farming_analysis` - Quest farming and reward rebalancing

## Integrating with Your Team's MCP

If your team has an existing MCP server with BigQuery access, you can add the questers analysis framework:

### Option 1: Copy Resources and Prompts
Copy the relevant sections from `resources.py` and `prompts.py` into your team's MCP:

```python
# In your team's MCP server
@mcp.resource("uri://questers/analysis-framework")
def questers_analysis():
    """3-Phase questers analysis framework"""
    # Copy DECOMPOSITION + QUEST_ALERTS_ENHANCED from resources.py
    return context_string

@mcp.prompt()
def weekly_questers_report():
    """Run weekly questers analysis"""
    # Copy questers_report() from prompts.py
    return prompt_string
```

### Option 2: Reference SQL Files
Share the SQL files directly for your team's BigQuery integration:
- `phase0_team_okr.sql` - Phase 0: Team OKR snapshot (30-day quota attainment)
- `phase3_quest_alerts.sql` - Phase 3: Quest audit with automated alerts

### Option 3: Run as Separate MCP Server
Keep as standalone server and reference from your main MCP using MCP-to-MCP communication.
