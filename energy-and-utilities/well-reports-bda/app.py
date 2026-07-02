"""
Streamlit UI for Oil & Gas Well Report Data Extraction using Amazon Bedrock Data Automation.

Wraps the existing bda.py and utils.py functions with a visual interface for:
- Uploading well reports (PDF)
- Selecting/creating blueprints
- Running BDA extraction jobs
- Viewing structured results
"""

import json
import os
import re
import time

import boto3
import pandas as pd
import streamlit as st
from botocore.exceptions import ClientError

# --- Constants ---
MAX_UPLOAD_SIZE_MB = 500  # BDA max file size
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe use as an S3 key.

    - Replaces spaces with underscores
    - Removes characters that are problematic in S3 keys or URLs
    - Preserves the file extension
    - Limits length to 255 characters
    """
    # Get name and extension
    name, ext = os.path.splitext(filename)

    # Replace spaces with underscores
    name = name.replace(" ", "_")

    # Remove characters that are problematic in S3/URLs
    # Allow only alphanumeric, underscores, hyphens, and dots
    name = re.sub(r"[^a-zA-Z0-9_\-.]", "", name)

    # Remove leading/trailing dots and dashes
    name = name.strip(".-")

    # Ensure name is not empty
    if not name:
        name = "unnamed_file"

    # Limit total length
    max_name_len = 255 - len(ext)
    name = name[:max_name_len]

    return f"{name}{ext}"


# Add project root to path so source imports work
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source.bda import (
    create_bda_project,
    create_custom_blueprint,
    search_bda_project,
    start_processing_job,
)
from source.utils import (
    get_aws_account_id,
    get_s3_to_dict,
    list_s3_files,
)
from source.consolidate import (
    consolidate_results,
    normalize_operator1_result,
    normalize_operator2_result,
    save_to_database,
    query_wells,
    EXAMPLE_QUERIES,
    UNIFIED_SCHEMA,
)
from source.batch_processor import BatchProcessor
from source.blueprint_analyzer import (
    compare_blueprints,
    get_differentiator_summary,
    get_extraction_instructions_summary,
    CONFIRMED_DATA_TYPES,
    INDUSTRY_DATA_TYPES,
)
from source.insights import generate_well_insights, generate_demo_insights

# --- Page Config ---
st.set_page_config(
    page_title="Well Report Data Extraction",
    page_icon="🛢️",
    layout="wide",
)

st.title("Oil & Gas Well Report Data Extraction")
st.markdown("Extract structured data from well reports using Amazon Bedrock Data Automation")


# --- Session State Init ---
if "session" not in st.session_state:
    st.session_state.session = None
if "bucket_name" not in st.session_state:
    st.session_state.bucket_name = ""
if "project_arn" not in st.session_state:
    st.session_state.project_arn = None
if "results" not in st.session_state:
    st.session_state.results = None


# --- Sidebar: AWS Configuration ---
with st.sidebar:
    st.header("AWS Configuration")

    aws_region = st.text_input("AWS Region", value="us-east-1")
    aws_profile = st.text_input("AWS Profile (optional)", value="")
    bucket_name = st.text_input("S3 Bucket Name", value=st.session_state.bucket_name)

    if st.button("Connect to AWS"):
        try:
            if aws_profile:
                session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
            else:
                session = boto3.Session(region_name=aws_region)

            account_id = get_aws_account_id(session)
            st.session_state.session = session
            st.session_state.bucket_name = bucket_name
            masked_id = account_id[:4] + "****" + account_id[-4:]
            st.success(f"Connected. Account: {masked_id}")
        except Exception as e:
            st.error(f"Connection failed: {e}")

    st.divider()
    st.markdown("**Status**")
    if st.session_state.session:
        st.markdown("🟢 AWS Connected")
    else:
        st.markdown("🔴 Not Connected")

    if st.session_state.project_arn:
        st.markdown(f"🟢 Project: `{st.session_state.project_arn.split('/')[-1]}`")


# --- Main Content ---
if not st.session_state.session:
    st.info("Configure AWS credentials in the sidebar to get started.")
    st.stop()

if not st.session_state.bucket_name:
    st.warning("Enter an S3 bucket name in the sidebar.")
    st.stop()


# --- Tabs ---
tab_upload, tab_blueprints, tab_extract, tab_results, tab_insights, tab_consolidate, tab_batch, tab_differentiator = st.tabs(
    ["Upload Reports", "Blueprints & Project", "Run Extraction", "View Results", "Insights", "Consolidated Data", "Batch Processing", "What's Special"]
)


# --- Tab 1: Upload Reports ---
with tab_upload:
    st.header("Upload Well Reports")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Upload New Files")
        uploaded_files = st.file_uploader(
            "Select PDF well reports",
            type=["pdf"],
            accept_multiple_files=True,
        )

        if uploaded_files and st.button("Upload to S3"):
            s3 = st.session_state.session.client("s3")
            progress = st.progress(0)
            skipped = []
            uploaded_count = 0
            for i, file in enumerate(uploaded_files):
                # Validate file size
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()
                file.seek(0)  # Reset to beginning

                if file_size > MAX_UPLOAD_SIZE_BYTES:
                    skipped.append(f"{file.name} ({file_size / 1024 / 1024:.1f} MB exceeds {MAX_UPLOAD_SIZE_MB} MB limit)")
                    continue

                if file_size == 0:
                    skipped.append(f"{file.name} (empty file)")
                    continue

                # Sanitize filename
                safe_name = sanitize_filename(file.name)
                s3_key = f"reports/{safe_name}"
                s3.upload_fileobj(file, st.session_state.bucket_name, s3_key)
                uploaded_count += 1
                progress.progress((i + 1) / len(uploaded_files))

            if uploaded_count > 0:
                st.success(f"Uploaded {uploaded_count} file(s) to s3://{st.session_state.bucket_name}/reports/")
            if skipped:
                for msg in skipped:
                    st.warning(f"Skipped: {msg}")

    with col2:
        st.subheader("Files in S3")
        if st.button("Refresh File List"):
            pass  # triggers rerun

        try:
            files = list_s3_files(
                st.session_state.bucket_name, "reports/", st.session_state.session
            )
            if files:
                for f in files:
                    st.text(f"📄 {f}")
            else:
                st.info("No PDF files found in reports/ prefix.")
        except Exception as e:
            st.error(f"Could not list files: {e}")


# --- Tab 2: Blueprints & Project ---
with tab_blueprints:
    st.header("Blueprints & BDA Project")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Available Blueprints")

        blueprint_dir = os.path.join(os.path.dirname(__file__), "data", "blueprints")
        blueprint_files = []
        if os.path.exists(blueprint_dir):
            blueprint_files = [
                f.replace(".json", "")
                for f in os.listdir(blueprint_dir)
                if f.endswith(".json")
            ]

        if blueprint_files:
            for bp in blueprint_files:
                st.text(f"📋 {bp}")
        else:
            st.info("No blueprint files found in data/blueprints/")

        st.divider()

        selected_blueprints = st.multiselect(
            "Select blueprints to register",
            options=blueprint_files,
            default=blueprint_files,
        )

        if st.button("Register Blueprints in BDA"):
            if not selected_blueprints:
                st.warning("Select at least one blueprint.")
            else:
                blueprint_arns = []
                for bp_name in selected_blueprints:
                    try:
                        bp_path = os.path.join(blueprint_dir, f"{bp_name}.json")
                        if not os.path.isfile(bp_path):
                            st.error(f"✗ {bp_name}: Blueprint file not found")
                            continue

                        arn = create_custom_blueprint(
                            bp_name,
                            st.session_state.session,
                            blueprint_dir=blueprint_dir,
                        )
                        blueprint_arns.append(arn)
                        st.success(f"✓ {bp_name}")
                    except Exception as e:
                        st.error(f"✗ {bp_name}: {e}")

                if blueprint_arns:
                    st.session_state.blueprint_arns = blueprint_arns

    with col2:
        st.subheader("BDA Project")

        project_name = st.text_input("Project Name", value="well-report-extraction")

        if st.button("Create / Find Project"):
            try:
                # Check if project exists
                existing = search_bda_project(project_name, st.session_state.session)
                if existing:
                    st.session_state.project_arn = existing
                    st.success(f"Found existing project: {existing}")
                elif "blueprint_arns" in st.session_state and st.session_state.blueprint_arns:
                    arn = create_bda_project(
                        project_name,
                        st.session_state.blueprint_arns,
                        session=st.session_state.session,
                    )
                    st.session_state.project_arn = arn
                    st.success(f"Created project: {arn}")
                else:
                    st.warning("Register blueprints first, then create the project.")
            except Exception as e:
                st.error(f"Project error: {e}")


# --- Tab 3: Run Extraction ---
with tab_extract:
    st.header("Run Extraction Jobs")

    if not st.session_state.project_arn:
        st.warning("Set up a BDA project in the 'Blueprints & Project' tab first.")
        st.stop()

    try:
        files = list_s3_files(
            st.session_state.bucket_name, "reports/", st.session_state.session
        )
    except Exception:
        files = []

    if not files:
        st.info("No files found. Upload reports in the 'Upload Reports' tab.")
        st.stop()

    selected_files = st.multiselect("Select files to process", options=files, default=files)

    wait_for_complete = st.checkbox("Wait for job completion", value=True)
    max_wait = st.slider("Max wait time (seconds)", 60, 1800, 600, step=60)

    if st.button("Start Extraction", type="primary"):
        if not selected_files:
            st.warning("Select at least one file.")
        else:
            st.session_state.results = []
            progress = st.progress(0)
            status_text = st.empty()

            for i, file_key in enumerate(selected_files):
                status_text.text(f"Processing: {file_key}...")
                try:
                    result = start_processing_job(
                        project_arn=st.session_state.project_arn,
                        file_name=file_key,
                        bucket_name=st.session_state.bucket_name,
                        wait_for_complete=wait_for_complete,
                        max_wait_seconds=max_wait,
                        session=st.session_state.session,
                    )
                    st.session_state.results.append(result)
                    st.success(f"✓ {file_key}")
                except TimeoutError as e:
                    st.warning(f"⏱ {file_key}: Timed out - {e}")
                except RuntimeError as e:
                    st.error(f"✗ {file_key}: {e}")
                except Exception as e:
                    st.error(f"✗ {file_key}: {e}")

                progress.progress((i + 1) / len(selected_files))

            status_text.text("Done!")


# --- Tab 4: View Results ---
with tab_results:
    st.header("Extraction Results")

    if not st.session_state.results:
        st.info("Run an extraction job first.")
        st.stop()

    for result in st.session_state.results:
        if not isinstance(result, dict) or "S3_URI" not in result:
            continue

        st.subheader(f"📄 {result.get('file', 'Unknown')}")

        s3_uri = result["S3_URI"]
        st.text(f"Output: {s3_uri}")

        try:
            # Load job metadata
            job_metadata = get_s3_to_dict(s3_uri, st.session_state.session)
            st.markdown(f"**Job Status**: {job_metadata.get('job_status', 'Unknown')}")

            output_metadata = job_metadata.get("output_metadata", [])

            for asset in output_metadata:
                asset_id = asset.get("asset_id", 0)
                input_path = asset.get("asset_input_path", {})
                st.markdown(f"**Asset {asset_id}**: `{input_path.get('s3_key', 'N/A')}`")

                segments = asset.get("segment_metadata", [])

                for segment in segments:
                    # Show custom output if available
                    custom_status = segment.get("custom_output_status", "")
                    custom_path = segment.get("custom_output_path", "")

                    if custom_path and custom_status != "NO_MATCH":
                        st.markdown("#### Custom Blueprint Output")
                        data = get_s3_to_dict(custom_path, st.session_state.session)

                        if "inference_result" in data:
                            inference = data["inference_result"]
                            for field_name, field_data in inference.items():
                                if isinstance(field_data, list) and field_data:
                                    st.markdown(f"**{field_name}**")
                                    df = pd.DataFrame(field_data)
                                    st.dataframe(df, width="stretch")
                                elif isinstance(field_data, dict):
                                    st.markdown(f"**{field_name}**")
                                    st.json(field_data)
                                else:
                                    st.markdown(f"**{field_name}**: {field_data}")
                        else:
                            st.json(data)
                    elif custom_status == "NO_MATCH":
                        st.info("No custom blueprint matched this document. Showing standard output.")

                    # Show standard output
                    standard_path = segment.get("standard_output_path", "")
                    if standard_path:
                        st.markdown("#### Standard Output")
                        standard_data = get_s3_to_dict(standard_path, st.session_state.session)

                        # Document-level info
                        doc = standard_data.get("document", {})
                        metadata = standard_data.get("metadata", {})

                        if metadata:
                            st.markdown(f"**File**: `{metadata.get('s3_key', 'N/A')}` | "
                                        f"**Pages**: {metadata.get('number_of_pages', 'N/A')} | "
                                        f"**Type**: {metadata.get('file_type', 'N/A')}")

                        # Show summary and description
                        if doc.get("summary"):
                            st.markdown("**Summary**")
                            st.info(doc["summary"])

                        if doc.get("description"):
                            st.markdown(f"**Description**: {doc['description']}")

                        # Show full document markdown
                        if doc.get("representation", {}).get("markdown"):
                            with st.expander("Full Document Content (Markdown)", expanded=False):
                                st.markdown(doc["representation"]["markdown"])

                        # Show per-page content
                        pages = standard_data.get("pages", [])
                        if pages:
                            st.markdown(f"**Pages processed**: {len(pages)}")
                            for page in pages:
                                page_idx = page.get("page_index", "?")
                                page_md = page.get("representation", {}).get("markdown", "")
                                with st.expander(f"Page {page_idx}", expanded=False):
                                    if page_md:
                                        st.markdown(page_md)
                                    else:
                                        st.text("No content extracted for this page.")

                        # Fallback: raw JSON if no recognized structure
                        if not doc and not pages:
                            with st.expander("Raw Standard Output", expanded=True):
                                st.json(standard_data)

        except Exception as e:
            st.warning(f"Could not load results: {e}")
            st.text("Raw result:")
            st.json(result)

        st.divider()

    # Export option
    if st.button("Export All Results as JSON"):
        export_data = json.dumps(st.session_state.results, indent=2, default=str)
        st.download_button(
            label="Download JSON",
            data=export_data,
            file_name="extraction_results.json",
            mime="application/json",
        )


# --- Tab 5: Insights ---
with tab_insights:
    st.header("Meaningful Insights from Extracted Data")
    st.markdown("""
    **This is what customers do with the data.** Raw tables aren't insights — 
    insights are actionable conclusions that drive decisions. Below are the types of 
    analysis enabled by structured extraction.
    """)

    st.markdown("---")

    # Check if we have real consolidated data
    has_real_data = False
    if st.session_state.results:
        custom_outputs = []
        for result in st.session_state.results:
            if not isinstance(result, dict) or "S3_URI" not in result:
                continue
            try:
                job_metadata = get_s3_to_dict(result["S3_URI"], st.session_state.session)
                for asset in job_metadata.get("output_metadata", []):
                    for segment in asset.get("segment_metadata", []):
                        custom_path = segment.get("custom_output_path", "")
                        custom_status = segment.get("custom_output_status", "")
                        if custom_path and custom_status != "NO_MATCH":
                            data = get_s3_to_dict(custom_path, st.session_state.session)
                            custom_outputs.append(data)
            except Exception:
                pass

        if custom_outputs:
            has_real_data = True
            consolidated = consolidate_results(custom_outputs)
            insights = generate_well_insights(consolidated)

    if not has_real_data:
        st.info(
            "Showing demo insights with sample data. Upload actual well reports "
            "to see insights derived from your extracted data."
        )
        insights = generate_demo_insights()

    # Display insights by category
    category_icons = {
        "cost": "💰 Cost Optimization",
        "compliance": "🏛️ Regulatory Compliance",
        "trend": "📊 Trends & Benchmarking",
        "quality": "⚠️ Data Quality",
        "anomaly": "🔍 Anomaly Detection",
    }

    # Group insights by category
    categories_seen = []
    for insight in insights:
        cat = insight.get("category", "other")
        if cat not in categories_seen:
            categories_seen.append(cat)

    for cat in categories_seen:
        cat_insights = [i for i in insights if i.get("category") == cat]
        st.subheader(category_icons.get(cat, cat))

        for insight in cat_insights:
            with st.expander(f"{insight.get('icon', '📌')} {insight['title']}", expanded=True):
                st.markdown(f"**{insight['description']}**")

                # Show supporting data
                if "data" in insight and isinstance(insight["data"], pd.DataFrame):
                    st.dataframe(insight["data"], width="stretch", hide_index=True)

                # Show recommended action
                if "action" in insight:
                    st.markdown(f"**Recommended Action:** {insight['action']}")

        st.markdown("---")

    # Summary
    st.subheader("From Data Points to Decisions")
    st.markdown("""
    | What BDA Extracts | What Insights Enable |
    |---|---|
    | Proppant volumes per stage | Cost optimization, design benchmarking |
    | Water usage per well | Regulatory compliance (FracFocus, state permits) |
    | Perforation intervals | Lateral length trends, stage spacing analysis |
    | Casing programs | Wellbore integrity verification, anomaly detection |
    | Well identification | Cross-well comparison, asset evaluation for M&A |
    
    **The pipeline**: Documents → Structured Data → Consolidated Database → Actionable Insights → Business Decisions
    """)


# --- Tab 6: Consolidated Data ---
with tab_consolidate:
    st.header("Consolidated Well Data")
    st.markdown("""
    **The Value**: Different operators produce reports in different formats. 
    BDA + custom blueprints normalize them into a single unified schema, 
    making all well data queryable from one location.
    """)

    st.markdown("---")

    # Show the normalization concept
    col1, col2, col3 = st.columns([2, 1, 2])
    with col1:
        st.markdown("**Input: Heterogeneous Formats**")
        st.markdown("""
        - Operator 1: `Stage_Length`, `Proppant_Volume`, `Top_Perf`
        - Operator 2: `Water`, `Proppant_Volume`, `Top Perf` (space)
        - Different layouts, different field names
        - Paper scans, PDFs, legacy exports
        """)
    with col2:
        st.markdown("")
        st.markdown("")
        st.markdown("### →")
    with col3:
        st.markdown("**Output: Unified Schema**")
        st.markdown("""
        - `well_information` (API, name, operator, location)
        - `perforation_data` (stage, top, bottom)
        - `casing_summary` (size, weight, depth)
        - `completion_summary` (proppant, water, stage length)
        """)

    st.markdown("---")

    # Load and consolidate custom outputs from results
    if not st.session_state.results:
        st.info("Run extraction jobs first to see consolidated data here.")
        st.stop()

    # Collect custom outputs
    custom_outputs = []
    for result in st.session_state.results:
        if not isinstance(result, dict) or "S3_URI" not in result:
            continue
        try:
            job_metadata = get_s3_to_dict(result["S3_URI"], st.session_state.session)
            for asset in job_metadata.get("output_metadata", []):
                for segment in asset.get("segment_metadata", []):
                    custom_path = segment.get("custom_output_path", "")
                    custom_status = segment.get("custom_output_status", "")
                    if custom_path and custom_status != "NO_MATCH":
                        data = get_s3_to_dict(custom_path, st.session_state.session)
                        custom_outputs.append(data)
        except Exception:
            pass

    if not custom_outputs:
        st.warning(
            "No custom blueprint matches found in current results. "
            "This tab shows consolidated data when well reports match the operator blueprints. "
            "Upload actual well completion reports to see this in action."
        )

        # Show demo with sample data
        st.markdown("---")
        st.subheader("Demo: What Consolidated Data Looks Like")
        st.markdown("Below is sample data showing how multiple operator formats merge into one view:")

        # Sample demo data
        demo_wells = pd.DataFrame([
            {"api_number": "17-033-12345", "well_name": "Smith #1H", "operator": "Operator A",
             "field": "Eagle Ford", "county_parish": "Karnes", "state": "TX",
             "spud_date": "2023-01-15", "measured_depth": "18500", "product_type": "Oil"},
            {"api_number": "17-033-67890", "well_name": "Jones #2H", "operator": "Operator B",
             "field": "Eagle Ford", "county_parish": "DeWitt", "state": "TX",
             "spud_date": "2023-03-22", "measured_depth": "19200", "product_type": "Gas"},
            {"api_number": "22-015-11111", "well_name": "Davis #3H", "operator": "Operator A",
             "field": "Haynesville", "county_parish": "Caddo", "state": "LA",
             "spud_date": "2022-11-08", "measured_depth": "16800", "product_type": "Gas"},
        ])

        demo_perfs = pd.DataFrame([
            {"well_name": "Smith #1H", "api_number": "17-033-12345", "stage": 1, "top_perf": 12500, "bottom_perf": 12800},
            {"well_name": "Smith #1H", "api_number": "17-033-12345", "stage": 2, "top_perf": 12800, "bottom_perf": 13100},
            {"well_name": "Jones #2H", "api_number": "17-033-67890", "stage": 1, "top_perf": 13200, "bottom_perf": 13500},
            {"well_name": "Jones #2H", "api_number": "17-033-67890", "stage": 2, "top_perf": 13500, "bottom_perf": 13800},
            {"well_name": "Davis #3H", "api_number": "22-015-11111", "stage": 1, "top_perf": 11000, "bottom_perf": 11300},
        ])

        demo_completions = pd.DataFrame([
            {"well_name": "Smith #1H", "api_number": "17-033-12345", "stage": 1, "proppant_volume": 450000, "water_volume": 12000, "stage_length": 300},
            {"well_name": "Smith #1H", "api_number": "17-033-12345", "stage": 2, "proppant_volume": 480000, "water_volume": 12500, "stage_length": 300},
            {"well_name": "Jones #2H", "api_number": "17-033-67890", "stage": 1, "proppant_volume": 520000, "water_volume": 14000, "stage_length": None},
            {"well_name": "Jones #2H", "api_number": "17-033-67890", "stage": 2, "proppant_volume": 510000, "water_volume": 13800, "stage_length": None},
            {"well_name": "Davis #3H", "api_number": "22-015-11111", "stage": 1, "proppant_volume": 390000, "water_volume": 10500, "stage_length": 280},
        ])

        st.markdown("**Well Information** (unified from all operators)")
        st.dataframe(demo_wells, width="stretch")

        st.markdown("**Perforation Data** (normalized across formats)")
        st.dataframe(demo_perfs, width="stretch")

        st.markdown("**Completion Summary** (merged from different field names)")
        st.dataframe(demo_completions, width="stretch")

        st.markdown("---")
        st.subheader("Query the Consolidated Data")
        st.markdown("Once data is consolidated, you can run cross-well queries:")

        selected_query = st.selectbox("Example queries", list(EXAMPLE_QUERIES.keys()))
        st.code(EXAMPLE_QUERIES[selected_query], language="sql")

    else:
        # Real consolidated data from actual extraction results
        st.subheader("Consolidated Extraction Results")

        consolidated = consolidate_results(custom_outputs)

        st.markdown("**Well Information**")
        st.dataframe(consolidated["well_information"], width="stretch")

        if not consolidated["perforation_data"].empty:
            st.markdown("**Perforation Data**")
            st.dataframe(consolidated["perforation_data"], width="stretch")

        if not consolidated["casing_summary"].empty:
            st.markdown("**Casing Summary**")
            st.dataframe(consolidated["casing_summary"], width="stretch")

        if not consolidated["completion_summary"].empty:
            st.markdown("**Completion Summary**")
            st.dataframe(consolidated["completion_summary"], width="stretch")

        # Save to database
        st.markdown("---")
        if st.button("Save to Local Database (SQLite)"):
            db_path = save_to_database(consolidated)
            st.success(f"Saved to `{db_path}`. You can now query this with any SQL tool.")

        # Query interface
        st.subheader("Query Consolidated Data")
        selected_query = st.selectbox("Example queries", list(EXAMPLE_QUERIES.keys()))
        st.code(EXAMPLE_QUERIES[selected_query], language="sql")

        # Safe query builder instead of free-text SQL
        st.markdown("**Query Builder** (select tables and filters):")
        query_table = st.selectbox(
            "Table",
            ["well_information", "perforation_data", "casing_summary", "completion_summary"],
            key="custom_query_table",
        )
        query_filter_col = st.text_input(
            "Filter column (optional, e.g. 'operator', 'state', 'well_name'):",
            key="custom_query_filter_col",
        )
        query_filter_val = st.text_input(
            "Filter value (optional):",
            key="custom_query_filter_val",
        )

        if st.button("Run Query"):
            try:
                import sqlite3 as _sqlite3
                conn = _sqlite3.connect(":memory:")
                for name, df in consolidated.items():
                    if not df.empty:
                        df.to_sql(name, conn, index=False)

                # Validate table name to prevent SQL injection
                valid_tables = ["well_information", "perforation_data", "casing_summary", "completion_summary"]
                if query_table not in valid_tables:
                    st.error(f"Invalid table: '{query_table}'")
                elif query_filter_col and query_filter_val:
                    # Validate column name against schema to prevent injection
                    valid_columns = set()
                    for cols in UNIFIED_SCHEMA.values():
                        valid_columns.update(cols)

                    if query_filter_col not in valid_columns:
                        st.error(f"Invalid column: '{query_filter_col}'. Valid columns: {', '.join(sorted(valid_columns))}")
                    else:
                        # Use parameterized query for the filter value
                        safe_query = f"SELECT * FROM {query_table} WHERE {query_filter_col} = ?"
                        result_df = pd.read_sql_query(safe_query, conn, params=[query_filter_val])
                        st.dataframe(result_df, width="stretch")
                else:
                    safe_query = f"SELECT * FROM {query_table}"
                    result_df = pd.read_sql_query(safe_query, conn)
                    st.dataframe(result_df, width="stretch")

                conn.close()
            except Exception as e:
                st.error(f"Query error: {e}")

        # Export
        st.markdown("---")
        if st.button("Export Consolidated Data as CSV"):
            for name, df in consolidated.items():
                if not df.empty:
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label=f"Download {name}.csv",
                        data=csv,
                        file_name=f"{name}.csv",
                        mime="text/csv",
                        key=f"download_{name}",
                    )

# --- Tab 6: Batch Processing ---
with tab_batch:
    st.header("Batch Processing (Scale Operations)")
    st.markdown("""
    Process large volumes of well reports in parallel. This demonstrates that the 
    extraction pipeline supports scale — concurrent job submission, retry logic, 
    throttle handling, and throughput metrics.
    """)

    st.markdown("---")

    # Scale info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Max File Size", "500 MB")
    with col2:
        st.metric("Max Pages/Doc", "3,000")
    with col3:
        st.metric("Concurrent Jobs", "Configurable")

    st.markdown("---")

    if not st.session_state.project_arn:
        st.warning("Set up a BDA project in the 'Blueprints & Project' tab first.")
        st.stop()

    # Configuration
    st.subheader("Batch Configuration")
    col1, col2 = st.columns(2)

    with col1:
        max_concurrent = st.slider(
            "Max concurrent jobs",
            min_value=1,
            max_value=20,
            value=5,
            help="Number of files processed simultaneously. Higher = faster but may hit account quotas.",
        )
        max_retries = st.slider(
            "Max retries per file",
            min_value=1,
            max_value=5,
            value=2,
            help="How many times to retry a failed file before giving up.",
        )

    with col2:
        max_wait_per_file = st.slider(
            "Max wait per file (seconds)",
            min_value=60,
            max_value=1800,
            value=600,
            step=60,
            help="Timeout for each individual file. Large files may need more time.",
        )
        poll_interval = st.slider(
            "Poll interval (seconds)",
            min_value=5,
            max_value=30,
            value=10,
            help="How often to check job status.",
        )

    st.markdown("---")

    # File selection
    st.subheader("Select Files for Batch Processing")
    try:
        all_files = list_s3_files(
            st.session_state.bucket_name, "reports/", st.session_state.session
        )
    except Exception:
        all_files = []

    if not all_files:
        st.info("No files found. Upload reports in the 'Upload Reports' tab.")
        st.stop()

    selected_batch_files = st.multiselect(
        "Select files to process in batch",
        options=all_files,
        default=all_files,
        key="batch_files",
    )

    st.markdown(f"**Selected**: {len(selected_batch_files)} files | "
                f"**Estimated time**: ~{len(selected_batch_files) * 90 / max_concurrent:.0f}s "
                f"(at ~90s/file with {max_concurrent} concurrent)")

    st.markdown("---")

    # Run batch
    if st.button("Start Batch Processing", type="primary", key="batch_start"):
        if not selected_batch_files:
            st.warning("Select at least one file.")
        else:
            processor = BatchProcessor(
                project_arn=st.session_state.project_arn,
                bucket_name=st.session_state.bucket_name,
                max_concurrent_jobs=max_concurrent,
                max_retries=max_retries,
                max_wait_per_file=max_wait_per_file,
                poll_interval=poll_interval,
                session=st.session_state.session,
            )

            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.empty()

            def update_progress(completed, total, current_file):
                progress_bar.progress(completed / total)
                status_text.text(
                    f"Completed: {completed}/{total} | Latest: {current_file}"
                )

            processor.set_progress_callback(update_progress)

            # Run the batch
            with st.spinner(f"Processing {len(selected_batch_files)} files..."):
                batch_results = processor.process_batch(selected_batch_files)

            # Show metrics
            st.markdown("---")
            st.subheader("Batch Results")

            m = processor.metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Successful", f"{m.successful}/{m.total_files}")
            with col2:
                st.metric("Failed", m.failed)
            with col3:
                st.metric("Avg Time/File", f"{m.avg_duration_seconds:.1f}s")
            with col4:
                st.metric("Throughput", f"{m.throughput_files_per_minute:.1f} files/min")

            st.markdown(f"**Total batch duration**: {m.total_duration_seconds:.1f}s | "
                        f"**Max concurrent**: {m.max_concurrent_jobs}")

            # Results table
            results_data = []
            for r in batch_results:
                results_data.append({
                    "File": r.file_key,
                    "Status": r.status,
                    "Duration (s)": f"{r.duration_seconds:.1f}",
                    "Attempts": r.attempts,
                    "Error": r.error_message or "",
                })

            st.dataframe(pd.DataFrame(results_data), width="stretch")

            # Store successful results for use in other tabs
            successful = processor.get_successful_results()
            if successful:
                st.session_state.results = successful
                st.success(
                    f"✓ {len(successful)} files processed successfully. "
                    f"View results in 'View Results' and 'Consolidated Data' tabs."
                )

            # Show failed files
            failed = processor.get_failed_files()
            if failed:
                st.warning(f"⚠ {len(failed)} files failed:")
                for f in failed:
                    st.text(f"  ✗ {f}")

    # Architecture explanation
    st.markdown("---")
    st.subheader("How Batch Processing Works")
    st.markdown("""
    ```
    ┌─────────────────────────────────────────────────────────┐
    │                   BatchProcessor                         │
    ├─────────────────────────────────────────────────────────┤
    │                                                         │
    │  File Queue ──→ ThreadPoolExecutor (N workers)          │
    │                      │                                  │
    │                      ├── Worker 1 → BDA Job → Poll      │
    │                      ├── Worker 2 → BDA Job → Poll      │
    │                      ├── Worker 3 → BDA Job → Poll      │
    │                      └── Worker N → BDA Job → Poll      │
    │                                                         │
    │  Features:                                              │
    │  • Configurable parallelism (1-20 concurrent jobs)      │
    │  • Exponential backoff on throttling                    │
    │  • Automatic retries on transient failures             │
    │  • Timeout handling per file                           │
    │  • Failure isolation (one file doesn't stop batch)     │
    │  • Throughput metrics and progress tracking            │
    │                                                         │
    │  Production scale pattern:                              │
    │  • Replace ThreadPool with SQS + Lambda/Step Functions │
    │  • Add DLQ for failed files                            │
    │  • Request BDA quota increases for higher throughput   │
    │  • Use S3 event notifications for auto-processing      │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
    ```
    """)

    st.info(
        "**Note**: This PoC has been tested with individual reports (10–50 pages). "
        "For production scale (>1,000 documents), request BDA quota increases via "
        "AWS Service Quotas and consider replacing the ThreadPool with "
        "SQS + Step Functions for durability."
    )


# --- Tab 7: What's Special (Differentiator) ---
with tab_differentiator:
    st.header("What's Special: BDA vs Standard Text Extraction")
    st.markdown("""
    This isn't just OCR. Custom blueprints enable **domain-aware structured extraction** 
    that understands industry-specific data types across different document formats.
    """)

    st.markdown("---")

    # Differentiator comparison table
    st.subheader("Capability Comparison")
    diff_df = get_differentiator_summary()
    st.dataframe(
        diff_df.rename(columns={
            "capability": "Capability",
            "generic_ocr": "Generic OCR (Textract/Tesseract)",
            "bda_standard": "BDA Standard Output",
            "bda_custom_blueprint": "BDA + Custom Blueprints",
        }),
        width="stretch",
        hide_index=True,
    )

    st.markdown("---")

    # Confirmed data types
    st.subheader("Confirmed Industry Data Types")
    st.markdown("Data types tested and validated in this PoC:")
    confirmed_df = pd.DataFrame(CONFIRMED_DATA_TYPES)
    st.dataframe(
        confirmed_df.rename(columns={
            "data_type": "Data Type",
            "status": "Status",
            "operators_tested": "Operators Tested",
            "fields": "Extracted Fields",
        }),
        width="stretch",
        hide_index=True,
    )

    st.markdown("---")

    # Blueprint comparison across operators
    st.subheader("Cross-Format Normalization: Same Schema, Different Layouts")
    st.markdown("""
    The key differentiator: two operators produce completion reports with **different page layouts, 
    table structures, and field names** — but the blueprints extract the same structured output.
    """)

    try:
        comparison_df, coverage_df = compare_blueprints(
            os.path.join(os.path.dirname(__file__), "data", "blueprints")
        )

        st.markdown("**Coverage by data type:**")
        st.dataframe(coverage_df, width="stretch", hide_index=True)

        with st.expander("Detailed field comparison across blueprints"):
            st.dataframe(comparison_df, width="stretch", hide_index=True)
    except Exception as e:
        st.warning(f"Could not analyze blueprints: {e}")

    st.markdown("---")

    # Extraction instructions — the real differentiator
    st.subheader("Targeted Extraction Instructions")
    st.markdown("""
    **This is what makes blueprints special.** Each field has an instruction telling BDA 
    exactly WHERE to find the data on the page — not just "extract all text."
    """)

    st.markdown("**Generic OCR approach:**")
    st.code("→ Extract all text from all pages → hope you can parse it downstream", language="text")

    st.markdown("**BDA Blueprint approach:**")
    st.code('→ "Extract the proppant volume pumped from the stimulation table\n   only on the wellbore diagram page"', language="text")

    try:
        instructions_df = get_extraction_instructions_summary(
            os.path.join(os.path.dirname(__file__), "data", "blueprints")
        )
        with st.expander("All extraction instructions (from blueprints)", expanded=True):
            st.dataframe(
                instructions_df[["blueprint", "field", "instruction"]],
                width="stretch",
                hide_index=True,
            )
    except Exception as e:
        st.warning(f"Could not load instructions: {e}")

    st.markdown("---")

    # Why each data type is special
    st.subheader("Why Domain-Specific Extraction Matters")
    for dtype, info in INDUSTRY_DATA_TYPES.items():
        with st.expander(f"**{info['description']}**"):
            st.markdown(f"**Fields**: {', '.join(info['examples'])}")
            st.markdown(f"**Why blueprints matter**: {info['why_special']}")
