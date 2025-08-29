import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any

import logfire
from fastmcp import Context, FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from google.api_core.exceptions import BadRequest
from google.cloud import bigquery
from google.oauth2 import service_account
from pydantic_ai import Agent, ModelRetry, RunContext, format_as_xml
from pydantic_ai.models.mcp_sampling import MCPSamplingModel

env = 'cloud' if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ else 'local'
logfire.configure(service_name=env, environment=env)

logfire.instrument_mcp()


class LogfireFlushMiddleware(Middleware):
    """Required to get traces immediately from AWS Lambda."""

    async def __call__(self, context: MiddlewareContext[Any], call_next: Any):
        try:
            return await call_next(context)
        finally:
            logfire.force_flush()


mcp = FastMCP('PyPI Downloads', middleware=[LogfireFlushMiddleware()])
table_name = 'bigquery-public-data.pypi.file_downloads'


@dataclass
class Deps:
    mcp_context: Context


pypi_agent = Agent(
    retries=2,
    deps_type=Deps,
    system_prompt=f"""
Your job is to help users analyze downloads of python packages.

Convert the user's query into a BigQuery SQL query against the `{table_name}`
table which has the following schema:

```sql
CREATE TABLE {table_name} (
    timestamp TIMESTAMP,
    country_code STRING, -- two letter ISO country code
    url STRING,
    project STRING,
    file STRUCT<
        filename STRING,
        project STRING,
        version STRING,
        type STRING
    >,
    details STRUCT<
        installer STRUCT<
            name STRING,
            version STRING
        >,
        python STRING,
        implementation STRUCT<
            name STRING,
            version STRING
        >,
        distro STRUCT<
            name STRING,
            version STRING,
            id STRING,
            libc STRUCT<
                lib STRING,
                version STRING
            >
        >,
        system STRUCT<
            name STRING,
            release STRING
        >,
        cpu STRING,
        openssl_version STRING,
        setuptools_version STRING,
        rustc_version STRING,
        ci BOOLEAN
    >,
    tls_protocol STRING,
    tls_cipher STRING
);
```

Where possible apply a lower bound constraint to the `timestamp` column to avoid scanning to many partitions.

For example, if the user asked for an example download of the pydantic package, you could use the following query:

```sql
SELECT *
FROM `bigquery-public-data.pypi.file_downloads`
WHERE
  file.project = 'pydantic'
  AND DATE(timestamp) = current_date()
LIMIT 1
```

If the user asked for "number of downloads of pydantic broken down by month, python version, operating system,
CPU architecture, and libc version for this year and last year", you could use the following query:

```sql
SELECT
  COUNT(*) AS num_downloads,
  DATE_TRUNC(DATE(timestamp), MONTH) AS `month`,
  REGEXP_EXTRACT(details.python, r"[0-9]+\\.[0-9]+") AS python_version,
  details.system.name AS os,
  details.cpu AS cpu,
  details.distro.libc.lib AS libc
FROM `bigquery-public-data.pypi.file_downloads`
WHERE
  file.project = 'pydantic'
  AND DATE_TRUNC(DATE(timestamp), YEAR) = DATE_TRUNC(date_sub(current_date(), interval 1 YEAR), YEAR)
GROUP BY `month`, `python_version`, `os`, `cpu`, `libc`
ORDER BY `month` DESC, `num_downloads` DESC
```
""",
)


@pypi_agent.output_validator
async def run_query(ctx: RunContext[Deps], sql: str) -> str:
    # remove "```sql...```"
    # m = re.search(r'```.*\n([.\n]*?)```', sql)
    m = re.search(r'```\w*\n(.*?)```', sql, flags=re.S)
    if m:
        sql = m.group(1).strip()

    logfire.info('running {sql}', sql=sql)
    await ctx.deps.mcp_context.log('running query')
    if f'from `{table_name}`' not in sql.lower():
        raise ModelRetry(f'Query must be against the `{table_name}` table')

    if service_account_content := os.getenv('SERVICE_ACCOUNT_CONTENT'):
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(service_account_content),
            scopes=['https://www.googleapis.com/auth/cloud-platform'],
        )
    else:
        credentials = None
    client = bigquery.Client(credentials=credentials)
    loop = asyncio.get_event_loop()
    try:
        query_job = await loop.run_in_executor(None, client.query, sql)
        rows = await loop.run_in_executor(None, query_job.result)
    except BadRequest as e:
        await ctx.deps.mcp_context.log('query error retrying', 'warning')
        raise ModelRetry(f'Invalid query: {e}') from e
    await ctx.deps.mcp_context.log('query successful')
    data = [dict(row) for row in rows]  # type: ignore
    return format_as_xml(data, item_tag='row')


@mcp.tool
async def pypi_downloads(question: str, ctx: Context) -> str:
    """Analyze downloads of packages from the Python package index PyPI to answer questions about package downloads."""
    result = await pypi_agent.run(question, model=MCPSamplingModel(session=ctx.session), deps=Deps(ctx))
    return result.output


if __name__ == '__main__':
    mcp.run(transport='streamable-http' if env == 'cloud' else 'stdio')
