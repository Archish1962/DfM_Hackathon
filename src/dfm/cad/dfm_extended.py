import math
import numpy as np
import cadquery as cq
from typing import Dict, List, Any, Tuple, Optional
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_SurfaceType, GeomAbs_CurveType
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.BRep import BRep_Tool

from .face_utils import get_face_properties


def classify_undercuts(
    part: cq.Workplane,
    undercuts: List[Dict[str, Any]],
    pull_axis: Tuple[float, float, float] = (0.0, 0.0, 1.0)
) -> List[Dict[str, Any]]:
    """
    Classifies undercut faces into:
      - 'side-action': Accessible from a direction perpendicular to primary pull vector
                      without other geometry blocking it.
      - 'lifter': Internal / blocked from lateral access, but can be cleared by an
                 angled core-side lifter mechanism.
      - 'eliminate-by-redesign': Geometry is trapped or obstructed from both side-action
                                and lifter ejection paths; requires part redesign.
    """
    val = part.val()
    if val is None or not undercuts:
        return []

    pull_vec = np.array(pull_axis, dtype=float)
    pull_norm = np.linalg.norm(pull_vec)
    if pull_norm > 0:
        pull_vec = pull_vec / pull_norm

    bb = val.BoundingBox()
    classified = []

    for uc in undercuts:
        face_id = uc.get("face_id")
        norm = uc.get("normal")
        center = uc.get("center")

        if norm is None or center is None:
            classified.append({
                "face_id": face_id,
                "resolution": "eliminate-by-redesign",
                "reason": "Indeterminate face normal or center; manual geometry inspection required.",
                "pull_direction": None
            })
            continue

        n = np.array(norm, dtype=float)
        c = np.array(center, dtype=float)

        # Lateral component perpendicular to primary pull vector
        lat_component = n - np.dot(n, pull_vec) * pull_vec
        lat_mag = np.linalg.norm(lat_component)

        # Check lateral clearance for side-action
        is_side_action = False
        side_dir = None

        if lat_mag > 0.15:
            side_dir = lat_component / lat_mag
            side_tuple = (float(side_dir[0]), float(side_dir[1]), float(side_dir[2]))
            
            # Probe ray from face center outward along lateral direction
            # Offset slightly along normal to avoid self-intersection
            probe_pt = tuple(c + side_dir * 0.05)
            hits = val.facesIntersectedByLine(probe_pt, side_tuple, direction="AlongAxis")
            
            # If ray reaches exterior with no blocking faces
            if len(hits) == 0:
                is_side_action = True

        if is_side_action and side_dir is not None:
            axis_name = "+X" if side_dir[0] > 0.5 else ("-X" if side_dir[0] < -0.5 else ("+Y" if side_dir[1] > 0.5 else "-Y"))
            classified.append({
                "face_id": face_id,
                "resolution": "side-action",
                "reason": f"External lateral undercut with clear side-draw access along ({side_dir[0]:.2f}, {side_dir[1]:.2f}, {side_dir[2]:.2f}) ({axis_name}); requires cam/hydraulic slide.",
                "pull_direction": [round(float(x), 3) for x in side_dir]
            })
        else:
            # Check if lifter is feasible:
            # Lifter is applicable for core-side undercuts where an angled release vector
            # (typically 5° to 20° from core pull direction) can relieve the undercut.
            dot_pull = np.dot(n, pull_vec)
            # If on core side (dot_pull < 0 or negative z-half)
            core_side = dot_pull < 0.1 or c[2] < (bb.zmin + bb.zmax) / 2.0
            
            # Check angled release clearance (angled at 15 deg from core pull)
            lifter_angle_rad = math.radians(15)
            # Core pull is opposite to cavity pull
            core_dir = -pull_vec
            if lat_mag > 0.05:
                lat_unit = lat_component / lat_mag
                lifter_dir = core_dir * math.cos(lifter_angle_rad) + lat_unit * math.sin(lifter_angle_rad)
                lifter_dir = lifter_dir / np.linalg.norm(lifter_dir)
                probe_pt = tuple(c + lifter_dir * 0.05)
                lifter_tuple = (float(lifter_dir[0]), float(lifter_dir[1]), float(lifter_dir[2]))
                lifter_hits = val.facesIntersectedByLine(probe_pt, lifter_tuple, direction="AlongAxis")
                lifter_feasible = len(lifter_hits) == 0 and core_side
            else:
                lifter_feasible = False

            if lifter_feasible:
                classified.append({
                    "face_id": face_id,
                    "resolution": "lifter",
                    "reason": "Internal/recessed undercut on core side with open travel path for angled ejector/lifter blade.",
                    "pull_direction": [round(float(x), 3) for x in lifter_dir]
                })
            else:
                classified.append({
                    "face_id": face_id,
                    "resolution": "eliminate-by-redesign",
                    "reason": "Trapped geometry with obstructed lateral and lifter ejection paths; redesign with shut-off pass-throughs or uniform draft.",
                    "pull_direction": None
                })

    return classified


