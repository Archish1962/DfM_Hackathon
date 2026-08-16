from typing import List, Dict

def detect_side_actions(undercuts: List[Dict]) -> List[Dict]:
    """
    Groups undercuts into side-action zones based on their face normals.
    Faces with similar normal vectors requiring side actions are grouped together.
    """
    actions = {}
    for uc in undercuts:
        norm = uc["normal"]
        if norm is None:
            continue
            
        # Group by normal direction (rounded to 1 decimal place to cluster similar faces)
        key = (round(norm[0], 1), round(norm[1], 1), round(norm[2], 1))
        
        if key not in actions:
            actions[key] = {
                "direction": key,
                "face_ids": []
            }
        actions[key]["face_ids"].append(uc["face_id"])
        
    return list(actions.values())
