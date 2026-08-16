from typing import List, Dict, Any
from .material_profiles import get_profile

def evaluate_part(geometry_findings: Dict[str, Any], material_name: str) -> Dict[str, Any]:
    """
    Evaluates raw geometry findings against the thresholds defined by the material profile.
    Returns a graded list of issues (warnings/fails).
    """
    profile = get_profile(material_name)
    
    graded_findings = {
        "material": profile.name,
        "issues": [],
        "pass_fail_summary": {"pass": 0, "warning": 0, "fail": 0}
    }
    
    # Evaluate drafts
    for draft in geometry_findings.get("draft_angles", []):
        angle = draft.get("draft_angle", 0.0)
        face_id = draft.get("face_id")
        
        # Ignore horizontal faces (top/bottom surfaces with high |draft|)
        if abs(angle) > 45.0:
            continue
            
        if abs(angle) < profile.min_draft_angle:
            severity = "fail"
            issue_type = "Insufficient Draft"
            threshold = profile.min_draft_angle
        elif abs(angle) < profile.marginal_draft_angle:
            severity = "warning"
            issue_type = "Marginal Draft"
            threshold = profile.marginal_draft_angle
        else:
            graded_findings["pass_fail_summary"]["pass"] += 1
            continue
            
        graded_findings["issues"].append({
            "category": "draft",
            "issue_type": issue_type,
            "severity": severity,
            "face_id": face_id,
            "measured_value": angle,
            "threshold": threshold
        })
        graded_findings["pass_fail_summary"][severity] += 1
        
    # Evaluate undercuts
    for uc in geometry_findings.get("undercuts", []):
        graded_findings["issues"].append({
            "category": "undercut",
            "issue_type": "Undercut Detected",
            "severity": "fail",
            "face_id": uc.get("face_id"),
            "measured_value": uc.get("dot", 0.0),
            "threshold": 0.0
        })
        graded_findings["pass_fail_summary"]["fail"] += 1
        
    return graded_findings
