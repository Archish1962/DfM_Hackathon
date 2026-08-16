import json
from typing import Dict, Any
from .prompts import SUMMARY_PROMPT, ISSUE_PROMPT
from .provider import generate

def narrate_findings(graded_findings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrates the narration of structured findings.
    Adds 'executive_summary' to the root and 'narrative' to each issue.
    """
    summary_text = generate(SUMMARY_PROMPT.format(findings=json.dumps(graded_findings.get("pass_fail_summary", {}))))
    graded_findings["executive_summary"] = summary_text
    
    for issue in graded_findings.get("issues", []):
        prompt = ISSUE_PROMPT.format(
            category=issue.get("category", "unknown"),
            issue_type=issue.get("issue_type", "unknown"),
            severity=issue.get("severity", "unknown"),
            measured_value=issue.get("measured_value", 0),
            threshold=issue.get("threshold", 0)
        )
        issue["narrative"] = generate(prompt)
        
    return graded_findings
