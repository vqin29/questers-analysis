"""
Weekly PM & CG Summary - All-in-one report
Run: python weekly_summary.py
"""

from google.cloud import bigquery
import warnings
warnings.filterwarnings("ignore")


def run_weekly_summary():
    client = bigquery.Client()

    # Get dates
    dates = list(client.query('''
    SELECT 
      DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 7 DAY) as c,
      DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 14 DAY) as p
    ''').result())[0]

    # Overall totals
    overall = list(client.query('''
    SELECT DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) as wk, COUNT(DISTINCT e.visitor_id) as q
    FROM `app_immutable_play.event` e
    JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
    LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
    LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id, UNNEST(q.quest_category) cat
    WHERE e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 21 DAY))
      AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
      AND v.is_front_end_cohort = TRUE AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
      AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained') AND g.plan_name != 'Maintenance'
      AND cat LIKE '%gameplay%'
    GROUP BY wk ORDER BY wk DESC
    ''').result())

    # Per-game data
    rows = list(client.query('''
    WITH wq AS (
      SELECT g.game_name, g.plan_name tier, g.account_manager_name am, DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) wk, COUNT(DISTINCT e.visitor_id) q
      FROM `app_immutable_play.event` e JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
      LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id, UNNEST(q.quest_category) cat
      WHERE e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 21 DAY)) AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
        AND v.is_front_end_cohort = TRUE AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
        AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained') AND g.plan_name != 'Maintenance' AND cat LIKE '%gameplay%'
      GROUP BY 1,2,3,4
    ), wb AS (
      SELECT g.game_name, DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) wk, COUNT(DISTINCT e.visitor_id) t, COUNT(DISTINCT CASE WHEN s.bot_score=1 THEN e.visitor_id END) b
      FROM `app_immutable_play.event` e JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
      LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
      LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id, UNNEST(q.quest_category) cat
      WHERE e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 21 DAY)) AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
        AND v.is_front_end_cohort = TRUE AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
        AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained') AND g.plan_name != 'Maintenance' AND cat LIKE '%gameplay%'
      GROUP BY 1,2
    ), wig AS (
      SELECT g.game_name, DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) wk, COUNT(DISTINCT q.quest_id) ig
      FROM `app_immutable_play.event` e LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
      LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id, UNNEST(q.quest_category) cat
      WHERE e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 21 DAY)) AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
        AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained') AND g.plan_name != 'Maintenance' AND cat LIKE '%in_game%'
      GROUP BY 1,2
    )
    SELECT COALESCE(c.game_name,p.game_name) game, COALESCE(c.tier,p.tier) tier, COALESCE(c.am,p.am) am,
      COALESCE(p.q,0) pq, COALESCE(c.q,0) cq, COALESCE(pig.ig,0) pig, COALESCE(cig.ig,0) cig,
      ROUND(100.0*COALESCE(pb.b,0)/NULLIF(pb.t,0),0) pbot, ROUND(100.0*COALESCE(cb.b,0)/NULLIF(cb.t,0),0) cbot
    FROM (SELECT * FROM wq WHERE wk=DATE_SUB(DATE_TRUNC(CURRENT_DATE(),WEEK(MONDAY)),INTERVAL 7 DAY)) c
    FULL OUTER JOIN (SELECT * FROM wq WHERE wk=DATE_SUB(DATE_TRUNC(CURRENT_DATE(),WEEK(MONDAY)),INTERVAL 14 DAY)) p ON c.game_name=p.game_name
    LEFT JOIN (SELECT * FROM wb WHERE wk=DATE_SUB(DATE_TRUNC(CURRENT_DATE(),WEEK(MONDAY)),INTERVAL 7 DAY)) cb ON COALESCE(c.game_name,p.game_name)=cb.game_name
    LEFT JOIN (SELECT * FROM wb WHERE wk=DATE_SUB(DATE_TRUNC(CURRENT_DATE(),WEEK(MONDAY)),INTERVAL 14 DAY)) pb ON COALESCE(c.game_name,p.game_name)=pb.game_name
    LEFT JOIN (SELECT * FROM wig WHERE wk=DATE_SUB(DATE_TRUNC(CURRENT_DATE(),WEEK(MONDAY)),INTERVAL 7 DAY)) cig ON COALESCE(c.game_name,p.game_name)=cig.game_name
    LEFT JOIN (SELECT * FROM wig WHERE wk=DATE_SUB(DATE_TRUNC(CURRENT_DATE(),WEEK(MONDAY)),INTERVAL 14 DAY)) pig ON COALESCE(c.game_name,p.game_name)=pig.game_name
    WHERE COALESCE(c.q,0)+COALESCE(p.q,0)>0 ORDER BY COALESCE(c.q,0) DESC
    ''').result())

    tp, tc = overall[1].q, overall[0].q

    print(f"\n## Executive Summary\n")
    print(f"**Period:** {dates.p} → {dates.c}")
    print(f"**Overall Gameplay Questers:** {tp:,} → {tc:,} ({tc-tp:+,}, {100*(tc-tp)/tp:+.1f}% WoW)\n")
    print(f"| Game | Tier | AM | Prev Wk | Curr Wk | WoW | Quests (P→C) | Bot% |")
    print(f"|------|------|-----|---------|---------|-----|--------------|------|")
    
    for r in rows:
        pq, cq = r.pq or 0, r.cq or 0
        ch = cq - pq
        wow = f"{ch:+,} ({100*ch/pq:+.0f}%)" if pq else f"+{cq:,} NEW"
        pig, cig = r.pig or 0, r.cig or 0
        pb, cb = int(r.pbot or 0), int(r.cbot or 0)
        flag = "🔴" if cb >= 80 else "🟡" if cb >= 60 else ""
        print(f"| {r.game} | {r.tier or '-'} | {r.am or '-'} | {pq:,} | {cq:,} | {wow} | {pig}→{cig} | {flag}{pb}%→{cb}% |")

    print(f"\n## Key Drivers\n")
    for r in rows:
        pq, cq = r.pq or 0, r.cq or 0
        ch, pct = cq - pq, 100*(cq-pq)/pq if pq else 100
        pig, cig = r.pig or 0, r.cig or 0
        pb, cb = int(r.pbot or 0), int(r.cbot or 0)
        
        if pq == 0 and cq > 0:
            flag = "⚠️ high bots" if cb > 70 else "✓ quality"
            print(f"- **{r.game}:** NEW launch (+{cq:,}) {flag}")
        elif cig < pig - 2 and pct < -20:
            print(f"- **{r.game}:** Quest reduction ({pig}→{cig}) → {ch:+,}")
        elif pb > 80 and pct < -50:
            print(f"- **{r.game}:** Bot cleanup (was {pb}% bots) → {ch:+,}")
        elif cb > pb + 20 and pct > 20:
            print(f"- **{r.game}:** ⚠️ Bot influx ({pb}%→{cb}%) → {ch:+,}")
        elif pct > 30:
            print(f"- **{r.game}:** Growth {pct:+.0f}% ({ch:+,})")
        elif pct < -30:
            print(f"- **{r.game}:** Decline {pct:+.0f}% ({ch:+,})")


if __name__ == "__main__":
    run_weekly_summary()
