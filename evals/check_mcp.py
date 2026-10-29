import asyncio

from mcp_client.fetch_client import FetchMCPClient, RESOURCES


async def main():
    client = FetchMCPClient()
    passed = 0

    for resource in RESOURCES:
        try:
            result = await client.fetch(resource)
            content = result["untrusted_web_content"]

            assert result["source"] == RESOURCES[resource]
            assert result["resource"] == resource
            assert isinstance(content, str)
            assert content.strip()
            assert len(content) <= 3500

            passed += 1
            print(f"PASS: {resource}")
            print(f"Source: {result['source']}")
            print(f"Content length: {len(content)}")

        except Exception as exc:
            errors = [exc]

            while errors:
                current = errors.pop(0)
                if isinstance(current, BaseExceptionGroup):
                    errors.extend(current.exceptions)
                else:
                    print(f"FAIL: {resource}")
                    print(f"{type(current).__name__}: {current}")

    print(f"\nMCP Results: {passed}/{len(RESOURCES)} passed")

    if passed != len(RESOURCES):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