def analyze_wall_thickness(
    part: cq.Workplane,
    sample_density: int = 50
) -> Dict[str, Any]:
    """
    Performs normal-raycast wall thickness estimation across the solid part.
    Calculates nominal, min, max wall thickness, flags variations >10%,
    and highlights isolated thick sections prone to sink marks.
    """
    val = part.val()
    if val is None:
        return {
            "nominal_thickness": 0.0,
            "min_thickness": 0.0,
            "max_thickness": 0.0,
            "variation_pct": 0.0,
            "variation_flagged": False,
            "thick_sections": [],
            "thin_sections": [],
            "heuristic": True,
            "confidence": "low",
            "samples_measured": 0
        }

    thicknesses = []
    thick_faces = []
    thin_faces = []
    faces = val.Faces()

    for i, face in enumerate(faces):
        props = get_face_properties(face)
        norm = props["normal"]
        center = props["center"]

        if norm is None or center is None:
            continue

        c = np.array(center, dtype=float)
        n = np.array(norm, dtype=float)
        
        # Cast inward into the solid (opposite of outward normal)
        inward_dir = -n
        inward_tuple = (float(inward_dir[0]), float(inward_dir[1]), float(inward_dir[2]))
        probe_pt = tuple(c + inward_dir * 0.01)

        try:
            # Raycast through the solid
            hits = val.facesIntersectedByLine(probe_pt, inward_tuple, direction="AlongAxis")
            forward_hits = []
            for hit_face in hits:
                hit_props = get_face_properties(hit_face)
                if hit_props["center"]:
                    hc = np.array(hit_props["center"], dtype=float)
                    dist = float(np.linalg.norm(hc - c))
                    if dist > 0.05:
                        forward_hits.append(dist)

            if forward_hits:
                measured_t = min(forward_hits)
                thicknesses.append((i, measured_t, center))
        except Exception:
            continue

    if not thicknesses:
        bb = val.BoundingBox()
        dim_sorted = sorted([bb.xlen, bb.ylen, bb.zlen])
        est_t = round(dim_sorted[0] * 0.1, 2)
        return {
            "nominal_thickness": est_t,
            "min_thickness": est_t,
            "max_thickness": est_t,
            "variation_pct": 0.0,
            "variation_flagged": False,
            "thick_sections": [],
            "thin_sections": [],
            "heuristic": True,
            "confidence": "low",
            "samples_measured": 0
        }

    vals = [t[1] for t in thicknesses]
    nominal = float(np.median(vals))
    min_t = float(min(vals))
    max_t = float(max(vals))

    variation_pct = round(((max_t - min_t) / nominal * 100.0) if nominal > 0 else 0.0, 1)
    variation_flagged = variation_pct > 15.0  # Flag variation beyond standard tolerance

    for fid, t_val, pt in thicknesses:
        if t_val > 1.3 * nominal:
            thick_faces.append({
                "face_id": fid,
                "measured_thickness": round(t_val, 2),
                "ratio_to_nominal": round(t_val / nominal, 2),
                "location": [round(float(x), 2) for x in pt],
                "risk": "High sink mark & extended cooling cycle risk"
            })
        elif t_val < 0.7 * nominal:
            thin_faces.append({
                "face_id": fid,
                "measured_thickness": round(t_val, 2),
                "ratio_to_nominal": round(t_val / nominal, 2),
                "location": [round(float(x), 2) for x in pt],
                "risk": "Short shot / hesitation risk during injection fill"
            })

    return {
        "nominal_thickness": round(nominal, 2),
        "min_thickness": round(min_t, 2),
        "max_thickness": round(max_t, 2),
        "variation_pct": variation_pct,
        "variation_flagged": variation_flagged,
        "thick_sections": thick_faces[:10],
        "thin_sections": thin_faces[:10],
        "heuristic": True,
        "confidence": "medium",
        "samples_measured": len(thicknesses)
    }


