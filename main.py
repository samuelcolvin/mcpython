import os
import sys
from typing import Any

import logfire
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext

env = 'local' if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ else 'prod'
logfire.configure(service_name=env, environment=env)

logfire.instrument_mcp()


class LogfireFlushMiddleware(Middleware):
    async def __call__(self, context: MiddlewareContext[Any], call_next: Any):
        try:
            return await call_next(context)
        finally:
            logfire.force_flush()


mcp = FastMCP('Hello World', middleware=[LogfireFlushMiddleware()])


@mcp.tool
def hello(name: str) -> str:
    logfire.info('env', environ=dict(os.environ))

    logfire.info('sys modules', modules=dict(sys.modules))

    return f'Hello, {name}!'


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
