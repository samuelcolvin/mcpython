from fastmcp import FastMCP

mcp = FastMCP("MyServer")


@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"
