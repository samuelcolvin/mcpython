import os
from pprint import pprint

import logfire
from fastmcp import FastMCP

# env = 'local'
env = 'prod'
logfire.configure(service_name=env, environment=env)

logfire.instrument_mcp()

mcp = FastMCP('Hello World')


@mcp.tool
def hello(name: str) -> str:
    logfire.info('env', environ=dict(os.environ))
    pprint(dict(os.environ))
    return f'Hello, {name}!'


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
