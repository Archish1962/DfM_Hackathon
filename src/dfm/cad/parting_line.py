import cadquery as cq
from typing import Tuple, List

def detect_parting_line(part: cq.Workplane, pull_axis: Tuple[float, float, float]) -> List[Tuple[float, float, float]]:
    """
    Extracts a candidate parting line as a polyline (list of 3D points).
    Hackathon simplification: returns the bounding box mid-plane perimeter.
    """
    val = part.val()
    if val is None:
        return []
        
    bb = val.BoundingBox()
    
    if pull_axis[2] != 0:
        z = (bb.zmax + bb.zmin) / 2
        return [
            (bb.xmin, bb.ymin, z), (bb.xmax, bb.ymin, z),
            (bb.xmax, bb.ymax, z), (bb.xmin, bb.ymax, z), (bb.xmin, bb.ymin, z)
        ]
    elif pull_axis[0] != 0:
        x = (bb.xmax + bb.xmin) / 2
        return [
            (x, bb.ymin, bb.zmin), (x, bb.ymax, bb.zmin),
            (x, bb.ymax, bb.zmax), (x, bb.ymin, bb.zmax), (x, bb.ymin, bb.zmin)
        ]
    else:
        y = (bb.ymax + bb.ymin) / 2
        return [
            (bb.xmin, y, bb.zmin), (bb.xmax, y, bb.zmin),
            (bb.xmax, y, bb.zmax), (bb.xmin, y, bb.zmax), (bb.xmin, y, bb.zmin)
        ]
