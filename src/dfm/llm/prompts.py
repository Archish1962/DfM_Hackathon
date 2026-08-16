SUMMARY_PROMPT = """
You are an expert injection molding design engineer.
Based on the following structured DfM findings, write a brief 2-3 sentence executive summary.
Do not hallucinate or fabricate geometric facts. Only narrate the structured data provided.

FINDINGS:
{findings}

EXECUTIVE SUMMARY:
"""

ISSUE_PROMPT = """
You are an expert injection molding design engineer.
Explain the following DfM issue in plain language (1-2 sentences) and suggest a standard remedy.
Do not hallucinate or fabricate geometric facts. Only narrate the structured data provided.

ISSUE DETAILS:
Category: {category}
Type: {issue_type}
Severity: {severity}
Measured Value: {measured_value}
Threshold Limit: {threshold}

EXPLANATION AND REMEDY:
"""
