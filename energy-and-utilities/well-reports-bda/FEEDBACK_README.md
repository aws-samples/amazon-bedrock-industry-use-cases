# Oil & Gas Well Report Data Extraction with Amazon Bedrock Data Automation

## The Problem: Fragmented Legacy Well Data

Oil and gas operators accumulate decades of well documentation — permits, completion reports, petrophysical logs, directional surveys, frac reports, and regulatory filings. This data lives in:

- Scanned paper records and PDFs with inconsistent layouts
- Operator-specific formats (each company structures reports differently)
- Mixed-content documents combining text, tables, wellbore diagrams, and engineering schematics
- Legacy systems like Wellview, OpenWells, and state databases (e.g., Louisiana SONRIS)

The result: critical engineering data is locked in unstructured documents, making cross-well analysis, regulatory compliance, and asset evaluation manual and error-prone.

## What This Project Does

This proof of concept demonstrates using **Amazon Bedrock Data Automation (BDA)** to extract **structured data** from heterogeneous well reports and normalize it into a unified, queryable format.

Specifically, BDA processes PDF well reports and returns structured fields including:

| Data Category | Extracted Fields |
|---|---|
| Well Identification | API number, well name, operator, field, county/parish, state, spud date, measured depth, product type |
| Perforation Data | Top/bottom perforation depths per stage |
| Completion Summary | Stage lengths, proppant volumes, water volumes |
| Casing Records | Casing size, weight, depth |
| Water Sources | Source name, supply type, volume used, location coordinates |

The output is structured JSON that can be loaded directly into DataFrames, databases, or analytics pipelines.

## Why BDA — Not Just OCR or Text Extraction

Standard text extraction (Textract, Tesseract, etc.) gives you raw text. BDA provides **domain-aware structured extraction** through custom blueprints:

| Capability | Generic OCR/Extraction | BDA with Custom Blueprints |
|---|---|---|
| Raw text from PDFs | ✓ | ✓ |
| Table detection | Partial | ✓ (structure-aware) |
| Domain-specific field mapping | ✗ | ✓ (blueprint-defined) |
| Cross-format normalization | ✗ | ✓ (same schema, different layouts) |
| Mixed content (diagrams + tables + text) | ✗ | ✓ |
| Operator-specific extraction logic | ✗ | ✓ (per-operator blueprints) |

### Custom Blueprints Are the Differentiator

This project includes two operator-specific blueprints (`operator1_engineering_blueprint.json` and `operator2_engineering_blueprint.json`) that demonstrate:

1. **Same output schema, different source layouts** — Both operators produce completion reports, but with different page structures, table formats, and terminology. The blueprints handle this variation while producing a normalized output.

2. **Targeted extraction instructions** — Each field includes explicit instructions telling BDA where to find data (e.g., "Extract the proppant volume pumped from the stimulation table only on the wellbore diagram page").

3. **Industry-specific data types** — The blueprints understand oil & gas concepts: perforation intervals, frac stages, casing strings, API numbers, and water source tracking for regulatory compliance.

## Project Structure

```
well-reports-bda/
├── app.py                                    # Streamlit UI application
├── requirements.txt                          # Python dependencies
├── 23-Energy_Well_Reports.ipynb              # Interactive walkthrough notebook
├── data/
│   ├── blueprints/                           # Custom extraction blueprints
│   │   ├── operator1_engineering_blueprint.json
│   │   └── operator2_engineering_blueprint.json
│   └── reports/                              # Sample well reports (PDF)
│       ├── operator1_report.pdf
│       └── operator2_report.pdf
├── source/                                   # Helper utility functions
│   ├── bda.py                                # BDA API wrapper (create blueprints, projects, run jobs)
│   ├── logger.py                             # Logging configuration
│   └── utils.py                              # AWS and data processing utilities
└── README.md
```

## Scale Considerations

### What Has Been Tested

- Individual well completion reports (typically 10–50 pages per document)
- Two distinct operator report formats with different layouts
- Extraction of structured fields from mixed-content pages (text + tables + diagrams)

### BDA Service Limits

