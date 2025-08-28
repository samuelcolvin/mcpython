import logfire
from fastmcp import FastMCP

logfire.configure()

logfire.instrument_mcp()

mcp = FastMCP('Hello World')


@mcp.tool
def hello(name: str) -> str:
    logfire.info('this is inside a tool')
    return f'Hello, {name}!'


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
