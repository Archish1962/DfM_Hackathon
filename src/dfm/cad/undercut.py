import cadquery as cq
from typing import Tuple, List, Dict
from .face_utils import get_face_properties

def detect_undercuts(part: cq.Workplane, pull_axis: Tuple[float, float, float]) -> List[Dict]:
    """
    Detect faces that are undercuts using raycasting.
    A face is an undercut if it is trapped (i.e. blocked from being pulled out).
    """
    val = part.val()
    if val is None:
        return []
    
    results = []
    
    # Core pulls in opposite of pull_axis, Cavity pulls in pull_axis
    core_pull = (-pull_axis[0], -pull_axis[1], -pull_axis[2])
    cavity_pull = (pull_axis[0], pull_axis[1], pull_axis[2])
    
    for i, face in enumerate(val.Faces()):
        props = get_face_properties(face)
        norm = props["normal"]
        center = props["center"]
        
        if norm is None:
            continue
            
        dot = norm[0]*pull_axis[0] + norm[1]*pull_axis[1] + norm[2]*pull_axis[2]
        is_undercut = False
        
        # Pointing down: formed by core pulling down. Blocked if something is below it.
        if dot < -0.01:
            hits = val.facesIntersectedByLine(center, core_pull, direction="AlongAxis")
            if len(hits) > 1:
                is_undercut = True
                
        # Pointing up: formed by cavity pulling up. Blocked if something is above it.
        elif dot > 0.01:
            hits = val.facesIntersectedByLine(center, cavity_pull, direction="AlongAxis")
            if len(hits) > 1:
                is_undercut = True
                
        if is_undercut:
            results.append({
                "face_id": i,
                "severity": "high",
                "normal": norm,
                "center": center,
                "dot": round(dot, 3)
            })
                
    return results
