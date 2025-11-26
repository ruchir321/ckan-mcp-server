import asyncio
import os
from mcp_ckan_server import search_datasets, analyze_neighborhood, business_insights, educational_data

async def main():
    print("Verifying CKAN MCP Server Prompts...")
    
    # Test Prompt: search_datasets
    print("\nTesting prompt: search_datasets...")
    try:
        if hasattr(search_datasets, 'fn'):
             prompt_text = search_datasets.fn(query="housing", file_format="CSV")
             print("Success! Prompt text:")
             print(prompt_text[:150] + "...")
        else:
             print("Could not find .fn attribute for prompt.")
    except Exception as e:
        print(f"Error testing search_datasets: {e}")

    # Test Prompt: analyze_neighborhood
    print("\nTesting prompt: analyze_neighborhood...")
    try:
        if hasattr(analyze_neighborhood, 'fn'):
             prompt_text = analyze_neighborhood.fn(neighborhood="Annex", topic="crime")
             print("Success! Prompt text:")
             print(prompt_text[:150] + "...")
        else:
             print("Could not find .fn attribute for prompt.")
    except Exception as e:
        print(f"Error testing analyze_neighborhood: {e}")

    # Test Prompt: business_insights
    print("\nTesting prompt: business_insights...")
    try:
        if hasattr(business_insights, 'fn'):
             prompt_text = business_insights.fn(business_type="Coffee Shop", location="Kensington Market")
             print("Success! Prompt text:")
             print(prompt_text[:150] + "...")
        else:
             print("Could not find .fn attribute for prompt.")
    except Exception as e:
        print(f"Error testing business_insights: {e}")

    # Test Prompt: educational_data
    print("\nTesting prompt: educational_data...")
    try:
        if hasattr(educational_data, 'fn'):
             prompt_text = educational_data.fn(topic="climate change", level="advanced")
             print("Success! Prompt text:")
             print(prompt_text[:150] + "...")
        else:
             print("Could not find .fn attribute for prompt.")
    except Exception as e:
        print(f"Error testing educational_data: {e}")

if __name__ == "__main__":
    asyncio.run(main())
