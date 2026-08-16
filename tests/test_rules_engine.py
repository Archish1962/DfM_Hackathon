from dfm.rules.engine import evaluate_part

def test_evaluate_part():
    findings = {
        "draft_angles": [
            {"face_id": 1, "draft_angle": 0.8}, # Fail for ABS (min 1.0), Pass for PP (min 0.5)
            {"face_id": 2, "draft_angle": 1.2}, # Warning for ABS (marginal 1.5), Pass for PP
            {"face_id": 3, "draft_angle": 90.0} # Ignore (horizontal)
        ],
        "undercuts": [
            {"face_id": 4, "dot": -0.5}
        ]
    }
    
    # Test ABS
    res_abs = evaluate_part(findings, "ABS")
    assert res_abs["material"] == "ABS"
    
    issues_abs = res_abs["issues"]
    assert len(issues_abs) == 3 # face 1 (fail), face 2 (warning), undercut (fail)
    
    fail_issues_abs = [i for i in issues_abs if i["severity"] == "fail"]
    assert len(fail_issues_abs) == 2
    
    # Test PP
    res_pp = evaluate_part(findings, "PP")
    assert res_pp["material"] == "PP"
    
    issues_pp = res_pp["issues"]
    # For PP, face 1 (0.8) > min (0.5) but < marginal (1.0), so Warning.
    # Face 2 (1.2) > marginal (1.0), so Pass.
    # Undercut is always fail.
    assert len(issues_pp) == 2 # face 1 (warning), undercut (fail)
    assert res_pp["pass_fail_summary"]["pass"] == 1 # face 2 passed
    assert res_pp["pass_fail_summary"]["warning"] == 1 # face 1 warned
    assert res_pp["pass_fail_summary"]["fail"] == 1 # undercut failed
