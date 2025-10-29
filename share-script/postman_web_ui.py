#!/usr/bin/env python3
"""
Postman Collections Exporter - Web UI
A user-friendly Streamlit interface for exporting Postman collections.
"""

import streamlit as st
import zipfile
import io
import json
import os
import sys
from datetime import datetime

# Import the postman exporter module
import importlib.util
spec = importlib.util.spec_from_file_location("postman_exporter", os.path.join(os.path.dirname(__file__), "postman-exporter.py"))
postman_exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(postman_exporter)

# Get the functions we need
export_postman_collections = postman_exporter.export_postman_collections
get_workspace = postman_exporter.get_workspace
validate_config = postman_exporter.validate_config

# ==============================================================================
# STREAMLIT CONFIGURATION
# ==============================================================================

st.set_page_config(
    page_title="Postman Collections Exporter",
    page_icon="📮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def display_workspace_info(workspace_info):
    """Display workspace information in a nice format."""
    if workspace_info:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Workspace Name", workspace_info.get('name', 'Unknown'))
        with col2:
            st.metric("Workspace Type", workspace_info.get('type', 'Unknown'))
        with col3:
            st.metric("Workspace ID", workspace_info.get('id', 'Unknown')[:8] + "...")

def create_zip_file(export_dir):
    """Create a ZIP file containing all exported files."""
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Walk through the export directory and add all files
        for root, dirs, files in os.walk(export_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, export_dir)
                zip_file.write(file_path, arcname)

    zip_buffer.seek(0)
    return zip_buffer

def get_collections_for_download(export_dir):
    """Get list of collection files for individual download."""
    collections_dir = os.path.join(export_dir, 'collections')
    collections = []

    if os.path.exists(collections_dir):
        for file in os.listdir(collections_dir):
            if file.endswith('.json'):
                collections.append(file)

    return collections

def get_environments_for_download(export_dir):
    """Get list of environment files for individual download."""
    environments_dir = os.path.join(export_dir, 'environments')
    environments = []

    if os.path.exists(environments_dir):
        for file in os.listdir(environments_dir):
            if file.endswith('.json'):
                environments.append(file)

    return environments

def read_file_content(file_path):
    """Read file content for download."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

# ==============================================================================
# MAIN APPLICATION
# ==============================================================================

def main():
    """Main Streamlit application."""
    st.title("📮 Postman Collections Exporter")
    st.markdown("---")
    st.markdown("Export your Postman collections and environments with a user-friendly web interface.")

    # Initialize session state
    if 'export_results' not in st.session_state:
        st.session_state.export_results = None
    if 'config' not in st.session_state:
        st.session_state.config = {}

    # Sidebar Configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # API Key
        api_key = st.text_input(
            "Postman API Key *",
            type="password",
            placeholder="Enter your Postman API key",
            help="Get your API key from: https://web.postman.co/settings/me/api-keys"
        )

        st.markdown("---")

        # Workspace Selection
        st.subheader("🏢 Workspace Selection")

        workspace_selection_method = st.radio(
            "Select workspace by:",
            options=["Type", "Specific Name", "Specific ID"],
            index=0
        )

        workspace_type = None
        workspace_name = ""
        workspace_id = ""

        if workspace_selection_method == "Type":
            workspace_type = st.selectbox(
                "Workspace Type:",
                options=["personal", "team", "private", "public", "partner", "all"],
                index=0,
                help="Filter workspaces by type"
            )
        elif workspace_selection_method == "Specific Name":
            workspace_name = st.text_input(
                "Workspace Name:",
                placeholder="Enter exact workspace name"
            )
            workspace_type = st.selectbox(
                "Workspace Type (optional):",
                options=["personal", "team", "private", "public", "partner", "all"],
                index=0,
                help="Optional: filter by type when searching by name"
            )
        else:  # Specific ID
            workspace_id = st.text_input(
                "Workspace ID:",
                placeholder="12345678-1234-1234-1234-123456789012"
            )

        st.markdown("---")

        # Export Options
        st.subheader("📤 Export Options")

        export_environments = st.checkbox(
            "Export Environments",
            value=True,
            help="Include environment files in the export"
        )

        include_timestamp = st.checkbox(
            "Include Timestamp in Directory Name",
            value=True,
            help="Add timestamp to export directory name for versioning"
        )

        collection_format = st.selectbox(
            "Collection Format:",
            options=["v2.1.0", "v2.0.0"],
            index=0,
            help="Postman collection format version (v2.1.0 recommended)"
        )

        export_directory = st.text_input(
            "Export Directory Name:",
            value="postman_exports",
            help="Base name for the export directory"
        )

        st.markdown("---")

        # Export Button
        export_button = st.button(
            "🚀 Start Export",
            type="primary",
            use_container_width=True
        )

    # Main Content Area
    if export_button:
        # Validate API Key
        if not api_key:
            st.error("❌ Please enter your Postman API key")
            return

        # Build configuration
        config = {
            'api_key': api_key,
            'workspace_type': workspace_type if workspace_type else 'personal',
            'workspace_name': workspace_name,
            'workspace_id': workspace_id,
            'export_directory': export_directory,
            'include_timestamp': include_timestamp,
            'collection_format': collection_format,
            'export_environments': export_environments,
        }

        st.session_state.config = config

        # Show progress
        progress_bar = st.progress(0, text="Initializing export...")
        status_text = st.empty()

        try:
            # Step 1: Validate configuration
            status_text.text("Validating configuration...")
            progress_bar.progress(10)
            validate_config(config)

            # Step 2: Get workspace information
            status_text.text("Fetching workspace information...")
            progress_bar.progress(25)

            workspace_result = get_workspace(config)
            if isinstance(workspace_result, tuple):
                workspace_id, workspace_info = workspace_result
            else:
                workspace_id = workspace_result
                workspace_info = None

            # Step 3: Perform export
            status_text.text("Exporting collections...")
            progress_bar.progress(40)

            result = export_postman_collections(config)

            # Step 4: Complete
            progress_bar.progress(100)
            status_text.text("✅ Export completed successfully!")

            # Store results in session state
            st.session_state.export_results = result
            st.session_state.workspace_info = workspace_info

            # Success message
            st.success(f"✅ Export completed successfully! {result['collections_count']} collections and {result['environments_count']} environments exported.")

        except Exception as e:
            st.error(f"❌ Export failed: {str(e)}")
            progress_bar.empty()
            status_text.empty()
            return

    # Display Export Results
    if st.session_state.export_results:
        st.markdown("---")
        st.header("📊 Export Results")

        result = st.session_state.export_results
        workspace_info = st.session_state.get('workspace_info')

        # Display workspace information
        if workspace_info:
            st.subheader("🏢 Workspace Information")
            display_workspace_info(workspace_info)

        # Display export statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Collections Exported", result['collections_count'])
        with col2:
            st.metric("Environments Exported", result['environments_count'])
        with col3:
            st.metric("Export Directory", result['export_directory'].split('/')[-1])

        # Download Section
        st.markdown("---")
        st.header("⬇️ Downloads")

        # Bulk Download
        st.subheader("📦 Complete Export Package")

        if os.path.exists(result['export_directory']):
            zip_data = create_zip_file(result['export_directory'])
            st.download_button(
                label="📥 Download All Files (ZIP)",
                data=zip_data,
                file_name=f"postman_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                use_container_width=True
            )

        # Individual Downloads
        collections = get_collections_for_download(result['export_directory'])
        environments = get_environments_for_download(result['export_directory'])

        if collections:
            st.subheader("📚 Individual Collections")
            cols = st.columns(min(3, len(collections)))
            for i, collection in enumerate(collections):
                with cols[i % 3]:
                    file_path = os.path.join(result['export_directory'], 'collections', collection)
                    content = read_file_content(file_path)
                    st.download_button(
                        label=f"📄 {collection.replace('.json', '')}",
                        data=content,
                        file_name=collection,
                        mime="application/json",
                        use_container_width=True
                    )

        if environments:
            st.subheader("🌍 Individual Environments")
            cols = st.columns(min(3, len(environments)))
            for i, environment in enumerate(environments):
                with cols[i % 3]:
                    file_path = os.path.join(result['export_directory'], 'environments', environment)
                    content = read_file_content(file_path)
                    st.download_button(
                        label=f"🌍 {environment.replace('.json', '')}",
                        data=content,
                        file_name=environment,
                        mime="application/json",
                        use_container_width=True
                    )

        # Summary Information
        if result.get('summary'):
            st.subheader("📄 Export Summary")
            summary_json = json.dumps(result['summary'], indent=2)
            st.download_button(
                label="📋 Export Summary (JSON)",
                data=summary_json,
                file_name="export_summary.json",
                mime="application/json"
            )

            # Display summary as JSON
            st.json(result['summary'])

# Footer
def footer():
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>Postman Collections Exporter - Built with Streamlit</p>
            <p>Need help? Check the <a href='https://github.com/anthropics/claude-code' target='_blank'>documentation</a>.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
    footer()