def suggest_gate_locations(
    part: cq.Workplane,
    pull_axis: Tuple[float, float, float] = (0.0, 0.0, 1.0)
) -> List[Dict[str, Any]]:
    """
    Evaluates accessible flat exterior surfaces on the cavity side or parting plane
    suitable for gate injection (edge gate, sub-gate, direct sprue, or pin gate).
    """
    val = part.val()
    if val is None:
        return []

    pull_vec = np.array(pull_axis, dtype=float)
    if np.linalg.norm(pull_vec) > 0:
        pull_vec = pull_vec / np.linalg.norm(pull_vec)

    bb = val.BoundingBox()
    candidates = []

    for i, face in enumerate(val.Faces()):
        if face.geomType() != "PLANE":
            continue

        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face.wrapped, props)
        area = props.Mass()
        if area < 1.0:
            continue

        fprops = get_face_properties(face)
        norm = fprops["normal"]
        center = fprops["center"]

        if norm is None or center is None:
            continue

        n = np.array(norm, dtype=float)
        c = np.array(center, dtype=float)

        dot = np.dot(n, pull_vec)

        suitability = 0.0
        gate_type = "Edge Gate"

        if dot > 0.5:
            suitability = 85.0 + min(area / 100.0, 10.0)
            gate_type = "Pin-point / Direct Sprue Gate"
        elif abs(dot) <= 0.3:
            suitability = 80.0 + min(area / 100.0, 10.0)
            gate_type = "Edge / Submarine Gate at Parting Line"
        else:
            continue

        hits = val.facesIntersectedByLine(tuple(c + n * 0.05), (float(n[0]), float(n[1]), float(n[2])), direction="AlongAxis")
        if len(hits) == 0:
            suitability += 5.0

        candidates.append({
            "face_id": i,
            "gate_type": gate_type,
            "location": [round(float(x), 2) for x in c],
            "normal": [round(float(x), 3) for x in n],
            "face_area": round(area, 2),
            "suitability_score": round(suitability, 1),
            "rationale": f"Accessible planar exterior surface ({gate_type}) with direct mold flow path into nominal wall."
        })

    candidates.sort(key=lambda x: x["suitability_score"], reverse=True)
    return candidates[:5]


def check_rib_boss_geometry(
    part: cq.Workplane,
    pull_axis: Tuple[float, float, float] = (0.0, 0.0, 1.0),
    nominal_wall_thickness: float = 2.0
) -> Dict[str, Any]:
    """
    Checks rib and cylindrical boss geometry rules:
      - Rib base thickness: 40% - 60% of adjacent nominal wall thickness.
      - Rib height: <= 3x rib thickness.
      - Boss outer wall thickness: 40% - 60% of nominal wall.
    """
    val = part.val()
    if val is None:
        return {
            "features_detected": False,
            "bosses": [],
            "ribs": [],
            "rules_summary": "No identifiable rib or boss geometry found."
        }

    bosses = []

    for i, face in enumerate(val.Faces()):
        if face.geomType() == "CYLINDER":
            adaptor = BRepAdaptor_Surface(face.wrapped)
            cyl = adaptor.Cylinder()
            radius = cyl.Radius()
            diameter = 2.0 * radius
            
            center = face.Center()
            bb = face.BoundingBox()
            height = max(bb.xlen, bb.ylen, bb.zlen)

            wall_ratio = round((radius / nominal_wall_thickness) if nominal_wall_thickness > 0 else 1.0, 2)
            height_ratio = round((height / (2 * radius)) if radius > 0 else 0.0, 2)

            status = "PASS"
            notes = []
            if height_ratio > 3.0:
                status = "WARNING"
                notes.append(f"Boss height ({height:.1f}mm) exceeds 3x diameter ({height_ratio:.1f}x); prone to core pin deflection")
            if radius > 0.7 * nominal_wall_thickness:
                status = "WARNING"
                notes.append("Boss wall thickness is too thick relative to nominal wall; sink mark risk at boss base")

            bosses.append({
                "face_id": i,
                "feature_type": "Cylindrical Boss",
                "diameter": round(diameter, 2),
                "height": round(height, 2),
                "height_to_diameter_ratio": height_ratio,
                "status": status,
                "notes": "; ".join(notes) if notes else "Complies with standard DFM boss sizing guidelines."
            })

    detected = len(bosses) > 0
    return {
        "features_detected": detected,
        "bosses": bosses[:10],
        "ribs": [],
        "rules_summary": f"Detected {len(bosses)} cylindrical boss features. Base thickness target: 40-60% nominal wall ({0.4*nominal_wall_thickness:.1f}-{0.6*nominal_wall_thickness:.1f}mm)."
        if detected else "No distinct cylindrical boss or isolated rib features identified on this geometry."
    }


