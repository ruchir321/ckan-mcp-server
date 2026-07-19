import asyncio
import os
import sys

# Add parent directory to path to import mcp_ckan_server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ckan_mcp_server.server import ckan_read_web_document


async def test_successful_fetch():
    print("Testing successful webpage fetch...")
    url = "https://www.toronto.ca/community-people/housing-shelter/rental-housing-standards/apartment-building-standards/"

    try:
        result = await ckan_read_web_document(url)

        print(f"Success! Fetched {len(result)} characters of markdown.")
        print("First 500 characters:")
        print("-" * 40)
        print(result[:500])
        print("-" * 40)

        # Basic assertions
        assert len(result) > 0, "Result should not be empty"
        assert "RentSafeTO" in result or "Toronto" in result, (
            "Result should contain expected keywords"
        )
        print("✓ Successful fetch test passed\n")

    except Exception as e:
        print(f"✗ Successful fetch test failed: {e}\n")
        raise e


async def test_failed_fetch():
    print("Testing failed fetch (invalid URL)...")
    url = "https://this-website-does-not-exist-12345.com"
    try:
        result = await ckan_read_web_document(url)

        print(f"Result: {result}")
        assert "Failed to fetch or parse" in result, "Result should contain error message"
        print("✓ Failed fetch test passed\n")

    except Exception as e:
        print(f"✗ Failed fetch test failed: {e}\n")
        raise e


async def main():
    print("Starting Web Document Tool Tests\n" + "=" * 30)
    await test_successful_fetch()
    await test_failed_fetch()
    print("All tests completed.")


if __name__ == "__main__":
    asyncio.run(main())