| Parameter | Limit |
|---|---|
| Maximum file size | 500 MB per document |
| Maximum pages | 3,000 pages per document |
| Supported formats | PDF, images (JPEG, PNG, TIFF) |
| Concurrent jobs | Account-level quotas apply (check AWS Service Quotas) |
| Processing timeout | Configurable; default 600s in this project |

### Production Considerations

- **Batch processing**: For large-scale digitization (thousands of well files), implement job queuing with SQS or Step Functions. The `start_processing_job` function supports async invocation for this purpose.
- **Large documents**: BDA supports documents up to 3,000 pages. For legacy well files that exceed this (e.g., bound field books), pre-split documents before processing.
- **Throughput**: Request quota increases via AWS Service Quotas for high-volume workloads. BDA processes documents asynchronously, so parallelism is achievable.
- **Cost**: BDA pricing is per-page. Budget accordingly for large-scale digitization projects.

> **Note**: This proof of concept has not been validated at production scale (>1,000 documents or >1,000 pages per document). Scale testing is recommended before production deployment.

## What's Next: Downstream Use Cases

Extracted structured data enables analytics that aren't possible with unstructured documents:

| Use Case | Description |
|---|---|
| **Cross-well comparison** | Compare completion designs, proppant loading, and water usage across wells in a field |
| **Regulatory compliance** | Automated verification of water source reporting, casing integrity records, and permit compliance |
| **Asset evaluation** | Rapid data room population for M&A due diligence — normalize decades of well files into queryable datasets |
| **Trend analysis** | Track changes in completion practices over time (stage counts, proppant volumes, lateral lengths) |
| **Anomaly detection** | Flag wells with unusual completion parameters or missing required data fields |
| **Type curve development** | Feed normalized completion and production data into decline curve analysis |

### Integration Patterns

```
Well Reports (PDF) → BDA Extraction → Structured JSON → 
    ├── Data Lake (S3 + Athena) for ad-hoc queries
    ├── Data Warehouse (Redshift) for cross-well analytics
    ├── Knowledge Base (Bedrock) for natural language Q&A
    └── Dashboard (QuickSight) for field-level KPIs
```

## Applicability Beyond Oil & Gas

While this demo focuses on oil & gas well reports, the pattern — **custom blueprints for domain-specific document extraction** — applies across energy and utilities:

| Sub-Vertical | Document Types | Extractable Data |
|---|---|---|
| **Solar** | Inspection reports, interconnection agreements | Panel degradation rates, inverter specs, grid capacity |
| **Wind** | Turbine maintenance logs, SCADA exports | Component failure history, downtime events, power curves |
| **Utilities** | Compliance filings, outage reports, rate cases | Reliability metrics, capital expenditure, customer impact |
| **Geothermal** | Well logs, reservoir assessments | Temperature gradients, flow rates, formation data |
| **Pipeline** | Integrity assessments, ILI reports | Anomaly locations, wall thickness, corrosion rates |

The key requirement is defining a blueprint schema that maps to your document structure.

## Getting Started

### Prerequisites

- AWS account with Amazon Bedrock Data Automation access enabled
- Python 3.9+ environment
- S3 bucket for document storage and processing output (see [SECURITY.md](SECURITY.md))

### Installation

```bash
pip install boto3>=1.38.27 pandas>=2.3.1 s3fs==2025.5.1 streamlit>=1.45.0
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

> **Note (macOS with Homebrew Python):** If you get an "externally-managed-environment" error, create a virtual environment first:
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate
> pip install -r requirements.txt
> ```

### Option A: Running the Streamlit UI (Recommended for Demos)

The project includes a Streamlit web application (`app.py`) that provides a visual interface for the entire extraction workflow — no Jupyter notebook required.

#### Prerequisites

1. **AWS credentials configured** on your machine:
   ```bash
   aws configure
   ```
   This sets up your Access Key ID, Secret Access Key, and default region.

2. **An existing S3 bucket** in your AWS account for document storage and output. BDA writes extraction results here.

3. **Amazon Bedrock Data Automation enabled** in your AWS region (default: `us-east-1`).

4. **IAM permissions** for your user/role:
   - `bedrock:*` (or scoped Bedrock Data Automation permissions)
   - `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on your bucket
   - `sts:GetCallerIdentity`

#### Running the UI

```bash
streamlit run app.py
```

This opens a browser at `http://localhost:8501` with four tabs:

