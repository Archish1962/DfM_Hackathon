import cadquery as cq
from typing import Tuple, Dict

def suggest_parting_plane(part: cq.Workplane, pull_axis: Tuple[float, float, float]) -> Dict:
    """
    Suggests a parting plane location based on the geometry.
    Hackathon simplified: mid-plane perpendicular to pull axis.
    """
    val = part.val()
    if val is None:
        return {}
        
    bb = val.BoundingBox()
    
    if pull_axis[2] != 0:
        center = (bb.zmax + bb.zmin) / 2
    elif pull_axis[0] != 0:
        center = (bb.xmax + bb.xmin) / 2
    else:
        center = (bb.ymax + bb.ymin) / 2
        
    return {
        "plane_center": center,
        "plane_normal": pull_axis
    }