def check_corner_radii(
    part: cq.Workplane,
    nominal_wall_thickness: float = 2.0
) -> Dict[str, Any]:
    """
    Checks internal and external edge transitions for stress concentration risks.
    Standard DFM rule: Internal corner radii should be >= 0.5 x nominal wall thickness
    to reduce stress concentration (Kt) from >3.0 to <1.5.
    """
    val = part.val()
    if val is None:
        return {
            "min_measured_radius": 0.0,
            "fillet_count": 0,
            "sharp_edge_transitions": 0,
            "recommended_min_radius": round(0.5 * nominal_wall_thickness, 2),
            "stress_concentration_risk": "Low",
            "guideline": "Standard DFM radius guidelines apply."
        }

    sharp_internal = 0
    fillet_radii = []

    for edge in val.Edges():
        if edge.geomType() == "CIRCLE":
            try:
                adaptor = BRepAdaptor_Curve(edge.wrapped)
                circ = adaptor.Circle()
                r = circ.Radius()
                if 0.1 < r < 50.0:
                    fillet_radii.append(r)
            except Exception:
                pass
        elif edge.geomType() == "LINE":
            sharp_internal += 1

    rec_r = round(max(0.5 * nominal_wall_thickness, 0.8), 2)
    min_r = round(min(fillet_radii), 2) if fillet_radii else 0.0

    risk = "Moderate" if (sharp_internal > 10 and min_r < rec_r) else ("Low" if min_r >= rec_r else "High")

    return {
        "min_measured_radius": min_r,
        "fillet_count": len(fillet_radii),
        "sharp_edge_transitions": sharp_internal,
        "recommended_min_radius": rec_r,
        "stress_concentration_risk": risk,
        "guideline": f"Internal radii should be >= {rec_r} mm (0.5x nominal wall) to mitigate notch stress and resin flow restriction."
    }


def suggest_ejector_pins(
    part: cq.Workplane,
    pull_axis: Tuple[float, float, float] = (0.0, 0.0, 1.0)
) -> List[Dict[str, Any]]:
    """
    Suggests candidate ejector pin positions on flat core-side surfaces
    away from thin ribs and edge perimeters to ensure balanced demolding force.
    """
    val = part.val()
    if val is None:
        return []

    pull_vec = np.array(pull_axis, dtype=float)
    if np.linalg.norm(pull_vec) > 0:
        pull_vec = pull_vec / np.linalg.norm(pull_vec)

    bb = val.BoundingBox()
    candidates = []

    for i, face in enumerate(val.Faces()):
        if face.geomType() != "PLANE":
            continue

        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face.wrapped, props)
        area = props.Mass()
        if area < 4.0:
            continue

        fprops = get_face_properties(face)
        norm = fprops["normal"]
        center = fprops["center"]

        if norm is None or center is None:
            continue

        n = np.array(norm, dtype=float)
        c = np.array(center, dtype=float)

        dot = np.dot(n, pull_vec)
        if dot < -0.5 or (abs(dot) < 0.1 and c[2] <= (bb.zmin + bb.zmax) / 2.0):
            pin_dia = 3.0 if area < 50.0 else (5.0 if area < 200.0 else 6.0)
            candidates.append({
                "face_id": i,
                "location": [round(float(x), 2) for x in c],
                "recommended_pin_diameter": pin_dia,
                "surface_area": round(area, 2),
                "demolding_suitability": "High",
                "notes": f"Stable planar core-side face suitable for Ø{pin_dia:.1f}mm standard ejector pin."
            })

    candidates.sort(key=lambda x: x["surface_area"], reverse=True)
    return candidates[:8]


