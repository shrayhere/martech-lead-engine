import os
import sys
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print total page count:
    'Page X of Y' in the running footer.
    """
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#475569"))

        # Running Header on all pages
        self.drawString(42, 11 * 72 - 28, "MARTECH LEAD ENGINE | ARCHITECTURAL AUDIT & PIPELINE Q&A REPORT")
        self.setFont("Helvetica", 7.5)
        self.drawRightString(8.5 * 72 - 42, 11 * 72 - 28, "FASTAPI + RAPIDFUZZ + SCIKIT-LEARN + REACT")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.6)
        self.line(42, 11 * 72 - 32, 8.5 * 72 - 42, 11 * 72 - 32)

        # Running Footer (all pages)
        self.line(42, 34, 8.5 * 72 - 42, 34)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(42, 23, "MarTech Data Quality & Lead Scoring Engine | Portfolio project report")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * 72 - 42, 23, page_text)
        self.restoreState()


def styled_table(data, widths, header_color=colors.HexColor("#0f172a")):
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    return t


def pct(x):
    return f"{x * 100:.1f}%"


def build_pdf(filename="MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"):
    # Every number in this report is computed from a fresh run of the code (backend/report_metrics.py).
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
    from report_metrics import collect
    M = collect()
    C = M["clean"]
    # Target 4 perfect pages: printable width = 528 pt, printable height = 712 pt
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=42,
        rightMargin=42,
        topMargin=40,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()

    primary_color = colors.HexColor("#0f172a")   # Slate 900
    brand_blue = colors.HexColor("#1d4ed8")      # Blue 700
    accent_indigo = colors.HexColor("#4338ca")   # Indigo 700
    text_dark = colors.HexColor("#1e293b")       # Slate 800
    text_muted = colors.HexColor("#475569")      # Slate 600

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=primary_color,
        spaceAfter=2
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=brand_blue,
        spaceAfter=3
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=text_muted,
        spaceAfter=6
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=primary_color,
        spaceBefore=0,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'QuestionH2',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12.5,
        textColor=brand_blue,
        spaceBefore=5,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=text_dark,
        spaceAfter=3
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=body_style,
        leftIndent=10,
        firstLineIndent=-7,
        spaceAfter=2
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.5,
        textColor=colors.HexColor("#0f172a")
    )

    code_style = ParagraphStyle(
        'CodeText',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0f172a")
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.2,
        textColor=text_dark
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.2,
        textColor=text_dark
    )

    story = []

    # =========================================================================
    # PAGE 1: TITLE, EXEC SUMMARY & SECTION 1 (DATA INGESTION)
    # =========================================================================
    story.append(Paragraph("MarTech Data Quality & Lead Scoring Engine", title_style))
    story.append(Paragraph("Engineering Audit & Algorithmic Pipeline Architecture Report", subtitle_style))
    story.append(Paragraph(
        f"<b>Repository:</b> <code>shrayhere/martech-lead-engine</code> &nbsp;|&nbsp; "
        f"<b>Tech Stack:</b> FastAPI &bull; RapidFuzz &bull; Scikit-Learn &bull; React &bull; Tailwind &bull; SQLite &nbsp;|&nbsp; "
        f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}",
        meta_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.2, color=brand_blue, spaceAfter=6))

    # Executive Overview Callout Box
    overview_text = (
        "<b>Executive Summary:</b> This technical audit provides exhaustive answers to core engineering questions "
        "concerning the 4-stage MarTech Engine: Data Ingestion, Data Quality & RapidFuzz Deduplication, Lead Scoring "
        "(Explainable Rule-Based & ML Classifier), and Automated Sales Rep Routing. Every figure in this report is "
        "computed by <code>backend/report_metrics.py</code> from a fresh run of the code on the built-in 200-lead sample."
    )
    overview_table = Table(
        [[Paragraph(overview_text, callout_style)]],
        colWidths=[528]
    )
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ('LINELEFT', (0, 0), (0, -1), 3.5, brand_blue),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph("1. Data Ingestion & Dataset Architecture", h1_style))

    # Q1.1
    story.append(Paragraph("1.1 Is the 200-lead dataset entirely synthetic, or have you tried real or messy external CSVs?", h2_style))
    story.append(Paragraph(
        "<b>Dataset Origin:</b> The built-in 200-lead file (<code>GET /api/leads/sample-csv</code>) is <b>100% synthetically generated</b> "
        "using Python's <code>sample_generator.py</code>, seeded with <code>random.seed(42)</code> for repeatable benchmarks.<br/>"
        "<b>Real / Messy External CSV Handling:</b> The engine's ingestion layer (<code>backend/app/services/ingestion_service.py</code>) "
        "was extended to ingest <b>arbitrary, messy external CSV files</b> from real-world CRM exports, marketing campaigns, and webform dumps:",
        body_style
    ))
    story.append(Paragraph("• <b>Dynamic Header Alias Resolution:</b> Automatically maps non-standard column synonyms across 11 canonical fields (e.g., <code>lead_name</code>, <code>fname</code>, <code>contact_number</code>, <code>employee_count</code>, <code>vertical</code>).", bullet_style))
    story.append(Paragraph("• <b>Full Name Auto-Splitting:</b> Intelligently detects combined 'Name' or 'Full Name' fields and splits them into <code>first_name</code> and <code>last_name</code> using smart whitespace parsing.", bullet_style))
    story.append(Paragraph("• <b>Robust Type Parsing & Cleaning:</b> Strips percentage signs (<code>'85%'</code> &rarr; <code>85.0</code>), extracts regex digits from company size strings (<code>'5,000 employees'</code> &rarr; <code>5000</code>), and supplies deterministic fallbacks.", bullet_style))

    # Q1.2
    story.append(Paragraph("1.2 In the generator, how did you plant flaws? Do you keep a ground-truth label for true duplicates?", h2_style))
    story.append(Paragraph(
        "The generator implements a three-tier flawed data synthesis pipeline to mirror real-world CRM data decay:<br/>"
        "• <b>Tier 1: 170 Base Records (170 distinct people) with Realistic Field Entropy:</b> Injects casing inconsistencies (20% random uppercase/lowercase company names), 5 distinct phone formatting styles (<code>(555) 234-5678</code>, <code>+15552345678</code>, <code>555-234-5678</code>, <code>555.234.5678</code>, <code>5552345678</code>), state spelling variants across 7 US states (<code>CA</code>, <code>calif</code>, <code>California</code>, <code>Calif.</code>, <code>ca</code>), and activity dates spread across 1–120 days ago.<br/>"
        "• <b>Tier 2: 20 Planted Duplicates with 4 Mutation Modes:</b> Duplicates are systematically derived from <code>base_records[i * 8]</code> across 4 targeted mutation types: (1) First name typographical swaps (e.g. <code>Jonathan</code> &rarr; <code>Jonathon</code>), (2) Company legal entity suffixes (e.g. <code>Acme Corp</code> &rarr; <code>Acme Corp Inc</code> or <code>Acme Corporation</code>), (3) Email sub-addressing (e.g. <code>@</code> &rarr; <code>.lead@</code>), and (4) Mixed casing combined with alternate phone representations.<br/>"
        "• <b>Tier 3: 10 Explicit Junk Archetypes:</b> Hardcoded rows containing missing contacts (null email AND phone), spam/bot placeholders (<code>'asdf'</code>, <code>'test company'</code>, <code>'dummy corp'</code>, <code>'null'</code>), invalid phone numbers (<code>'0000000000'</code>, <code>'1234567'</code>), and fake domains (<code>@asdf</code>, <code>@test</code>, <code>@spam</code>).<br/>"
        "<b>Ground-Truth Labeling:</b> The downloaded CSV has no duplicate label (a blind upload). Internally, "
        "<code>generate_sample_leads()</code> tags every record with <code>_person_id</code>, and the generator guarantees the 170 base "
        "people are distinct (an earlier version could randomly create two base records with the same name, company and email, "
        "which made the '20 duplicates' ground truth untrue). <code>backend/evaluate_dedup.py</code> uses these ids to measure "
        f"deduplication accuracy: the dataset contains exactly <b>{M['planted_pairs']}</b> true duplicate pairs.",
        body_style
    ))

    # Q1.3
    story.append(Paragraph("1.3 What fields does a lead have? Does it include behavioral data (opens, clicks), or only static fields?", h2_style))
    story.append(Paragraph(
        "Each lead record models both <b>static firmographic attributes</b> and <b>behavioral activity signals</b> stored in the canonical schema:",
        body_style
    ))

    # Schema Table
    schema_data = [
        [Paragraph("Category", table_header_style), Paragraph("Field Name", table_header_style), Paragraph("Type", table_header_style), Paragraph("Description & Pipeline Usage", table_header_style)],
        [Paragraph("Identity", table_cell_bold), Paragraph("<code>first_name</code>, <code>last_name</code>", table_cell_style), Paragraph("String", table_cell_style), Paragraph("Contact identity, RapidFuzz token matching, auto-name splitting.", table_cell_style)],
        [Paragraph("Contact", table_cell_bold), Paragraph("<code>email</code>, <code>phone</code>", table_cell_style), Paragraph("String", table_cell_style), Paragraph("E.164 phone normalization, domain parsing, junk lead gating.", table_cell_style)],
        [Paragraph("Firmographic", table_cell_bold), Paragraph("<code>company</code>, <code>job_title</code>", table_cell_style), Paragraph("String", table_cell_style), Paragraph("Casing normalization, seniority classification (C-Level, VP, Manager).", table_cell_style)],
        [Paragraph("Firmographic", table_cell_bold), Paragraph("<code>state</code>, <code>industry</code>", table_cell_style), Paragraph("String", table_cell_style), Paragraph("Standardized 2-letter postal code; Territory & Industry routing rules.", table_cell_style)],
        [Paragraph("Firmographic", table_cell_bold), Paragraph("<code>company_size</code>", table_cell_style), Paragraph("Integer", table_cell_style), Paragraph("Employee headcount, enterprise tier scoring bucket (15% weight).", table_cell_style)],
        [Paragraph("Behavioral", table_cell_bold), Paragraph("<code>engagement_score</code>", table_cell_style), Paragraph("Float (0–100)", table_cell_style), Paragraph("Aggregated marketing intent (email opens, link clicks, page visits) (35% weight).", table_cell_style)],
        [Paragraph("Behavioral", table_cell_bold), Paragraph("<code>last_activity_date</code>", table_cell_style), Paragraph("Date (ISO)", table_cell_style), Paragraph("Recency timestamp; drives exponential intent decay formula (25% weight).", table_cell_style)],
    ]
    schema_table = Table(schema_data, colWidths=[65, 115, 55, 293])
    schema_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(schema_table)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<i>Note on Behavioral Data:</i> Behavioral interactions are represented as <b>pre-aggregated indices</b> (<code>engagement_score</code>) and activity timestamps rather than raw event streams (individual clickstream logs). This mirrors standard CRM lead entities in Salesforce and Marketo.",
        callout_style
    ))

    # End of Page 1
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: SECTION 2 (CLEANING & RAPIDFUZZ DEDUPLICATION)
    # =========================================================================
    story.append(Paragraph("2. Data Quality & RapidFuzz Deduplication", h1_style))

    # Q2.1
    story.append(Paragraph("2.1 Why 85%? Did you tune it against anything, or was it a default?", h2_style))
    story.append(Paragraph(
        "<b>Honest answer:</b> 85% started as a default, not a tuned value. It has since been tested against the generator's "
        "ground truth (<code>backend/evaluate_dedup.py</code>). The test showed that the original rule (RapidFuzz "
        "<code>token_sort_ratio</code> on <code>'first last | company | email'</code> alone) is <b>name-blind</b>: two different people at the "
        "same company share most of that string and score around 85%, so they were merged. The rule was therefore changed: a fuzzy "
        "match now also requires the <b>same last name</b>, a <b>first name &ge; 85% similar</b> and the <b>same company or email domain</b> "
        "(<code>backend/app/services/match_rules.py</code>). Exact email or phone matches merge as before.",
        body_style
    ))
    ev_rows = [[Paragraph(h, table_header_style) for h in ("Rule", "Threshold", "Correct merges", "Wrong merges", "Missed", "Precision", "Recall")]]
    for rule, t, tp, fp, fn_, p, r in M["eval"]:
        if t in (80.0, 85.0, 90.0):
            ev_rows.append([Paragraph(rule, table_cell_style), Paragraph(f"{t:.0f}%", table_cell_style), Paragraph(str(tp), table_cell_style),
                            Paragraph(f"<b>{fp}</b>", table_cell_style), Paragraph(str(fn_), table_cell_style),
                            Paragraph(f"{p:.0%}", table_cell_style), Paragraph(f"{r:.0%}", table_cell_style)])
    story.append(styled_table(ev_rows, [140, 60, 70, 70, 50, 68, 70]))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        f"<i>Limit of this test:</i> in the sample data every planted duplicate still shares an email or phone with its original "
        f"({M['new_exact_merges']} of {M['new_merges']} merges are exact matches), so the fuzzy path is exercised by unit tests "
        "(<code>backend/tests/test_dedup_rules.py</code>) rather than by this dataset. The threshold remains 85%; with the name guards "
        "in place it no longer decides between colleagues.",
        callout_style
    ))

    # Q2.2
    story.append(Paragraph("2.2 What does a merge do to the surviving record when fields conflict? Which one wins, and why?", h2_style))
    story.append(Paragraph(
        "<b>Winner Selection Algorithm:</b> When a duplicate cluster is detected, records are scored using a deterministic completeness-and-engagement objective function (<code>cleaning_service.py</code>, <code>score_lead_for_merge</code>):",
        body_style
    ))

    code_box = Table(
        [[Paragraph(
            "<b>Merge Priority Objective Function:</b><br/>"
            "<code>Priority Score = (Completeness Ratio &times; 10) + (Engagement Score / 10)</code><br/>"
            "<i>Where Completeness Ratio is the proportion of non-null, valid contact fields (name, email, company, phone, state).</i>",
            code_style
        )]],
        colWidths=[528]
    )
    code_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(code_box)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>Conflict Resolution Behavior:</b> (1) <b>Winner-Take-All for Canonical Table:</b> The winning record's field values are written to <code>clean_leads</code>. (2) <b>Full Audit Archival:</b> Secondary (losing) records are not deleted permanently; they are archived in <code>merged_leads_log</code> with the kept and archived record IDs (same ID type, labelled by <code>id_type</code>), original contact values, the similarity score, the match reason and a timestamp. (3) <i>Architectural Trade-Off:</i> The system uses winner-take-all rather than field-level coalescing (e.g. adopting the loser's phone if the winner's phone is missing). Because the winner is the most complete record, it usually carries the most data, but nothing from the losing record is copied over (no enrichment). In an enterprise CRM, secondary phones can be preserved in an alternate contact array.",
        body_style
    ))

    # Q2.3
    story.append(Paragraph("2.3 Have you looked at borderline matches (80–90%)? What did they look like?", h2_style))
    story.append(Paragraph(
        "Yes. The pairs below are real outputs: the first rows are wrong merges the <b>old</b> rule made at 85% on the sample data "
        "(different people, same company); the last rows are constructed typo pairs run through the <b>new</b> rule.",
        body_style
    ))
    bl = [[Paragraph(h, table_header_style) for h in ("Composite score", "Old rule", "New rule", "Record pair", "Why")]]
    for score, a, b in M["old_wrong_merges"][:4]:
        bl.append([Paragraph(f"<b>{score}%</b>", table_cell_style), Paragraph("<font color='#dc2626'><b>MERGED</b></font>", table_cell_style),
                   Paragraph("<font color='#059669'><b>KEPT SEPARATE</b></font>", table_cell_style),
                   Paragraph(f"• {a}<br/>• {b}", table_cell_style), Paragraph("Different last names: different people.", table_cell_style)])
    for (ok, score, reason), a, b in M["fuzzy_examples"]:
        bl.append([Paragraph(f"<b>{score}%</b>", table_cell_style), Paragraph("-", table_cell_style),
                   Paragraph("<font color='#059669'><b>MERGED</b></font>" if ok else "<font color='#b45309'><b>NOT MERGED</b></font>", table_cell_style),
                   Paragraph(f"• {a['first_name']} {a['last_name']} | {a['company']} | {a['email']}<br/>• {b['first_name']} {b['last_name']} | {b['company']} | {b['email']}", table_cell_style),
                   Paragraph(reason + ("" if ok else ". A true duplicate missed: this is the case a human review queue should catch."), table_cell_style)])
    story.append(styled_table(bl, [55, 55, 70, 190, 158]))

    # Q2.4
    story.append(Paragraph(f"2.4 Math audit: {M['raw_count']} raw leads, {C['duplicate_records_merged']} merged, {M['assigned']} assigned. Where does each lead go?", h2_style))
    audit_rows = [[Paragraph(h, table_header_style) for h in ("Pipeline Stage", "Lead Count", "Database Entity", "Description")]]
    for stage, count, entity, desc in (
        ("1. Raw ingestion", f"{M['raw_count']}", "raw_leads", "Leads ingested from the sample CSV."),
        ("2. Deduplication", f"- {C['duplicate_records_merged']}", "merged_leads_log", "Duplicates merged into cluster winners and archived."),
        ("3. Clean leads stored", f"{M['clean_count']}", "clean_leads", f"{M['clean_count'] - M['junk_count']} valid + {M['junk_count']} junk records."),
        ("4. Junk quarantine", f"- {M['junk_count']}", "is_junk = True", "Placeholder/bot records kept for reporting, excluded from routing."),
        ("5. Sales rep assignment", f"{M['assigned']}", "assignment_log", "Every non-junk lead routed with a rationale."),
    ):
        audit_rows.append([Paragraph(stage, table_cell_bold), Paragraph(f"<b>{count}</b>", table_cell_style),
                           Paragraph(f"<code>{entity}</code>", table_cell_style), Paragraph(desc, table_cell_style)])
    story.append(styled_table(audit_rows, [105, 60, 105, 258]))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>Code verification:</b> the assignment service selects <code>CleanLead.is_junk == False</code>. Junk records stay in "
        "<code>clean_leads</code> for governance reporting but are never routed to sales reps.",
        body_style
    ))

    # End of Page 2
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: SECTION 3 (LEAD SCORING ENGINE)
    # =========================================================================
    story.append(Paragraph("3. Lead Scoring Engine (Dual Architecture)", h1_style))

    # Q3.1
    story.append(Paragraph("3.1 What data was the ML model trained on, and where did its labels come from? Are they independent of rule weights?", h2_style))
    story.append(Paragraph(
        "<b>Model Architecture:</b> Implemented in <code>backend/app/ml/scoring_model.py</code> using Scikit-Learn: "
        "a <code>Pipeline([('scaler', StandardScaler()), ('classifier', LogisticRegression(max_iter=1000))])</code>.<br/>"
        "<b>Training Data & Ground-Truth Generation:</b> The model was trained on a synthetic historical cohort of <b>N = 1,500 B2B leads</b>. "
        "Binary conversion labels (<code>converted &isin; {0, 1}</code>) were generated by a hand-written simulation (the coefficients below are assumptions, not fitted to real conversion data):",
        body_style
    ))

    formula_box = Table(
        [[Paragraph(
            "<b>Latent Conversion Logit Equation:</b><br/>"
            "<code>logit = -2.5 + 0.4&times;ln(1 + size/100) + 0.8&times;TargetInd + 0.015&times;Seniority + 0.035&times;Engagement - 0.02&times;DaysActive</code><br/>"
            "<code>P(converted) = 1 / (1 + exp(-logit)) &nbsp;&nbsp;|&nbsp;&nbsp; converted = 1 if P(converted) &gt; U(0, 1) else 0</code>",
            code_style
        )]],
        colWidths=[528]
    )
    formula_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(formula_box)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>Independence Analysis:</b><br/>"
        "• <b>Functional Independence:</b> The models use distinct mathematical formalisms. The rule-based engine uses a piece-wise linear weighted sum with step functions for firmographic tiers and exponential decay for recency. The ML model uses log-transformed features and logistic regression with standard scaling, trained with stochastic binomial variance.<br/>"
        "• <b>Hypothesis Alignment:</b> The conversion labels are derived from a domain simulation rather than live CRM closed-won deal logs. Consequently, both models embody the same fundamental domain hypothesis: higher engagement + recent activity + enterprise decision-maker seniority = higher probability of conversion.",
        body_style
    ))

    # Q3.2
    story.append(Paragraph("3.2 How did you choose the weights (35% engagement, 25% recency, etc.)? Reasoned, copied, or guessed?", h2_style))
    story.append(Paragraph(
        "<b>Source & Rationale:</b> The weights were <b>chosen by judgement</b>, following the common lead-scoring practice of combining "
        "behavioural and firmographic signals. They were not taken from a published benchmark and have not been fitted to outcome data.",
        body_style
    ))

    weights_data = [
        [Paragraph("Category", table_header_style), Paragraph("Signal Name", table_header_style), Paragraph("Weight", table_header_style), Paragraph("Core Revenue Operations Rationale", table_header_style)],
        [Paragraph("Behavioral", table_cell_bold), Paragraph("Engagement Score", table_cell_style), Paragraph("<b>35%</b>", table_cell_style), Paragraph("Direct marketing intent (email opens, link clicks, high-intent page visits). Highest predictor of immediate sales receptivity.", table_cell_style)],
        [Paragraph("Behavioral", table_cell_bold), Paragraph("Recency Decay", table_cell_style), Paragraph("<b>25%</b>", table_cell_style), Paragraph("Applies exponential half-life decay (S = 100 &times; e^(-0.02 &times; days)). Inbound buyer intent deteriorates rapidly within 30 days.", table_cell_style)],
        [Paragraph("Firmographic", table_cell_bold), Paragraph("Target Industry", table_cell_style), Paragraph("<b>15%</b>", table_cell_style), Paragraph("ICP alignment (SaaS, Fintech, Cybersecurity, Healthcare IT). Focuses sales team on highest LTV markets.", table_cell_style)],
        [Paragraph("Firmographic", table_cell_bold), Paragraph("Company Size", table_cell_style), Paragraph("<b>15%</b>", table_cell_style), Paragraph("Tiered scoring (&lt;50: 35pts, 100-999: 65pts, 5000+: 100pts). Enterprise accounts generate higher Average Contract Value (ACV).", table_cell_style)],
        [Paragraph("Firmographic", table_cell_bold), Paragraph("Job Seniority", table_cell_style), Paragraph("<b>10%</b>", table_cell_style), Paragraph("Decision-maker authority (C-Level: 100pts, VP/Director: 80pts, Manager: 50pts, Staff: 25pts). Shortens sales cycle velocity.", table_cell_style)],
    ]
    weights_table = Table(weights_data, colWidths=[65, 95, 50, 318])
    weights_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(weights_table)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>The 60/40 split (behavioural over firmographic):</b> behavioural signals get 60% of the weight and firmographic fit 40%, a "
        "deliberate choice to favour recent intent (1.5&times; the weight, not a measured predictive ratio). The reasoning: a large account "
        "with no activity in 90 days is less ready than a mid-size account reading pricing pages this week. This assumption is untested.",
        body_style
    ))

    # Q3.3
    story.append(Paragraph("3.3 Is there any way to check that Hot leads convert better than Cold ones, or is the score unvalidated?", h2_style))
    story.append(Paragraph(
        "<b>Current Validation Status:</b> The score is <b>directionally validated</b> against the ML model's predicted conversion probability distribution, "
        "but <b>empirically unvalidated against live post-assignment sales outcomes</b>, because the uploaded dataset reflects top-of-funnel inbound leads rather than completed sales opportunities.<br/>"
        "<b>Validation Methodology for Production Deployment:</b><br/>"
        "1. <b>Cohort Conversion Funnel Analysis:</b> Measure conversion rates across score bands through subsequent funnel stages: MQL &rarr; SQL &rarr; Opportunity &rarr; Closed-Won. The bands are only useful if Hot converts clearly better than Warm, and Warm better than Cold; target rates should be set from the team&#39;s own historical data.<br/>"
        "2. <b>Statistical Discrimination Metrics:</b> Once sales reps log deal outcomes in <code>assignment_log</code>, compute ROC-AUC and Brier score to measure how well the score separates and calibrates outcomes; set targets after a baseline is measured.<br/>"
        "3. <b>Continuous Feedback Loop:</b> Retrain Logistic Regression coefficients quarterly against verified Salesforce/HubSpot closed-won outcomes.",
        body_style
    ))

    # End of Page 3
    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: SECTION 4 (OUTCOMES, RETROSPECTIVE & ASSESSMENT)
    # =========================================================================
    story.append(Paragraph("4. Pipeline Outcomes & Architectural Retrospective", h1_style))

    # Q4.1
    story.append(Paragraph(f"4.1 What do before/after numbers show beyond {M['raw_count']} &rarr; {M['clean_count']}?", h2_style))
    story.append(Paragraph("Measured on the built-in 200-lead sample:", body_style))
    out_rows = [[Paragraph(h, table_header_style) for h in ("Metric", "Before", "After", "Notes")]]
    for metric, before, after, note in (
        ("Duplicate rate", f"{C['duplicate_rate_before']}% ({C['duplicate_records_merged']} duplicate records)", "0% (merged into winners)", "One record per person before routing."),
        ("Field completeness", f"{C['completeness_score_before']}%", f"{C['completeness_score_after']}%",
         "Small rise because the most complete record of each cluster is kept; no fields are enriched."),
        ("Phones in E.164 format", pct(M['raw_phone_e164']), pct(M['phone_e164']), "Normalised to +1XXXXXXXXXX."),
        ("States as 2-letter codes", pct(M['raw_state_codes']), pct(M['state_codes']), "'calif', 'New York' etc. mapped to CA, NY."),
        ("Junk records", f"{M['junk_count']} ({M['junk_count'] / M['raw_count']:.0%})", f"{M['junk_count']} quarantined", "Kept for reporting, never routed."),
        ("Routing", "None", f"{M['assigned']} leads routed with rationale", "Every non-junk lead assigned."),
    ):
        out_rows.append([Paragraph(f"<b>{metric}</b>", table_cell_style), Paragraph(before, table_cell_style),
                         Paragraph(f"<b>{after}</b>", table_cell_style), Paragraph(note, table_cell_style)])
    story.append(styled_table(out_rows, [110, 120, 120, 178]))
    story.append(Spacer(1, 3))
    rule_names = {"Rule 1": "Territory + Industry match", "Rule 2": "Territory match only",
                  "Rule 3": "Industry specialty only", "Rule 4": "Round-robin fallback"}
    lines = "".join(
        f"&bull; <b>{k} ({rule_names[k]}):</b> {M['rules'].get(k, 0)} leads ({M['rules'].get(k, 0) / max(1, M['assigned']):.0%})<br/>"
        for k in rule_names)
    story.append(Paragraph(
        f"<b>Sales assignment rule breakdown ({M['assigned']} leads):</b><br/>{lines}"
        "<i>Every sample lead falls in a state covered by a rep, so Rules 3 and 4 are not reached on this dataset.</i>",
        body_style
    ))

    # Q4.2
    story.append(Paragraph("4.2 What's the one thing you're proudest of, and the one thing you know is weak?", h2_style))
    story.append(Paragraph(
        "<b>The One Thing I'm Proudest Of:</b><br/>"
        "<b>The Complete, End-to-End Explainability and Auditability Architecture.</b><br/>"
        "Many commercial CRM routing and scoring engines are impenetrable black boxes. In this engine, every automated action is completely transparent and defensible to sales and marketing leadership:",
        body_style
    ))
    story.append(Paragraph("• <i>Deduplication Transparency:</i> Every merged record writes to <code>merged_leads_log</code> with the kept and archived record IDs, the similarity score and the match reason.", bullet_style))
    story.append(Paragraph("• <i>Scoring Transparency:</i> Every scored lead stores a full JSON breakdown containing individual point contributions, weights, and explanations for each of the 5 firmographic and behavioral signals.", bullet_style))
    story.append(Paragraph("• <i>Assignment Transparency:</i> Every routed lead carries a clear routing rationale (e.g. <code>'Assigned to Rep Sarah Jenkins: territory match (CA) + industry match (SaaS)'</code>) logged in <code>assignment_log</code>.", bullet_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>The One Thing I Know is Weak:</b><br/>"
        "<b>The Lack of a Closed-Loop CRM Outcome Feedback Loop (Static Calibration).</b><br/>"
        "Currently, the ML scoring model is trained on synthetic conversion simulations, and rule weights are static constants. The engine operates in a feed-forward manner without an automated feedback webhook from downstream CRM deals (Closed-Won / Closed-Lost outcomes). "
        "If sales reps disqualify certain lead profiles or close deals at unexpected rates, that outcome data does not yet automatically update the Logistic Regression weights. In a future iteration, an automated closed-loop retraining pipeline would enable true self-optimizing lead intelligence.",
        body_style
    ))

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated: {filename}")

if __name__ == "__main__":
    output_filename = "MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"
    build_pdf(output_filename)
