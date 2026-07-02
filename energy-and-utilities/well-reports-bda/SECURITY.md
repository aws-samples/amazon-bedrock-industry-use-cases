# Security

## Disclaimer

This project is **sample/educational code** provided as a proof of concept for document extraction using Amazon Bedrock Data Automation. It is **not production-ready** and should not be deployed in production environments without proper security hardening.

## Reporting Vulnerabilities

If you discover a potential security issue in this project, please report it to [aws-security@amazon.com](mailto:aws-security@amazon.com). **Do not** create public GitHub issues for security vulnerabilities.

## AWS Services Used

| Service | Purpose |
|---|---|
| **Amazon Bedrock Data Automation** | Extracts structured data from well report PDFs using custom blueprints |
| **Amazon S3** | Stores input documents (well reports) and BDA extraction output (JSON) |
| **AWS STS** | Verifies caller identity and account information |

## Prerequisites & Permissions

The following IAM permissions are required for the execution role:

### Bedrock Data Automation

```json
{
    "Effect": "Allow",
    "Action": [
        "bedrock:CreateDataAutomationProject",
        "bedrock:UpdateDataAutomationProject",
        "bedrock:GetDataAutomationProject",
        "bedrock:ListDataAutomationProjects",
        "bedrock:InvokeDataAutomationAsync",
        "bedrock:GetDataAutomationStatus",
        "bedrock:CreateBlueprint",
        "bedrock:GetBlueprint",
        "bedrock:ListBlueprints",
        "bedrock:UpdateBlueprint",
        "bedrock:DeleteBlueprint"
    ],
    "Resource": "arn:aws:bedrock:*:ACCOUNT_ID:*"
}
```

### Amazon S3

```json
{
    "Effect": "Allow",
    "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
    ],
    "Resource": [
        "arn:aws:s3:::YOUR_BUCKET_NAME",
        "arn:aws:s3:::YOUR_BUCKET_NAME/*"
    ]
}
```

### AWS STS

```json
{
    "Effect": "Allow",
    "Action": "sts:GetCallerIdentity",
    "Resource": "*"
}
```

## Known Security Considerations

The following items have been reviewed and accepted as security debt for this proof-of-concept:

### SD-1: SQL f-string interpolation with whitelist validation (app.py:807-811)

**Severity**: Medium

The query builder in `app.py` constructs SQL queries using f-string interpolation for table and column names. This pattern is safe in context because:

1. Table names come from a `st.selectbox` with hardcoded options (cannot be user-modified)
2. Table names are explicitly validated against a `valid_tables` whitelist before interpolation
3. Column names are validated against `UNIFIED_SCHEMA` (the known schema definition) before use
4. Filter values use parameterized queries (`?` placeholders)

**Risk**: Low in this context, but the pattern could be copied unsafely by customers. For production use, replace with an ORM or pre-built query templates.

### SD-2: Bare `except Exception: pass` in display logic (app.py:557, 676)

**Severity**: Low

Two locations use bare exception handling when collecting custom outputs for the insights and consolidation display tabs. These are non-critical display paths where:

- Failure only affects optional UI sections (insights/consolidation)
- No security-sensitive operations occur in these blocks
- The pattern prevents the entire UI from crashing due to one malformed result

**Risk**: May hide issues during debugging but has no security impact. Acceptable for PoC.

### SD-3: Hardcoded `us-east-1` region in bda.py

**Severity**: Low

The default region is hardcoded as `us-east-1` in the BDA utility module. The Streamlit UI allows users to configure a different region via the sidebar. For production use, parameterize the region through environment variables or configuration files.

## Production Hardening Recommendations

If adapting this code for production use, implement the following:

### IAM Permissions

- **Scope permissions** from `bedrock:*` to only the specific BDA actions listed above
- Use **resource-level ARNs** (not wildcards) for Bedrock projects and blueprints
- Apply the **principle of least privilege** for S3 bucket access

### S3 Bucket Security

- Enable **SSE-KMS encryption** (server-side encryption with AWS KMS keys)
- Enable **S3 Block Public Access** on the bucket
- Enforce **TLS-only** access via bucket policy condition `aws:SecureTransport`
- Enable **S3 access logging** for audit trails
- Configure **lifecycle policies** to expire processing output after retention period

### Application Security

- **Replace SQL f-string interpolation** with an ORM (e.g., SQLAlchemy) or pre-built query templates
- **Parameterize the AWS region** via environment variables (`AWS_DEFAULT_REGION`)
- **Add authentication** if deploying the Streamlit app publicly (e.g., Streamlit authentication, Cognito, or a reverse proxy)
- **Add input length limits** for filter values in the query builder
- **Add rate limiting** for query execution to prevent resource exhaustion
- **Replace bare except blocks** with specific exception handling and logging

### Dependency Management

- All dependencies are pinned to exact versions in `requirements.txt`
- Regularly update dependencies and audit for new CVEs
- Use `pip audit` or equivalent tooling in CI/CD pipelines

## Dependency Status

| Package | Version | Notes |
|---|---|---|
| boto3 | 1.38.27 | AWS SDK |
| pandas | 2.3.1 | Data manipulation |
| streamlit | 1.58.0 | Web UI framework |

### Resolved Vulnerabilities

| CVE | Package | Fixed In | Description |
|---|---|---|---|
| CVE-2026-33682 | streamlit | 1.54.0 | Windows-only SSRF via improper filesystem path validation. Updated from 1.45.0 to 1.54.0. |
