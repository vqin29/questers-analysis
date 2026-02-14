-- Phase 2: Metric Decomposition - WoW Driver Attribution
-- Breaks down total WoW delta into 3 mutually exclusive buckets:
-- 1. New Games (launched this week)
-- 2. Discontinued/Off Games (stopped or turned off)
-- 3. Continuing Games (active both weeks, showing organic change)
-- 
-- Each bucket is further split by Human vs Bot users for quality assessment

WITH last_2_weeks AS (
  -- Get gameplay questers by game for last 2 complete weeks, split by bot status
  SELECT 
    g.game_name,
    g.plan_name as tier,
    g.account_manager_name as am,
    DATE_TRUNC(DATE(e.event_ts), WEEK(MONDAY)) as week_start,
    COUNT(DISTINCT e.visitor_id) as total_users,
    COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) as bot_users,
    COUNT(DISTINCT CASE WHEN s.bot_score IS NULL OR s.bot_score < 1 THEN e.visitor_id END) as human_users,
    COUNT(DISTINCT q.quest_id) as quest_count
  FROM `app_immutable_play.event` e
  INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
  LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
  LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
  LEFT JOIN UNNEST(q.quest_category) AS category
  LEFT JOIN `mod_imx.sybil_score` s ON v.user_id = s.user_id
  WHERE 
    e.event_ts >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 14 DAY))
    AND e.event_ts < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)))
    AND v.is_front_end_cohort = TRUE
    AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
    AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
    AND g.plan_name != 'Maintenance'
    AND category LIKE '%gameplay%'
  GROUP BY g.game_name, g.plan_name, g.account_manager_name, week_start
),

current_week AS (
  SELECT * FROM last_2_weeks 
  WHERE week_start = DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 7 DAY)
),

previous_week AS (
  SELECT * FROM last_2_weeks 
  WHERE week_start = DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)), INTERVAL 14 DAY)
),

game_changes AS (
  SELECT 
    COALESCE(c.game_name, p.game_name) as game_name,
    COALESCE(c.tier, p.tier) as tier,
    COALESCE(c.am, p.am) as am,
    
    -- Current week metrics
    COALESCE(c.total_users, 0) as curr_total,
    COALESCE(c.bot_users, 0) as curr_bots,
    COALESCE(c.human_users, 0) as curr_humans,
    COALESCE(c.quest_count, 0) as curr_quests,
    
    -- Previous week metrics
    COALESCE(p.total_users, 0) as prev_total,
    COALESCE(p.bot_users, 0) as prev_bots,
    COALESCE(p.human_users, 0) as prev_humans,
    COALESCE(p.quest_count, 0) as prev_quests,
    
    -- Calculate changes
    COALESCE(c.total_users, 0) - COALESCE(p.total_users, 0) as delta_total,
    COALESCE(c.bot_users, 0) - COALESCE(p.bot_users, 0) as delta_bots,
    COALESCE(c.human_users, 0) - COALESCE(p.human_users, 0) as delta_humans,
    
    -- Calculate bot percentages
    ROUND(100.0 * COALESCE(c.bot_users, 0) / NULLIF(COALESCE(c.total_users, 0), 0), 1) as curr_bot_pct,
    ROUND(100.0 * COALESCE(p.bot_users, 0) / NULLIF(COALESCE(p.total_users, 0), 0), 1) as prev_bot_pct,
    
    -- Classify into buckets
    CASE 
      WHEN COALESCE(p.total_users, 0) = 0 AND COALESCE(c.total_users, 0) > 0 THEN 'New'
      WHEN COALESCE(p.total_users, 0) > 0 AND COALESCE(c.total_users, 0) = 0 THEN 'Discontinued'
      WHEN COALESCE(p.total_users, 0) > 0 AND COALESCE(c.total_users, 0) > 0 THEN 'Continuing'
      ELSE 'Unknown'
    END as bucket
    
  FROM current_week c
  FULL OUTER JOIN previous_week p ON c.game_name = p.game_name
)

-- Final output: Games by bucket with detailed metrics
SELECT 
  bucket,
  game_name,
  tier,
  am,
  
  -- Previous week
  prev_total as prev_users,
  prev_humans,
  prev_bots,
  prev_bot_pct,
  prev_quests,
  
  -- Current week
  curr_total as curr_users,
  curr_humans,
  curr_bots,
  curr_bot_pct,
  curr_quests,
  
  -- Changes
  delta_total,
  delta_humans,
  delta_bots,
  ROUND(100.0 * delta_total / NULLIF(prev_total, 0), 1) as pct_change
  
FROM game_changes
ORDER BY 
  -- Order by bucket priority, then by impact
  CASE bucket
    WHEN 'New' THEN 1
    WHEN 'Discontinued' THEN 2
    WHEN 'Continuing' THEN 3
    ELSE 4
  END,
  ABS(delta_total) DESC;
