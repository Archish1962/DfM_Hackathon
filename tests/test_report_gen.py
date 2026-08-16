import os
import json
import pytest
import tempfile
import cadquery as cq

from dfm.report.runner import analyze_and_generate_report
from dfm.report.json_gen import determine_draft_status, build_dfm_report_json
from dfm.cad.step_parser import load_step_file, GeometryError
from dfm.cad.dfm_extended import (
    analyze_wall_thickness,
    classify_undercuts,
    suggest_gate_locations,
    check_rib_boss_geometry,
    check_corner_radii,
    suggest_ejector_pins,
    evaluate_parting_line_quality,
    generate_known_gaps
)

SAMPLE_BOX_PATH = "sample_parts/test_box.step"
SAMPLE_PART3_PATH = "actual_part/Part3.stp"


def test_draft_threshold_switching():
    # Plain (default: 1.0 deg)
    assert determine_draft_status(0.0, 1.0) == "ZERO_DRAFT"
    assert determine_draft_status(-0.5, 1.0) == "NEGATIVE_DRAFT"
    assert determine_draft_status(0.5, 1.0) == "LOW_DRAFT"
    assert determine_draft_status(1.5, 1.0) == "PASS"

    # Textured (3.0 deg)
    assert determine_draft_status(2.0, 3.0) == "LOW_DRAFT"
    assert determine_draft_status(3.5, 3.0) == "PASS"

    # Leather (5.0 deg)
    assert determine_draft_status(4.2, 5.0) == "LOW_DRAFT"
    assert determine_draft_status(5.5, 5.0) == "PASS"


def test_report_generation_box(tmp_path):
    outdir = str(tmp_path)
    json_path, pdf_path, report_data = analyze_and_generate_report(
        input_path=SAMPLE_BOX_PATH,
        part_name="test_box_unit",
        texture="textured",
        material="ABS",
        units="mm",
        outdir=outdir
    )

    # 1. Check file existence
    assert os.path.exists(json_path)
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000

    # 2. Check JSON Schema Validity & Traceability
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Part Summary
    assert "part_summary" in data
    summary = data["part_summary"]
    assert summary["part_name"] == "test_box_unit"
    assert summary["faces"] == 6
    assert summary["edges"] == 12
    assert summary["volume"] == 1000.0
    assert summary["surface_area"] == 600.0
    assert summary["material"] == "ABS"
    assert summary["units"] == "mm"
    assert "bounding_box" in summary

    # Mold Direction
    assert "mold_direction" in data
    mdir = data["mold_direction"]
    assert len(mdir["vector"]) == 3
    assert mdir["algorithm"] == "6-axis-cardinal-score"
    assert len(mdir["cardinal_scores"]) == 6

    # Draft Analysis
    assert "draft_analysis" in data
    da = data["draft_analysis"]
    assert da["threshold_used"] == 3.0
    assert da["texture_type"] == "textured"
    assert len(da["faces"]) == 6
    assert da["summary"]["ZERO_DRAFT"] >= 4

    # Undercuts
    assert "undercuts" in data
    assert isinstance(data["undercuts"], list)

    # Parting Line
    assert "parting_line" in data
    assert data["parting_line"]["is_closed"] is True
    assert "planarity" in data["parting_line"]
    assert "flash_risk" in data["parting_line"]

    # Mold Assembly
    assert "mold_assembly" in data
    ma = data["mold_assembly"]
    assert ma["stock_block_volume"] > 0
    assert ma["cavity_volume"] > 0
    assert ma["core_volume"] > 0
    assert "side_sliders" in ma

    # Extended DFM
    assert "wall_thickness" in data
    assert data["wall_thickness"]["nominal_thickness"] > 0
    assert data["wall_thickness"]["heuristic"] is True

    assert "gate_locations" in data
    assert len(data["gate_locations"]) > 0

    assert "rib_boss_geometry" in data
    assert "radii_checks" in data
    assert "ejector_pins" in data
    assert len(data["ejector_pins"]) > 0

    assert "known_gaps" in data
    assert len(data["known_gaps"]) >= 3


def test_report_generation_part3(tmp_path):
    outdir = str(tmp_path)
    json_path, pdf_path, report_data = analyze_and_generate_report(
        input_path=SAMPLE_PART3_PATH,
        part_name="Part3_unit",
        texture="leather",
        material="PP",
        units="mm",
        outdir=outdir
    )

    assert os.path.exists(json_path)
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 5000

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Verify undercut classification
    undercuts = data["undercuts"]
    assert len(undercuts) > 0
    for uc in undercuts:
        assert uc["resolution"] in ["side-action", "lifter", "eliminate-by-redesign"]
        assert len(uc["reason"]) > 5

    # Verify leather threshold applied
    assert data["draft_analysis"]["threshold_used"] == 5.0
    assert data["draft_analysis"]["texture_type"] == "leather"


def test_multibody_rejection(tmp_path):
    # Create a compound with two disconnected solid bodies
    b1 = cq.Workplane("XY").box(10, 10, 10)
    b2 = cq.Workplane("XY").box(10, 10, 10).translate((20, 0, 0))
    multi_part = b1.add(b2)
    step_file = str(tmp_path / "multi_body.step")
    cq.exporters.export(multi_part, step_file)

    # Should raise GeometryError
    with pytest.raises(GeometryError, match="Multi-body STEP file detected"):
        load_step_file(step_file)
