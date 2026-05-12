# Energy Well Reports Processing with Amazon Bedrock Data Automation

This project demonstrates how to leverage Amazon Bedrock Data Automation to extract insights from energy well reports and operational documents. The solution provides a comprehensive walkthrough notebook and utility functions to help jumpstart processing various document types commonly found in the energy sector.

## Overview

The energy industry generates large volumes of unstructured documents such as well permits, petrophysical logs, directional surveys, bit reports, frack data, and regulatory filings. This project shows how to use Amazon Bedrock Data Automation to automate extracting key insights from technical documentation. 

## Project Structure

```
23-Energy-Well-Reports/
├── 23-Energy_Well_Reports.ipynb          # Interactive walkthrough notebook
├── data/                                 # Sample data and configurations
│   ├── blueprints/                       # Custom extraction blueprints
│   │   ├── operator1_engineering_blueprint.json
│   │   └── operator2_engineering_blueprint.json
│   └── reports/                          # Sample well reports (PDF)
│       ├── operator1_report.pdf
│       └── operator2_report.pdf
├── source/                               # Helper utility functions
│   ├── bda.py                            # Bedrock Data Automation utilities
│   ├── logger.py                         # Logging configuration
│   └── utils.py                          # AWS and data processing utilities
└── README.md                           
```

## Key Features

### Utility Functions

The `source/utils.py` module provides essential functions for:

- **AWS Integration**: Get account ID and manage AWS sessions
- **S3 Operations**: Upload documents, list files, and download results
- **Data Processing**: Convert inference results to DataFrames
- **Custom Output Handling**: Extract and process custom blueprint outputs

### Sample Documents

The project includes sample well reports from different operators to demonstrate:
- Processing documents with varying formats and structures
- Creating operator-specific extraction blueprints
- Handling multimodal content (text, tables, diagrams)

## Security

Before running this project, review **[SECURITY.md](SECURITY.md)** for guidance on:
- Configuring least-privilege **IAM policies** for Bedrock, S3, and STS.
- Securing the **S3 bucket** used for document storage and processing output (encryption, public-access blocking, TLS-only policies).

This code does **not** create IAM policies or S3 buckets — that is the user's responsibility.

## Changes and Fixes

The following issues were identified via manual review (ASH summary) and automated scanning (Holmes Content Security Review) and have been resolved:

### Code Fixes (source/bda.py)

| Issue | Severity | Fix |
|---|---|---|
| Infinite polling loop with no timeout | High | Added `max_wait_seconds` (default 600s) and `poll_interval` (default 10s) parameters. Raises `TimeoutError` when the limit is exceeded. |
| No handling of failed/error job status | High | Added check for terminal failure states (`ServiceError`, `ClientError`). Raises `RuntimeError` immediately on failure. |
| `create_custom_blueprint` swallows errors | Medium | `ClientError` is now re-raised after logging. `ConflictException` is handled gracefully by looking up the existing blueprint ARN. |
| `create_bda_project` ignores session parameter | Medium | Fixed to use `session.client()` instead of `boto3.client()` directly. |
| `open()` missing explicit encoding | Low | Added `encoding="utf-8"` to file open call. |
| Unnecessary `else` after `return` in `search_bda_project` | Low | Removed redundant `else` block. |

### Documentation Additions

| Issue | Fix |
|---|---|
| No IAM policy guidance (Issue 4) | Created `SECURITY.md` with minimum required IAM permissions table and best practices. |
| No S3 bucket security guidance (Issue 5) | Added S3 hardening section to `SECURITY.md` (encryption, public-access blocking, TLS-only bucket policy, versioning, lifecycle rules). |
| Prerequisites lack setup links (Holmes Finding 4) | Added links to Bedrock Getting Started guide and BDA IAM role documentation in notebook. |
| SONRIS reference unexplained (Holmes Finding 5) | Expanded SONRIS description with full context and fixed broken link. |
| Emojis as section markers (Holmes Finding 6) | Removed emojis from notebook section headers for screen-reader accessibility. |

### Holmes Scan Findings Triage

| Finding | Severity | File | Verdict |
|---|---|---|---|
| HTTP `$schema` URL in blueprints (Findings 1-2) | Medium | Blueprint JSONs | **False positive** — `$schema` is a JSON Schema identifier, not a fetched URL. The BDA API validates this exact string and rejects HTTPS. |
| `square-access-token` detected (Finding 3) | Low | Notebook | **False positive** — flagged string is a Jupyter auto-generated cell UUID, not a credential. |
| Prerequisites lack guidance (Finding 4) | Low | Notebook | **True positive** — fixed with documentation links. |
| SONRIS unexplained (Finding 5) | Low | Notebook | **True positive** — fixed with expanded description. |
| Emoji accessibility (Finding 6) | Low | Notebook | **True positive** — fixed by removing emojis from headers. |

## Getting Started

1. **Prerequisites**:
   - AWS account with Bedrock Data Automation access
   - Python environment with required dependencies
   - S3 bucket for document storage and processing (see [SECURITY.md](SECURITY.md))

2. **Setup**:
   - Clone this repository
   - Configure AWS credentials
   - Install required Python packages 
      - boto3>=1.38.27 
      - pandas>=2.3.1
      - s3fs==2025.5.1

3. **Run the Notebook**:
   - Open `23-Energy_Well_Reports.ipynb`
   - Follow the step-by-step walkthrough
   - Experiment with the sample documents and blueprints

## Contributors
   - Trace Smith
   - Pavan Pusuluri
   - Avneet Bansal
   - Jin Fei
   - Sachin Khanna
   - Colin Sturm

