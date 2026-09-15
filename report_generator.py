import io
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage, KeepTogether
)
from PIL import Image as PILImage


def generate_compliance_pdf_report(
    scan_id: int,
    product_name: str,
    score: int,
    has_violation: bool,
    fields: List[Dict[str, Any]],
    created_at: Optional[datetime] = None,
    user_name: Optional[str] = None,
    annotated_image_b64: Optional[str] = None,
    brand_name: Optional[str] = None,
) -> io.BytesIO:
    """
    Generates a professional Legal Metrology Compliance Audit PDF report
    using ReportLab Platypus, incorporating the SIH26034 hackathon format
    with PackSight branding and itemized rule verification table.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )

    section_head_style = ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )

    cell_bold_style = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )

    cell_body_style = ParagraphStyle(
        "CellBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )

    cell_code_style = ParagraphStyle(
        "CellCode",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748b"),
    )

    elements = []

    # Title and Subtitle
    elements.append(Paragraph("PackSight — Legal Metrology Compliance Report", title_style))
    elements.append(
        Paragraph(
            "Legal Metrology (Packaged Commodities) Rules, 2011 — Automated Audit Certificate",
            subtitle_style,
        )
    )

    # Divider
    elements.append(
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3b82f6"), spaceAfter=12)
    )

    # Status determination
    status_label = "NON-COMPLIANT" if has_violation else "COMPLIANT"
    status_hex = "#b91c1c" if has_violation else "#15803d"

    date_str = created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if created_at else datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Summary Metadata Box
    brand_display = brand_name if (brand_name and brand_name != "Packaged Commodity") else "N/A"
    summary_data = [
        [
            Paragraph(f"<b>Product Name:</b> {product_name or 'N/A'}", body_style),
            Paragraph(f"<b>Identified Brand:</b> {brand_display}", body_style),
        ],
        [
            Paragraph(f"<b>Scan ID:</b> #{scan_id}", body_style),
            Paragraph(f"<b>Audit Date:</b> {date_str}", body_style),
        ],
        [
            Paragraph(f"<b>Auditor / User:</b> {user_name or 'System Auditor'}", body_style),
            Paragraph(
                f"<b>Score & Verdict:</b> <b>{score}%</b> — <font color='{status_hex}'><b>{status_label}</b></font>",
                body_style,
            ),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[270, 270])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # Itemized Declarations Section
    elements.append(Paragraph("Itemized LMPC Rule Verification", section_head_style))

    # Table Header
    headers = [
        Paragraph("<b>Rule Code</b>", cell_bold_style),
        Paragraph("<b>Mandatory Declaration</b>", cell_bold_style),
        Paragraph("<b>Status</b>", cell_bold_style),
        Paragraph("<b>Extracted Evidence / Audit Details</b>", cell_bold_style),
    ]

    table_data = [headers]

    for f in fields:
        rule_id = str(f.get("rule_id", "—"))
        field_name = str(f.get("field", "—"))
        verdict = str(f.get("verdict", "review")).upper()
        evidence = str(f.get("evidence", "No text detected"))

        if verdict == "PASS":
            v_color = "#16a34a"
            v_text = f"<font color='{v_color}'><b>PASS</b></font>"
        elif verdict == "FAIL":
            v_color = "#dc2626"
            v_text = f"<font color='{v_color}'><b>VIOLATION</b></font>"
        else:
            v_color = "#d97706"
            v_text = f"<font color='{v_color}'><b>REVIEW</b></font>"

        row = [
            Paragraph(rule_id, cell_code_style),
            Paragraph(f"<b>{field_name}</b>", cell_bold_style),
            Paragraph(v_text, cell_bold_style),
            Paragraph(evidence, cell_body_style),
        ]
        table_data.append(row)

    col_widths = [90, 130, 70, 250]
    rules_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table_style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ]

    for i in range(1, len(table_data)):
        bg = colors.HexColor("#ffffff") if i % 2 != 0 else colors.HexColor("#f8fafc")
        table_style_commands.append(("BACKGROUND", (0, i), (-1, i), bg))

        verdict_val = str(fields[i - 1].get("verdict", "review")).upper() if i - 1 < len(fields) else "REVIEW"
        if verdict_val == "PASS":
            status_cell_bg = colors.HexColor("#dcfce7")
        elif verdict_val == "FAIL":
            status_cell_bg = colors.HexColor("#fee2e2")
        else:
            status_cell_bg = colors.HexColor("#fef3c7")
        table_style_commands.append(("BACKGROUND", (2, i), (2, i), status_cell_bg))
        table_style_commands.append(("ALIGN", (2, i), (2, i), "CENTER"))

    rules_table.setStyle(TableStyle(table_style_commands))
    elements.append(rules_table)

    # Annotated Image Section
    if annotated_image_b64:
        try:
            img_bytes = base64.b64decode(annotated_image_b64)
            pil_img = PILImage.open(io.BytesIO(img_bytes))
            orig_w, orig_h = pil_img.size

            max_w = 520
            max_h = 360
            scale_f = min(max_w / orig_w, max_h / orig_h, 1.0)
            disp_w = orig_w * scale_f
            disp_h = orig_h * scale_f

            img_block = [
                Spacer(1, 14),
                Paragraph("Annotated Packaging Inspection Visualizer", section_head_style),
                Spacer(1, 6),
                RLImage(io.BytesIO(img_bytes), width=disp_w, height=disp_h),
            ]
            elements.append(KeepTogether(img_block))
        except Exception as img_err:
            print(f"Failed to embed annotated image in PDF: {img_err}")

    elements.append(Spacer(1, 16))

    # Disclaimer from Hackathon project
    disclaimer_text = (
        "<b>Notice & Legal Metrology Disclaimer:</b> This audit report was automatically generated by the "
        "PackSight SIH Legal Metrology Compliance Engine under the Legal Metrology (Packaged Commodities) "
        "Rules, 2011. Results are intended for administrative and preliminary screening purposes. For statutory "
        "enforcement actions, officers must verify flagged items against the physical packaging."
    )
    elements.append(Paragraph(disclaimer_text, disclaimer_style))

    # Build document
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_legal_show_cause_notice_pdf(
    scan_id: int,
    product_name: str,
    brand_name: Optional[str],
    violations: List[Dict[str, Any]],
    liability_info: Dict[str, Any],
    inspecting_officer: str = "Authorized Legal Metrology Officer",
    created_at: Optional[datetime] = None,
) -> io.BytesIO:
    """
    Generates a formal, printable Legal Metrology Show-Cause Notice / Inspection Memorandum
    under Section 36 of the Legal Metrology Act, 2009 and Rule 6 of the Legal Metrology
    (Packaged Commodities) Rules, 2011.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        "GovtHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        alignment=1, # Centered
        textColor=colors.HexColor("#1e293b"),
    )
    title_style = ParagraphStyle(
        "NoticeTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        alignment=1,
        textColor=colors.HexColor("#991b1b"), # Crimson Red
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "NoticeBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8,
    )
    bold_body = ParagraphStyle(
        "NoticeBoldBody",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    elements = []

    # 1. Government Emblem & Department Header
    elements.append(Paragraph("GOVERNMENT OF INDIA<br/>MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION<br/>DEPARTMENT OF LEGAL METROLOGY", header_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#991b1b"), spaceAfter=12))

    # 2. Formal Notice Title
    elements.append(Paragraph("FORMAL SHOW-CAUSE NOTICE & INSPECTION MEMORANDUM", title_style))
    elements.append(Spacer(1, 6))

    # 3. Reference and Metadata Table
    notice_date = (created_at or datetime.now()).strftime("%d/%m/%Y %H:%M")
    ref_no = f"LM-IND/NOT-2026/SCN-{scan_id:05d}"
    meta_data = [
        [Paragraph("<b>Notice Ref No:</b>", body_style), Paragraph(ref_no, body_style),
         Paragraph("<b>Date of Issue:</b>", body_style), Paragraph(notice_date, body_style)],
        [Paragraph("<b>Commodity Name:</b>", body_style), Paragraph(product_name, body_style),
         Paragraph("<b>Inspecting Authority:</b>", body_style), Paragraph(inspecting_officer, body_style)],
        [Paragraph("<b>Brand / Trademark:</b>", body_style), Paragraph(brand_name or "Not Specified", body_style),
         Paragraph("<b>Inspection Mode:</b>", body_style), Paragraph("PackSight Statutory AI Scan", body_style)],
    ]
    meta_table = Table(meta_data, colWidths=[110, 160, 120, 140])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 14))

    # 4. Legal Preamble
    preamble = (
        "<b>WHEREAS</b>, upon automated computer vision and optical statutory inspection of the packaged commodity "
        f"<b>'{product_name}'</b> under the provisions of the <b>Legal Metrology Act, 2009</b> read with the "
        "<b>Legal Metrology (Packaged Commodities) Rules, 2011 (as amended)</b>, the undersigned authorized officer has "
        "detected prima facie non-compliance with the mandatory statutory labeling declarations."
    )
    elements.append(Paragraph(preamble, body_style))
    elements.append(Spacer(1, 10))

    # 5. Table of Violations
    elements.append(Paragraph("<b>SCHEDULE OF STATUTORY INFRACTIONS DETECTED:</b>", bold_body))
    elements.append(Spacer(1, 4))

    viol_rows = [[
        Paragraph("<b>Statutory Rule</b>", bold_body),
        Paragraph("<b>Mandatory Declaration</b>", bold_body),
        Paragraph("<b>Infraction Evidence / Finding</b>", bold_body)
    ]]

    if not violations:
        viol_rows.append([
            Paragraph("N/A", body_style),
            Paragraph("All Mandatory Declarations Verified", body_style),
            Paragraph("No statutory infractions found during inspection.", body_style)
        ])
    else:
        for v in violations:
            viol_rows.append([
                Paragraph(f"<b>{v.get('rule_id', 'LMPC')}</b>", body_style),
                Paragraph(v.get("field", "Declaration"), body_style),
                Paragraph(v.get("reason", "Not declared as required"), body_style),
            ])

    viol_table = Table(viol_rows, colWidths=[90, 150, 290])
    viol_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#dc2626")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fecaca")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(viol_table)
    elements.append(Spacer(1, 14))

    # 6. Statutory Liability Assessment
    elements.append(Paragraph("<b>STATUTORY PENALTY COMPUTATION (SECTION 36):</b>", bold_body))
    elements.append(Spacer(1, 4))

    penalty_1 = liability_info.get("penalty_first_offense", 25000)
    penalty_2 = liability_info.get("penalty_second_offense", 50000)
    sections_str = ", ".join(liability_info.get("applicable_sections", ["Section 36(1)"]))

    liability_text = (
        f"Under <b>{sections_str}</b> of the Legal Metrology Act, 2009:<br/>"
        f"• <b>First Offence:</b> Penalty extending up to <b>₹{penalty_1:,}</b> per director / partner / company.<br/>"
        f"• <b>Second Offence:</b> Penalty extending up to <b>₹{penalty_2:,}</b>.<br/>"
        f"• <b>Subsequent Offences:</b> Fine up to <b>₹1,00,000</b> and/or imprisonment for term up to <b>one year</b>.<br/>"
        f"• <b>Compounding of Offence:</b> Under Section 48, the company may apply for compounding before court proceedings."
    )
    elements.append(Paragraph(liability_text, body_style))
    elements.append(Spacer(1, 14))

    # 7. Directive & 15-Day Response Window
    directive = (
        "<b>NOW THEREFORE</b>, you are hereby called upon to <b>SHOW CAUSE within 15 (fifteen) calendar days</b> "
        "from the receipt of this notice as to why statutory prosecution under Section 36 of the Legal Metrology Act, 2009 "
        "should not be initiated against your enterprise and responsible directors. "
        "Failure to submit written representation or rectifying evidence within the stipulated period shall result in immediate "
        "statutory compounding summons or filing of a formal complaint in the Court of Judicial Magistrate."
    )
    elements.append(Paragraph(directive, body_style))
    elements.append(Spacer(1, 28))

    # 8. Signature & Seal Block
    sig_data = [
        ["", "For and on behalf of Controller of Legal Metrology:"],
        ["", ""],
        ["", "_____________________________________"],
        ["", f"<b>{inspecting_officer}</b>"],
        ["", "PackSight AI Enforcement Verification Cell"],
    ]
    sig_table = Table(sig_data, colWidths=[270, 260])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)

    # Build document
    doc.build(elements)
    buffer.seek(0)
    return buffer
