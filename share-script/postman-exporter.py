#!/usr/bin/env python3
"""
Postman Collections Exporter
Export all collections from your Postman workspace to local JSON files.
No external dependencies required - uses only Python built-in libraries.
"""

import urllib.request
import urllib.error
import json
import os
import sys
from datetime import datetime

# ==============================================================================
# DEFAULT CONFIGURATION - These can be overridden via function parameters
# ==============================================================================

# Default values used when running as standalone script
DEFAULT_CONFIG = {
    'api_key': 'YOUR_POSTMAN_API_KEY_HERE',
    'workspace_type': 'personal',
    'workspace_name': '',
    'workspace_id': '',
    'export_directory': 'postman_exports',
    'include_timestamp': True,
    'collection_format': 'v2.1.0',
    'export_environments': True,
}

# For backward compatibility - expose as module-level variables
API_KEY = DEFAULT_CONFIG['api_key']
WORKSPACE_TYPE = DEFAULT_CONFIG['workspace_type']
WORKSPACE_NAME = DEFAULT_CONFIG['workspace_name']
WORKSPACE_ID = DEFAULT_CONFIG['workspace_id']
EXPORT_DIRECTORY = DEFAULT_CONFIG['export_directory']
INCLUDE_TIMESTAMP = DEFAULT_CONFIG['include_timestamp']
COLLECTION_FORMAT = DEFAULT_CONFIG['collection_format']
EXPORT_ENVIRONMENTS = DEFAULT_CONFIG['export_environments']

# ==============================================================================
# SCRIPT - No need to modify below this line
# ==============================================================================

def make_request(url, headers=None):
    """Make an HTTP GET request using urllib."""
    if headers is None:
        headers = {}
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            data = response.read()
            return json.loads(data.decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_msg = f"HTTP Error {e.code}: {e.reason}"
        if e.code == 401:
            error_msg += " (Invalid API key)"
        elif e.code == 404:
            error_msg += " (Resource not found)"
        raise Exception(error_msg)
    except urllib.error.URLError as e:
        raise Exception(f"Connection error: {e.reason}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON response: {e}")

def validate_config(config=None):
    """Validate configuration settings."""
    if config is None:
        config = DEFAULT_CONFIG

    if not config.get('api_key'):
        raise ValueError("API key is required. Get your API key from: https://web.postman.co/settings/me/api-keys")

    valid_workspace_types = ['personal', 'team', 'private', 'public', 'partner', 'all']
    if config['workspace_type'] not in valid_workspace_types:
        raise ValueError(f"Invalid workspace_type. Must be one of: {', '.join(valid_workspace_types)}")

def create_export_directory(config=None):
    """Create the export directory."""
    if config is None:
        config = DEFAULT_CONFIG

    dir_name = config['export_directory']
    if config['include_timestamp']:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dir_name = f"{config['export_directory']}_{timestamp}"

    os.makedirs(dir_name, exist_ok=True)
    os.makedirs(f"{dir_name}/collections", exist_ok=True)
    if config['export_environments']:
        os.makedirs(f"{dir_name}/environments", exist_ok=True)

    return dir_name

def get_workspace(config=None):
    """Get the workspace to export from."""
    if config is None:
        config = DEFAULT_CONFIG

    headers = {'X-Api-Key': config['api_key']}

    # If specific workspace ID is provided, use it directly
    if config['workspace_id']:
        return config['workspace_id']

    # Get all workspaces
    try:
        response = make_request('https://api.getpostman.com/workspaces', headers=headers)
    except Exception as e:
        raise Exception(f"Failed to fetch workspaces: {e}")

    workspaces = response.get('workspaces', [])

    if not workspaces:
        raise Exception("No workspaces found")

    # Filter workspaces based on configuration
    filtered_workspaces = []
    for workspace in workspaces:
        # Filter by type if specified
        if config['workspace_type'] != 'all' and workspace.get('type') != config['workspace_type']:
            continue

        # Filter by name if specified
        if config['workspace_name'] and workspace.get('name') != config['workspace_name']:
            continue

        filtered_workspaces.append(workspace)

    if not filtered_workspaces:
        error_msg = f"No {config['workspace_type']} workspace found"
        if config['workspace_name']:
            error_msg += f" with name '{config['workspace_name']}'"
        raise Exception(error_msg)

    # Return the first matching workspace
    selected_workspace = filtered_workspaces[0]
    return selected_workspace['id'], selected_workspace

def export_collections(workspace_id, export_dir, config=None):
    """Export all collections from the specified workspace."""
    if config is None:
        config = DEFAULT_CONFIG

    headers = {'X-Api-Key': config['api_key']}
    
    # Get collections from workspace
    print(f"\n📚 Fetching collections from workspace...")
    try:
        response = make_request(
            f'https://api.getpostman.com/collections?workspace={workspace_id}',
            headers=headers
        )
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch collections: {e}")
        return 0
    
    collections = response.get('collections', [])
    print(f"   Found {len(collections)} collection(s)")
    
    if not collections:
        print("   No collections to export")
        return 0
    
    # Export each collection
    exported_count = 0
    for i, collection in enumerate(collections, 1):
        collection_id = collection['id']
        collection_name = collection['name']
        
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in collection_name)
        safe_name = safe_name.strip()
        
        print(f"\n   [{i}/{len(collections)}] Exporting: {collection_name}")
        
        try:
            # Get full collection data
            collection_data = make_request(
                f'https://api.getpostman.com/collections/{collection_id}',
                headers=headers
            )
            
            # Extract the inner collection object (remove wrapper)
            # Postman API returns: {"collection": {...actual v2.1.0 data...}}
            # But import tools expect: {...actual v2.1.0 data...} at root level
            if 'collection' not in collection_data:
                raise Exception("Invalid API response: missing 'collection' field")

            collection_content = collection_data['collection']

            # Save to file
            filename = f"{export_dir}/collections/{safe_name}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(collection_content, f, indent=2, ensure_ascii=False)
            
            print(f"       ✓ Saved to: {filename}")
            exported_count += 1
            
        except Exception as e:
            print(f"       ✗ Failed to export: {e}")
    
    return exported_count

