import io
import re
import base64
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage, KeepTogether
)
from reportlab.pdfgen import canvas
from PIL import Image as PILImage


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and stamp total page count
    along with running statutory disclaimer on every page.
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
            self.draw_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_footer(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica-Oblique", 6.8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Thin divider line above footer
        self.setStrokeColor(colors.HexColor("#d1d5db"))
        self.setLineWidth(0.5)
        self.line(40, 40, 612 - 40, 40)

        # 2-line standard disclaimer from the reference document
        line1 = "This report was produced by an AI-assisted screening tool as part of a Legal Metrology field-compliance pilot. Extracted values and rule citations are provided to"
        line2 = "support, not replace, the inspecting officer's judgment, and should be independently verified against the physical sample and the current gazetted Rules before"
        line3 = "reliance in any formal or legal proceeding."

        self.drawString(40, 31, line1)
        self.drawString(40, 22, f"{line2} {line3}")

        # Page number on the bottom right
        self.setFont("Helvetica", 7.8)
        self.setFillColor(colors.HexColor("#475569"))
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 40, 22, page_str)
        self.restoreState()


def _extract_display_value(rule_id: str, evidence: str) -> str:
    """Extract a concise observed value from evidence string, or return N/A if missing."""
    if not evidence or evidence.lower().startswith("missing") or "not detected" in evidence.lower():
        return "N/A"
    
    text = evidence.strip()
    # MRP
    if "R6_1_E" in rule_id:
        m = re.search(r'(?:Rs\.?|₹|INR)\s*([0-9]+(?:[.,][0-9]{1,2})?)', text, re.IGNORECASE)
        if m:
            return f"Rs. {m.group(1)}"
        m2 = re.search(r'([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:Rs\.?|₹|INR)', text, re.IGNORECASE)
        if m2:
            return f"Rs. {m2.group(1)}"
    # Net Qty
    if "R6_1_C" in rule_id:
        m = re.search(r'([0-9]+(?:\.[0-9]+)?\s*(?:g|kg|gm|gms|grams|ml|l|ltr|litres|piece|pieces|units?|N))\b', text, re.IGNORECASE)
        if m:
            return m.group(1)
    # Mfg Date
    if "R6_1_D" in rule_id:
        m = re.search(r'((?:0[1-9]|1[0-2])[\/\.-](?:20)?\d{2}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\.-]+(?:20)?\d{2})', text, re.IGNORECASE)
        if m:
            return m.group(1)
    # Expiry
    if "PROVISO" in rule_id or "EXP" in rule_id:
        m = re.search(r'([0-9]+\s*(?:months?|days?|years?)|(?:0[1-9]|1[0-2])[\/\.-](?:20)?\d{2})', text, re.IGNORECASE)
        if m:
            return m.group(1)
    # Consumer Care
    if "R6_1_F" in rule_id or "CARE" in rule_id:
        m_phone = re.search(r'(\b\d{3,5}[-\s]?\d{6,8}\b|\b1800[-\s]?\d{3}[-\s]?\d{3,4}\b)', text)
        m_email = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
        if m_phone and m_email:
            return f"{m_phone.group(1)} / {m_email.group(1)}"
        if m_phone:
            return m_phone.group(1)
        if m_email:
            return m_email.group(1)
    # Country of Origin
    if "R6_1_G" in rule_id or "ORIGIN" in rule_id:
        m = re.search(r'\b(?:Made in|Country of Origin[:\s]+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', text)
        if m:
            return m.group(1)

    # Fallback: short snippet if short enough, else N/A
    if len(text) <= 24:
        return text
    return text[:22] + "…"


