import cadquery as cq
from typing import Tuple, List

def detect_parting_line(part: cq.Workplane, pull_axis: Tuple[float, float, float]) -> dict:
    """
    Extracts parting line visual indicators.
    For this 4-block tooling split, we return planes that indicate where the molds meet.
    """
    val = part.val()
    if val is None:
        return {}
        
    bb = val.BoundingBox()
    cx = (bb.xmin + bb.xmax) / 2.0
    cy = (bb.ymin + bb.ymax) / 2.0
    cz = (bb.zmin + bb.zmax) / 2.0
    
    # Render translucent intersecting planes to visualize the mold splits
    # Top/Bottom Cavity splits at Z=4.0 and Z=22.0
    # Left/Right Slider splits at X=cx
    return {
        "planes": [
            {"axis": "Z", "offset": 4.0, "color": "#10b981", "name": "Bottom Core Split"},
            {"axis": "Z", "offset": 22.0, "color": "#3b82f6", "name": "Top Cavity Split"},
            {"axis": "X", "offset": cx, "color": "#f59e0b", "name": "Left/Right Slider Split"}
        ],
        "bbox": {
            "xlen": bb.xlen, "ylen": bb.ylen, "zlen": bb.zlen,
            "cx": cx, "cy": cy, "cz": cz
        }
    }
