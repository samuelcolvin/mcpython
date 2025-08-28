import os
import sys

import logfire
from fastmcp import FastMCP

env = 'prod' if 'AWS_LAMBDA_FUNCTION_NAME' in os.environ else 'local'
logfire.configure(service_name=env, environment=env)

logfire.instrument_mcp()

mcp = FastMCP('Hello World')


@mcp.tool
def hello(name: str) -> str:
    logfire.info('env', environ=dict(os.environ))

    try:
        with logfire.span('import LambdaRuntimeClient'):
            from lambda_runtime_client import LambdaRuntimeClient
    except Exception:
        pass

    logfire.info('sys modules:', modules=dict(sys.modules))

    for mod_name, mod in list(sys.modules.items()):
        try:
            client = getattr(mod, 'LambdaRuntimeClient', None)
        except Exception:  # pragma: no cover
            continue
        if not client:
            continue
        logfire.info('LambdaRuntimeClient:', mod_name=mod_name, client=client)

    # logfire.force_flush()

    return f'Hello, {name}!'


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
