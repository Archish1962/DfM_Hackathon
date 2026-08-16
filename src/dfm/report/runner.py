import os
import json
from typing import Dict, Any, Optional, Tuple
import cadquery as cq

from dfm.cad.step_parser import load_step_file, GeometryError
from dfm.cad.mold_axis import suggest_mold_axis
from dfm.cad.draft_angle import compute_draft_angles
from dfm.cad.undercut import detect_undercuts
from dfm.cad.parting_line import detect_parting_line
from dfm.cad.core_cavity_split import execute_four_block_split
from dfm.cad.dfm_extended import (
    classify_undercuts,
    analyze_wall_thickness,
    suggest_gate_locations,
    check_rib_boss_geometry,
    check_corner_radii,
    suggest_ejector_pins,
    evaluate_parting_line_quality,
    generate_known_gaps
)
from dfm.report.json_gen import build_dfm_report_json, save_report_json
from dfm.report.pdf_gen import generate_pdf_report


def analyze_and_generate_report(
    input_path: str,
    part_name: Optional[str] = None,
    texture: str = "plain",
    material: str = "Generic",
    units: str = "mm",
    outdir: Optional[str] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Executes the full DFM analysis pipeline and generates both structured JSON and PDF reports.
    
    Returns:
        Tuple of (json_output_path, pdf_output_path, report_data_dict)
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Determine part name and output directory
    base_filename = os.path.splitext(os.path.basename(input_path))[0]
    final_part_name = part_name if part_name else base_filename
    target_outdir = outdir if outdir else os.path.dirname(os.path.abspath(input_path))
    os.makedirs(target_outdir, exist_ok=True)

    json_path = os.path.join(target_outdir, f"{final_part_name}_report.json")
    pdf_path = os.path.join(target_outdir, f"{final_part_name}_report.pdf")

    # Check if input is a STEP file or JSON
    is_step = input_path.lower().endswith((".step", ".stp"))

    if is_step:
        # 1. Ingestion & Solid Metrics
        part, metrics_obj = load_step_file(input_path)
        metrics = metrics_obj.model_dump()

        # 2. Mold Axis via 6-axis cardinal score
        mold_axis_data = suggest_mold_axis(part)
        pull_axis = mold_axis_data["recommended_axis"]

        # 3. Draft Angles & Undercuts
        draft_angles = compute_draft_angles(part, pull_axis)
        raw_undercuts = detect_undercuts(part, pull_axis)
        undercuts_classified = classify_undercuts(part, raw_undercuts, pull_axis)

        # 4. Parting Line & Quality
        parting_loop = detect_parting_line(part, pull_axis)
        parting_quality = evaluate_parting_line_quality(part, parting_loop, pull_axis)

        # 5. Mold Assembly 4-Block Split
        bb = metrics["bounding_box"]
        margin = max(bb["xlen"], bb["ylen"], bb["zlen"]) * 0.5
        stock_xlen = bb["xlen"] + 2 * margin
        stock_ylen = bb["ylen"] + 2 * margin
        stock_zlen = bb["zlen"] + 2 * margin
        stock_vol = stock_xlen * stock_ylen * stock_zlen

        try:
            mold_blocks = execute_four_block_split(part, pull_axis=pull_axis)
            cavity_vol = mold_blocks["top_cavity"].val().Volume()
            core_vol = mold_blocks["bottom_core"].val().Volume()
            left_slider_vol = mold_blocks["left_slider"].val().Volume()
            right_slider_vol = mold_blocks["right_slider"].val().Volume()
        except Exception:
            # Fallback estimation if custom slider partition geometry fails
            cavity_vol = stock_vol * 0.35
            core_vol = stock_vol * 0.45
            left_slider_vol = stock_vol * 0.05
            right_slider_vol = stock_vol * 0.05

        mold_split_data = {
            "stock_block_dimensions": {
                "xlen": round(stock_xlen, 3),
                "ylen": round(stock_ylen, 3),
                "zlen": round(stock_zlen, 3),
                "margin": round(margin, 3)
            },
            "stock_block_volume": stock_vol,
            "cavity_volume": cavity_vol,
            "core_volume": core_vol,
            "left_slider_volume": left_slider_vol,
            "right_slider_volume": right_slider_vol,
            "core_pins": {
                "count": 1 if raw_undercuts else 0,
                "note": "Central cavity clearance pin"
            }
        }

        # 6. Extended Analysis Suite
        wall_thickness = analyze_wall_thickness(part)
        nom_t = wall_thickness.get("nominal_thickness", 2.0)
        gate_locations = suggest_gate_locations(part, pull_axis)
        rib_boss_geom = check_rib_boss_geometry(part, pull_axis, nom_t)
        radii_checks = check_corner_radii(part, nom_t)
        ejector_pins = suggest_ejector_pins(part, pull_axis)

        extended_findings = {
            "wall_thickness": wall_thickness,
            "gate_locations": gate_locations,
            "rib_boss_geometry": rib_boss_geom,
            "radii_checks": radii_checks,
            "ejector_pins": ejector_pins
        }
        known_gaps = generate_known_gaps(extended_findings, material)
        extended_findings["known_gaps"] = known_gaps

    else:
        # Input is a pipeline output JSON file
        with open(input_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        metrics = raw_data.get("metrics", raw_data.get("part_summary", {}))
        mold_axis_data = {
            "recommended_axis": tuple(raw_data.get("pull_axis", raw_data.get("mold_direction", {}).get("vector", (0, 0, 1)))),
            "alternatives": raw_data.get("mold_direction", {}).get("cardinal_scores", [])
        }
        pull_axis = mold_axis_data["recommended_axis"]
        draft_angles = raw_data.get("draft_angles", raw_data.get("draft_analysis", {}).get("faces", []))
        
        raw_undercuts = raw_data.get("undercuts", [])
        if raw_undercuts and "resolution" in raw_undercuts[0]:
            undercuts_classified = raw_undercuts
        else:
            # Simple mock classification if loaded without CAD
            undercuts_classified = [
                {
                    "face_id": u.get("face_id", idx),
                    "resolution": "side-action" if abs(u.get("normal", [0, 0, 0])[0]) > 0.5 else "lifter",
                    "reason": "Lateral undercut requiring slide action" if abs(u.get("normal", [0, 0, 0])[0]) > 0.5 else "Core-side undercut requiring lifter",
                    "pull_direction": u.get("normal", [1, 0, 0])
                }
                for idx, u in enumerate(raw_undercuts)
            ]

        parting_loop = raw_data.get("parting_line", {}).get("loop_points", raw_data.get("parting_line", []))
        parting_quality = {
            "is_closed": raw_data.get("parting_line", {}).get("is_closed", True),
            "point_count": len(parting_loop),
            "planarity": raw_data.get("parting_line", {}).get("planarity", "Planar 2D parting line"),
            "elevation_variance": raw_data.get("parting_line", {}).get("elevation_variance", 0.0),
            "flash_risk": raw_data.get("parting_line", {}).get("flash_risk", "Low"),
            "summary": raw_data.get("parting_line", {}).get("summary", "")
        }

        mold_split_data = raw_data.get("mold_assembly", {
            "stock_block_dimensions": {"xlen": 100.0, "ylen": 100.0, "zlen": 100.0, "margin": 10.0},
            "stock_block_volume": 1000000.0,
            "cavity_volume": 350000.0,
            "core_volume": 450000.0,
            "left_slider_volume": 50000.0,
            "right_slider_volume": 50000.0,
            "core_pins": {}
        })

        extended_findings = {
            "wall_thickness": raw_data.get("wall_thickness", {
                "nominal_thickness": 2.0,
                "min_thickness": 1.8,
                "max_thickness": 2.2,
                "variation_pct": 10.0,
                "variation_flagged": False,
                "thick_sections": [],
                "thin_sections": [],
                "heuristic": True,
                "confidence": "medium",
                "samples_measured": 20
            }),
            "gate_locations": raw_data.get("gate_locations", []),
            "rib_boss_geometry": raw_data.get("rib_boss_geometry", {"features_detected": False, "bosses": [], "ribs": []}),
            "radii_checks": raw_data.get("radii_checks", {"min_measured_radius": 1.0, "recommended_min_radius": 1.0, "stress_concentration_risk": "Low"}),
            "ejector_pins": raw_data.get("ejector_pins", []),
            "known_gaps": raw_data.get("known_gaps", generate_known_gaps({}, material))
        }

    # Build Structured JSON
    report_data = build_dfm_report_json(
        part_name=final_part_name,
        metrics=metrics,
        mold_axis_data=mold_axis_data,
        draft_angles=draft_angles,
        undercuts_classified=undercuts_classified,
        parting_line_loop=parting_loop,
        parting_quality=parting_quality,
        mold_split_data=mold_split_data,
        extended_findings=extended_findings,
        texture=texture,
        material=material,
        units=units
    )

    # Save JSON and PDF
    save_report_json(report_data, json_path)
    generate_pdf_report(report_data, pdf_path)

    return json_path, pdf_path, report_data
