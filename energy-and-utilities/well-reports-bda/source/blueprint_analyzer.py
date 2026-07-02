"""
Blueprint Analyzer Module

Demonstrates what makes BDA custom blueprints different from standard text extraction:
1. Domain-specific field definitions (not generic OCR)
2. Targeted extraction instructions (tells BDA WHERE to look on the page)
3. Cross-format normalization (same schema handles different operator layouts)
4. Industry data type coverage analysis

This module analyzes blueprint schemas to show:
- What industry-specific data types are defined
- How extraction instructions differ from generic text extraction
- Which fields have been tested across operator formats
- Coverage gaps and potential additions
"""

import json
import os
from typing import Dict, List, Tuple

import pandas as pd

from source.logger import get_logger

logger = get_logger(__name__)


# Industry data types that BDA blueprints can identify
# (vs generic OCR which just returns raw text)
INDUSTRY_DATA_TYPES = {
    "well_identification": {
        "description": "Well header information (API, name, operator, location)",
        "examples": ["API_Number", "Well_Name", "Operator", "Field", "County_Parish"],
        "why_special": "OCR gives you text; blueprints know that '17-033-12345' is an API number, not a phone number",
    },
    "perforation_data": {
        "description": "Perforation intervals per frac stage",
        "examples": ["Top_Perf", "Bottom_Perf", "stage number"],
        "why_special": "OCR sees numbers in a table; blueprints understand these are depth measurements defining where the well was perforated",
    },
    "completion_summary": {
        "description": "Hydraulic fracturing job parameters per stage",
        "examples": ["Proppant_Volume", "Water", "Stage_Length"],
        "why_special": "OCR extracts table cells; blueprints know that 'K#' means thousands of pounds of proppant and which page/table to find it on",
    },
    "casing_data": {
        "description": "Casing string specifications",
        "examples": ["Size", "Weight", "Depth"],
        "why_special": "OCR sees '5 1/2'; blueprints know this is a casing diameter in inches from the casing record section",
    },
    "water_sources": {
        "description": "Water supply tracking for regulatory compliance",
        "examples": ["Source_Name", "Supply_Type", "Volume_Used", "Source_Location"],
        "why_special": "OCR can't distinguish water source data from other tables; blueprints target the specific 'Hydraulic Fracture Stimulation' section",
    },
}


