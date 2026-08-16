import os
from dfm.llm.narrate import narrate_findings

def test_fallback_narration(monkeypatch):
    # Ensure no API keys are present
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    
    graded_findings = {
        "material": "Generic",
        "pass_fail_summary": {"pass": 0, "warning": 1, "fail": 1},
        "issues": [
            {
                "category": "draft",
                "issue_type": "Insufficient Draft",
                "severity": "fail",
                "face_id": 1,
                "measured_value": 0.5,
                "threshold": 1.0
            }
        ]
    }
    
    result = narrate_findings(graded_findings)
    
    # Check summary
    assert "executive_summary" in result
    assert "manufacturability issues" in result["executive_summary"]
    
    # Check issue
    assert len(result["issues"]) == 1
    issue = result["issues"][0]
    assert "narrative" in issue
    assert "violates standard DfM guidelines" in issue["narrative"]
