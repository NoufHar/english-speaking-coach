
import asyncio
import os

RESOURCES = {
    "grammar": "https://www.gutenberg.org/ebooks/37134",
}


class FetchMCPClient:
    async def fetch(self, resource):
        if resource not in RESOURCES:
            raise PermissionError("Resource is not allowlisted")

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        url = RESOURCES[resource]
        params = StdioServerParameters(
            command="uvx",
            args=["mcp-server-fetch"]
        )

        async def run():
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()

                    result = await session.call_tool(
                        "fetch",
                        {
                            "url": url,
                            "max_length": 3500
                        }
                    )

                    content = "\n".join(
                        getattr(part, "text", str(part))
                        for part in result.content
                    )

                    if result.isError:
                        raise RuntimeError(
                            f"Fetch MCP returned an error: {content[:1500]}"
                        )

                    if not content.strip():
                        raise RuntimeError(
                            "Fetch MCP returned empty content"
                        )

                    return {
                        "source": url,
                        "resource": resource,
                        "untrusted_web_content": content[:3500]
                    }

        return await asyncio.wait_for(
            run(),
            timeout=float(
                os.getenv("FETCH_TIMEOUT_SECONDS", "18")
            )
        )
