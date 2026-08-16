import cadquery as cq
from pydantic import BaseModel
from typing import Dict, Tuple

class CADMetrics(BaseModel):
    is_solid: bool
    volume: float
    surface_area: float
    bounding_box: Dict[str, float]
    face_count: int
    edge_count: int

class GeometryError(Exception):
    pass

import numpy as np
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.gp import gp_Trsf, gp_Mat

def _auto_align_solid(val: cq.Shape) -> cq.Shape:
    """
    Auto-aligns the solid by preserving its original Z-axis orientation,
    but rotating around the Z-axis so that the largest side planar faces
    align with the X or Y axes. Offsets to origin.
    """
    planar_faces = []
    for f in val.Faces():
        if f.geomType() == "PLANE":
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(f.wrapped, props)
            area = props.Mass()
            try:
                center = f.Center()
                normal = f.normalAt(center)
                # Only consider faces that are roughly parallel to the Z axis
                # (meaning their normal is orthogonal to Z, i.e., normal.z ~ 0)
                if abs(normal.z) < 0.1:
                    n_vec = np.array([normal.x, normal.y, normal.z])
                    n_vec = n_vec / np.linalg.norm(n_vec)
                    planar_faces.append({"area": area, "normal": n_vec})
            except:
                continue
                
    rotated_val = val
    
    if planar_faces:
        planar_faces.sort(key=lambda x: x["area"], reverse=True)
        primary_normal = planar_faces[0]["normal"]
        
        # We want to rotate this normal to align with either X or Y.
        # Let's align it with X (1, 0, 0)
        # We project the normal onto the XY plane just to be safe
        n_xy = np.array([primary_normal[0], primary_normal[1]])
        n_xy = n_xy / np.linalg.norm(n_xy)
        
        # Calculate angle to (1, 0)
        angle = np.arctan2(n_xy[1], n_xy[0])
        
        # We want to rotate by -angle around Z axis
        # But we also want it to align to the *nearest* axis (X, Y, -X, -Y)
        # to minimize the rotation if it's already close
        
        # Let's just align the primary normal perfectly to (1, 0)
        # CadQuery's rotate takes an axis (point, direction) and an angle in degrees.
        angle_deg = -np.degrees(angle)
        
        # Apply the rotation
        # val is a cq.Shape, we need to wrap it to rotate, or use moved.
        wp = cq.Workplane("XY").add(val).rotate((0,0,0), (0,0,1), angle_deg)
        rotated_val = wp.val()
    
    bbox = rotated_val.BoundingBox()
    dx = -(bbox.xmin + bbox.xmax) / 2.0
    dy = -(bbox.ymin + bbox.ymax) / 2.0
    dz = -bbox.zmin
    
    return rotated_val.translate((dx, dy, dz))

def load_step_file(filepath: str) -> Tuple[cq.Workplane, CADMetrics]:
    """
    Loads a STEP file, auto-aligns it, and validates that it contains solid geometry.
    Returns the cadquery Workplane/Shape and its extracted metrics.
    """
    try:
        part = cq.importers.importStep(filepath)
    except Exception as e:
        raise GeometryError(f"Failed to load STEP file: {e}")
        
    val = part.val()
    if val is None:
        raise GeometryError("STEP file contains no valid geometry.")
        
    solids = val.Solids()
    if not solids:
        raise GeometryError("STEP file does not contain solid geometry.")
    
    # Auto-align the geometry
    val = _auto_align_solid(val)
    part = cq.Workplane(val)
    
    bb = val.BoundingBox()
    
    metrics = CADMetrics(
        is_solid=True,
        volume=val.Volume(),
        surface_area=val.Area(),
        bounding_box={
            "xmin": bb.xmin, "ymin": bb.ymin, "zmin": bb.zmin,
            "xmax": bb.xmax, "ymax": bb.ymax, "zmax": bb.zmax,
            "xlen": bb.xlen, "ylen": bb.ylen, "zlen": bb.zlen,
        },
        face_count=len(val.Faces()),
        edge_count=len(val.Edges())
    )
    
    return part, metrics