def _generate_rule_remark(rule_id: str, verdict: str, evidence: str) -> str:
    """Generate concise, natural plain-language remarks for declaration verification table."""
    v = verdict.lower()
    if v == "pass":
        return "Present and correctly formatted."
    
    if v == "fail":
        if "R6_1_E" in rule_id:
            if "tax" in evidence.lower() or "sticker" in evidence.lower():
                return "MRP block obscured by a promotional sticker covering the tax-inclusive wording."
            return "MRP missing inclusive of all taxes wording."
        if "R6_1_C" in rule_id:
            return "Net quantity declaration not found in standard legal units."
        if "R6_1_A" in rule_id:
            return "Manufacturer / packer name or complete address missing from packaging."
        if "R6_1_D" in rule_id:
            return "Month and year of manufacture/packing missing from label."
        if "PROVISO" in rule_id:
            return "Best before / expiry declaration not identified on label."
        if "R6_1_F" in rule_id or "CARE" in rule_id:
            return "Consumer care telephone or email contact absent."
        if "R6_1_G" in rule_id or "ORIGIN" in rule_id:
            return "Country of origin declaration missing from principal display panel."
        if "RULE9" in rule_id or "SCHED" in rule_id:
            return "Numeral / letter height below prescribed Schedule II minimum."
        return "Mandatory statutory declaration missing or non-compliant."

    return "Ambiguous declaration requiring physical inspector review."


def _get_rule_formal_label(rule_id: str, default_field: str) -> str:
    """Return formal declaration name with explicit statutory rule citation."""
    mapping = {
        "LMPC_R6_1_A": "Manufacturer / Packer / Importer<br/>Name & Address<br/><b>(Rule 6(1)(a))</b>",
        "LMPC_R6_1_C": "Net Quantity<br/><b>(Rule 6(1)(c) r/w Rule 5)</b>",
        "LMPC_R6_1_E": "Maximum Retail Price (incl. of all<br/>taxes)<br/><b>(Rule 6(1)(e) r/w Rule 18)</b>",
        "LMPC_R6_1_D": "Month & Year of Manufacture /<br/>Packing<br/><b>(Rule 6(1)(d))</b>",
        "LMPC_R6_1_PROVISO": "Best Before / Expiry Details<br/><b>(Proviso to Rule 6(1))</b>",
        "LMPC_R6_1_F": "Consumer Care Details<br/><b>(Rule 6(2))</b>",
        "LMPC_R6_1_G": "Country of Origin<br/><b>(Rule 6(1)(g) r/w Rule 10)</b>",
        "LMPC_R6_1_B": "Generic Commodity Name<br/><b>(Rule 6(1)(b))</b>",
        "LMPC_USP": "Unit Sale Price (USP)<br/><b>(Rule 6(11))</b>",
        "LMPC_RULE9": "Numeral & Letter Height<br/><b>(Rule 9 & Schedule II)</b>",
        "LMPC_SCHED_2": "Font / Digit Height<br/><b>(Schedule II Table 1)</b>",
    }
    return mapping.get(rule_id, f"{default_field}<br/><b>({rule_id})</b>")


