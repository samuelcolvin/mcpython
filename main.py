import functools
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


def wrap_client_post_invocation_method(client_method: Any) -> Any:  # pragma: no cover
    @functools.wraps(client_method)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            logfire.force_flush(timeout_millis=3000)
        except Exception:
            import traceback

            traceback.print_exc()

        return client_method(*args, **kwargs)

    return wrapper


LambdaRuntimeClient.post_invocation_error = wrap_client_post_invocation_method(
    LambdaRuntimeClient.post_invocation_error
)
LambdaRuntimeClient.post_invocation_result = wrap_client_post_invocation_method(
    LambdaRuntimeClient.post_invocation_result
)


@mcp.tool
def hello(name: str) -> str:
    logfire.info('env', environ=dict(os.environ))

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