def export_environments(workspace_id, export_dir, config=None):
    """Export all environments from the specified workspace."""
    if config is None:
        config = DEFAULT_CONFIG

    if not config['export_environments']:
        return 0

    headers = {'X-Api-Key': config['api_key']}
    
    # Get workspace details to find environments
    print(f"\n🌍 Fetching environments from workspace...")
    try:
        response = make_request(
            f'https://api.getpostman.com/workspaces/{workspace_id}',
            headers=headers
        )
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch workspace details: {e}")
        return 0
    
    workspace_data = response.get('workspace', {})
    environments = workspace_data.get('environments', [])
    print(f"   Found {len(environments)} environment(s)")
    
    if not environments:
        print("   No environments to export")
        return 0
    
    # Export each environment
    exported_count = 0
    for i, env in enumerate(environments, 1):
        env_id = env['id']
        env_name = env.get('name', f'environment_{env_id}')
        
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in env_name)
        safe_name = safe_name.strip()
        
        print(f"\n   [{i}/{len(environments)}] Exporting: {env_name}")
        
        try:
            # Get full environment data
            env_data = make_request(
                f'https://api.getpostman.com/environments/{env_id}',
                headers=headers
            )
            
            # Save to file
            filename = f"{export_dir}/environments/{safe_name}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(env_data, f, indent=2, ensure_ascii=False)
            
            print(f"       ✓ Saved to: {filename}")
            exported_count += 1
            
        except Exception as e:
            print(f"       ✗ Failed to export: {e}")
    
    return exported_count

def create_summary_file(export_dir, collections_count, environments_count, config=None):
    """Create a summary file with export information."""
    if config is None:
        config = DEFAULT_CONFIG

    summary = {
        "export_date": datetime.now().isoformat(),
        "workspace_type": config['workspace_type'],
        "workspace_name": config['workspace_name'] if config['workspace_name'] else "Not specified",
        "collections_exported": collections_count,
        "environments_exported": environments_count,
        "export_directory": export_dir
    }

    summary_file = f"{export_dir}/export_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return summary

def export_postman_collections(config=None, progress_callback=None):
    """
    Main export function that can be used by both CLI and web UI.

    Args:
        config: Dictionary with configuration parameters
        progress_callback: Optional function to report progress (for web UI)

    Returns:
        Dictionary with export results including directory path and statistics
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Validate configuration
    validate_config(config)

    # Create export directory
    export_dir = create_export_directory(config)

    # Get workspace
    workspace_result = get_workspace(config)
    if isinstance(workspace_result, tuple):
        workspace_id, workspace_info = workspace_result
    else:
        workspace_id = workspace_result
        workspace_info = None

    # Export collections
    collections_count = export_collections(workspace_id, export_dir, config)

    # Export environments
    environments_count = 0
    if config['export_environments']:
        environments_count = export_environments(workspace_id, export_dir, config)

    # Create summary file
    summary = create_summary_file(export_dir, collections_count, environments_count, config)

    return {
        'export_directory': export_dir,
        'collections_count': collections_count,
        'environments_count': environments_count,
        'workspace_info': workspace_info,
        'summary': summary
    }

def main():
    """Main execution function for CLI usage."""
    print("=" * 60)
    print("🚀 Postman Collections Exporter")
    print("=" * 60)

    try:
        # Use default configuration for CLI
        result = export_postman_collections()

        # Final summary
        print("\n" + "=" * 60)
        print("✨ Export Complete!")
        print(f"   Collections exported: {result['collections_count']}")
        if EXPORT_ENVIRONMENTS:
            print(f"   Environments exported: {result['environments_count']}")
        print(f"   Files saved to: {result['export_directory']}/")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
