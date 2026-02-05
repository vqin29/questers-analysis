# Questers MCP Server

MCP server for tracking and analyzing gameplay questers across Immutable games.

## Quick Start

```bash
# Run weekly decomposition model
python3 decomposition.py

# Run PM/CG summary
python3 weekly_summary.py
```

## Features

### 1. Weekly Summary (`weekly_summary.py`)
PM-ready table with all active games:
- Questers WoW comparison
- Quest availability (in-game quests)
- Bot % by game
- Key drivers (new launches, declines, bot influx)

### 2. Metric Decomposition (`decomposition.py`)
Explains WHY questers changed with non-overlapping buckets:
```
Total Δ = [New Games] + [Discontinued Games] + [Continuing Games]
```

### 3. Quest Farming Analysis
Identifies over-farmed quests and under-incentivized real players:
- Bot % by quest
- Completions per user (grinding indicator)
- Reward rebalancing recommendations

### 4. MCP Server (`server.py`)
FastMCP server with prompts for AI-assisted analysis.

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
| `decomposition.py` | Metric decomposition model |
| `weekly_summary.py` | PM/CG weekly summary |
| `server.py` | MCP server entry point |
| `prompts.py` | Analysis prompts |
| `resources.py` | Context and definitions |
| `tools.py` | BigQuery query tool |

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Authenticate with Google Cloud:
```bash
gcloud auth application-default login
```

3. Run scripts:
```bash
python3 decomposition.py
python3 weekly_summary.py
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

## Prompts Available

- `questers_report` - Standard weekly report
- `metric_decomposition` - WoW delta breakdown
- `quest_farming_analysis` - Bot/farming detection
- `investigate_game` - Deep dive into specific game
- `bot_analysis` - Bot activity across all games
