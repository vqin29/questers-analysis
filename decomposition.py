"""
Metric Decomposition Model - Weekly Quester Analysis
Run: python decomposition.py
"""

from google.cloud import bigquery
import warnings
warnings.filterwarnings("ignore")


def run_decomposition():
    client = bigquery.Client()

    # Get per-game WoW data with bot breakdown
    games = list(client.query('''
    WITH prev AS (
      SELECT g.game_name, COUNT(DISTINCT e.visitor_id) total,
        COUNT(DISTINCT CASE WHEN s.bot_score=1 THEN e.visitor_id END) bots
      FROM `app_immutable_play.event` e
      JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
      LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
      LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
      LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id, UNNEST(q.quest_category) cat
      WHERE e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 14 DAY))
        AND e.event_ts < TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 7 DAY))
        AND v.is_front_end_cohort = TRUE AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
        AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained') AND g.plan_name != 'Maintenance'
        AND cat LIKE '%gameplay%'
      GROUP BY g.game_name
    ),
    curr AS (
      SELECT g.game_name, COUNT(DISTINCT e.visitor_id) total,
        COUNT(DISTINCT CASE WHEN s.bot_score=1 THEN e.visitor_id END) bots
      FROM `app_immutable_play.event` e
      JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
      LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
      LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
      LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id, UNNEST(q.quest_category) cat
      WHERE e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 7 DAY))
        AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
        AND v.is_front_end_cohort = TRUE AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
        AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained') AND g.plan_name != 'Maintenance'
        AND cat LIKE '%gameplay%'
      GROUP BY g.game_name
    )
    SELECT COALESCE(c.game_name, p.game_name) game,
      COALESCE(p.total,0) pt, COALESCE(c.total,0) ct,
      COALESCE(p.bots,0) pb, COALESCE(c.bots,0) cb
    FROM curr c FULL OUTER JOIN prev p ON c.game_name = p.game_name
    ORDER BY ABS(COALESCE(c.total,0) - COALESCE(p.total,0)) DESC
    ''').result())

    # Get overall totals
    totals = list(client.query('''
    SELECT 
      DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) wk,
      COUNT(DISTINCT e.visitor_id) total,
      COUNT(DISTINCT CASE WHEN s.bot_score=1 THEN e.visitor_id END) bots
    FROM `app_immutable_play.event` e
    JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
    LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
    LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
    LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id, UNNEST(q.quest_category) cat
    WHERE e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 21 DAY))
      AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
      AND v.is_front_end_cohort = TRUE AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
      AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained') AND g.plan_name != 'Maintenance'
      AND cat LIKE '%gameplay%'
    GROUP BY wk ORDER BY wk DESC
    ''').result())

    prev_total, curr_total = totals[1].total, totals[0].total
    prev_bots, curr_bots = totals[1].bots, totals[0].bots
    total_delta = curr_total - prev_total

    # Categorize games
    new_games = [(g.game, g.ct, g.cb) for g in games if g.pt == 0 and g.ct > 0]
    discontinued = [(g.game, g.pt, g.pb) for g in games if g.ct == 0 and g.pt > 0]
    continuing = [(g.game, g.pt, g.ct, g.pb, g.cb) for g in games if g.pt > 0 and g.ct > 0]

    # Calculate bucket totals
    new_total = sum(g[1] for g in new_games)
    new_bots = sum(g[2] for g in new_games)
    disc_total = sum(g[1] for g in discontinued)
    disc_bots = sum(g[2] for g in discontinued)
    cont_delta = sum(g[2] - g[1] for g in continuing)
    cont_bot_delta = sum(g[4] - g[3] for g in continuing)

    # Output
    print("=" * 80)
    print(" METRIC DECOMPOSITION MODEL ".center(80))
    print("=" * 80)
    print()
    print(f"## HEADLINE: Questers {total_delta:+,} ({100*total_delta/prev_total:+.1f}%) WoW")
    print(f"   {prev_total:,} → {curr_total:,}")
    print()
    print("-" * 80)
    print("## DECOMPOSITION")
    print("-" * 80)
    print()
    print(f"| Bucket | User Δ | Bot Δ | Human Δ | % of Total |")
    print(f"|--------|--------|-------|---------|------------|")

    new_human = new_total - new_bots
    print(f"| **New Games** | +{new_total:,} | +{new_bots:,} | +{new_human:,} | +{100*new_total/abs(total_delta):.0f}% |")

    disc_human = disc_total - disc_bots
    print(f"| **Discontinued** | -{disc_total:,} | -{disc_bots:,} | -{disc_human:,} | -{100*disc_total/abs(total_delta):.0f}% |")

    cont_human_delta = cont_delta - cont_bot_delta
    print(f"| **Continuing Games** | {cont_delta:+,} | {cont_bot_delta:+,} | {cont_human_delta:+,} | {100*cont_delta/abs(total_delta):+.0f}% |")
    print()

    print("-" * 80)
    print("## BUCKET 1: NEW GAMES (+{:,})".format(new_total))
    print("-" * 80)
    print()
    print(f"| Game | Users | Bots | Humans | Bot % |")
    print(f"|------|-------|------|--------|-------|")
    for g in sorted(new_games, key=lambda x: -x[1]):
        bp = 100*g[2]/g[1] if g[1] else 0
        flag = "⚠️" if bp > 70 else "✓"
        print(f"| {g[0]} | +{g[1]:,} | +{g[2]:,} | +{g[1]-g[2]:,} | {bp:.0f}% {flag} |")
    print()

    print("-" * 80)
    print("## BUCKET 2: DISCONTINUED GAMES (-{:,})".format(disc_total))
    print("-" * 80)
    print()
    print(f"| Game | Users Lost | Were Bots | Were Humans |")
    print(f"|------|------------|-----------|-------------|")
    for g in sorted(discontinued, key=lambda x: -x[1]):
        print(f"| {g[0]} | -{g[1]:,} | -{g[2]:,} | -{g[1]-g[2]:,} |")
    print()

    print("-" * 80)
    print("## BUCKET 3: CONTINUING GAMES ({:+,})".format(cont_delta))
    print("-" * 80)
    print()
    print(f"| Game | Prev | Curr | Δ Users | Δ Bots | Δ Humans |")
    print(f"|------|------|------|---------|--------|----------|")
    for g in sorted(continuing, key=lambda x: -(x[2]-x[1]))[:10]:
        d = g[2] - g[1]
        bd = g[4] - g[3]
        hd = d - bd
        print(f"| {g[0][:25]} | {g[1]:,} | {g[2]:,} | {d:+,} | {bd:+,} | {hd:+,} |")
    print("| ... | | | | | |")
    for g in sorted(continuing, key=lambda x: (x[2]-x[1]))[:5]:
        d = g[2] - g[1]
        bd = g[4] - g[3]
        hd = d - bd
        print(f"| {g[0][:25]} | {g[1]:,} | {g[2]:,} | {d:+,} | {bd:+,} | {hd:+,} |")
    print(f"| **TOTAL** | | | {cont_delta:+,} | {cont_bot_delta:+,} | {cont_human_delta:+,} |")
    print()

    print("=" * 80)
    print(" SUMMARY ".center(80))
    print("=" * 80)
    print()
    print(f"**Total Change: {total_delta:+,} ({100*total_delta/prev_total:+.1f}%)**")
    print()
    print("```")
    print(f"  + New Games:        +{new_total:,}  (+{100*new_total/abs(total_delta):.0f}% of change)")
    for g in new_games:
        bp = 100*g[2]/g[1] if g[1] else 0
        flag = "⚠️" if bp > 70 else "✓"
        print(f"      └─ {g[0]}: +{g[1]:,} ({bp:.0f}% bots) {flag}")
    print()
    print(f"  - Discontinued:     -{disc_total:,}  (-{100*disc_total/abs(total_delta):.0f}% of change)")
    for g in discontinued:
        print(f"      └─ {g[0]}: -{g[1]:,}")
    print()
    print(f"  ± Continuing Games: {cont_delta:+,}  ({100*cont_delta/abs(total_delta):+.0f}% of change)")
    top_growth = sorted(continuing, key=lambda x: -(x[2]-x[1]))[:3]
    top_decline = sorted(continuing, key=lambda x: (x[2]-x[1]))[:3]
    print(f"      Growth:")
    for g in top_growth:
        print(f"        └─ {g[0]}: {g[2]-g[1]:+,}")
    print(f"      Decline:")
    for g in top_decline:
        print(f"        └─ {g[0]}: {g[2]-g[1]:+,}")
    print()
    print(f"  ─────────────────────────────")
    print(f"  = Total:            {total_delta:+,}")
    print("```")
    print()
    print("**Quality Split:**")
    print(f"  • Human users: {curr_total - curr_bots:,} ({100*(curr_total-curr_bots)/curr_total:.0f}% of total)")
    print(f"  • Bot users:   {curr_bots:,} ({100*curr_bots/curr_total:.0f}% of total)")


if __name__ == "__main__":
    run_decomposition()
