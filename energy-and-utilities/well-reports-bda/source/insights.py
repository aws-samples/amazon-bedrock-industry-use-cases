"""
Insights Module

Derives meaningful insights from extracted well data — not just raw tables,
but actionable conclusions that answer business questions:

- Which wells used the most proppant? (cost optimization)
- Are there anomalies in completion designs? (quality control)
- How do operators compare on water usage? (regulatory compliance)
- What's the trend in lateral lengths over time? (technology adoption)
- Which wells have incomplete data? (data quality)

This module transforms structured data into business-relevant insights
that demonstrate the value beyond "here's a CSV."
"""

from typing import Dict, List, Optional

import pandas as pd

from source.logger import get_logger

logger = get_logger(__name__)


def generate_well_insights(consolidated: Dict[str, pd.DataFrame]) -> List[Dict]:
    """
    Generate meaningful insights from consolidated well data.

    Args:
        consolidated: Dictionary of DataFrames from consolidate_results()

    Returns:
        List of insight dictionaries with:
        - title: Short insight headline
        - category: Type of insight (cost, compliance, quality, trend, anomaly)
        - description: Explanation of what this means
        - data: Supporting data (DataFrame or value)
        - action: Recommended action based on this insight
    """
    insights = []

    wells_df = consolidated.get("well_information", pd.DataFrame())
    perfs_df = consolidated.get("perforation_data", pd.DataFrame())
    completions_df = consolidated.get("completion_summary", pd.DataFrame())
    casings_df = consolidated.get("casing_summary", pd.DataFrame())

    # --- Insight 1: Proppant Loading Comparison ---
    if not completions_df.empty and "proppant_volume" in completions_df.columns:
        proppant_by_well = completions_df.groupby("well_name")["proppant_volume"].sum().reset_index()
        proppant_by_well.columns = ["well_name", "total_proppant"]
        proppant_by_well = proppant_by_well.sort_values("total_proppant", ascending=False)

        if len(proppant_by_well) > 0:
            avg_proppant = proppant_by_well["total_proppant"].mean()
            max_well = proppant_by_well.iloc[0]

            insights.append({
                "title": "Proppant Loading by Well",
                "category": "cost",
                "icon": "💰",
                "description": (
                    f"Average total proppant per well: {avg_proppant:,.0f} lbs. "
                    f"Highest: {max_well['well_name']} at {max_well['total_proppant']:,.0f} lbs."
                ),
                "data": proppant_by_well,
                "action": "Compare proppant loading against production rates to identify optimal designs.",
            })

    # --- Insight 2: Water Usage for Regulatory Compliance ---
    if not completions_df.empty and "water_volume" in completions_df.columns:
        water_data = completions_df[completions_df["water_volume"].notna()]
        if not water_data.empty:
            water_by_well = water_data.groupby("well_name")["water_volume"].sum().reset_index()
            water_by_well.columns = ["well_name", "total_water_bbls"]
            total_water = water_by_well["total_water_bbls"].sum()

            insights.append({
                "title": "Water Usage Summary (Regulatory)",
                "category": "compliance",
                "icon": "🏛️",
                "description": (
                    f"Total water used across all wells: {total_water:,.0f} barrels. "
                    f"This data is required for state regulatory filings (e.g., FracFocus)."
                ),
                "data": water_by_well,
                "action": "Verify water volumes match FracFocus submissions and state permit limits.",
            })

    # --- Insight 3: Lateral Length / Stage Count Analysis ---
    if not perfs_df.empty and "top_perf" in perfs_df.columns and "bottom_perf" in perfs_df.columns:
        # Calculate lateral length (deepest perf - shallowest perf)
        lateral_by_well = perfs_df.groupby("well_name").agg(
            stages=("stage", "count"),
            shallowest=("top_perf", "min"),
            deepest=("bottom_perf", "max"),
        ).reset_index()
        lateral_by_well["lateral_length_ft"] = lateral_by_well["deepest"] - lateral_by_well["shallowest"]
        lateral_by_well = lateral_by_well[["well_name", "stages", "lateral_length_ft", "shallowest", "deepest"]]

        if len(lateral_by_well) > 0:
            avg_stages = lateral_by_well["stages"].mean()
            avg_lateral = lateral_by_well["lateral_length_ft"].mean()

            insights.append({
                "title": "Completion Design Summary",
                "category": "trend",
                "icon": "📊",
                "description": (
                    f"Average stages per well: {avg_stages:.1f}. "
                    f"Average perforated interval: {avg_lateral:,.0f} ft. "
                    f"Longer laterals with more stages indicate modern completion designs."
                ),
                "data": lateral_by_well,
                "action": "Track stage count trends over time to measure technology adoption.",
            })

    # --- Insight 4: Data Completeness Check ---
    if not wells_df.empty:
        missing_fields = {}
        for col in wells_df.columns:
            missing_count = wells_df[col].isna().sum() + (wells_df[col] == "").sum()
            if missing_count > 0:
                missing_fields[col] = missing_count

        if missing_fields:
            missing_df = pd.DataFrame([
                {"field": k, "missing_count": v, "percent_missing": f"{v / len(wells_df) * 100:.0f}%"}
                for k, v in missing_fields.items()
            ])

            insights.append({
                "title": "Data Quality: Missing Fields",
                "category": "quality",
                "icon": "⚠️",
                "description": (
                    f"{len(missing_fields)} fields have missing data across {len(wells_df)} wells. "
                    f"Incomplete records may indicate extraction issues or missing source documents."
                ),
                "data": missing_df,
                "action": "Review source documents for wells with missing API numbers or spud dates.",
            })

    # --- Insight 5: Operator Comparison ---
    if not wells_df.empty and "operator" in wells_df.columns and len(wells_df["operator"].unique()) > 1:
        operator_summary = wells_df.groupby("operator").agg(
            well_count=("well_name", "count"),
            states=("state", "nunique"),
            fields=("field", "nunique"),
        ).reset_index()

        insights.append({
            "title": "Operator Portfolio Comparison",
            "category": "trend",
            "icon": "🏢",
            "description": (
                f"{len(operator_summary)} operators represented in the dataset. "
                f"Cross-operator comparison enables benchmarking of completion practices."
            ),
            "data": operator_summary,
            "action": "Compare completion designs across operators to identify best practices.",
        })

    # --- Insight 6: Casing Program Anomalies ---
    if not casings_df.empty and "depth" in casings_df.columns:
        casing_by_well = casings_df.groupby("well_name").agg(
            casing_strings=("size", "count"),
            max_depth=("depth", "max"),
        ).reset_index()

        if len(casing_by_well) > 1:
            avg_strings = casing_by_well["casing_strings"].mean()
            anomalies = casing_by_well[
                (casing_by_well["casing_strings"] < avg_strings - 1) |
                (casing_by_well["casing_strings"] > avg_strings + 1)
            ]

            if not anomalies.empty:
                insights.append({
                    "title": "Casing Program Anomalies",
                    "category": "anomaly",
                    "icon": "🔍",
                    "description": (
                        f"Average casing strings per well: {avg_strings:.1f}. "
                        f"{len(anomalies)} well(s) have unusual casing programs that may warrant review."
                    ),
                    "data": anomalies,
                    "action": "Verify wells with fewer casing strings meet regulatory requirements.",
                })

    # --- Insight 7: Proppant Intensity (lbs per foot) ---
    if not completions_df.empty and not perfs_df.empty:
        if "proppant_volume" in completions_df.columns:
            proppant_total = completions_df.groupby("well_name")["proppant_volume"].sum()
            perf_intervals = perfs_df.groupby("well_name").apply(
                lambda x: x["bottom_perf"].max() - x["top_perf"].min()
                if x["bottom_perf"].max() > x["top_perf"].min() else 0
            )

            intensity_df = pd.DataFrame({
                "total_proppant": proppant_total,
                "perf_interval_ft": perf_intervals,
            }).dropna()

            if not intensity_df.empty and (intensity_df["perf_interval_ft"] > 0).any():
                intensity_df = intensity_df[intensity_df["perf_interval_ft"] > 0]
                if intensity_df.empty:
                    return insights
                intensity_df["lbs_per_foot"] = intensity_df["total_proppant"] / intensity_df["perf_interval_ft"]
                intensity_df = intensity_df.reset_index()

                avg_intensity = intensity_df["lbs_per_foot"].mean()
                insights.append({
                    "title": "Proppant Intensity (lbs/ft)",
                    "category": "cost",
                    "icon": "📈",
                    "description": (
                        f"Average proppant intensity: {avg_intensity:,.0f} lbs/ft. "
                        f"Higher intensity may correlate with better production but increases cost."
                    ),
                    "data": intensity_df[["well_name", "total_proppant", "perf_interval_ft", "lbs_per_foot"]],
                    "action": "Correlate proppant intensity with 30/60/90-day production to find optimal loading.",
                })

    return insights


