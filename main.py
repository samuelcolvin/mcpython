import os
import sys
from typing import Any

import logfire
from awslambdaric.lambda_runtime_client import LambdaRuntimeClient
from fastmcp import FastMCP

env = 'prod' if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ else 'local'
logfire.configure(service_name=env, environment=env)

logfire.instrument_mcp()

mcp = FastMCP('Hello World')


@mcp.tool
def hello(name: str) -> str:
    logfire.info('env', environ=dict(os.environ))

    logfire.info('sys modules', modules=dict(sys.modules))

    return f'Hello, {name}!'


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
