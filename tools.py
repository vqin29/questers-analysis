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
    - query_bigquery: Execute SQL queries against BigQuery with safety checks and parameter support
    """
    
    @mcp.tool()
    def query_bigquery(sql: str, parameters: dict = None) -> str:
        """
        Execute a SQL query against BigQuery with optional parameters.
        
        IMPORTANT: Always filter event_ts when querying app_immutable_play.event
        to avoid expensive queries (700M+ rows).
        
        Args:
            sql: The SQL query to execute (use @param_name for parameters)
            parameters: Optional dict of parameters for parameterized queries
                       Example: {"game_name": "MetalCore", "days": 7}
        
        Returns:
            JSON string with query results
        
        Examples:
            # Without parameters
            query_bigquery("SELECT COUNT(*) FROM table")
            
            # With parameters (prevents SQL injection)
            query_bigquery(
                "SELECT * FROM game WHERE game_name = @game_name",
                {"game_name": "MetalCore"}
            )
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
            
            # Add query parameters if provided
            if parameters:
                query_parameters = []
                for param_name, param_value in parameters.items():
                    # Infer parameter type from Python type
                    if isinstance(param_value, bool):
                        param_type = "BOOL"
                    elif isinstance(param_value, int):
                        param_type = "INT64"
                    elif isinstance(param_value, float):
                        param_type = "FLOAT64"
                    else:
                        param_type = "STRING"
                    
                    query_parameters.append(
                        bigquery.ScalarQueryParameter(param_name, param_type, param_value)
                    )
                job_config.query_parameters = query_parameters
            
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
