-- Phase 0: Team OKR Snapshot - 30-Day Quota Attainment
-- Shows which active games are meeting their monthly gameplay targets
-- Run this to get team-level portfolio health overview
-- 
-- Filters:
-- - Games with ≥10 questers in last 30 days (excludes testing/inactive)
-- - Games with at least 1 non-testing gameplay quest
-- - Active subscriptions only, excludes Maintenance tier

WITH last_30d_questers AS (
  -- Calculate distinct gameplay questers per game (last 30 days)
  SELECT 
    g.game_name,
    g.plan_name as tier,
    g.account_manager_name as am,
    g.monthly_gameplay_target as target,
    COUNT(DISTINCT e.visitor_id) as actual_questers_30d,
    COUNT(DISTINCT q.quest_id) as gameplay_quests,
    -- Count non-testing gameplay quests
    COUNT(DISTINCT CASE 
      WHEN NOT EXISTS (
        SELECT 1 FROM UNNEST(q.quest_category) AS cat 
        WHERE LOWER(cat) LIKE '%testing%'
      ) THEN q.quest_id 
    END) as non_testing_quests
  FROM `app_immutable_play.event` e
  INNER JOIN `app_immutable_play.visitor` v ON e.visitor_id = v.visitor_id
  LEFT JOIN `app_immutable_play.quest` q ON e.quest_id = q.quest_id
  LEFT JOIN `app_immutable_play.game` g ON q.game_id = g.game_id
  LEFT JOIN UNNEST(q.quest_category) AS category
  WHERE 
    e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
    AND v.is_front_end_cohort = TRUE
    AND (v.is_immutable_employee = FALSE OR v.is_immutable_employee IS NULL)
    AND g.game_name NOT IN ('Guild of Guardians', 'Gods Unchained')
    AND g.plan_name != 'Maintenance'
    AND g.active_subscription = TRUE
    AND category LIKE '%gameplay%'
    AND g.monthly_gameplay_target IS NOT NULL  -- Only games with targets
  GROUP BY 1,2,3,4
  HAVING COUNT(DISTINCT e.visitor_id) >= 10  -- Filter: At least 10 questers
),

quota_status AS (
  SELECT 
    game_name,
    tier,
    am,
    actual_questers_30d,
    target,
    ROUND(100.0 * actual_questers_30d / NULLIF(target, 0), 1) as pct_of_quota,
    actual_questers_30d - target as gap,
    gameplay_quests,
    non_testing_quests,
    CASE 
      WHEN actual_questers_30d >= target THEN 1 
      ELSE 0 
    END as meeting_quota
  FROM last_30d_questers
  WHERE non_testing_quests > 0  -- Filter: Must have at least 1 non-testing gameplay quest
)

-- QUERY 1: Overall Summary
SELECT 
  SUM(meeting_quota) as games_meeting_quota,
  COUNT(*) as total_games,
  ROUND(100.0 * SUM(meeting_quota) / COUNT(*), 1) as pct_meeting
FROM quota_status;

-- QUERY 2: Tier Breakdown
SELECT 
  tier,
  SUM(meeting_quota) as games_meeting_quota,
  COUNT(*) as total_games,
  ROUND(100.0 * SUM(meeting_quota) / COUNT(*), 1) as pct_meeting
FROM quota_status
GROUP BY tier
ORDER BY 
  CASE tier
    WHEN 'Ultra Boost' THEN 1
    WHEN 'Boost' THEN 2
    WHEN 'Core' THEN 3
  END;

-- QUERY 3: Games Below Quota (detail table)
SELECT 
  game_name,
  tier,
  COALESCE(am, 'Unassigned') as account_manager,
  actual_questers_30d,
  target as monthly_target,
  pct_of_quota,
  gap,
  gameplay_quests,
  non_testing_quests
FROM quota_status
WHERE meeting_quota = 0  -- Only games below quota
ORDER BY pct_of_quota ASC, tier, game_name;
