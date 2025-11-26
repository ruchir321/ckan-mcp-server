import asyncio
import os
from mcp_ckan_server import ckan_resource_preview, ckan_dataset_schema, ckan_package_search

async def main():
    print("Verifying Analysis Tools...")
    
    try:
        print(f"CKAN_URL: {os.getenv('CKAN_URL', 'Not set (using default)')}")
        
        search_results = await ckan_package_search.fn(q="budget", rows=1)
        package_id = None
        
        if search_results and search_results.get("results"):
            package = search_results["results"][0]
            package_id = package["id"]
            print(f"Found package via search: {package['title']} ({package_id})")
        else:
            print("Search returned no results. Trying package_list...")
            from mcp_ckan_server import ckan_package_list
            package_list = await ckan_package_list.fn(limit=1)
            if package_list and len(package_list) > 0:
                 # package_list returns list of strings (IDs) or dicts depending on API, usually strings
                 # The tool implementation returns result of package_list action
                 # CKAN package_list action returns list of names (strings)
                 package_id = package_list[0]
                 print(f"Found package via list: {package_id}")
            else:
                 print("No packages found via list either.")
                 return

        if not package_id:
             print("Could not resolve a package ID.")
             return

        
        # 2. Test ckan_dataset_schema
        print(f"\nTesting ckan_dataset_schema for {package_id}...")
        schema = await ckan_dataset_schema.fn(id=package_id)
        print("Schema retrieved successfully.")
        print(f"Dataset Title: {schema.get('dataset_title')}")
        print(f"Number of resources: {len(schema.get('resources', []))}")
        
        # 3. Test ckan_resource_preview
        if schema.get("resources"):
            resource = schema["resources"][0]
            resource_id = resource["id"]
            print(f"\nTesting ckan_resource_preview for resource {resource_id}...")
            preview = await ckan_resource_preview.fn(resource_id=resource_id, rows=3)
            print("Preview retrieved successfully.")
            if "records" in preview:
                print(f"Got {len(preview['records'])} records.")
            else:
                print("Preview result (metadata):", str(preview)[:200] + "...")
        else:
            print("No resources found in package to test preview.")
            
    except Exception as e:
        print(f"Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(main())