def load_blueprint(blueprint_name: str, blueprint_dir: str = "data/blueprints") -> dict:
    """Load a blueprint JSON file."""
    path = os.path.join(blueprint_dir, f"{blueprint_name}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_fields_from_blueprint(blueprint: dict) -> List[Dict]:
    """
    Extract all field definitions from a blueprint schema.

    Returns list of dicts with: field_name, data_type, instruction, parent_section
    """
    fields = []

    definitions = blueprint.get("definitions", {})
    for section_name, section_def in definitions.items():
        properties = section_def.get("properties", {})
        for field_name, field_def in properties.items():
            fields.append({
                "section": section_name,
                "field_name": field_name,
                "data_type": field_def.get("type", "unknown"),
                "inference_type": field_def.get("inferenceType", "unknown"),
                "instruction": field_def.get("instruction", ""),
            })

    return fields


def compare_blueprints(
    blueprint_dir: str = "data/blueprints",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compare all blueprints to show cross-format normalization.

    Returns:
        - comparison_df: Side-by-side field comparison across operators
        - coverage_df: Which data types each blueprint covers
    """
    blueprint_files = [
        f.replace(".json", "")
        for f in os.listdir(blueprint_dir)
        if f.endswith(".json")
    ]

    all_fields = {}
    for bp_name in blueprint_files:
        blueprint = load_blueprint(bp_name, blueprint_dir)
        fields = extract_fields_from_blueprint(blueprint)
        all_fields[bp_name] = fields

    # Build comparison table
    comparison_rows = []
    for bp_name, fields in all_fields.items():
        for field in fields:
            comparison_rows.append({
                "blueprint": bp_name,
                "section": field["section"],
                "field": field["field_name"],
                "type": field["data_type"],
                "instruction": field["instruction"][:100] + "..." if len(field["instruction"]) > 100 else field["instruction"],
            })

    comparison_df = pd.DataFrame(comparison_rows)

    # Build coverage table
    sections_per_blueprint = {}
    for bp_name, fields in all_fields.items():
        sections = set(f["section"] for f in fields)
        sections_per_blueprint[bp_name] = sections

    all_sections = set()
    for sections in sections_per_blueprint.values():
        all_sections.update(sections)

    coverage_rows = []
    for section in sorted(all_sections):
        row = {"data_type": section}
        for bp_name in blueprint_files:
            row[bp_name] = "✓" if section in sections_per_blueprint.get(bp_name, set()) else "✗"
        coverage_rows.append(row)

    coverage_df = pd.DataFrame(coverage_rows)

    return comparison_df, coverage_df


def get_extraction_instructions_summary(blueprint_dir: str = "data/blueprints") -> pd.DataFrame:
    """
    Show all extraction instructions — this is what makes blueprints special.

    Generic OCR: "extract all text from the page"
    BDA Blueprint: "Extract the proppant volume pumped from the stimulation table
                    only on the wellbore diagram page"

    The instructions tell BDA WHERE to look and WHAT to interpret.
    """
    blueprint_files = [
        f.replace(".json", "")
        for f in os.listdir(blueprint_dir)
        if f.endswith(".json")
    ]

    rows = []
    for bp_name in blueprint_files:
        blueprint = load_blueprint(bp_name, blueprint_dir)
        fields = extract_fields_from_blueprint(blueprint)
        for field in fields:
            if field["instruction"]:
                rows.append({
                    "blueprint": bp_name,
                    "field": f"{field['section']}.{field['field_name']}",
                    "instruction": field["instruction"],
                    "what_ocr_would_give": "Raw text/numbers without context",
                    "what_bda_gives": f"Structured {field['data_type']} value from specific document location",
                })

    return pd.DataFrame(rows)


def get_differentiator_summary() -> pd.DataFrame:
    """
    Summary table: Generic OCR vs BDA with Custom Blueprints.
    Shows why this isn't just 'standard text extraction'.
    """
    rows = [
        {
            "capability": "Extract raw text from PDF",
            "generic_ocr": "✓",
            "bda_standard": "✓",
            "bda_custom_blueprint": "✓",
        },
        {
            "capability": "Detect tables",
            "generic_ocr": "Partial (layout-based)",
            "bda_standard": "✓ (structure-aware)",
            "bda_custom_blueprint": "✓ (structure-aware)",
        },
        {
            "capability": "Identify document type",
            "generic_ocr": "✗",
            "bda_standard": "✓ (auto-classification)",
            "bda_custom_blueprint": "✓ (blueprint matching)",
        },
        {
            "capability": "Extract specific named fields",
            "generic_ocr": "✗",
            "bda_standard": "✗",
            "bda_custom_blueprint": "✓ (schema-defined)",
        },
        {
            "capability": "Target specific page/section",
            "generic_ocr": "✗",
            "bda_standard": "✗",
            "bda_custom_blueprint": "✓ (instruction-guided)",
        },
        {
            "capability": "Handle mixed content (diagrams + tables)",
            "generic_ocr": "✗",
            "bda_standard": "✓",
            "bda_custom_blueprint": "✓ (with field-level targeting)",
        },
        {
            "capability": "Normalize across operator formats",
            "generic_ocr": "✗",
            "bda_standard": "✗",
            "bda_custom_blueprint": "✓ (same schema, different layouts)",
        },
        {
            "capability": "Domain-specific data typing",
            "generic_ocr": "✗ (everything is text)",
            "bda_standard": "✗",
            "bda_custom_blueprint": "✓ (API numbers, depths, volumes)",
        },
        {
            "capability": "Regulatory field extraction",
            "generic_ocr": "✗",
            "bda_standard": "✗",
            "bda_custom_blueprint": "✓ (water sources, compliance data)",
        },
    ]
    return pd.DataFrame(rows)


# Confirmed data types tested in this PoC
CONFIRMED_DATA_TYPES = [
    {"data_type": "Perforations", "status": "✓ Confirmed", "operators_tested": 2,
     "fields": "Top_Perf, Bottom_Perf (per stage)"},
    {"data_type": "Completion/Stimulation", "status": "✓ Confirmed", "operators_tested": 2,
     "fields": "Proppant_Volume, Water, Stage_Length"},
    {"data_type": "Casing Strings", "status": "✓ Confirmed", "operators_tested": 2,
     "fields": "Size, Weight, Depth"},
    {"data_type": "Well Identification", "status": "✓ Confirmed", "operators_tested": 2,
     "fields": "API_Number, Well_Name, Operator, Field, State, Spud_Date, Measured_Depth"},
    {"data_type": "Water Sources", "status": "✓ Confirmed", "operators_tested": 1,
     "fields": "Source_Name, Supply_Type, Volume_Used, Source_Location"},
    {"data_type": "Directional Surveys", "status": "Not yet tested", "operators_tested": 0,
     "fields": "Could add: MD, Inclination, Azimuth"},
    {"data_type": "Production Data", "status": "Not yet tested", "operators_tested": 0,
     "fields": "Could add: Oil_Rate, Gas_Rate, Water_Rate, Date"},
    {"data_type": "Cement Records", "status": "Not yet tested", "operators_tested": 0,
     "fields": "Could add: Top_Cement, Sacks, Yield"},
]
