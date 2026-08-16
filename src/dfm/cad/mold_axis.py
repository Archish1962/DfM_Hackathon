import cadquery as cq
from typing import Tuple, Dict
from .face_utils import iterate_faces

def suggest_mold_axis(part: cq.Workplane) -> Dict:
    """
    Evaluates candidate pull directions (X, Y, Z axes) and recommends the best one.
    Heuristic: The best pull axis minimizes the number of undercut faces.
    Tie-breaker: Minimize zero draft faces.
    """
    candidates = [
        (1, 0, 0), (-1, 0, 0),
        (0, 1, 0), (0, -1, 0),
        (0, 0, 1), (0, 0, -1)
    ]
    
    faces = iterate_faces(part)
    
    best_axis = (0, 0, 1)
    best_score = float('inf')
    best_zero_draft = float('inf')
    results = []
    
    for axis in candidates:
        undercut_count = 0
        zero_draft_count = 0
        
        for f in faces:
            norm = f["normal"]
            if norm is None:
                continue
            dot = norm[0]*axis[0] + norm[1]*axis[1] + norm[2]*axis[2]
            
            # Undercut: face points away from pull direction
            if dot < -0.01:
                undercut_count += 1
            # Zero draft: face is parallel to pull direction
            elif abs(dot) <= 0.01:
                zero_draft_count += 1
                
        results.append({
            "axis": axis, 
            "undercuts": undercut_count,
            "zero_draft_faces": zero_draft_count
        })
        
        if undercut_count < best_score:
            best_score = undercut_count
            best_zero_draft = zero_draft_count
            best_axis = axis
        elif undercut_count == best_score and zero_draft_count < best_zero_draft:
            best_zero_draft = zero_draft_count
            best_axis = axis
            
    return {
        "recommended_axis": best_axis,
        "alternatives": results
    }