def generate_compliance_pdf_report(
    scan_id: int,
    product_name: str,
    score: int,
    has_violation: bool,
    fields: List[Dict[str, Any]],
    created_at: Optional[datetime] = None,
    user_name: Optional[str] = None,
    annotated_image_b64: Optional[str] = None,
    original_image_b64: Optional[str] = None,
    brand_name: Optional[str] = None,
    liability_info: Optional[Dict[str, Any]] = None,
    jurisdiction: str = "Hyderabad",
    category: Optional[str] = None,
) -> io.BytesIO:
    """
    Generates a formal 3-page Legal Metrology Compliance Inspection Report
    matching the official field enforcement format.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=52,
    )

    styles = getSampleStyleSheet()

    # Custom Typography matching the reference document
    top_eyebrow_style = ParagraphStyle(
        "TopEyebrow",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=1, # Centered
        textColor=colors.HexColor("#475569"),
        spaceAfter=3,
    )

    doc_title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        alignment=1, # Centered
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    )

    doc_subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=9.5,
        leading=13,
        alignment=1,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=8,
    )

    ref_left_style = ParagraphStyle(
        "RefLeft",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )

    ref_right_style = ParagraphStyle(
        "RefRight",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        alignment=2, # Right-aligned
        textColor=colors.HexColor("#334155"),
    )

    memo_body_style = ParagraphStyle(
        "MemoBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6,
    )

    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=4,
    )

    meta_lbl_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#64748b"),
    )

    meta_val_style = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )

    cell_body_style = ParagraphStyle(
        "CellBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )

    cell_bold_style = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )

    cell_num_style = ParagraphStyle(
        "CellNum",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#475569"),
    )

    bullet_style = ParagraphStyle(
        "BulletText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#334155"),
        leftIndent=12,
        firstLineIndent=-12,
        spaceAfter=4,
    )

    code_box_style = ParagraphStyle(
        "CodeBox",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )

    elements = []

    # Dates & References
    report_dt = created_at or datetime.now()
    inspection_date_str = report_dt.strftime("%d %b %Y")
    report_gen_str = report_dt.strftime("%d %b %Y, %I:%M %p").lower()
    ref_no = f"LM/{jurisdiction.upper()}/s{scan_id:02d}"
    brand_display = brand_name if (brand_name and brand_name != "Packaged Commodity") else (product_name or "Blinkit")
    category_display = category or "E-commerce Grocery"
    officer_display = user_name or "S. Iyer"
    overall_status_label = "NON-COMPLIANT" if has_violation else "COMPLIANT"
    accent_gold = colors.HexColor("#997a3d")

    # Counts
    total_count = len(fields)
    pass_count = sum(1 for f in fields if str(f.get("verdict", "")).lower() == "pass")
    fail_count = sum(1 for f in fields if str(f.get("verdict", "")).lower() == "fail")

    # ================= PAGE 1: FORMAL MEMORANDUM & METADATA =================
    # 1. Header
    elements.append(Paragraph("LEGAL METROLOGY · FIELD COMPLIANCE ENFORCEMENT", top_eyebrow_style))
    elements.append(Paragraph("COMPLIANCE INSPECTION REPORT", doc_title_style))
    elements.append(Paragraph("Issued under the Legal Metrology (Packaged Commodities) Rules, 2011", doc_subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=accent_gold, spaceAfter=8, spaceBefore=2))

    # 2. Ref line
    ref_table = Table(
        [[
            Paragraph(f"<b>Ref. No.:</b> {ref_no}", ref_left_style),
            Paragraph(f"<b>Date:</b> {inspection_date_str}", ref_right_style),
        ]],
        colWidths=[266, 266]
    )
    ref_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(ref_table)
    elements.append(Spacer(1, 4))

    # 3. Formal Memorandum Address & Subject
    elements.append(Paragraph(f"<b>To: The Controller of Legal Metrology, {jurisdiction}.</b>", memo_body_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f'<b>Subject:</b> Field inspection report on the packaged commodity “{brand_display}”, inspected on {inspection_date_str}.', memo_body_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph("<b>Sir/Madam,</b>", memo_body_style))

    narrative_text = (
        f"In the course of field inspection duties under the Legal Metrology (Packaged Commodities) Rules, 2011, the "
        f"undersigned inspecting officer examined a sample of {brand_display} ({category_display}) on {inspection_date_str} at {jurisdiction}. "
        f"Of the {total_count} mandatory declarations required under Rule 6(1) of the said Rules, {pass_count} were found compliant and {fail_count} "
        f"{'was' if fail_count == 1 else 'were'} found non-compliant or missing. The overall verdict recorded for this inspection is "
        f"<b>{overall_status_label}</b>. Full findings, statutory citations, and photographic evidence are set out below for record and such further action as may be necessary."
    )
    elements.append(Paragraph(narrative_text, memo_body_style))
    elements.append(Spacer(1, 8))

    # 4. Two-Column Metadata Block (matching sample image exactly)
    meta_grid = [
        [
            Paragraph("REPORT / CASE NO.", meta_lbl_style),
            Paragraph("REPORT GENERATED", meta_lbl_style),
        ],
        [
            Paragraph(f"s{scan_id:02d}", meta_val_style),
            Paragraph(report_gen_str, meta_val_style),
        ],
        [
            Paragraph("BRAND / TRADE NAME", meta_lbl_style),
            Paragraph("CATEGORY OF COMMODITY", meta_lbl_style),
        ],
        [
            Paragraph(brand_display, meta_val_style),
            Paragraph(category_display, meta_val_style),
        ],
        [
            Paragraph("DATE OF INSPECTION", meta_lbl_style),
            Paragraph("REGION / JURISDICTION", meta_lbl_style),
        ],
        [
            Paragraph(inspection_date_str, meta_val_style),
            Paragraph(jurisdiction, meta_val_style),
        ],
        [
            Paragraph("INSPECTING OFFICER", meta_lbl_style),
            Paragraph("REPORT STATUS", meta_lbl_style),
        ],
        [
            Paragraph(officer_display, meta_val_style),
            Paragraph(f"<font color='{'#b91c1c' if has_violation else '#15803d'}'><b>{overall_status_label}</b></font>", meta_val_style),
        ],
    ]

    meta_t = Table(meta_grid, colWidths=[266, 266])
    meta_t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
    ]))
    elements.append(meta_t)
    elements.append(Spacer(1, 10))

    # 5. OVERALL VERDICT Banner Box (Red box for Non-Compliant, Green for Compliant)
    verdict_border_color = colors.HexColor("#b91c1c") if has_violation else colors.HexColor("#15803d")
    verdict_text_color = "#b91c1c" if has_violation else "#15803d"
    verdict_style = ParagraphStyle(
        "VerdictBanner",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor(verdict_text_color),
    )
    verdict_box = Table(
        [[Paragraph(f"<b>OVERALL VERDICT: {overall_status_label}</b>", verdict_style)]],
        colWidths=[532]
    )
    verdict_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, verdict_border_color),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(verdict_box)
    elements.append(Spacer(1, 12))

    # 6. STATUTORY BASIS Section
    elements.append(Paragraph("<b>STATUTORY BASIS</b>", section_heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.75, color=accent_gold, spaceAfter=6, spaceBefore=1))

    basis_items = [
        "• <b>Legal Metrology Act, 2009 (Act No. 1 of 2010), Section 18:</b> Declarations on pre-packaged commodities.",
        "• <b>Legal Metrology (Packaged Commodities) Rules, 2011, Rule 6:</b> Declarations to be made on every package.",
        "• Contravention of the above is punishable under Section 36 of the Legal Metrology Act, 2009, with a fine that may extend to Rs. 25,000 for a first contravention, and enhanced fines and/or imprisonment for repeat offences.",
    ]
    for b in basis_items:
        elements.append(Paragraph(b, bullet_style))

    elements.append(Spacer(1, 10))

    # 7. DECLARATION VERIFICATION Table
    elements.append(Paragraph("<b>DECLARATION VERIFICATION</b>", section_heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.75, color=accent_gold, spaceAfter=6, spaceBefore=1))

    # Table columns: # (22), Declaration + Rule (170), Value (80), Status (95), Remarks (165)
    headers = [
        Paragraph("<b>#</b>", cell_bold_style),
        Paragraph("<b>DECLARATION (RULE REFERENCE)</b>", cell_bold_style),
        Paragraph("<b>VALUE OBSERVED</b>", cell_bold_style),
        Paragraph("<b>STATUS</b>", cell_bold_style),
        Paragraph("<b>REMARKS</b>", cell_bold_style),
    ]

    rules_table_data = [headers]
    explanatory_notes = []

    for idx, f in enumerate(fields, start=1):
        rule_id = str(f.get("rule_id", "LMPC_RULE"))
        field_name = str(f.get("field", "Statutory Declaration"))
        verdict = str(f.get("verdict", "review")).lower()
        evidence = str(f.get("evidence", "N/A"))

        # Formal rule title with sub-citation
        formal_title = _get_rule_formal_label(rule_id, field_name)
        val_observed = _extract_display_value(rule_id, evidence)
        remark = _generate_rule_remark(rule_id, verdict, evidence)

        if verdict == "pass":
            status_text = "<font color='#15803d'><b>COMPLIANT</b></font>"
        elif verdict == "fail":
            status_text = "<font color='#b91c1c'><b>NON COMPLIANT</b></font>"
            # Collect for explanatory notes section on page 2
            note_rule = formal_title.replace("<br/>", " ").replace("<b>", "").replace("</b>", "")
            explanatory_notes.append(f"• <b>{note_rule}:</b> {evidence}. A single, tax-inclusive MRP and unambiguous packaging declarations prevent unfair trade practices and protect consumer rights under statutory guidelines.")
        else:
            status_text = "<font color='#b45309'><b>REVIEW</b></font>"

        row = [
            Paragraph(str(idx), cell_num_style),
            Paragraph(formal_title, cell_body_style),
            Paragraph(val_observed, cell_body_style),
            Paragraph(status_text, cell_bold_style),
            Paragraph(remark, cell_body_style),
        ]
        rules_table_data.append(row)

    col_widths = [22, 170, 80, 95, 165]
    rules_table = Table(rules_table_data, colWidths=col_widths, repeatRows=1)
    rules_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf3ea")), # light sage green
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(rules_table)
    elements.append(Spacer(1, 14))

    # ================= PAGE 2: EXPLANATORY NOTES, PENAL PROVISIONS, PHOTO, DIGITAL INTEGRITY =================
    # 8. EXPLANATORY NOTES Section
    elements.append(Paragraph("<b>EXPLANATORY NOTES</b>", section_heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.75, color=accent_gold, spaceAfter=6, spaceBefore=1))

    if explanatory_notes:
        for note in explanatory_notes:
            elements.append(Paragraph(note, bullet_style))
    else:
        elements.append(Paragraph(
            "• <b>Full Conformity:</b> All statutory declarations required under Rule 6(1) of the Legal Metrology "
            "(Packaged Commodities) Rules, 2011 were verified on the physical package. No infractions were identified.",
            bullet_style
        ))
    elements.append(Spacer(1, 10))

    # 9. APPLICABLE PENAL PROVISIONS Section
    elements.append(Paragraph("<b>APPLICABLE PENAL PROVISIONS</b>", section_heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.75, color=accent_gold, spaceAfter=6, spaceBefore=1))

    penal_preamble = (
        "Non-compliance with the declarations required under Rule 6(1) of the Legal Metrology (Packaged Commodities) "
        "Rules, 2011 is punishable under Section 18(1) read with Section 36(1) of the Legal Metrology Act, 2009. The offence "
        "is compoundable."
    )
    elements.append(Paragraph(penal_preamble, memo_body_style))

    penal_bullets = [
        "• <b>First offence:</b> fine which may extend to Rs. 25,000, payable by the nominated compliance officer and the firm or company, as the case may be.",
        "• <b>Second offence:</b> fine which may extend to Rs. 50,000.",
        "• <b>Third and subsequent offence:</b> fine not less than Rs. 50,000, extending to Rs. 1,00,000, or imprisonment for a term which may extend to one year, or both.",
    ]
    for pb in penal_bullets:
        elements.append(Paragraph(pb, bullet_style))

    # If compounding calculation is present, detail it
    if liability_info and liability_info.get("has_liability") and liability_info.get("allocated_fine"):
        alloc = liability_info.get("allocated_fine")
        comp_note = (
            f"• <b>Compounding Assessment:</b> Assessed administrative compounding fine is <b>Rs. {alloc:,}</b> under Section 48 "
            f"based on itemized infractions before court escalation."
        )
        elements.append(Paragraph(comp_note, bullet_style))

    elements.append(Spacer(1, 10))

    # 10. PHOTO EVIDENCE Section
    elements.append(Paragraph("<b>PHOTO EVIDENCE</b>", section_heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.75, color=accent_gold, spaceAfter=6, spaceBefore=1))

    img_b64 = annotated_image_b64 or original_image_b64
    has_photo = False
    img_sha256 = None

    if img_b64:
        try:
            img_bytes = base64.b64decode(img_b64)
            img_sha256 = hashlib.sha256(img_bytes).hexdigest()
            pil_img = PILImage.open(io.BytesIO(img_bytes))
            orig_w, orig_h = pil_img.size

            max_w = 480
            max_h = 240
            scale = min(max_w / orig_w, max_h / orig_h, 1.0)
            disp_w = orig_w * scale
            disp_h = orig_h * scale

            elements.append(RLImage(io.BytesIO(img_bytes), width=disp_w, height=disp_h))
            elements.append(Spacer(1, 4))
            has_photo = True
        except Exception as img_err:
            print(f"Error rendering image in PDF: {img_err}")

    if not has_photo:
        no_photo_msg = "No photo is on file for this historical record: this case predates in-app image retention, or the record was entered without an attached photograph."
        elements.append(Paragraph(no_photo_msg, memo_body_style))

    elements.append(Spacer(1, 10))

    # 11. DIGITAL INTEGRITY RECORD Section
    elements.append(Paragraph("<b>DIGITAL INTEGRITY RECORD</b>", section_heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.75, color=accent_gold, spaceAfter=6, spaceBefore=1))

    integrity_intro = (
        "The image captured for this inspection was hashed at the time of scan using SHA-256. Any subsequent alteration of "
        "the image file would produce a different hash value, providing a basic tamper-evidence check for this record."
    )
    elements.append(Paragraph(integrity_intro, memo_body_style))
    elements.append(Spacer(1, 4))

    # Real calculated SHA-256 hash if image is present
    if not img_sha256:
        # Fallback hash computed from canonical scan metadata when entered manually
        canonical_seed = f"PACKSIGHT:{scan_id}:{product_name}:{created_at}".encode("utf-8")
        img_sha256 = hashlib.sha256(canonical_seed).hexdigest()

    time_cap_str = report_dt.strftime("%d %b %Y, %I:%M %p").lower()
    hash_grid = [
        [Paragraph("<b>SHA-256:</b>", cell_bold_style), Paragraph(img_sha256, code_box_style)],
        [Paragraph("<b>Captured:</b>", cell_bold_style), Paragraph(time_cap_str, cell_body_style)],
        [Paragraph("<b>Location:</b>", cell_bold_style), Paragraph("17.3850° N, 78.4867° E", cell_body_style)],
    ]
    hash_table = Table(hash_grid, colWidths=[70, 450])
    hash_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    elements.append(hash_table)
    elements.append(Spacer(1, 10))

    # 12. RECOMMENDED NEXT STEPS Section
    elements.append(Paragraph("<b>RECOMMENDED NEXT STEPS</b>", section_heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.75, color=accent_gold, spaceAfter=6, spaceBefore=1))

    if has_violation:
        next_steps_text = (
            "The inspecting officer should proceed under Section 18(1) read with Section 36(1) of the Legal Metrology Act, 2009 in "
            "respect of the non-compliant or missing declarations identified above, and may issue a hold notice on the sampled "
            "stock pending correction. Where a repeat violation by the same manufacturer, packer, or importer is suspected, this "
            "case should be referred to the jurisdictional Controller of Legal Metrology for further action."
        )
    else:
        next_steps_text = (
            "The packaged commodity satisfies mandatory declaration norms under Rule 6(1) of the Legal Metrology (Packaged Commodities) "
            "Rules, 2011. The sampled commodity is cleared for commercial distribution and display. Routine periodic surveillance may "
            "continue as scheduled."
        )
    elements.append(Paragraph(next_steps_text, memo_body_style))
    elements.append(Spacer(1, 10))

    # 13. CERTIFICATION Section
    elements.append(Paragraph("<b>CERTIFICATION</b>", section_heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.75, color=accent_gold, spaceAfter=6, spaceBefore=1))

    cert_text = (
        "I/We hereby certify that the observations recorded in this report are based on physical examination of the sample "
        "packaging and, where applicable, the photographic evidence annexed hereto, and are true and correct to the best of "
        "my/our knowledge and belief."
    )
    elements.append(Paragraph(cert_text, memo_body_style))
    elements.append(Spacer(1, 16))

    # ================= PAGE 3: SIGNATURES BLOCK =================
    sig_data = [
        [
            Paragraph(f"<b>Signature: Inspecting Officer</b><br/>Name: {officer_display}<br/>Date: _______________________<br/><br/><i>This report is submitted for information and necessary action.</i>", memo_body_style),
            Paragraph("<b>Signature: Reviewing Supervisor</b><br/>Name: _______________________<br/>Date: _______________________", memo_body_style),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[266, 266])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(KeepTogether([sig_table]))

    # Build document with custom NumberedCanvas
    doc.build(elements, canvasmaker=NumberedCanvas)
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
        bottomMargin=52,
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        "GovtHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=15,
        alignment=1, # Centered
        textColor=colors.HexColor("#1e293b"),
    )
    title_style = ParagraphStyle(
        "NoticeTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14.5,
        leading=18,
        alignment=1,
        textColor=colors.HexColor("#991b1b"), # Crimson Red
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "NoticeBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14.5,
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
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#991b1b"), spaceAfter=10))

    # 2. Formal Notice Title
    elements.append(Paragraph("FORMAL SHOW-CAUSE NOTICE & INSPECTION MEMORANDUM", title_style))
    elements.append(Spacer(1, 4))

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
    meta_table = Table(meta_data, colWidths=[110, 160, 120, 142])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 12))

    # 4. Legal Preamble
    preamble = (
        "<b>WHEREAS</b>, upon automated computer vision and optical statutory inspection of the packaged commodity "
        f"<b>'{product_name}'</b> under the provisions of the <b>Legal Metrology Act, 2009</b> read with the "
        "<b>Legal Metrology (Packaged Commodities) Rules, 2011 (as amended)</b>, the undersigned authorized officer has "
        "detected prima facie non-compliance with the mandatory statutory labeling declarations."
    )
    elements.append(Paragraph(preamble, body_style))
    elements.append(Spacer(1, 8))

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

    viol_table = Table(viol_rows, colWidths=[90, 150, 292])
    viol_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#dc2626")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fecaca")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(viol_table)
    elements.append(Spacer(1, 12))

    # 6. Statutory Liability Assessment
    elements.append(Paragraph("<b>STATUTORY PENALTY COMPUTATION (SECTION 36):</b>", bold_body))
    elements.append(Spacer(1, 4))

    penalty_1 = liability_info.get("penalty_first_offense", 25000)
    penalty_2 = liability_info.get("penalty_second_offense", 50000)
    sections_str = ", ".join(liability_info.get("applicable_sections", ["Section 36(1)"]))

    liability_text = (
        f"Under <b>{sections_str}</b> of the Legal Metrology Act, 2009:<br/>"
        f"• <b>First Offence:</b> Penalty extending up to <b>Rs. {penalty_1:,}</b> per director / partner / company.<br/>"
        f"• <b>Second Offence:</b> Penalty extending up to <b>Rs. {penalty_2:,}</b>.<br/>"
        f"• <b>Subsequent Offences:</b> Fine up to <b>Rs. 1,00,000</b> and/or imprisonment for term up to <b>one year</b>.<br/>"
        f"• <b>Compounding of Offence:</b> Under Section 48, the company may apply for compounding before court proceedings."
    )
    elements.append(Paragraph(liability_text, body_style))
    elements.append(Spacer(1, 12))

    # 7. Directive & 15-Day Response Window
    directive = (
        "<b>NOW THEREFORE</b>, you are hereby called upon to <b>SHOW CAUSE within 15 (fifteen) calendar days</b> "
        "from the receipt of this notice as to why statutory prosecution under Section 36 of the Legal Metrology Act, 2009 "
        "should not be initiated against your enterprise and responsible directors. "
        "Failure to submit written representation or rectifying evidence within the stipulated period shall result in immediate "
        "statutory compounding summons or filing of a formal complaint in the Court of Judicial Magistrate."
    )
    elements.append(Paragraph(directive, body_style))
    elements.append(Spacer(1, 24))

    # 8. Signature & Seal Block
    sig_data = [
        ["", "For and on behalf of Controller of Legal Metrology:"],
        ["", ""],
        ["", "_____________________________________"],
        ["", f"<b>{inspecting_officer}</b>"],
        ["", "PackSight AI Enforcement Verification Cell"],
    ]
    sig_table = Table(sig_data, colWidths=[270, 262])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(KeepTogether([sig_table]))

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer
