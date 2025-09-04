from datetime import date

import logfire
from mcp.types import LoggingMessageNotificationParams
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP

logfire.configure(service_name='mcp-client')

logfire.instrument_pydantic_ai()
logfire.instrument_mcp()


async def log_handler(params: LoggingMessageNotificationParams):
    print(f'MCP log {params.level}: {params.data["msg"]}')


# url = 'https://mcpython.fastmcp.app/mcp'
# server = MCPServerStreamableHTTP(url=url, log_handler=log_handler)
server = MCPServerStdio(command='uv', args=['run', 'main.py'])
libs_agent = Agent(
    'anthropic:claude-sonnet-4-0',
    toolsets=[server],
    instructions='your job is to help the user research software libraries and packages using the tools provided',
)
libs_agent.set_mcp_sampling_model()


@libs_agent.system_prompt
def add_date():
    return f'Today is {date.today():%Y-%m-%d}'


async def main():
    async with libs_agent:
        result = await libs_agent.run('How many times has pydantic been downloaded this year')
    print(result.output)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
