import pytest
from dfm.cad.step_parser import load_step_file
from dfm.cad.mold_axis import suggest_mold_axis
from dfm.cad.draft_angle import compute_draft_angles
from dfm.cad.undercut import detect_undercuts
from dfm.cad.parting_line import detect_parting_line
from dfm.cad.parting_plane_sweep import suggest_parting_plane
from dfm.cad.core_cavity_split import split_core_cavity
from dfm.cad.side_action import detect_side_actions

SAMPLE_BOX_PATH = "sample_parts/test_box.step"

def test_dfm_pipeline():
    part, metrics = load_step_file(SAMPLE_BOX_PATH)
    
    # 1. Mold Axis
    axis_res = suggest_mold_axis(part)
    best_axis = axis_res["recommended_axis"]
    assert best_axis in [(1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1)]
    
    # 2. Draft Angles
    drafts = compute_draft_angles(part, pull_axis=best_axis)
    assert len(drafts) == 6
    # A box has 0 draft on its side walls relative to any principal axis
    zero_drafts = [d for d in drafts if abs(d["draft_angle"]) < 1.0]
    assert len(zero_drafts) >= 4
    
    # 3. Undercuts
    # A simple box has no undercuts if pulled along a principal axis
    undercuts = detect_undercuts(part, pull_axis=best_axis)
    assert len(undercuts) == 0
    
    # 4. Parting Line
    pline = detect_parting_line(part, pull_axis=best_axis)
    assert len(pline) == 5 # 4 corners + closed loop
    
    # 5. Parting Plane
    plane_res = suggest_parting_plane(part, pull_axis=best_axis)
    assert "plane_center" in plane_res
    
    # 6. Split Core/Cavity
    core, cavity = split_core_cavity(part, best_axis, plane_res["plane_center"])
    # The split should create two halves
    assert core.val().Volume() > 0
    assert cavity.val().Volume() > 0
    # Combined volume should be roughly original
    assert abs(core.val().Volume() + cavity.val().Volume() - metrics.volume) < 1.0
    
    # 7. Side actions
    # Since undercuts is empty, side actions should be empty
    actions = detect_side_actions(undercuts)
    assert len(actions) == 0
