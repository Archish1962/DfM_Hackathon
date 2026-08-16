import os
import pytest
from dfm.cad.step_parser import load_step_file, GeometryError
from dfm.cad.mesh_export import export_mesh
from dfm.cad.face_utils import iterate_faces

SAMPLE_BOX_PATH = "sample_parts/test_box.step"

def test_load_step_file():
    # Load the test box generated in Phase 0
    part, metrics = load_step_file(SAMPLE_BOX_PATH)
    
    assert metrics.is_solid is True
    # The box is 10x10x10, so volume should be 1000
    assert abs(metrics.volume - 1000.0) < 1e-5
    # Surface area for a 10x10x10 box is 6 * 100 = 600
    assert abs(metrics.surface_area - 600.0) < 1e-5
    
    # Check bounding box
    bb = metrics.bounding_box
    assert abs(bb["xlen"] - 10.0) < 1e-5
    assert abs(bb["ylen"] - 10.0) < 1e-5
    assert abs(bb["zlen"] - 10.0) < 1e-5
    
    # 6 faces on a box
    assert metrics.face_count == 6
    # 12 edges on a box
    assert metrics.edge_count == 12

def test_load_invalid_file(tmp_path):
    # Create a dummy file
    dummy = tmp_path / "dummy.step"
    dummy.write_text("Not a real STEP file")
    
    with pytest.raises(GeometryError):
        load_step_file(str(dummy))

def test_export_mesh(tmp_path):
    part, _ = load_step_file(SAMPLE_BOX_PATH)
    out_glb = str(tmp_path / "out.glb")
    export_mesh(part, out_glb)
    
    assert os.path.exists(out_glb)
    assert os.path.getsize(out_glb) > 0

def test_iterate_faces():
    part, _ = load_step_file(SAMPLE_BOX_PATH)
    faces = iterate_faces(part)
    
    # Should be 6 faces
    assert len(faces) == 6
    for f in faces:
        assert f["type"] == "PLANE"
        assert f["normal"] is not None
