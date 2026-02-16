-- Phase 1: Weekly Trends - Gameplay Questers Analysis
-- Shows overall and per-game gameplay quester counts with WoW comparison
-- Run these queries to get Phase 1 baseline metrics

-- QUERY 1: Overall Gameplay Questers (Last 2 Complete Weeks)
-- Excludes current incomplete week to ensure accurate WoW comparison
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
ORDER BY week_start DESC;

-- QUERY 2: Per-Game Breakdown with WoW (Last Week Only)
-- Shows each game's gameplay questers, quest count, bot %, and account manager
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
ORDER BY gameplay_questers DESC;

-- QUERY 3: Quest Farming Analysis (Last Week)
-- Identifies over-farmed quests with high bot % and excessive completions per user
-- Note: Analyzes ALL quest types (gameplay, social post, engage) since farming can occur in any category
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
ORDER BY bot_pct DESC, completions DESC;
