import streamlit as st
import requests
import pandas as pd
from utils import format_search_results
import yaml
from io import StringIO

# --- Configuration ---
# Set the layout and title for the Streamlit page.
st.set_page_config(
    page_title="Data Lake Frontend",
    page_icon="🌊",
    layout="wide",
)


def show_upload_page(api_base_url):
    """Renders the upload page UI and logic."""
    st.header("Upload a New File")
    st.markdown("Select a data file and fill in the metadata form to upload.")

    # Step 1: File Uploader
    data_file = st.file_uploader(
        "Select the data file you want to upload.", type=None, key="data_file_uploader"
    )

    # Step 2: Metadata Form (appears only after a file is selected)
    if data_file is not None:
        st.markdown("---")
        st.subheader(f"Metadata for: `{data_file.name}`")

        with st.form(key="metadata_form"):
            # Form fields for metadata
            research_project_id = st.text_input(
                "Research Project ID*", placeholder="e.g., BBBO"
            )
            author = st.text_input("Author*", placeholder="e.g., wkm2109")
            experiment_type = st.text_input(
                "Experiment Type", placeholder="e.g., Data Calibration"
            )
            date_conducted = st.date_input("Date Conducted")
            custom_tags = st.text_input(
                "Custom Tags (comma-separated)",
                placeholder="e.g., tag1, important_data",
            )

            submit_button = st.form_submit_button(label="Upload File and Metadata")

            if submit_button:
                # Basic validation
                if not research_project_id or not author:
                    st.error("Please fill in all required fields (*).")
                    return

                # Create metadata dictionary from form data
                metadata_dict = {
                    "research_project_id": research_project_id,
                    "author": author,
                    "experiment_type": experiment_type,
                    "date_conducted": date_conducted.isoformat()
                    if date_conducted
                    else None,
                    "custom_tags": custom_tags,
                }

                # Convert dictionary to a YAML string
                yaml_string = yaml.dump(metadata_dict, sort_keys=False)

                # Create an in-memory text file for the metadata
                metadata_file_obj = StringIO(yaml_string)
                metadata_file_obj.name = "metadata.yaml"  # Give it a name

                # Prepare files for the multipart/form-data request.
                # By passing the file object (data_file) directly instead of using .getvalue(),
                # the requests library will stream the upload, which is memory-efficient for large files.
                files = {
                    "data_file": (data_file.name, data_file, data_file.type),
                    "metadata_file": (
                        metadata_file_obj.name,
                        metadata_file_obj.getvalue(),
                        "text/yaml",
                    ),
                }

                try:
                    with st.spinner(f"Uploading `{data_file.name}`..."):
                        response = requests.post(
                            f"{api_base_url}/uploadfile/",
                            files=files,
                            timeout=3600,  # Set a longer timeout for very large uploads (e.g., 1 hour)
                        )

                    if response.status_code == 200:
                        st.success("File uploaded successfully!")
                        st.json(response.json())
                    else:
                        st.error(f"Upload failed. Status code: {response.status_code}")
                        try:
                            st.json(response.json())
                        except requests.exceptions.JSONDecodeError:
                            st.text(response.text)

                except requests.exceptions.RequestException as e:
                    st.error(f"An error occurred during upload: {e}")


