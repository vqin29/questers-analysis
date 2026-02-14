-- Phase 3: Quest-Level Completions Analysis
-- Drill down from game-level to individual quest completions
-- Shows which specific quests are driving changes in questers

-- QUERY 1: All Active Games - Quest Completions (Last 3 Days)
-- Default query showing every quest with completions across all active games
SELECT
  g.game_name,
  q.quest_name,
  q.quest_id,
  COUNT(*) AS quest_completions,
  COUNT(DISTINCT e.visitor_id) AS unique_completers,
  ROUND(1.0 * COUNT(*) / NULLIF(COUNT(DISTINCT e.visitor_id), 0), 1) AS completions_per_user
FROM `app_immutable_play.event` e
INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
LEFT JOIN UNNEST(q.quest_category) AS category
WHERE
  e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
  AND g.plan_name != 'Maintenance'
  AND category LIKE '%gameplay%'
GROUP BY g.game_name, q.quest_name, q.quest_id
ORDER BY g.game_name, quest_completions DESC;

-- QUERY 2: Specific Game with Bot % (Last 3 Days)
-- Replace {game_name} with actual game name for detailed quest-level analysis
SELECT
  g.game_name,
  q.quest_name,
  q.quest_id,
  COUNT(*) AS quest_completions,
  COUNT(DISTINCT e.visitor_id) AS unique_completers,
  COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) AS bot_completers,
  COUNT(DISTINCT CASE WHEN s.bot_score IS NULL OR s.bot_score < 1 THEN e.visitor_id END) AS human_completers,
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) /
        NULLIF(COUNT(DISTINCT e.visitor_id), 0), 1) AS bot_pct,
  ROUND(1.0 * COUNT(*) / NULLIF(COUNT(DISTINCT e.visitor_id), 0), 1) AS completions_per_user
FROM `app_immutable_play.event` e
INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
LEFT JOIN UNNEST(q.quest_category) AS category
LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id
WHERE
  e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY))
  AND v.is_front_end_cohort = TRUE
  AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
  AND g.game_name = '{game_name}'  -- Replace with actual game name
  AND g.plan_name != 'Maintenance'
  AND category LIKE '%gameplay%'
GROUP BY g.game_name, q.quest_name, q.quest_id
ORDER BY quest_completions DESC;
