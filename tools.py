"""
Tools - Actions the AI can perform
"""
from google.cloud import bigquery
import json

# Initialize BigQuery client
bq_client = bigquery.Client()


def register(mcp):
    """
    Register all tools with the MCP server.
    
    Tools registered:
    - query_bigquery: Execute SQL queries against BigQuery with safety checks
    """
    
    @mcp.tool()
    def query_bigquery(sql: str) -> str:
        """
        Execute a SQL query against BigQuery.
        
        IMPORTANT: Always filter event_ts when querying app_immutable_play.event
        to avoid expensive queries (700M+ rows).
        
        Args:
            sql: The SQL query to execute
        
        Returns:
            JSON string with query results
        """
        # Warn if querying event table without time filter
        sql_lower = sql.lower()
        if 'app_immutable_play.event' in sql_lower or 'event e' in sql_lower:
            if 'event_ts' not in sql_lower:
                return json.dumps({
                    "error": "Query includes event table but no event_ts filter. "
                             "Always filter on event_ts to avoid costly queries. "
                             "Example: WHERE e.event_ts >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))"
                }, indent=2)
        
        try:
            # Configure query with safety limits
            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=10_000_000_000  # 10 GB limit to prevent runaway costs
            )
            
            # Execute query with timeout
            query_job = bq_client.query(sql, job_config=job_config)
            results = query_job.result(timeout=300)  # 5 minute timeout
            
            rows = []
            for row in results:
                row_dict = {}
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row_dict[key] = value.isoformat()
                    else:
                        row_dict[key] = value
                rows.append(row_dict)
            return json.dumps(rows, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)
