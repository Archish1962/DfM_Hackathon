import os
import json
from typing import Dict, List, Any, Tuple, Optional


def determine_draft_status(angle: float, threshold: float) -> str:
    """
    Classifies face draft angle against the active texture threshold:
      - ZERO_DRAFT: abs(angle) < 0.01 (perfect vertical wall)
      - NEGATIVE_DRAFT: angle < -0.01 (undercut / reverse taper)
      - LOW_DRAFT: 0.01 <= angle < threshold (insufficient draft)
      - PASS: angle >= threshold
    """
    if abs(angle) < 0.01:
        return "ZERO_DRAFT"
    elif angle < -0.01:
        return "NEGATIVE_DRAFT"
    elif angle < threshold:
        return "LOW_DRAFT"
    else:
        return "PASS"


def build_dfm_report_json(
    part_name: str,
    metrics: Dict[str, Any],
    mold_axis_data: Dict[str, Any],
    draft_angles: List[Dict[str, Any]],
    undercuts_classified: List[Dict[str, Any]],
    parting_line_loop: List[Tuple[float, float, float]],
    parting_quality: Dict[str, Any],
    mold_split_data: Dict[str, Any],
    extended_findings: Dict[str, Any],
    texture: str = "plain",
    material: str = "Generic",
    units: str = "mm"
) -> Dict[str, Any]:
    """
    Constructs the fully structured DFM JSON report matching the required specification.
    """
    # 1. Texture Threshold mapping (degrees)
    # plain: 1.0°, textured: 3.0° (standard VDI 24-30), leather: 5.0° (deep grain texture)
    threshold_map = {
        "plain": 1.0,
        "textured": 3.0,
        "leather": 5.0
    }
    threshold = threshold_map.get(texture.lower(), 1.0)

    # 2. Part Summary
    bb = metrics.get("bounding_box", {})
    part_summary = {
        "part_name": part_name,
        "faces": metrics.get("face_count", 0),
        "edges": metrics.get("edge_count", 0),
        "volume": round(metrics.get("volume", 0.0), 3),
        "surface_area": round(metrics.get("surface_area", 0.0), 3),
        "material": material,
        "units": units,
        "bounding_box": {
            "xmin": round(bb.get("xmin", 0.0), 3),
            "ymin": round(bb.get("ymin", 0.0), 3),
            "zmin": round(bb.get("zmin", 0.0), 3),
            "xmax": round(bb.get("xmax", 0.0), 3),
            "ymax": round(bb.get("ymax", 0.0), 3),
            "zmax": round(bb.get("zmax", 0.0), 3),
            "xlen": round(bb.get("xlen", 0.0), 3),
            "ylen": round(bb.get("ylen", 0.0), 3),
            "zlen": round(bb.get("zlen", 0.0), 3),
        }
    }

    # 3. Mold Pull Direction
    recommended_axis = mold_axis_data.get("recommended_axis", (0.0, 0.0, 1.0))
    alternatives = mold_axis_data.get("alternatives", [])
    mold_direction = {
        "vector": [round(float(x), 3) for x in recommended_axis],
        "algorithm": "6-axis-cardinal-score",
        "confidence": "high" if alternatives else "medium",
        "cardinal_scores": alternatives
    }

    # 4. Draft Analysis
    draft_faces = []
    status_counts = {
        "PASS": 0,
        "LOW_DRAFT": 0,
        "ZERO_DRAFT": 0,
        "NEGATIVE_DRAFT": 0
    }

    for d in draft_angles:
        face_id = d.get("face_id")
        angle = d.get("draft_angle", 0.0)
        norm = d.get("normal")
        status = determine_draft_status(angle, threshold)
        status_counts[status] += 1

        draft_faces.append({
            "face_id": face_id,
            "angle": round(angle, 3),
            "status": status,
            "normal": [round(float(x), 3) for x in norm] if norm else None
        })

    draft_analysis = {
        "threshold_used": threshold,
        "texture_type": texture.lower(),
        "summary": status_counts,
        "faces": draft_faces
    }

    # 5. Parting Line
    loop_pts = [[round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 3)] for p in parting_line_loop]
    parting_line = {
        "loop_points": loop_pts,
        "is_closed": parting_quality.get("is_closed", True),
        "point_count": len(loop_pts),
        "planarity": parting_quality.get("planarity", "Planar 2D parting line"),
        "elevation_variance": parting_quality.get("elevation_variance", 0.0),
        "flash_risk": parting_quality.get("flash_risk", "Low"),
        "summary": parting_quality.get("summary", "")
    }

    # 6. Mold Assembly
    stock_dims = mold_split_data.get("stock_block_dimensions", {})
    stock_vol = mold_split_data.get("stock_block_volume", 0.0)
    cavity_vol = mold_split_data.get("cavity_volume", 0.0)
    core_vol = mold_split_data.get("core_volume", 0.0)
    left_slider_vol = mold_split_data.get("left_slider_volume", 0.0)
    right_slider_vol = mold_split_data.get("right_slider_volume", 0.0)
    core_pins = mold_split_data.get("core_pins", {})

    mold_assembly = {
        "stock_block_dimensions": stock_dims,
        "stock_block_volume": round(stock_vol, 3),
        "cavity_volume": round(cavity_vol, 3),
        "core_volume": round(core_vol, 3),
        "side_sliders": {
            "left_slider_volume": round(left_slider_vol, 3),
            "right_slider_volume": round(right_slider_vol, 3),
            "total_slider_volume": round(left_slider_vol + right_slider_vol, 3)
        },
        "core_pins": core_pins,
        "volume_ratios": {
            "cavity_to_stock_pct": round((cavity_vol / stock_vol * 100.0) if stock_vol > 0 else 0.0, 2),
            "core_to_stock_pct": round((core_vol / stock_vol * 100.0) if stock_vol > 0 else 0.0, 2)
        }
    }

    # 7. Extended Checks & Known Gaps
    wall_thickness = extended_findings.get("wall_thickness", {})
    gate_locations = extended_findings.get("gate_locations", [])
    rib_boss_geom = extended_findings.get("rib_boss_geometry", {})
    radii_checks = extended_findings.get("radii_checks", {})
    ejector_pins = extended_findings.get("ejector_pins", [])
    known_gaps = extended_findings.get("known_gaps", [])

    report_dict = {
        "part_summary": part_summary,
        "mold_direction": mold_direction,
        "draft_analysis": draft_analysis,
        "undercuts": undercuts_classified,
        "parting_line": parting_line,
        "mold_assembly": mold_assembly,
        "wall_thickness": wall_thickness,
        "gate_locations": gate_locations,
        "rib_boss_geometry": rib_boss_geom,
        "radii_checks": radii_checks,
        "ejector_pins": ejector_pins,
        "known_gaps": known_gaps
    }

    return report_dict


def save_report_json(report_data: Dict[str, Any], output_path: str):
    """Saves the structured DFM report to a JSON file."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
