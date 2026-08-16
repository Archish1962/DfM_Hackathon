import cadquery as cq
import math
from typing import Tuple, List, Dict
from .face_utils import get_face_properties

def compute_draft_angles(part: cq.Workplane, pull_axis: Tuple[float, float, float]) -> List[Dict]:
    """
    Computes the signed draft angle for each face relative to the pull axis.

    Convention (matches Siemens NX / Design Center):
      - Positive draft: face normal tilts toward the pull direction (good for ejection).
      - Negative draft: face normal tilts against the pull direction (undercut-prone).
      - Zero draft: face is perfectly parallel to the pull axis (vertical wall).

    The signed draft angle is  degrees(asin(dot(normal, pullAxis))).
    Range: -90° (normal opposite to pull) … 0° (vertical wall) … +90° (normal along pull).
    """
    val = part.val()
    if val is None:
        return []

    results = []
    for i, face in enumerate(val.Faces()):
        props = get_face_properties(face)
        norm = props["normal"]

        if norm is None:
            results.append({"face_id": i, "draft_angle": 0.0, "normal": norm})
            continue

        dot = norm[0]*pull_axis[0] + norm[1]*pull_axis[1] + norm[2]*pull_axis[2]
        dot = max(min(dot, 1.0), -1.0)

        # Signed draft angle
        angle = math.degrees(math.asin(dot))

        results.append({
            "face_id": i,
            "draft_angle": round(angle, 3),
            "normal": norm
        })

    return results
