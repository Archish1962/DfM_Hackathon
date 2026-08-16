import cadquery as cq
import math
import numpy as np
from typing import List, Dict, Tuple

# ---------------------------------------------------------------------------
# Siemens-style 4-colour draft scheme
# ---------------------------------------------------------------------------
#   > +5°   →  Green   (sufficient positive draft)
#   0 to +5 →  Yellow  (marginal positive draft)
#  -5 to  0 →  Blue    (slight negative draft / vertical wall)
#   < -5°   →  Red     (severe negative draft)
# ---------------------------------------------------------------------------
DRAFT_LIMIT = 5.0  # degrees – matches the Siemens "Limit Angle"

COLOR_POS_OUTSIDE = [0, 200, 0, 255]       # Green  –  > +limit
COLOR_POS_INSIDE  = [255, 220, 0, 255]     # Yellow –  0 to +limit
COLOR_NEG_INSIDE  = [30, 60, 220, 255]     # Blue   – -limit to 0
COLOR_NEG_OUTSIDE = [210, 20, 20, 255]     # Red    –  < -limit

COLOR_STANDARD    = [200, 200, 210, 255]   # light grey (standard view)
COLOR_UC_YES      = [210, 20, 20, 255]     # red   (undercut)
COLOR_UC_NO       = [180, 180, 190, 255]   # grey  (no undercut)


def export_mesh(part: cq.Workplane, output_path: str):
    """Legacy single-mesh export (standard grey, used by tests)."""
    import tempfile, trimesh, os

    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        tmp_name = tmp.name
    try:
        cq.exporters.export(part, tmp_name, exportType="STL")
        mesh = trimesh.load(tmp_name, file_type="stl")
        mesh.export(output_path, file_type="glb")
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
    return output_path


def _tessellate_brep_faces(part: cq.Workplane, tolerance: float = 0.1):
    """
    Tessellate each BREP face individually so every triangle maps back to
    its originating BREP face ID.
    """
    import trimesh

    val = part.val()
    all_vertices = []
    all_faces = []
    face_ids = []
    vertex_offset = 0

    for brep_idx, face in enumerate(val.Faces()):
        try:
            tess = face.tessellate(tolerance)
        except Exception:
            continue
        verts, tris = tess[0], tess[1]

        for v in verts:
            all_vertices.append([v.x, v.y, v.z])
        for tri in tris:
            all_faces.append([
                tri[0] + vertex_offset,
                tri[1] + vertex_offset,
                tri[2] + vertex_offset,
            ])
            face_ids.append(brep_idx)
        vertex_offset += len(verts)

    vertices = np.array(all_vertices, dtype=np.float64)
    faces = np.array(all_faces, dtype=np.int64)
    face_id_arr = np.array(face_ids, dtype=np.int32)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return mesh, face_id_arr


def _draft_color(angle: float):
    """Map a signed draft angle to the Siemens 4-colour palette."""
    if angle > DRAFT_LIMIT:
        return COLOR_POS_OUTSIDE
    elif angle > 0:
        return COLOR_POS_INSIDE
    elif angle > -DRAFT_LIMIT:
        return COLOR_NEG_INSIDE
    else:
        return COLOR_NEG_OUTSIDE


def export_colored_meshes(
    part: cq.Workplane,
    draft_angles: List[Dict],
    undercuts: List[Dict],
    pull_axis: Tuple[float, float, float],
    base_path: str,
):
    """
    Export three coloured GLBs:
      *_standard.glb  – neutral grey
      *_draft.glb     – Siemens-style 4-colour signed-draft heatmap
      *_undercut.glb  – red for undercut faces, grey otherwise
    """
    mesh, face_id_per_tri = _tessellate_brep_faces(part)
    n_tris = len(face_id_per_tri)

    # Build per-BREP-face lookup tables
    draft_by_face: Dict[int, float] = {}
    for d in draft_angles:
        draft_by_face[d["face_id"]] = d["draft_angle"]

    undercut_ids = {u["face_id"] for u in undercuts}

    # ---- Standard mesh ----
    std_colors = np.tile(COLOR_STANDARD, (n_tris, 1)).astype(np.uint8)
    std_mesh = mesh.copy()
    std_mesh.visual.face_colors = std_colors
    std_path = base_path + "_standard.glb"
    std_mesh.export(std_path, file_type="glb")

    # ---- Draft heatmap mesh ----
    draft_colors = np.zeros((n_tris, 4), dtype=np.uint8)
    for i in range(n_tris):
        angle = draft_by_face.get(face_id_per_tri[i], 90.0)
        draft_colors[i] = _draft_color(angle)
    draft_mesh = mesh.copy()
    draft_mesh.visual.face_colors = draft_colors
    draft_path = base_path + "_draft.glb"
    draft_mesh.export(draft_path, file_type="glb")

    # ---- Undercut mesh ----
    uc_colors = np.zeros((n_tris, 4), dtype=np.uint8)
    for i in range(n_tris):
        brep_id = face_id_per_tri[i]
        uc_colors[i] = COLOR_UC_YES if brep_id in undercut_ids else COLOR_UC_NO
    uc_mesh = mesh.copy()
    uc_mesh.visual.face_colors = uc_colors
    uc_path = base_path + "_undercut.glb"
    uc_mesh.export(uc_path, file_type="glb")

    return {
        "standard": std_path,
        "draft": draft_path,
        "undercut": uc_path,
    }

def export_mold_blocks(blocks: Dict[str, cq.Workplane], base_path: str) -> Dict[str, str]:
    """
    Exports the dictionary of 4 mold blocks to separate GLB files.
    """
    paths = {}
    for name, block in blocks.items():
        # E.g. part3_mold_top_cavity.glb
        out_path = f"{base_path}_mold_{name}.glb"
        export_mesh(block, out_path)
        paths[f"mold_{name}"] = out_path
    return paths
