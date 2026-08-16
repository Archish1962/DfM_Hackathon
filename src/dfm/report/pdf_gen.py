from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from typing import Dict, Any

def generate_pdf_report(findings: Dict[str, Any], output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = styles['Title']
    h1_style = styles['Heading1']
    h2_style = styles['Heading2']
    normal_style = styles['Normal']
    
    story = []
    
    # Title
    story.append(Paragraph("DfM Intelligence Analysis Report", title_style))
    story.append(Spacer(1, 12))
    
    # Material
    story.append(Paragraph(f"<b>Material Profile:</b> {findings.get('material', 'Unknown')}", normal_style))
    story.append(Spacer(1, 12))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", h1_style))
    story.append(Paragraph(findings.get('executive_summary', 'No summary available.'), normal_style))
    story.append(Spacer(1, 24))
    
    # Metrics
    if 'metrics' in findings:
        story.append(Paragraph("Part Metrics", h1_style))
        metrics = findings['metrics']
        vol = metrics.get('volume', 0)
        area = metrics.get('surface_area', 0)
        story.append(Paragraph(f"Volume: {vol:.2f} mm³", normal_style))
        story.append(Paragraph(f"Surface Area: {area:.2f} mm²", normal_style))
        story.append(Spacer(1, 24))
        
    # Issues
    story.append(Paragraph("Identified Issues", h1_style))
    issues = findings.get('issues', [])
    if not issues:
        story.append(Paragraph("No critical manufacturability issues found.", normal_style))
    else:
        # Table of issues
        data = [["Type", "Severity", "Measured", "Threshold"]]
        for issue in issues:
            data.append([
                issue.get('issue_type', ''),
                issue.get('severity', '').upper(),
                f"{issue.get('measured_value', 0):.2f}",
                f"{issue.get('threshold', 0):.2f}"
            ])
            
        t = Table(data, colWidths=[150, 80, 80, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ]))
        story.append(t)
        story.append(Spacer(1, 24))
        
        # Narratives
        story.append(Paragraph("Issue Narratives", h2_style))
        for idx, issue in enumerate(issues):
            story.append(Paragraph(f"<b>{idx+1}. {issue.get('issue_type')}</b>", normal_style))
            story.append(Paragraph(issue.get('narrative', ''), normal_style))
            story.append(Spacer(1, 12))
            
    doc.build(story)