def generate_demo_insights() -> List[Dict]:
    """
    Generate demo insights using sample data to show what the insights look like
    when real well reports are processed.
    """
    demo_insights = [
        {
            "title": "Proppant Loading by Well",
            "category": "cost",
            "icon": "💰",
            "description": (
                "Average total proppant per well: 1,430,000 lbs. "
                "Highest: Smith #1H at 1,860,000 lbs. "
                "Lowest: Davis #3H at 780,000 lbs (40% below average — possible underperformer)."
            ),
            "data": pd.DataFrame([
                {"well_name": "Smith #1H", "total_proppant": 1860000, "vs_average": "+30%"},
                {"well_name": "Jones #2H", "total_proppant": 1650000, "vs_average": "+15%"},
                {"well_name": "Davis #3H", "total_proppant": 780000, "vs_average": "-45%"},
            ]),
            "action": "Investigate Davis #3H — low proppant loading may explain underperformance. Compare against type curve.",
        },
        {
            "title": "Water Usage Summary (Regulatory)",
            "category": "compliance",
            "icon": "🏛️",
            "description": (
                "Total water used: 76,800 barrels across 3 wells. "
                "Jones #2H used 32,000 bbls — verify this matches FracFocus submission."
            ),
            "data": pd.DataFrame([
                {"well_name": "Smith #1H", "total_water_bbls": 24500, "permit_limit_bbls": 30000, "status": "✓ Within limit"},
                {"well_name": "Jones #2H", "total_water_bbls": 32000, "permit_limit_bbls": 30000, "status": "⚠️ Exceeds permit"},
                {"well_name": "Davis #3H", "total_water_bbls": 20300, "permit_limit_bbls": 30000, "status": "✓ Within limit"},
            ]),
            "action": "URGENT: Jones #2H water usage exceeds permit limit. Verify with field office and update regulatory filing.",
        },
        {
            "title": "Completion Design Trends",
            "category": "trend",
            "icon": "📊",
            "description": (
                "Average stages: 42. Average lateral length: 8,200 ft. "
                "Smith #1H (2023) has 15% more stages than Davis #3H (2022) — "
                "indicates tighter stage spacing adoption."
            ),
            "data": pd.DataFrame([
                {"well_name": "Smith #1H", "year": 2023, "stages": 48, "lateral_ft": 9200, "spacing_ft": 192},
                {"well_name": "Jones #2H", "year": 2023, "stages": 44, "lateral_ft": 8400, "spacing_ft": 191},
                {"well_name": "Davis #3H", "year": 2022, "stages": 34, "lateral_ft": 7000, "spacing_ft": 206},
            ]),
            "action": "Tighter spacing (190 ft vs 206 ft) in 2023 wells. Track production to validate ROI of additional stages.",
        },
        {
            "title": "Proppant Intensity Analysis",
            "category": "cost",
            "icon": "📈",
            "description": (
                "Average proppant intensity: 1,740 lbs/ft. "
                "Industry benchmark for Eagle Ford: 1,500–2,000 lbs/ft. "
                "All wells within expected range."
            ),
            "data": pd.DataFrame([
                {"well_name": "Smith #1H", "lbs_per_foot": 2022, "benchmark": "1,500-2,000", "status": "Slightly above"},
                {"well_name": "Jones #2H", "lbs_per_foot": 1964, "benchmark": "1,500-2,000", "status": "Within range"},
                {"well_name": "Davis #3H", "lbs_per_foot": 1114, "benchmark": "1,500-2,000", "status": "Below range"},
            ]),
            "action": "Davis #3H below benchmark — may explain lower production. Consider higher loading on offset wells.",
        },
        {
            "title": "Data Quality Alert",
            "category": "quality",
            "icon": "⚠️",
            "description": (
                "1 well missing spud date, 1 well missing product type. "
                "Incomplete records affect type curve analysis and regulatory reporting."
            ),
            "data": pd.DataFrame([
                {"field": "spud_date", "missing_wells": "Davis #3H", "impact": "Cannot calculate days-to-TD"},
                {"field": "product_type", "missing_wells": "Jones #2H", "impact": "Cannot classify for decline analysis"},
            ]),
            "action": "Pull original completion reports for Davis #3H and Jones #2H to fill gaps.",
        },
    ]
    return demo_insights