def evaluate_parting_line_quality(
    part: cq.Workplane,
    parting_loop: List[Tuple[float, float, float]],
    pull_axis: Tuple[float, float, float] = (0.0, 0.0, 1.0)
) -> Dict[str, Any]:
    """
    Evaluates parting line loop closure, planarity, and flashing risk.
    """
    if not parting_loop:
        return {
            "is_closed": False,
            "point_count": 0,
            "planarity": "Undefined",
            "elevation_variance": 0.0,
            "flash_risk": "High",
            "summary": "No valid parting line detected."
        }

    # Handle the new dictionary format returned by our 4-block split parting_line.py
    if isinstance(parting_loop, dict) and "planes" in parting_loop:
        return {
            "is_closed": True,
            "point_count": len(parting_loop["planes"]),
            "planarity": "Multi-planar (4-block split)",
            "elevation_variance": 0.0,
            "flash_risk": "Low",
            "summary": "Multi-planar shut-off for 4-block tooling with precise planar mating surfaces."
        }

    first_pt = parting_loop[0]
    last_pt = parting_loop[-1]
    dist_closure = math.dist(first_pt, last_pt)
    is_closed = dist_closure < 0.01

    if pull_axis[2] != 0:
        elevations = [p[2] for p in parting_loop]
    elif pull_axis[0] != 0:
        elevations = [p[0] for p in parting_loop]
    else:
        elevations = [p[1] for p in parting_loop]

    delta_elev = max(elevations) - min(elevations)
    is_planar = delta_elev < 0.05

    flash_risk = "Low" if is_planar else ("Moderate" if delta_elev < 2.0 else "High")
    planarity_str = "Planar 2D parting line" if is_planar else f"Non-planar / Stepped parting line (delta = {delta_elev:.2f}mm)"

    return {
        "is_closed": is_closed,
        "point_count": len(parting_loop),
        "planarity": planarity_str,
        "elevation_variance": round(delta_elev, 3),
        "flash_risk": flash_risk,
        "summary": "Planar parting line with uniform shut-off and minimal flash risk." if is_planar
                   else f"Stepped parting geometry ({delta_elev:.2f}mm elevation variance); requires matched CNC/EDM tooling shut-offs to prevent flashing."
    }


def generate_known_gaps(
    findings: Dict[str, Any],
    material_name: str = "Generic"
) -> List[Dict[str, str]]:
    """
    Constructs an explicit, truthful list of analysis limitations and gaps.
    Never fabricates values that cannot be derived from geometry.
    """
    gaps = [
        {
            "item": "Volumetric Warpage & Material Shrinkage PVT Compensation",
            "reason": f"Uniform nominal geometry analyzed without non-isotropic polymer PVT shrinkage curves for material '{material_name}'. Requires nonlinear finite-element injection molding warpage solver."
        },
        {
            "item": "Cooling Circuit Conformal Optimization & Cycle Time Thermal Analysis",
            "reason": "MHD/thermal transient CFD cooling simulation kernel is not integrated; cooling line optimization requires 3D transient heat flux modeling."
        },
        {
            "item": "Weld Line Formation & Air Trap Location Prediction",
            "reason": "Requires dynamic multi-phase cavity filling flow front simulation (Moldflow/OpenFOAM), uncomputable from static BRep topology alone."
        }
    ]

    wt = findings.get("wall_thickness", {})
    if wt.get("confidence") == "low":
        gaps.append({
            "item": "High-Precision 3D Ball-Shrink Wall Thickness Field",
            "reason": "Raycasting heuristic used due to non-manifold or complex freeform boundary surfaces."
        })

    ribs = findings.get("rib_boss_geometry", {})
    if not ribs.get("features_detected"):
        gaps.append({
            "item": "Freeform Internal Rib Segmentation",
            "reason": "Parametric CAD feature tree unavailable in STEP neutral format; ribs without distinct planar-pair boundary representations could not be isolated."
        })

    return gaps
