"""
Data Consolidation Module

Demonstrates the core value proposition: multiple operator report formats
normalized into a single unified, queryable schema using BDA custom blueprints.

This module:
1. Processes extraction results from multiple operators
2. Normalizes them into a unified DataFrame/schema
3. Stores consolidated data in a local SQLite database for querying
4. Provides query functions for cross-well analysis
"""

import json
import os
import sqlite3
from typing import Dict, List, Optional

import pandas as pd

from source.logger import get_logger
from source.utils import get_s3_to_dict

logger = get_logger(__name__)

# Unified schema that all operator formats normalize into
UNIFIED_SCHEMA = {
    "well_information": [
        "api_number",
        "well_name",
        "operator",
        "field",
        "county_parish",
        "state",
        "spud_date",
        "measured_depth",
        "product_type",
    ],
    "perforation_data": [
        "well_name",
        "api_number",
        "stage",
        "top_perf",
        "bottom_perf",
    ],
    "casing_summary": [
        "well_name",
        "api_number",
        "size",
        "weight",
        "depth",
    ],
    "completion_summary": [
        "well_name",
        "api_number",
        "stage",
        "proppant_volume",
        "water_volume",
        "stage_length",
    ],
}


def normalize_operator1_result(data: dict) -> dict:
    """
    Normalize Operator 1 extraction results to unified schema.

    Operator 1 reports include: Well_Information, Perforation_Data,
    Completion_Summary (with Stage_Length, Proppant_Volume), Casing_Summary,
    Water_Sources.
    """
    inference = data.get("inference_result", data)
    well_info = inference.get("Well_Information", {})

    normalized = {
        "well_information": {
            "api_number": well_info.get("API_Number", ""),
            "well_name": well_info.get("Well_Name", ""),
            "operator": well_info.get("Operator", ""),
            "field": well_info.get("Field", ""),
            "county_parish": well_info.get("County_Parish", ""),
            "state": well_info.get("State", ""),
            "spud_date": well_info.get("Spud_Date", ""),
            "measured_depth": well_info.get("Measured_Depth", ""),
            "product_type": well_info.get("Product_Type", ""),
        },
        "perforation_data": [],
        "casing_summary": [],
        "completion_summary": [],
    }

    # Normalize perforations
    for i, perf in enumerate(inference.get("Perforation_Data", [])):
        normalized["perforation_data"].append({
            "well_name": well_info.get("Well_Name", ""),
            "api_number": well_info.get("API_Number", ""),
            "stage": i + 1,
            "top_perf": perf.get("Top_Perf"),
            "bottom_perf": perf.get("Bottom_Perf"),
        })

    # Normalize casing
    for casing in inference.get("Casing_Summary", []):
        normalized["casing_summary"].append({
            "well_name": well_info.get("Well_Name", ""),
            "api_number": well_info.get("API_Number", ""),
            "size": casing.get("Size", ""),
            "weight": casing.get("Weight"),
            "depth": casing.get("Depth"),
        })

    # Normalize completion - Operator 1 has Stage_Length and Proppant_Volume
    for i, comp in enumerate(inference.get("Completion_Summary", [])):
        normalized["completion_summary"].append({
            "well_name": well_info.get("Well_Name", ""),
            "api_number": well_info.get("API_Number", ""),
            "stage": i + 1,
            "proppant_volume": comp.get("Proppant_Volume"),
            "water_volume": None,  # Operator 1 tracks water in Water_Sources
            "stage_length": comp.get("Stage_Length"),
        })

    return normalized


def normalize_operator2_result(data: dict) -> dict:
    """
    Normalize Operator 2 extraction results to unified schema.

    Operator 2 reports include: Well_Information, Perforation_Data (Top Perf/Bottom Perf),
    Completion_Summary (with Water, Proppant_Volume), Casing_Summary.
    Note: Operator 2 uses different field names (spaces vs underscores).
    """
    inference = data.get("inference_result", data)
    well_info = inference.get("Well_Information", {})

    normalized = {
        "well_information": {
            "api_number": well_info.get("API_Number", ""),
            "well_name": well_info.get("Well_Name", ""),
            "operator": well_info.get("Operator", ""),
            "field": well_info.get("Field", ""),
            "county_parish": well_info.get("County_Parish", ""),
            "state": well_info.get("State", ""),
            "spud_date": well_info.get("Spud_Date", ""),
            "measured_depth": well_info.get("Measured_Depth", ""),
            "product_type": well_info.get("Product_Type", ""),
        },
        "perforation_data": [],
        "casing_summary": [],
        "completion_summary": [],
    }

    # Normalize perforations - Operator 2 uses "Top Perf" / "Bottom Perf" (with spaces)
    for i, perf in enumerate(inference.get("Perforation_Data", [])):
        normalized["perforation_data"].append({
            "well_name": well_info.get("Well_Name", ""),
            "api_number": well_info.get("API_Number", ""),
            "stage": i + 1,
            "top_perf": perf.get("Top Perf", perf.get("Top_Perf")),
            "bottom_perf": perf.get("Bottom Perf", perf.get("Bottom_Perf")),
        })

    # Normalize casing
    for casing in inference.get("Casing_Summary", []):
        normalized["casing_summary"].append({
            "well_name": well_info.get("Well_Name", ""),
            "api_number": well_info.get("API_Number", ""),
            "size": casing.get("Size", ""),
            "weight": casing.get("Weight"),
            "depth": casing.get("Depth"),
        })

    # Normalize completion - Operator 2 has Water and Proppant_Volume
    for i, comp in enumerate(inference.get("Completion_Summary", [])):
        normalized["completion_summary"].append({
            "well_name": well_info.get("Well_Name", ""),
            "api_number": well_info.get("API_Number", ""),
            "stage": i + 1,
            "proppant_volume": comp.get("Proppant_Volume"),
            "water_volume": comp.get("Water"),
            "stage_length": None,  # Operator 2 doesn't report stage length
        })

    return normalized


