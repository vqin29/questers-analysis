-- Enhanced Quest Dashboard with Alert Flags
-- Flags potentially broken quests and high botting quests for account managers
-- Run this to get quest metrics with alert indicators

WITH quest_activity AS (
  SELECT 
    g.game_name,
    g.plan_name,
    g.account_manager_name,
    q.quest_id,
    q.quest_name,
    q.quest_category,
    COUNT(*) as total_completions_l30d,
    COUNT(DISTINCT e.visitor_id) as distinct_users_l30d,
    COUNT(DISTINCT CASE WHEN s.bot_score = 1 THEN e.visitor_id END) as bot_users,
    MAX(e.event_ts) as latest_completion,
    
    -- Last 48 hours activity
    COUNT(DISTINCT CASE 
      WHEN e.event_ts >= TIMESTAMP(DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 48 HOUR)) 
      THEN e.visitor_id 
    END) as users_48h,

    COUNT(CASE 
      WHEN e.event_ts >= TIMESTAMP(DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 48 HOUR)) 
      THEN 1 
    END) as completions_48h,
    
    -- Previous 48 hours (48-96h ago)
    COUNT(DISTINCT CASE 
      WHEN e.event_ts >= TIMESTAMP(DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 96 HOUR))
        AND e.event_ts < TIMESTAMP(DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 48 HOUR))
      THEN e.visitor_id 
    END) as users_prev_48h,
    
    COUNT(CASE 
      WHEN e.event_ts >= TIMESTAMP(DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 96 HOUR))
        AND e.event_ts < TIMESTAMP(DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 48 HOUR))
      THEN 1 
    END) as completions_prev_48h,
    
    -- Last 7 days activity
    COUNT(CASE 
      WHEN e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)) 
      THEN 1 
    END) as completions_7d,
    
    -- Previous 7 days (7-14 days ago)
    COUNT(CASE 
      WHEN e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY))
        AND e.event_ts < TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY))
      THEN 1 
    END) as completions_prev_7d
    
  FROM `prod-im-data.app_immutable_play.event` e
  LEFT JOIN `prod-im-data.app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
  LEFT JOIN `prod-im-data.app_immutable_play.quest` q ON e.quest_id = q.quest_id
  LEFT JOIN `prod-im-data.app_immutable_play.game` g ON q.game_id = g.game_id
  LEFT JOIN `prod-im-data.mod_imx.sybil_score` s ON v.user_id = s.user_id
  
  WHERE e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
    AND v.is_front_end_cohort = TRUE 
    AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
    AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
    AND g.plan_name IN ('Core', 'Boost', 'Ultra Boost', 'Maintenance')  -- Active subscriptions only
    AND q.quest_id IS NOT NULL
    AND g.active_subscription IS TRUE
    
  GROUP BY 1,2,3,4,5,6
),

quest_metrics AS (
  SELECT 
    game_name,
    plan_name,
    account_manager_name,
    quest_id,
    quest_name,
    ARRAY_TO_STRING(quest_category, ', ') as categories,
    total_completions_l30d,
    distinct_users_l30d,
    bot_users,
    ROUND(100.0 * bot_users / NULLIF(distinct_users_l30d, 0), 1) as bot_rate_pct,
    latest_completion,
    users_48h,
    completions_48h,
    users_prev_48h,
    completions_prev_48h,
    completions_7d,
    completions_prev_7d,

    ROUND(total_completions_l30d / NULLIF(distinct_users_l30d, 0), 1) as completions_per_user,
    DATE_DIFF(CURRENT_DATE(), DATE(latest_completion), DAY) as days_since_last_completion,
    TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), latest_completion, HOUR) as hours_since_last_completion,
    
    -- Calculate activity drop percentage
    CASE 
      WHEN users_prev_48h > 0 
      THEN ROUND(100.0 * (users_prev_48h - users_48h) / users_prev_48h, 1)
      ELSE 0 
    END as activity_drop_pct,
    
    -- Calculate 7-day trend (completions drop percentage)
    CASE 
      WHEN completions_prev_7d > 0 
      THEN ROUND(100.0 * (completions_prev_7d - completions_7d) / completions_prev_7d, 1)
      ELSE 0 
    END as completions_7d_drop_pct,
    
    -- Check if gameplay quest
    CASE 
      WHEN ARRAY_TO_STRING(quest_category, ', ') LIKE '%gameplay%' 
      THEN 'Gameplay' 
      ELSE 'Social/Other' 
    END as quest_type
  
  FROM quest_activity
  WHERE DATE(latest_completion) >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)  -- Active in last 14 days
)

-- Final output with alert flags for Account Managers
SELECT 
  game_name,
  plan_name,
  COALESCE(account_manager_name, 'Unassigned') as account_manager,
  quest_name,
  categories,
  
  -- 🚨 NEW: ALERT FLAG FOR ACCOUNT MANAGERS
  CASE
    -- Critical bot rate (>90%)
    WHEN bot_rate_pct >= 90 THEN '🔴 CRITICAL BOT RATE'
    -- High bot rate (80-90%)
    WHEN bot_rate_pct >= 80 THEN '🔴 HIGH BOT RATE'
    -- Excessive farming/grinding (>20 completions per user)
    WHEN completions_per_user > 20 
      AND users_48h >= 10
      THEN '🔴 EXCESSIVE FARMING'
    -- No completions in past 7 days (but had completions 7-14d ago)
    WHEN completions_7d = 0 
      AND completions_prev_7d > 10
      THEN '⚠️ NO COMPLETIONS LAST 7D'
    -- Elevated bot rate (70-80%)
    WHEN bot_rate_pct >= 70 THEN '🟡 ELEVATED BOT RATE'
    -- High farming (10-20 completions per user)
    WHEN completions_per_user > 10 
      AND users_48h >= 10
      THEN '🟡 HIGH FARMING'
    -- Possibly broken (0 completions in 48h but had activity before)
    WHEN completions_48h = 0 
      AND completions_prev_48h > 5 
      AND hours_since_last_completion <= 96 
      THEN '⚠️ POSSIBLY BROKEN'
    -- Major activity drop (>70% decline)
    WHEN activity_drop_pct > 70 
      AND users_prev_48h >= 10 
      THEN '⚠️ MAJOR ACTIVITY DROP'
    -- Trending downwards (>25% drop in completions over 7 days)
    WHEN completions_7d_drop_pct > 25 
      AND completions_prev_7d >= 20
      THEN '📉 TRENDING DOWNWARDS'
    -- Low recent activity
    WHEN users_48h < 5 
      AND users_prev_48h >= 20 
      AND hours_since_last_completion <= 96 
      THEN '⚠️ LOW RECENT ACTIVITY'
    -- No recent completions (>48h ago but <7d ago)
    WHEN hours_since_last_completion > 48 
      AND hours_since_last_completion <= 168 
      AND users_prev_48h > 0 
      THEN '⚠️ NO RECENT COMPLETIONS'
    ELSE '✅ No Issues'
  END as alert_flag,
  
  -- 🚨 NEW: DETAILED ALERT MESSAGE FOR AM CONTEXT
  CASE
    WHEN bot_rate_pct >= 90 THEN CONCAT(CAST(ROUND(bot_rate_pct, 0) AS STRING), '% bots (', CAST(bot_users AS STRING), '/', CAST(distinct_users_l30d AS STRING), ' users) - URGENT ACTION NEEDED')
    WHEN bot_rate_pct >= 80 THEN CONCAT(CAST(ROUND(bot_rate_pct, 0) AS STRING), '% bots (', CAST(bot_users AS STRING), '/', CAST(distinct_users_l30d AS STRING), ' users) - Review quest rewards/requirements')
    WHEN completions_per_user > 20 AND users_48h >= 10 THEN CONCAT(CAST(ROUND(completions_per_user, 1) AS STRING), 'x completions per user - Quest may be too easy to farm')
    WHEN completions_7d = 0 AND completions_prev_7d > 10 THEN CONCAT('0 completions in last 7 days (was ', CAST(completions_prev_7d AS STRING), ' in prev 7d) - CHECK IF QUEST IS BROKEN')
    WHEN bot_rate_pct >= 70 THEN CONCAT(CAST(ROUND(bot_rate_pct, 0) AS STRING), '% bots - Monitor closely')
    WHEN completions_per_user > 10 AND users_48h >= 10 THEN CONCAT(CAST(ROUND(completions_per_user, 1) AS STRING), 'x completions per user - Monitor for farming')
    WHEN completions_48h = 0 AND completions_prev_48h > 5 THEN CONCAT('0 completions in 48h (was ', CAST(completions_prev_48h AS STRING), ' prev 48h) - Possible issue')
    WHEN activity_drop_pct > 70 AND users_prev_48h >= 10 THEN CONCAT(CAST(ROUND(activity_drop_pct, 0) AS STRING), '% drop: ', CAST(users_prev_48h AS STRING), '→', CAST(users_48h AS STRING), ' users - Investigate cause')
    WHEN completions_7d_drop_pct > 25 AND completions_prev_7d >= 20 THEN CONCAT(CAST(ROUND(completions_7d_drop_pct, 0) AS STRING), '% decline: ', CAST(completions_prev_7d AS STRING), '→', CAST(completions_7d AS STRING), ' completions (7d trend)')
    WHEN users_48h < 5 AND users_prev_48h >= 20 THEN CONCAT('Only ', CAST(users_48h AS STRING), ' users in 48h (was ', CAST(users_prev_48h AS STRING), ') - Low engagement')
    WHEN hours_since_last_completion > 48 AND hours_since_last_completion <= 168 THEN CONCAT('Last completion ', CAST(ROUND(hours_since_last_completion, 0) AS STRING), 'h ago - Check quest status')
    ELSE 'Quest operating normally'
  END as alert_message,
  
  -- 🚨 NEW: PRIORITY LEVEL (1=Urgent, 2=High, 3=Medium, 4=Low, 5=No Issue)
  CASE
    WHEN bot_rate_pct >= 90 THEN 1
    WHEN bot_rate_pct >= 80 THEN 2
    WHEN (completions_per_user > 20 AND users_48h >= 10) THEN 2
    WHEN (completions_48h = 0 AND completions_prev_48h > 5 AND hours_since_last_completion <= 96) THEN 2
    WHEN (completions_7d = 0 AND completions_prev_7d > 10) THEN 2
    WHEN bot_rate_pct >= 70 THEN 3
    WHEN (completions_per_user > 10 AND users_48h >= 10) THEN 3
    WHEN (activity_drop_pct > 70 AND users_prev_48h >= 10) THEN 3
    WHEN (completions_7d_drop_pct > 25 AND completions_prev_7d >= 20) THEN 3
    WHEN (users_48h < 5 AND users_prev_48h >= 20 AND hours_since_last_completion <= 96) THEN 4
    WHEN (hours_since_last_completion > 48 AND hours_since_last_completion <= 168 AND users_prev_48h > 0) THEN 4
    ELSE 5
  END as alert_priority,
  
  -- Original columns from your starting query
  total_completions_l30d,
  distinct_users_l30d,
  bot_users,
  bot_rate_pct,
  latest_completion,
  users_48h,
  completions_48h,
  completions_per_user,
  days_since_last_completion,
  hours_since_last_completion

FROM quest_metrics

-- Optional: Filter to only show quests with alerts (comment out to see all quests)
-- WHERE bot_rate_pct >= 70  
--   OR (completions_per_user > 10 AND users_48h >= 10)
--   OR (completions_7d = 0 AND completions_prev_7d > 10)
--   OR (completions_48h = 0 AND completions_prev_48h > 5 AND hours_since_last_completion <= 96)
--   OR (activity_drop_pct > 70 AND users_prev_48h >= 10)
--   OR (completions_7d_drop_pct > 25 AND completions_prev_7d >= 20)
--   OR (users_48h < 5 AND users_prev_48h >= 20 AND hours_since_last_completion <= 96)
--   OR (hours_since_last_completion > 48 AND hours_since_last_completion <= 168 AND users_prev_48h > 0)

ORDER BY alert_priority, bot_rate_pct DESC, total_completions_l30d DESC;
