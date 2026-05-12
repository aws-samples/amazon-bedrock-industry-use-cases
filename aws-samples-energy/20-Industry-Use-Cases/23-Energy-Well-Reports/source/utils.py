import json
import os
from pathlib import Path

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from source.logger import get_logger

logger = get_logger(__name__)


def get_aws_account_id(session=None) -> str:
    """Lazy load AWS account ID"""
    try:
        if session is None:
            session = boto3.Session()
        return session.client("sts").get_caller_identity()["Account"]
    except ClientError as e:
        logger.critical(f"Failed to get AWS account ID: {e}")
        raise


def upload_data_to_s3(bucket_name, local_data_dir="data/reports", session=None):
    """Upload files from local directory to S3 bucket.

    Args:
        bucket_name: S3 bucket name
        data_dir: Local directory path
        session: boto3.Session object (optional, uses default if None)
    """
    if session is None:
        session = boto3.Session()

    s3 = session.client("s3")

    for file_path in Path(local_data_dir).iterdir():
        if file_path.is_file():
            s3.upload_file(
                str(file_path), bucket_name, os.path.join("reports", file_path.name)
            )
            logger.info(f"Uploaded {file_path.name}")


def list_s3_files(bucket, prefix, session=None):
    """List PDF files in S3 bucket with given prefix.

    Args:
        bucket: S3 bucket name
        prefix: S3 key prefix
        session: boto3.Session object (optional, uses default if None)

    Returns:
        List of PDF file keys
    """
    if session is None:
        session = boto3.Session()

    s3 = session.client("s3")
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    files = [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].endswith(".pdf")
    ]
    return files


def get_s3_to_dict(s3_url: str, session=None) -> dict:
    """Download and parse JSON file from S3.

    Args:
        s3_url: S3 URL in format 's3://bucket-name/path/to/file.json'
        session: boto3.Session object (optional, uses default if None)

    Returns:
        Parsed JSON content as dictionary
    """
    if session is None:
        session = boto3.Session()

    s3 = session.client("s3")

    bucket_name = s3_url.split("/")[2]
    object_key = "/".join(s3_url.split("/")[3:])

    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    json_content = response["Body"].read().decode("utf-8")

    return json.loads(json_content)


def get_dataframe(data: dict, field: str) -> pd.DataFrame:
    """Extract field from inference result and convert to DataFrame.

    Args:
        data: Dictionary containing inference results
        field: Field name to extract from inference_result

    Returns:
        DataFrame containing the specified field data
    """
    return pd.DataFrame(data["inference_result"][field])


def get_custom_output_path(meta_data_path: str) -> str:
    """Extract custom output path from metadata JSON file.

    Args:
        meta_data_path: Path to metadata JSON file

    Returns:
        Custom output path from segment metadata
    """
    meta = pd.read_json(meta_data_path).loc[0]
    paths = [p["custom_output_path"] for p in meta["output_metadata"]["segment_metadata"]]
    return paths
