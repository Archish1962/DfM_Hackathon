import cadquery as cq

def get_face_properties(face: cq.Face):
    """Extract properties of a single face."""
    geom_type = face.geomType()
    center = face.Center()
    
    # Attempt to compute normal at the center of the face
    try:
        normal = face.normalAt(center)
        normal_vec = (normal.x, normal.y, normal.z)
    except Exception:
        normal_vec = None
        
    return {
        "type": geom_type,
        "center": (center.x, center.y, center.z),
        "normal": normal_vec
    }

def iterate_faces(part: cq.Workplane):
    """Iterates through all faces of a part and returns their properties."""
    results = []
    val = part.val()
    if val is None:
        return results
        
    for i, face in enumerate(val.Faces()):
        props = get_face_properties(face)
        props["id"] = i
        results.append(props)
        
    return results
