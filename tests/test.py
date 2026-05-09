from agents import Agent, Runner, trace
from agents.mcp import MCPServer, MCPServerStdio
import asyncio
import shutil
from dotenv import load_dotenv


load_dotenv()

async def run(mcp_server: MCPServer):
    agent = Agent(
        name="Assistant",
        instructions=f"Answer questions about the ckan site",
        mcp_servers=[mcp_server],
    )

    message = "Who created the most Datasets?"
    print("\n" + "-" * 40)
    print(f"Running: {message}")
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    message = "which is the newest Dataset?."
    print("\n" + "-" * 40)
    print(f"Running: {message}")
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

async def main():
    # Ask the user for the directory path
    # directory_path = input("Please enter the path to the git repository: ")

    async with MCPServerStdio(
        cache_tools_list=True,  # Cache the tools list, for demonstration
        params={"command": "uv", "args": ["run","mcp_ckan_server.py"],"cwd":".."},
    ) as server:
        with trace(workflow_name="MCP Git Example"):
            await run(server)


if __name__ == "__main__":

    if not shutil.which("uvx"):
        raise RuntimeError("uvx is not installed. Please install it with `pip install uvx`.")

    asyncio.run(main())