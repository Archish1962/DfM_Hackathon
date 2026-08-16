import os
import tempfile
from dfm.report.pdf_gen import generate_pdf_report

def test_generate_pdf():
    findings = {
        "material": "Generic",
        "executive_summary": "This is a test summary.",
        "metrics": {
            "volume": 1000.5,
            "surface_area": 500.2,
            "bbox_dimensions": [10, 10, 10]
        },
        "issues": [
            {
                "issue_type": "Insufficient Draft",
                "severity": "fail",
                "measured_value": 0.5,
                "threshold": 1.0,
                "narrative": "This face has almost no draft."
            }
        ]
    }
    
    tmp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(tmp_dir, "test_report.pdf")
    
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        
    generate_pdf_report(findings, pdf_path)
    
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000 # Should be larger than 1KB
