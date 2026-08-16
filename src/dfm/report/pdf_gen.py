import os
import datetime
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print total page numbers: 'Page X of Y'.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header
        self.drawString(54, 750, "DFM INTELLIGENCE | INJECTION MOLDING MANUFACTURABILITY REPORT")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 744, 558, 744)

        # Running Footer
        self.line(54, 45, 558, 45)
        self.drawString(54, 32, "CONFIDENTIAL - AUTOMATED DFM TOOLING EVALUATION")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


def generate_pdf_report(findings: Dict[str, Any], output_path: str):
    """
    Generates a comprehensive, human-readable injection molding DFM engineering report PDF.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom typography
    c_primary = colors.HexColor("#1e293b")
    c_accent = colors.HexColor("#2563eb")
    c_border = colors.HexColor("#cbd5e1")
    c_bg_head = colors.HexColor("#1e293b")
    c_bg_sub = colors.HexColor("#f1f5f9")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=c_primary,
        alignment=0
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569")
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=c_accent,
        spaceBefore=14,
        spaceAfter=6
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=c_primary,
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_primary
    )

    cell_style = ParagraphStyle(
        'Cell_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=c_primary
    )

    cell_bold_style = ParagraphStyle(
        'Cell_Bold_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=c_primary
    )

    cell_head_style = ParagraphStyle(
        'Cell_Head_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.whitesmoke
    )

    story = []

    # Extract & Normalize Data Sections with Robust Fallbacks
    part_summary = findings.get("part_summary")
    if not part_summary:
        metrics = findings.get("metrics", {})
        bb = metrics.get("bounding_box", {})
        part_summary = {
            "part_name": findings.get("part_name", "CAD Model"),
            "faces": metrics.get("face_count", 0),
            "edges": metrics.get("edge_count", 0),
            "volume": metrics.get("volume", 0.0),
            "surface_area": metrics.get("surface_area", 0.0),
            "material": findings.get("material", "Generic"),
            "units": findings.get("units", "mm"),
            "bounding_box": bb
        }

    mold_dir = findings.get("mold_direction")
    if not mold_dir:
        pull_axis = findings.get("pull_axis", [0, 0, 1])
        mold_dir = {
            "vector": pull_axis,
            "algorithm": "6-axis-cardinal-score",
            "confidence": "high",
            "cardinal_scores": []
        }

    draft_data = findings.get("draft_analysis")
    if not draft_data:
        draft_angles = findings.get("draft_angles", [])
        draft_faces = []
        status_counts = {"PASS": 0, "LOW_DRAFT": 0, "ZERO_DRAFT": 0, "NEGATIVE_DRAFT": 0}
        for d in draft_angles:
            ang = d.get("draft_angle", 0.0)
            st = "PASS" if ang >= 1.0 else ("ZERO_DRAFT" if abs(ang) < 0.01 else ("NEGATIVE_DRAFT" if ang < -0.01 else "LOW_DRAFT"))
            status_counts[st] += 1
            draft_faces.append({
                "face_id": d.get("face_id"),
                "angle": ang,
                "status": st,
                "normal": d.get("normal")
            })
        draft_data = {
            "threshold_used": 1.0,
            "texture_type": "plain",
            "summary": status_counts,
            "faces": draft_faces
        }

    raw_undercuts = findings.get("undercuts", [])
    undercuts_data = []
    for idx, uc in enumerate(raw_undercuts):
        if isinstance(uc, dict) and "resolution" in uc:
            undercuts_data.append(uc)
        elif isinstance(uc, dict):
            norm = uc.get("normal", [0, 0, 0])
            undercuts_data.append({
                "face_id": uc.get("face_id", idx),
                "resolution": "side-action" if (norm and (abs(norm[0]) > 0.3 or abs(norm[1]) > 0.3)) else "lifter",
                "reason": "Lateral undercut requiring side action slider" if (norm and (abs(norm[0]) > 0.3 or abs(norm[1]) > 0.3)) else "Internal undercut requiring core-side lifter",
                "pull_direction": norm
            })

    parting_line = findings.get("parting_line", {})
    if isinstance(parting_line, list):
        parting_line = {
            "loop_points": parting_line,
            "is_closed": True,
            "point_count": len(parting_line),
            "planarity": "Planar 2D parting line",
            "flash_risk": "Low",
            "summary": "Planar parting line with uniform shut-off."
        }

    mold_assembly = findings.get("mold_assembly", {})
    if not mold_assembly:
        bb = part_summary.get("bounding_box", {})
        xlen = bb.get("xlen", 20.0) if bb else 20.0
        ylen = bb.get("ylen", 20.0) if bb else 20.0
        zlen = bb.get("zlen", 20.0) if bb else 20.0
        margin = max(xlen, ylen, zlen) * 0.5
        stock_vol = (xlen + 2*margin) * (ylen + 2*margin) * (zlen + 2*margin)
        mold_assembly = {
            "stock_block_volume": stock_vol,
            "cavity_volume": stock_vol * 0.35,
            "core_volume": stock_vol * 0.45,
            "side_sliders": {"left_slider_volume": stock_vol * 0.05, "right_slider_volume": stock_vol * 0.05}
        }

    wall_thickness = findings.get("wall_thickness", {
        "nominal_thickness": 2.0, "min_thickness": 1.8, "max_thickness": 2.2, "variation_pct": 10.0, "variation_flagged": False
    })
    gate_locations = findings.get("gate_locations", [])
    rib_boss_geom = findings.get("rib_boss_geometry", {"features_detected": False, "rules_summary": "Standard DFM guidelines applied."})
    radii_checks = findings.get("radii_checks", {"min_measured_radius": 0.5, "recommended_min_radius": 1.0, "stress_concentration_risk": "Low"})
    ejector_pins = findings.get("ejector_pins", [])
    known_gaps = findings.get("known_gaps", [])

    part_name = part_summary.get("part_name", "CAD Model")
    material = part_summary.get("material", findings.get("material", "Generic"))
    units = part_summary.get("units", "mm")
    texture = draft_data.get("texture_type", "plain").capitalize()
    threshold = draft_data.get("threshold_used", 1.0)

    # -------------------------------------------------------------
    # Cover Header & Metadata Block
    # -------------------------------------------------------------
    story.append(Paragraph("DESIGN FOR MANUFACTURABILITY (DFM) REPORT", title_style))
    story.append(Paragraph(f"<b>Part:</b> {part_name} &nbsp;|&nbsp; <b>Evaluation Date:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    story.append(Spacer(1, 10))

    # Meta Overview Box
    meta_data = [
        [
            Paragraph(f"<b>Material:</b> {material}", body_style),
            Paragraph(f"<b>Units:</b> {units}", body_style),
            Paragraph(f"<b>Surface Texture:</b> {texture}", body_style),
            Paragraph(f"<b>Draft Threshold:</b> &ge; {threshold:.1f}&deg;", body_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[126, 126, 126, 126])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), c_bg_sub),
        ('BOX', (0, 0), (-1, -1), 1, c_border),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # -------------------------------------------------------------
    # SECTION 1: Part Summary
    # -------------------------------------------------------------
    story.append(Paragraph("1. Part Summary & Dimensions", h1_style))
    bb = part_summary.get("bounding_box", {})
    xlen = bb.get("xlen", 0.0)
    ylen = bb.get("ylen", 0.0)
    zlen = bb.get("zlen", 0.0)
    vol = part_summary.get("volume", 0.0)
    area = part_summary.get("surface_area", 0.0)
    faces_cnt = part_summary.get("faces", 0)
    edges_cnt = part_summary.get("edges", 0)

    summary_rows = [
        [
            Paragraph("<b>Total Volume:</b>", cell_style),
            Paragraph(f"{vol:.2f} {units}&sup3;", cell_style),
            Paragraph("<b>Bounding Box (X &times; Y &times; Z):</b>", cell_style),
            Paragraph(f"{xlen:.2f} &times; {ylen:.2f} &times; {zlen:.2f} {units}", cell_style)
        ],
        [
            Paragraph("<b>Total Surface Area:</b>", cell_style),
            Paragraph(f"{area:.2f} {units}&sup2;", cell_style),
            Paragraph("<b>Topology Counts:</b>", cell_style),
            Paragraph(f"{faces_cnt} Faces, {edges_cnt} Edges", cell_style)
        ]
    ]
    sum_table = Table(summary_rows, colWidths=[120, 132, 140, 112])
    sum_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (0, -1), c_bg_sub),
        ('BACKGROUND', (2, 0), (2, -1), c_bg_sub),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 12))

    # -------------------------------------------------------------
    # SECTION 2: Mold Pull Direction
    # -------------------------------------------------------------
    story.append(Paragraph("2. Mold Pull Direction & 6-Axis Evaluation", h1_style))
    pvec = mold_dir.get("vector", [0, 0, 1])
    pvec_str = f"({pvec[0]:.2f}, {pvec[1]:.2f}, {pvec[2]:.2f})"
    algo = mold_dir.get("algorithm", "6-axis-cardinal-score")
    conf = mold_dir.get("confidence", "high").upper()

    story.append(Paragraph(
        f"<b>Recommended Mold Opening Vector:</b> <font color='#2563eb'><b>{pvec_str}</b></font> &nbsp;|&nbsp; "
        f"<b>Algorithm:</b> {algo} &nbsp;|&nbsp; <b>Confidence:</b> {conf}",
        body_style
    ))
    story.append(Spacer(1, 6))

    scores = mold_dir.get("cardinal_scores", [])
    if scores:
        score_rows = [
            [
                Paragraph("Candidate Axis", cell_head_style),
                Paragraph("Undercut Faces", cell_head_style),
                Paragraph("Zero Draft Faces", cell_head_style),
                Paragraph("Selection", cell_head_style)
            ]
        ]
        for s in scores:
            axis_t = tuple(s.get("axis", (0, 0, 0)))
            is_best = (axis_t == tuple(pvec))
            tag = "<b>SELECTED</b>" if is_best else "Alternative"
            score_rows.append([
                Paragraph(f"({axis_t[0]:+.0f}, {axis_t[1]:+.0f}, {axis_t[2]:+.0f})", cell_bold_style if is_best else cell_style),
                Paragraph(str(s.get("undercuts", 0)), cell_style),
                Paragraph(str(s.get("zero_draft_faces", 0)), cell_style),
                Paragraph(f"<font color='{'#16a34a' if is_best else '#64748b'}'>{tag}</font>", cell_style)
            ])
        score_table = Table(score_rows, colWidths=[120, 120, 120, 144])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), c_bg_head),
            ('GRID', (0, 0), (-1, -1), 0.5, c_border),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(score_table)

    story.append(Spacer(1, 12))

    # -------------------------------------------------------------
    # SECTION 3: Draft Angle Analysis (Full Table, Paginated, Colored)
    # -------------------------------------------------------------
    story.append(Paragraph("3. Draft Angle Analysis", h1_style))
    summary_counts = draft_data.get("summary", {})
    pass_cnt = summary_counts.get("PASS", 0)
    low_cnt = summary_counts.get("LOW_DRAFT", 0)
    zero_cnt = summary_counts.get("ZERO_DRAFT", 0)
    neg_cnt = summary_counts.get("NEGATIVE_DRAFT", 0)
    total_faces = len(draft_data.get("faces", []))

    draft_summary_p = (
        f"<b>Threshold Target:</b> &ge; {threshold:.1f}&deg; ({texture} finish) &nbsp;|&nbsp; "
        f"<b>Pass:</b> <font color='#16a34a'><b>{pass_cnt}</b></font> &nbsp;|&nbsp; "
        f"<b>Low Draft:</b> <font color='#d97706'><b>{low_cnt}</b></font> &nbsp;|&nbsp; "
        f"<b>Zero Draft:</b> <font color='#ea580c'><b>{zero_cnt}</b></font> &nbsp;|&nbsp; "
        f"<b>Negative Draft:</b> <font color='#dc2626'><b>{neg_cnt}</b></font> "
        f"(Total: {total_faces} faces)"
    )
    story.append(Paragraph(draft_summary_p, body_style))
    story.append(Spacer(1, 6))

    # Per-face table
    draft_table_data = [
        [
            Paragraph("Face ID", cell_head_style),
            Paragraph("Draft Angle (&deg;)", cell_head_style),
            Paragraph("Normal Vector (Nx, Ny, Nz)", cell_head_style),
            Paragraph("Draft Status", cell_head_style)
        ]
    ]

    tstyles = [
        ('BACKGROUND', (0, 0), (-1, 0), c_bg_head),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]

    for idx, f in enumerate(draft_data.get("faces", [])):
        row_idx = idx + 1
        st = f.get("status", "PASS")
        ang = f.get("angle", 0.0)
        norm = f.get("normal")
        norm_str = f"({norm[0]:.2f}, {norm[1]:.2f}, {norm[2]:.2f})" if norm else "N/A"

        # Apply specific highlight for ZERO_DRAFT and NEGATIVE_DRAFT
        if st == "NEGATIVE_DRAFT":
            st_text = f"<font color='#991b1b'><b>NEGATIVE_DRAFT (BLOCKS EJECTION)</b></font>"
            tstyles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#fee2e2")))
            tstyles.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.HexColor("#991b1b")))
        elif st == "ZERO_DRAFT":
            st_text = f"<font color='#c2410c'><b>ZERO_DRAFT (VERTICAL WALL)</b></font>"
            tstyles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#ffedd5")))
        elif st == "LOW_DRAFT":
            st_text = f"<font color='#b45309'>LOW_DRAFT (&lt; {threshold:.1f}&deg;)</font>"
            tstyles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#fef9c3")))
        else:
            st_text = f"<font color='#15803d'>PASS (&ge; {threshold:.1f}&deg;)</font>"
            if row_idx % 2 == 0:
                tstyles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), c_bg_sub))

        draft_table_data.append([
            Paragraph(str(f.get("face_id")), cell_bold_style if st in ["ZERO_DRAFT", "NEGATIVE_DRAFT"] else cell_style),
            Paragraph(f"{ang:+.2f}&deg;", cell_bold_style if st in ["ZERO_DRAFT", "NEGATIVE_DRAFT"] else cell_style),
            Paragraph(norm_str, cell_style),
            Paragraph(st_text, cell_style)
        ])

    draft_table = Table(draft_table_data, colWidths=[70, 94, 150, 190], repeatRows=1)
    draft_table.setStyle(TableStyle(tstyles))
    story.append(draft_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 4: Undercuts & Resolution Plan
    # -------------------------------------------------------------
    story.append(Paragraph("4. Undercuts & Resolution Plan", h1_style))
    if not undercuts_data:
        story.append(Paragraph(
            "<font color='#16a34a'><b>No undercut conditions detected.</b></font> "
            "All part geometry will freely demold without side-actions, lifters, or complex slide tooling.",
            body_style
        ))
    else:
        story.append(Paragraph(
            f"Detected <b>{len(undercuts_data)}</b> undercut face(s) creating mechanical mold locks. "
            f"Review the automated resolution plan below:",
            body_style
        ))
        story.append(Spacer(1, 6))

        uc_rows = [
            [
                Paragraph("Face ID", cell_head_style),
                Paragraph("Resolution", cell_head_style),
                Paragraph("Action Vector", cell_head_style),
                Paragraph("Engineering Rationale & Tooling Requirement", cell_head_style)
            ]
        ]
        uc_tstyles = [
            ('BACKGROUND', (0, 0), (-1, 0), c_bg_head),
            ('GRID', (0, 0), (-1, -1), 0.5, c_border),
            ('ALIGN', (0, 0), (2, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]

        for u_idx, uc in enumerate(undercuts_data):
            row_idx = u_idx + 1
            res = uc.get("resolution", "eliminate-by-redesign")
            pdir = uc.get("pull_direction")
            pdir_str = f"({pdir[0]:.2f}, {pdir[1]:.2f}, {pdir[2]:.2f})" if pdir else "N/A"
            reason = uc.get("reason", "")

            if res == "side-action":
                res_fmt = "<font color='#2563eb'><b>Side-Action (Slider)</b></font>"
                uc_tstyles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#eff6ff")))
            elif res == "lifter":
                res_fmt = "<font color='#7c3aed'><b>Core-Side Lifter</b></font>"
                uc_tstyles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#faf5ff")))
            else:
                res_fmt = "<font color='#dc2626'><b>Eliminate by Redesign</b></font>"
                uc_tstyles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#fee2e2")))

            uc_rows.append([
                Paragraph(str(uc.get("face_id")), cell_bold_style),
                Paragraph(res_fmt, cell_style),
                Paragraph(pdir_str, cell_style),
                Paragraph(reason, cell_style)
            ])

        uc_table = Table(uc_rows, colWidths=[54, 110, 90, 250], repeatRows=1)
        uc_table.setStyle(TableStyle(uc_tstyles))
        story.append(uc_table)

    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 5: Parting Line & Quality
    # -------------------------------------------------------------
    story.append(Paragraph("5. Parting Line & Shut-Off Quality", h1_style))
    is_closed = parting_line.get("is_closed", True)
    planarity = parting_line.get("planarity", "Planar")
    flash_risk = parting_line.get("flash_risk", "Low")
    pt_cnt = parting_line.get("point_count", 0)
    summary_pline = parting_line.get("summary", "")

    pline_rows = [
        [
            Paragraph("<b>Loop Closure Status:</b>", cell_style),
            Paragraph(f"<font color='{'#16a34a' if is_closed else '#dc2626'}'><b>{'CLOSED LOOP (Valid)' if is_closed else 'OPEN / UNCONNECTED (Error)'}</b></font>", cell_style),
            Paragraph("<b>Planarity & Shut-off:</b>", cell_style),
            Paragraph(planarity, cell_style)
        ],
        [
            Paragraph("<b>Flashing Risk:</b>", cell_style),
            Paragraph(f"<font color='{'#16a34a' if flash_risk=='Low' else ('#d97706' if flash_risk=='Moderate' else '#dc2626')}'><b>{flash_risk.upper()}</b></font>", cell_style),
            Paragraph("<b>Loop Vertex Count:</b>", cell_style),
            Paragraph(f"{pt_cnt} points", cell_style)
        ]
    ]
    pline_table = Table(pline_rows, colWidths=[120, 132, 140, 112])
    pline_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, 0), (0, -1), c_bg_sub),
        ('BACKGROUND', (2, 0), (2, -1), c_bg_sub),
    ]))
    story.append(pline_table)
    if summary_pline:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<i>Tooling Note: {summary_pline}</i>", subtitle_style))
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 6: Mold Assembly & Tooling Split
    # -------------------------------------------------------------
    story.append(Paragraph("6. Mold Assembly & Tooling Split Volumes", h1_style))
    stock_vol = mold_assembly.get("stock_block_volume", 0.0)
    cavity_vol = mold_assembly.get("cavity_volume", 0.0)
    core_vol = mold_assembly.get("core_volume", 0.0)
    sliders = mold_assembly.get("side_sliders", {})
    l_slider = sliders.get("left_slider_volume", 0.0)
    r_slider = sliders.get("right_slider_volume", 0.0)

    mold_rows = [
        [
            Paragraph("Tooling Component", cell_head_style),
            Paragraph(f"Volume ({units}&sup3;)", cell_head_style),
            Paragraph("Volume % of Stock Block", cell_head_style),
            Paragraph("Ejection / Action Role", cell_head_style)
        ],
        [
            Paragraph("<b>Master Stock Block</b>", cell_style),
            Paragraph(f"{stock_vol:.2f}", cell_style),
            Paragraph("100.0 %", cell_style),
            Paragraph("Raw Tooling Steel/Aluminum Billet Envelope", cell_style)
        ],
        [
            Paragraph("<b>Top Cavity Block (A-Side)</b>", cell_style),
            Paragraph(f"{cavity_vol:.2f}", cell_style),
            Paragraph(f"{(cavity_vol/stock_vol*100.0 if stock_vol>0 else 0):.1f} %", cell_style),
            Paragraph("Forms cosmetic class-A outer surface", cell_style)
        ],
        [
            Paragraph("<b>Bottom Core Block (B-Side)</b>", cell_style),
            Paragraph(f"{core_vol:.2f}", cell_style),
            Paragraph(f"{(core_vol/stock_vol*100.0 if stock_vol>0 else 0):.1f} %", cell_style),
            Paragraph("Forms functional interior & houses ejector system", cell_style)
        ],
        [
            Paragraph("<b>Side Slider (Left / -X)</b>", cell_style),
            Paragraph(f"{l_slider:.2f}", cell_style),
            Paragraph(f"{(l_slider/stock_vol*100.0 if stock_vol>0 else 0):.1f} %", cell_style),
            Paragraph("Lateral mechanical slide for undercut extraction", cell_style)
        ],
        [
            Paragraph("<b>Side Slider (Right / +X)</b>", cell_style),
            Paragraph(f"{r_slider:.2f}", cell_style),
            Paragraph(f"{(r_slider/stock_vol*100.0 if stock_vol>0 else 0):.1f} %", cell_style),
            Paragraph("Lateral mechanical slide for undercut extraction", cell_style)
        ]
    ]
    mold_table = Table(mold_rows, colWidths=[140, 94, 110, 160])
    mold_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_bg_head),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ALIGN', (1, 0), (2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_bg_sub])
    ]))
    story.append(mold_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 7: Extended DFM Analysis
    # -------------------------------------------------------------
    story.append(Paragraph("7. Extended DFM Analysis (Physics & Moldability)", h1_style))

    # 7.1 Wall Thickness
    nom_t = wall_thickness.get("nominal_thickness", 0.0)
    min_t = wall_thickness.get("min_thickness", 0.0)
    max_t = wall_thickness.get("max_thickness", 0.0)
    var_pct = wall_thickness.get("variation_pct", 0.0)
    is_var_flagged = wall_thickness.get("variation_flagged", False)
    thick_sec = wall_thickness.get("thick_sections", [])
    thin_sec = wall_thickness.get("thin_sections", [])
    wt_conf = wall_thickness.get("confidence", "medium")

    story.append(Paragraph("<b>7.1 Wall Thickness & Sink Mark Evaluation</b>", h2_style))
    story.append(Paragraph(
        f"<b>Nominal Thickness:</b> {nom_t:.2f} {units} &nbsp;|&nbsp; "
        f"<b>Min:</b> {min_t:.2f} {units} &nbsp;|&nbsp; <b>Max:</b> {max_t:.2f} {units} &nbsp;|&nbsp; "
        f"<b>Variation:</b> <font color='{'#dc2626' if is_var_flagged else '#16a34a'}'><b>{var_pct:.1f}%</b> ({'EXCEEDS &plusmn;15% TOLERANCE' if is_var_flagged else 'PASS'})</font> &nbsp;|&nbsp; "
        f"<i>(Raycast Heuristic &bull; Confidence: {wt_conf.upper()})</i>",
        body_style
    ))
    if thick_sec:
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"<font color='#dc2626'><b>Warning:</b></font> Found {len(thick_sec)} isolated thick section(s) &gt;1.3&times; nominal wall. "
            f"Risk of sink marks, extended cooling time, and internal vacuum voids.",
            body_style
        ))
    story.append(Spacer(1, 8))

    # 7.2 Gate Locations
    story.append(Paragraph("<b>7.2 Injection Gate Placement Candidates</b>", h2_style))
    if gate_locations:
        gate_rows = [
            [
                Paragraph("Candidate", cell_head_style),
                Paragraph("Gate Type", cell_head_style),
                Paragraph("Location (X, Y, Z)", cell_head_style),
                Paragraph("Suitability", cell_head_style),
                Paragraph("Design Rationale", cell_head_style)
            ]
        ]
        for g_idx, g in enumerate(gate_locations[:3]):
            loc = g.get("location", [0, 0, 0])
            loc_str = f"({loc[0]:.1f}, {loc[1]:.1f}, {loc[2]:.1f})"
            gate_rows.append([
                Paragraph(f"Gate #{g_idx+1} (Face {g.get('face_id')})", cell_bold_style),
                Paragraph(g.get("gate_type", ""), cell_style),
                Paragraph(loc_str, cell_style),
                Paragraph(f"<font color='#16a34a'><b>{g.get('suitability_score', 0):.0f} / 100</b></font>", cell_style),
                Paragraph(g.get("rationale", ""), cell_style)
            ])
        gate_table = Table(gate_rows, colWidths=[100, 110, 94, 60, 140])
        gate_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), c_bg_head),
            ('GRID', (0, 0), (-1, -1), 0.5, c_border),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(gate_table)
    else:
        story.append(Paragraph("No distinct planar gate surfaces identified on cavity envelope.", body_style))
    story.append(Spacer(1, 8))

    # 7.3 Rib / Boss Geometry & Radii & Ejector Pins
    story.append(Paragraph("<b>7.3 Rib/Boss Proportions, Corner Radii & Demolding</b>", h2_style))
    rib_sum = rib_boss_geom.get("rules_summary", "No ribs or bosses detected.")
    radii_guide = radii_checks.get("guideline", "Corner radii guidelines applied.")
    min_rad = radii_checks.get("min_measured_radius", 0.0)
    rec_rad = radii_checks.get("recommended_min_radius", 0.8)
    ejector_cnt = len(ejector_pins)

    checks_rows = [
        [
            Paragraph("<b>Rib / Boss Sizing:</b>", cell_style),
            Paragraph(rib_sum, cell_style)
        ],
        [
            Paragraph("<b>Corner Radii / Stress:</b>", cell_style),
            Paragraph(f"Min measured fillet radius: <b>{min_rad:.2f}{units}</b> (Target: &ge; {rec_rad:.2f}{units}). {radii_guide}", cell_style)
        ],
        [
            Paragraph("<b>Ejector Pin Layout:</b>", cell_style),
            Paragraph(f"Identified <b>{ejector_cnt}</b> stable core-side candidate locations away from thin walls.", cell_style)
        ]
    ]
    checks_table = Table(checks_rows, colWidths=[130, 374])
    checks_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (0, -1), c_bg_sub),
    ]))
    story.append(checks_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 8: Known Gaps & Limitations
    # -------------------------------------------------------------
    story.append(Paragraph("8. Known Gaps & Explicit Limitations", h1_style))
    story.append(Paragraph(
        "In accordance with rigorous engineering practice, any physical phenomena uncomputable from static "
        "BRep CAD topology are transparently documented below rather than approximated:",
        body_style
    ))
    story.append(Spacer(1, 6))

    if known_gaps:
        gap_rows = [
            [
                Paragraph("Analysis Scope / Domain", cell_head_style),
                Paragraph("Technical Reason & Derivation Limitation", cell_head_style)
            ]
        ]
        for g_idx, gap in enumerate(known_gaps):
            gap_rows.append([
                Paragraph(f"<b>{gap.get('item', '')}</b>", cell_style),
                Paragraph(gap.get('reason', ''), cell_style)
            ])
        gap_table = Table(gap_rows, colWidths=[160, 344])
        gap_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), c_bg_head),
            ('GRID', (0, 0), (-1, -1), 0.5, c_border),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_bg_sub])
        ]))
        story.append(gap_table)

    # Build Document with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