# --- UI Sections ---
def show_search_page(api_base_url):
    """Renders the search page UI and logic."""
    st.header("Search the Data Lake")
    st.markdown(
        "Use the filters below to find files. Leave a field blank to ignore it in the search."
    )

    # --- Search Filter Inputs ---
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            research_project_id = st.text_input(
                "Research Project ID", placeholder="e.g., BBBO"
            )
            author = st.text_input("Author", placeholder="e.g., wkm2109")
            file_type = st.text_input("File Type", placeholder="e.g., PDF, MAT, TXT")

        with col2:
            experiment_type = st.text_input(
                "Experiment Type", placeholder="e.g., Data Calibration"
            )
            tags_contain = st.text_input(
                "Tags Contain", placeholder="e.g., 1.5V, 5hz, etc."
            )
            # Date inputs
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                date_after = st.date_input("Conducted On or After", value=None)
            with date_col2:
                date_before = st.date_input("Conducted On or Before", value=None)

    # --- Search Button and Logic ---
    if st.button("🔎 Search", use_container_width=True):
        # Prepare the parameters for the API request
        params = {
            "research_project_id": research_project_id,
            "author": author,
            "file_type": file_type,
            "experiment_type": experiment_type,
            "tags_contain": tags_contain,
            "date_after": date_after.isoformat() if date_after else None,
            "date_before": date_before.isoformat() if date_before else None,
        }
        # Remove any empty filters so they aren't sent to the API
        params = {k: v for k, v in params.items() if v}

        try:
            with st.spinner("Searching..."):
                response = requests.get(
                    f"{api_base_url}/search", params=params, timeout=60
                )

            if response.status_code == 200:
                results = response.json()
                if results:
                    st.success(f"Found {len(results)} matching files.")
                    # Store results in session state to persist them
                    st.session_state.search_results = results
                else:
                    st.info("No files found matching your criteria.")
                    st.session_state.search_results = []  # Clear previous results
            else:
                st.error(f"Search failed. Status code: {response.status_code}")
                try:
                    st.json(response.json())
                except requests.exceptions.JSONDecodeError:
                    st.text(response.text)  # Show raw text if not JSON
                st.session_state.search_results = []

        except requests.exceptions.RequestException as e:
            st.error(f"An error occurred during search: {e}")
            st.session_state.search_results = []

    # --- Results Display ---
    st.markdown("---")
    st.subheader("Results")
    if "search_results" in st.session_state and st.session_state.search_results:
        results_df = format_search_results(
            pd.DataFrame(st.session_state.search_results)
        )
        st.dataframe(results_df, use_container_width=True)

        # --- Download Section ---
        st.markdown("---")
        st.subheader("Download a File: ")

        # Create a list of unique filenames for the dropdown
        filenames = results_df["file_name"].unique().tolist()

        selected_filename = st.selectbox(
            "Select a file from the results above to download:",
            options=filenames,
            index=None,  # Default to no selection
            placeholder="Choose a file...",
        )

        if selected_filename:
            # Check for duplicates
            matching_files = results_df[results_df["file_name"] == selected_filename]

            if len(matching_files) > 1:
                # Handle duplicates with a second dropdown for file_id
                st.warning(
                    f"Found {len(matching_files)} files named '{selected_filename}'. Please select the specific File ID to download."
                )

                # Get a list of file IDs for the dropdown
                file_ids = matching_files["file_id"].tolist()

                selected_file_id = st.selectbox(
                    "Select the exact File ID to download:",
                    options=file_ids,
                    index=None,
                    placeholder="Choose a File ID...",
                )

                if selected_file_id:
                    download_url = f"{api_base_url}/download/{selected_file_id}"
                    st.link_button(
                        f"Download File ID: {selected_file_id}",
                        url=download_url,
                        use_container_width=True,
                    )

            else:
                # No duplicates, proceed as normal
                selected_file_id = matching_files.iloc[0]["file_id"]
                download_url = f"{api_base_url}/download/{selected_file_id}"
                st.link_button(
                    f"Download '{selected_filename}'",
                    url=download_url,
                    use_container_width=True,
                )

    else:
        st.write(
            "No search results to display. Use the filters above to start a new search."
        )


# --- Main App Logic ---

# --- Sidebar for Navigation and Settings ---
with st.sidebar:
    st.title("Navigation")
    page = st.radio(
        "Choose a page to navigate to:",
        ("Search/Download", "Upload"),
        label_visibility="collapsed",
    )

    st.markdown("---")

    with st.expander("Settings & API Status"):
        st.header("Settings")
        api_base_url = st.text_input(
            "Backend API URL",
            value="http://localhost:8001",
            help="The address of the FastAPI backend service.",
        )

        st.subheader("API Status")
        try:
            response = requests.get(f"{api_base_url}/status", timeout=5)
            if response.status_code == 200:
                st.success("Connected")
            else:
                st.error(f"Status: {response.status_code}")
        except requests.exceptions.RequestException:
            st.error("Connection Error")


# --- Page Content ---
if page == "Upload":
    show_upload_page(api_base_url)

elif page == "Search/Download":
    show_search_page(api_base_url)
