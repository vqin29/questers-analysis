# Questers MCP Server

Track weekly gameplay quester activity and analyze trends for active games.

## Definitions

| Term | Meaning |
|------|---------|
| **Gameplay Questers** | Users completing quests with `gameplay` category |
| **Bot** | User with `bot_score = 1` in `mod_imx.sybil_score` |
| **Active Games** | Games with plan_name = Core, Boost, or Ultra Boost (not Maintenance) |

## Required Filters (Always Applied)

```sql
AND v.is_front_end_cohort = TRUE
AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
AND g.plan_name != 'Maintenance'
```

## Important Notes

- **Week Definition**: Monday to Sunday (UTC)
- **Comparisons**: Always use last 2 **complete** weeks (exclude current incomplete week)
- **Overall Total**: Never sum per-game totals (users quest across multiple games)

## Structure

```
vivian-questers-bot/
├── server.py       # Entry point
├── resources.py    # Context (definitions, tables, filters)
├── prompts.py      # Pre-defined workflows
├── tools.py        # Actions (query_bigquery)
├── requirements.txt
└── README.md
```

## Components

### Resources
| Resource | Purpose |
|----------|---------|
| `questers://context/definitions` | Quester definitions, required filters |
| `questers://context/tables` | Table schemas |
| `questers://context/analysis` | Query patterns |

### Tools
| Tool | Purpose |
|------|---------|
| `query_bigquery` | Execute SQL (blocks queries without event_ts filter) |

### Prompts
| Prompt | Purpose |
|--------|---------|
| `questers_report` | Weekly gameplay questers report |
| `weekly_quester_report` | Multi-week trends |
| `investigate_game` | Deep dive on one game |
| `bot_analysis` | Bot activity breakdown |
| `compare_periods` | Compare two time periods |

## Tables

| Table | Purpose |
|-------|---------|
| `app_immutable_play.event` | Quest completions (always filter event_ts!) |
| `app_immutable_play.quest` | Quest definitions |
| `app_immutable_play.visitor` | User profiles |
| `app_immutable_play.game` | Game metadata (plan_name, account_manager_name) |
| `mod_imx.sybil_score` | Bot detection (bot_score = 1) |

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Authenticate with Google Cloud
gcloud auth application-default login

# 3. Add to ~/.cursor/mcp.json
{
  "mcpServers": {
    "questers": {
      "command": "python3",
      "args": ["/path/to/vivian-questers-bot/server.py"]
    }
  }
}

# 4. Restart Cursor
```

## Usage

```
@questers How are gameplay questers doing?
@questers Investigate Chainers
@questers Show me bot activity by game
```