def consolidate_results(
    results: List[dict],
) -> dict:
    """
    Consolidate multiple extraction results into unified DataFrames.

    Auto-detects operator format based on field names in the extraction output.

    Args:
        results: List of BDA custom output dictionaries

    Returns:
        Dictionary with unified DataFrames:
        {
            "well_information": pd.DataFrame,
            "perforation_data": pd.DataFrame,
            "casing_summary": pd.DataFrame,
            "completion_summary": pd.DataFrame,
        }
    """
    all_wells = []
    all_perfs = []
    all_casings = []
    all_completions = []

    for result in results:
        # Auto-detect operator format based on field names
        inference = result.get("inference_result", result)
        completion = inference.get("Completion_Summary", [])

        if completion and len(completion) > 0 and "Stage_Length" in completion[0]:
            normalized = normalize_operator1_result(result)
        elif completion and len(completion) > 0 and "Water" in completion[0]:
            normalized = normalize_operator2_result(result)
        else:
            # Default to operator1 format
            normalized = normalize_operator1_result(result)

        all_wells.append(normalized["well_information"])
        all_perfs.extend(normalized["perforation_data"])
        all_casings.extend(normalized["casing_summary"])
        all_completions.extend(normalized["completion_summary"])

    return {
        "well_information": pd.DataFrame(all_wells),
        "perforation_data": pd.DataFrame(all_perfs) if all_perfs else pd.DataFrame(columns=UNIFIED_SCHEMA["perforation_data"]),
        "casing_summary": pd.DataFrame(all_casings) if all_casings else pd.DataFrame(columns=UNIFIED_SCHEMA["casing_summary"]),
        "completion_summary": pd.DataFrame(all_completions) if all_completions else pd.DataFrame(columns=UNIFIED_SCHEMA["completion_summary"]),
    }


def save_to_database(
    consolidated: dict,
    db_path: str = "well_data.db",
) -> str:
    """
    Save consolidated data to a SQLite database for querying.

    Args:
        consolidated: Dictionary of DataFrames from consolidate_results()
        db_path: Path to SQLite database file

    Returns:
        Path to the created database
    """
    conn = sqlite3.connect(db_path)

    try:
        for table_name, df in consolidated.items():
            if not df.empty:
                df.to_sql(table_name, conn, if_exists="replace", index=False)
                logger.info(f"Saved {len(df)} rows to table '{table_name}'")

        logger.info(f"Database saved to: {db_path}")
        return db_path
    finally:
        conn.close()


def query_wells(db_path: str = "well_data.db", query: str = None, params: list = None) -> pd.DataFrame:
    """
    Query the consolidated well database using predefined safe queries.

    Args:
        db_path: Path to SQLite database
        query: SQL query key from EXAMPLE_QUERIES, or a validated query string
               from the safe query builder. Must be a SELECT statement.
        params: Optional list of parameter values for parameterized queries.

    Returns:
        Query results as DataFrame
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)

    try:
        if query is None:
            query = "SELECT * FROM well_information"

        # Validate that query is read-only (SELECT statements only)
        query_stripped = query.strip()
        query_upper = query_stripped.upper()
        if not query_upper.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed for security reasons")

        # Block destructive keywords even within SELECT (subqueries, CTEs)
        blocked_keywords = {"DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
                            "TRUNCATE", "REPLACE", "ATTACH", "DETACH", "PRAGMA",
                            "VACUUM", "REINDEX"}
        import re
        query_words = set(re.findall(r"\b[A-Z]+\b", query_upper))
        found_blocked = query_words & blocked_keywords
        if found_blocked:
            raise ValueError(f"Blocked keywords found: {', '.join(found_blocked)}. Only SELECT queries are allowed.")

        # Block multiple statements
        if ";" in query_stripped.rstrip(";").rstrip():
            raise ValueError("Multiple statements are not allowed.")

        # Use parameterized query if params provided
        if params:
            result = pd.read_sql_query(query, conn, params=params)
        else:
            result = pd.read_sql_query(query, conn)
        return result
    finally:
        conn.close()


# --- Example queries for cross-well analysis ---

EXAMPLE_QUERIES = {
    "All wells": "SELECT * FROM well_information",
    "Wells by operator": "SELECT operator, COUNT(*) as well_count FROM well_information GROUP BY operator",
    "Wells by state": "SELECT state, COUNT(*) as well_count FROM well_information GROUP BY state",
    "Perforation summary": """
        SELECT well_name, COUNT(*) as stages, 
               MIN(top_perf) as shallowest_perf,
               MAX(bottom_perf) as deepest_perf
        FROM perforation_data 
        GROUP BY well_name
    """,
    "Total proppant by well": """
        SELECT well_name, SUM(proppant_volume) as total_proppant
        FROM completion_summary 
        GROUP BY well_name
        ORDER BY total_proppant DESC
    """,
    "Casing programs": """
        SELECT well_name, size, weight, depth
        FROM casing_summary
        ORDER BY well_name, depth
    """,
}