| Tab | What It Does |
|---|---|
| **Upload Reports** | Drag-and-drop PDF well reports, uploads them to your S3 bucket |
| **Blueprints & Project** | Register custom extraction blueprints in BDA and create a processing project |
| **Run Extraction** | Select uploaded files, submit BDA extraction jobs, monitor progress |
| **View Results** | Display extracted structured data — summaries, tables, per-page content |

#### UI Workflow

1. **Sidebar** → Enter your AWS Region, Profile (optional), and S3 Bucket Name → Click **Connect to AWS**
2. **Upload Reports** tab → Upload PDF files (or verify existing files in S3)
3. **Blueprints & Project** tab → Click **Register Blueprints in BDA** → Click **Create / Find Project**
4. **Run Extraction** tab → Select files → Click **Start Extraction** (takes 1–3 minutes per file)
5. **View Results** tab → See extracted data: summary, description, full markdown content, per-page breakdown

#### How the UI Works (Technical Overview)

The app is a single Python file (`app.py`, ~250 lines) built with [Streamlit](https://streamlit.io). It wraps the existing `source/bda.py` and `source/utils.py` functions with a visual interface:

```
Browser ←→ Streamlit Server (app.py) ←→ AWS (Bedrock, S3, STS)
                    ↓
         source/bda.py (create blueprints, run jobs)
         source/utils.py (S3 uploads, downloads, data conversion)
```

- **No separate backend needed** — Streamlit runs Python server-side and renders the UI
- **State management** — Uses `st.session_state` to persist AWS session, project ARN, and results across interactions
- **Re-run model** — Streamlit re-executes the script on every user interaction; session state preserves data between reruns

### Option B: Running the Jupyter Notebook

1. Clone this repository
2. Configure AWS credentials (`aws configure` or environment variables)
3. Open `23-Energy_Well_Reports.ipynb`
4. Follow the step-by-step walkthrough to:
   - Create custom blueprints from the provided schemas
   - Set up a BDA project with those blueprints
   - Process sample well reports
   - View extracted structured data as DataFrames

## Security

Before running this project, review **[SECURITY.md](SECURITY.md)** for guidance on:
- Configuring least-privilege IAM policies for Bedrock, S3, and STS
- Securing the S3 bucket (encryption, public-access blocking, TLS-only policies)

This code does **not** create IAM policies or S3 buckets — that is the user's responsibility.

## Changes and Fixes

The following issues were identified via manual review and automated scanning and have been resolved:

### Code Fixes (source/bda.py)

| Issue | Severity | Fix |
|---|---|---|
| Infinite polling loop with no timeout | High | Added `max_wait_seconds` (default 600s) and `poll_interval` (default 10s) parameters. Raises `TimeoutError` when exceeded. |
| No handling of failed/error job status | High | Added check for terminal failure states (`ServiceError`, `ClientError`). Raises `RuntimeError` on failure. |
| `create_custom_blueprint` swallows errors | Medium | `ClientError` is now re-raised after logging. `ConflictException` handled gracefully. |
| `create_bda_project` ignores session parameter | Medium | Fixed to use `session.client()` instead of `boto3.client()`. |
| `open()` missing explicit encoding | Low | Added `encoding="utf-8"` to file open call. |
| Unnecessary `else` after `return` | Low | Removed redundant `else` block. |

### Documentation Additions

| Issue | Fix |
|---|---|
| No IAM policy guidance | Created `SECURITY.md` with minimum required IAM permissions. |
| No S3 bucket security guidance | Added S3 hardening section to `SECURITY.md`. |
| Prerequisites lack setup links | Added links to Bedrock Getting Started guide and BDA IAM role docs. |
| SONRIS reference unexplained | Expanded SONRIS description with full context. |
| Emojis as section markers | Removed emojis from notebook headers for accessibility. |

## Contributors

- [Pavan Pusuluri](https://www.linkedin.com/in/pavan-pusuluri-03871021)
- [Avneet Bansal](https://www.linkedin.com/in/avneet-bansal-4402231b)
- [Jin Fei](https://www.linkedin.com/in/jin-fei-64926a7)
- [Sachin Khanna](https://in.linkedin.com/in/sachinkhanna43)
- [Colin Sturm](https://www.linkedin.com/in/colinsturm)

---

## Reviewer Feedback and Solutions

**Feedback:** What are the 'insights' that are referred to in the line "to automate extracting key insights from these complex documents"? I can see an output table, and I assume a CSV of data points. But those aren't 'insights'. What would our customers do once they have this data extracted?

**Solution (Documentation):** Replaced all "insights" language with "structured data extraction" to accurately describe what BDA produces (structured fields, not insights). Added downstream use cases showing what customers do with extracted data: cross-well comparison, regulatory compliance automation, M&A due diligence, trend analysis, anomaly detection, and type curve development. Added an integration architecture showing data flowing into Athena, Redshift, Bedrock Knowledge Bases, and QuickSight.

**Solution (Code):** Added `source/insights.py` and an "Insights" tab in the Streamlit UI that shows what customers DO with extracted data — not raw tables, but actionable conclusions:

- `generate_well_insights()` — Derives 7 types of insights from consolidated data:
  ```
  Raw Data (tables/CSV)  →  Meaningful Insights (decisions)
  
  Proppant volumes       →  "Davis #3H is 45% below average — possible underperformer"
  Water usage            →  "Jones #2H exceeds permit limit — update regulatory filing"
  Perforation intervals  →  "2023 wells use tighter spacing (190ft vs 206ft) — track ROI"
  Casing programs        →  "1 well has unusual casing — verify regulatory compliance"
  Missing fields         →  "2 wells have gaps — pull original documents"
  ```
- `generate_demo_insights()` — Shows sample insights with demo data when no real well reports are loaded
- Each insight includes: description, supporting data table, and **recommended action**
- Insights grouped by category: Cost Optimization, Regulatory Compliance, Trends, Data Quality, Anomaly Detection
- **UI "Insights" tab** — Demonstrates the full value chain: Documents → Structured Data → Insights → Decisions

---

**Feedback:** O&G companies have many old well files (paper, scans) and well databases (Wellview, OpenWells, etc.), getting all of that data into one queryable/usable format and location is likely to be valuable to them.

**Solution (Documentation):** Added framing around the problem of fragmented well data across paper scans, operator-specific PDFs, and legacy systems (Wellview, OpenWells, state databases like SONRIS). Positioned BDA as the normalization layer that consolidates heterogeneous legacy formats into a single unified, queryable schema.

**Solution (Code):** Added `source/consolidate.py` and a "Consolidated Data" tab in the Streamlit UI that proves the claim:

- `normalize_operator1_result()` / `normalize_operator2_result()` — Maps different operator field names to one unified schema:
  ```
  Operator 1: "Top_Perf", "Stage_Length"   →  unified: "top_perf", "stage_length"
  Operator 2: "Top Perf" (space), "Water"  →  unified: "top_perf", "water_volume"
  ```
- `consolidate_results()` — Merges multiple operator results into unified DataFrames
- `save_to_database()` — Stores everything in one SQLite database (one queryable location)
- `query_wells()` + `EXAMPLE_QUERIES` — Run SQL across all wells regardless of source format
- **UI "Consolidated Data" tab** — Visually demonstrates the transformation with demo data and a live SQL query interface

---

**Feedback:** Has this been proven over large numbers of files, or large file sizes? What scale can this operate at? (i.e. we've seen issues handling large file sizes, >1000 pages, at some customers)

**Solution (Documentation):** Documented what has been tested (individual reports, 10–50 pages), BDA service limits (500 MB max file size, 3,000 pages max per document), and production patterns for scale (job queuing with SQS/Step Functions, async parallelism, quota increases). Added an honest note that >1,000 document scale has not been validated in this PoC and scale testing is recommended before production deployment.

**Solution (Code):** Added `source/batch_processor.py` and a "Batch Processing" tab in the Streamlit UI that proves the pipeline supports scale:

- `BatchProcessor` class — Processes multiple files in parallel using `ThreadPoolExecutor`:
  ```
  File Queue → ThreadPoolExecutor (N workers)
                    ├── Worker 1 → BDA Job → Poll → Result
                    ├── Worker 2 → BDA Job → Poll → Result
                    └── Worker N → BDA Job → Poll → Result
  ```
- `process_batch()` — Submits all files concurrently (configurable 1–20 simultaneous jobs)
- Exponential backoff on AWS throttling (`ThrottlingException` → wait 20s, 40s, 80s...)
- `max_retries` — Automatic retries per file (transient failures don't lose data)
- Timeout handling per file (large files don't block the entire batch)
- Failure isolation (one file failing doesn't stop the rest)
- `BatchMetrics` — Tracks throughput (files/min), avg duration, success/fail counts
- **UI "Batch Processing" tab** — Configurable sliders for concurrency/retries/timeouts, real-time progress bar, results table with per-file metrics, and architecture diagram showing production scale pattern (SQS + Step Functions)

---

**Feedback:** This example seems to show standard text extraction from PDFs/Images, etc. What is special about what this example does? I would think that highlighting that it correctly identifies types of industry data (i.e. perfs/stimulations) across different types of documents (has that been confirmed? Have other data types been tested?)

**Solution (Documentation):** Added a comparison table showing generic OCR vs BDA with custom blueprints. Highlighted that custom blueprints are the differentiator — they enable domain-aware extraction where the same output schema handles different operator document layouts.

**Solution (Code):** Added `source/blueprint_analyzer.py` and a "What's Special" tab in the Streamlit UI that proves the differentiation:

- `get_differentiator_summary()` — Generates comparison table (Generic OCR vs BDA Standard vs BDA + Blueprints):
  ```
  Generic OCR:        "Extract all text from all pages" → raw text
  BDA + Blueprints:   "Extract the proppant volume pumped from the stimulation 
                       table only on the wellbore diagram page" → structured field
  ```
- `compare_blueprints()` — Analyzes both operator blueprints side-by-side showing same schema, different extraction instructions
- `get_extraction_instructions_summary()` — Lists every targeted instruction proving BDA knows WHERE to look on each page
- `CONFIRMED_DATA_TYPES` — Documents which industry data types have been tested (perforations ✓, stimulations ✓, casing ✓, water sources ✓) and which are future work (directional surveys, production data, cement records)
- `INDUSTRY_DATA_TYPES` — Explains WHY each data type needs domain-aware extraction (e.g., "OCR sees '5 1/2'; blueprints know this is a casing diameter in inches")
- **UI "What's Special" tab** — Interactive comparison showing capability table, confirmed data types, cross-format coverage, and all extraction instructions from the blueprints

---

**Feedback:** This example is very specific to Oil & Gas (renewables and utilities don't have oil wells), so people may have trouble connecting it to their use cases.

**Solution (Documentation):** Renamed the title to explicitly scope to "Oil & Gas Well Report Data Extraction" so there's no confusion. Added a cross-sector applicability table mapping the blueprint-based extraction pattern to solar (inspection reports), wind (turbine maintenance logs), utilities (compliance filings), geothermal (well logs), and pipeline (ILI/integrity reports).

**Solution (Code):** Added sample blueprints for other energy sub-verticals proving the pattern is reusable:

- `data/blueprints/solar_inspection_blueprint.json` — Extracts from solar panel inspection reports:
  ```
  Site_Information:    Site_Name, Site_ID, Location, System_Capacity_kW
  Panel_Conditions:    Panel_ID, Degradation_Percent, Defect_Type, Severity
  Inverter_Status:     Inverter_ID, Efficiency_Percent, Error_Codes
  Performance_Metrics: Actual_Output_kWh, Expected_Output_kWh, Performance_Ratio
  ```
- `data/blueprints/wind_turbine_maintenance_blueprint.json` — Extracts from wind turbine maintenance logs:
  ```
  Turbine_Information: Turbine_ID, Wind_Farm, Manufacturer, Rated_Capacity_MW
  Maintenance_Events:  Event_Date, Event_Type, Component, Downtime_Hours
  Performance_Data:    Availability_Percent, Capacity_Factor, Energy_Produced_MWh
  ```
- Same code works for all blueprints — `create_custom_blueprint()`, `create_bda_project()`, `start_processing_job()`, and `consolidate_results()` are blueprint-agnostic
- **UI "What's Special" tab** — The blueprint analyzer automatically picks up all blueprints in the folder, showing cross-sector coverage



