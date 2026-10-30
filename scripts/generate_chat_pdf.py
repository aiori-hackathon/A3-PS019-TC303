"""
scripts/generate_chat_pdf.py
============================
Generates a comprehensive, professional PDF document summarizing the entire
PrivSight TRACERA conversation, architecture, bug fixes, file changes, and
operational status for handoff to a new chat session.
"""

import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
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
        self.setFillColor(colors.HexColor("#71717A"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "PRIVSIGHT · TRACERA — Complete Session Handoff & Technical Dossier")
            self.drawRightString(558, 750, "CONFIDENTIAL / INTERNAL")
            self.setStrokeColor(colors.HexColor("#E4E4E7"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(54, 36, "PrivSight Technical Handoff Document · AI Relationship Intelligence")
        self.drawRightString(558, 36, page_str)
        self.setStrokeColor(colors.HexColor("#E4E4E7"))
        self.setLineWidth(0.5)
        self.line(54, 46, 558, 46)
        
        self.restoreState()


def build_pdf(filename="PrivSight_TRACERA_Chat_Session_Handoff.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Brand Colors
    c_primary = colors.HexColor("#0C2B1E")    # Forest obsidian green
    c_gold = colors.HexColor("#D4A72C")       # Muted rich gold
    c_orange = colors.HexColor("#EA580C")     # Accent orange
    c_dark = colors.HexColor("#18181B")       # Text dark
    c_muted = colors.HexColor("#52525B")      # Text muted
    c_bg_subtle = colors.HexColor("#F4F4F5")  # Table / box subtle
    c_border = colors.HexColor("#E4E4E7")

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_primary,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=c_gold,
        spaceAfter=14
    )

    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_muted
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=c_dark,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=c_dark,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'CodeSnippet',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#09090B")
    )

    chat_user_style = ParagraphStyle(
        'ChatUser',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0F766E")
    )

    chat_ai_style = ParagraphStyle(
        'ChatAI',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_dark
    )

    story = []

    # ==========================================
    # COVER / HEADER BLOCK
    # ==========================================
    story.append(Paragraph("PRIVSIGHT · TRACERA", subtitle_style))
    story.append(Paragraph("Full Session Handoff & Technical Architecture Dossier", title_style))
    story.append(Paragraph("Trace. Analyze. Understand. — AI-Powered Relationship Intelligence Assistant", subtitle_style))
    
    meta_data = [
        [
            Paragraph("<b>Generated:</b> " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"), meta_style),
            Paragraph("<b>Target Branch:</b> main", meta_style),
            Paragraph("<b>Latest Commit:</b> 107e7bb", meta_style),
        ],
        [
            Paragraph("<b>Repository:</b> aiori-hackathon/A3-PS019-TC303", meta_style),
            Paragraph("<b>Dev Server:</b> http://127.0.0.1:8000", meta_style),
            Paragraph("<b>Status:</b> Clean & Verified (11/11 tests pass)", meta_style),
        ]
    ]
    t_meta = Table(meta_data, colWidths=[170, 170, 164])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_subtle),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=c_gold, spaceAfter=14))

    # ==========================================
    # SECTION 1: EXECUTIVE SUMMARY
    # ==========================================
    story.append(Paragraph("1. Executive Summary & Purpose", h1_style))
    story.append(Paragraph(
        "This dossier contains the complete context, architectural blueprints, bug resolution history, "
        "and conversation logs of the <b>TRACERA AI Assistant</b> within the <b>PrivSight</b> privacy "
        "governance platform. A new chat instance can ingest this document to immediately resume development "
        "without losing architectural context or repeating previous diagnostic cycles.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Core Product Identity:</b> TRACERA (<i>Trace. Analyze. Understand.</i>) is PrivSight's native "
        "AI relationship intelligence assistant. It provides zero-fabrication relational reasoning across "
        "scanned CSVs, SQLite databases, and multi-format files, distinguishing confirmed foreign/primary keys "
        "from confidence-scored inferences with strict PII masking.",
        body_style
    ))

    # ==========================================
    # SECTION 2: COMPLETED WORK & CHRONOLOGY
    # ==========================================
    story.append(Paragraph("2. Chronology of Completed Tasks", h1_style))
    
    tasks = [
        ("Milestone 1: Terminology Normalization", 
         "Updated legacy labels to exact standardized enterprise terms: 'Data Fields Checked' (from Fields Scanned), 'Personal Data Found' (from PII Candidates), 'Metadata Completed' (from Complete Metadata), and 'Missing Proof' (from Evidence Gaps) without altering business logic."),
        
        ("Milestone 2: Relationship Explorer Engine", 
         "Built end-to-end backend and frontend relationship engine in backend/relationships/: relationship graph models, schema constraint discovery, cross-dataset intersection heuristics, Cytoscape.js interactive topology graph, and CSV/SQLite multi-source scanner."),
        
        ("Milestone 3: Dedicated TRACERA Page Integration", 
         "Integrated TRACERA as a top-level dedicated platform page at /tracera inside PrivSight, featuring persistent threads, sidebar history, dataset filter pill trays, format preference selectors (Text, Graph, Table, Timeline, Flowchart), and disclaimer banners."),
        
        ("Milestone 4: Chat Message Alignment & Deduplication Fix (Highest Priority)", 
         "Completely re-engineered message lifecycle: resolved duplicate message rendering via client-side Set deduplication, added request mutex locks, fixed context inheritance bugs where queries inherited previous entities, applied strict ChatGPT-style right-alignment for user bubbles and left-alignment for TRACERA AI cards, and implemented full Markdown rendering for tables and code blocks.")
    ]

    for title, desc in tasks:
        story.append(Paragraph(f"• <b>{title}:</b> {desc}", bullet_style))
    story.append(Spacer(1, 8))

    # ==========================================
    # SECTION 3: ROOT CAUSE FIXES & ARCHITECTURE
    # ==========================================
    story.append(Paragraph("3. Root Causes & Technical Solutions Implemented", h1_style))
    
    fixes_table_data = [
        [
            Paragraph("<b>Issue Category</b>", h2_style),
            Paragraph("<b>Root Cause Diagnosed</b>", h2_style),
            Paragraph("<b>Architectural Solution Applied</b>", h2_style)
        ],
        [
            Paragraph("<b>Message Alignment</b>", body_style),
            Paragraph("User and assistant messages shared the same row wrapper with no strict flexbox justification.", body_style),
            Paragraph("Created distinct CSS classes: <code>.tracera-message-row.user</code> (flex-end, 75% max width) and <code>.tracera-message-row.assistant</code> (flex-start, full width card with avatar and header).", body_style)
        ],
        [
            Paragraph("<b>Conversation ID Disconnect</b>", body_style),
            Paragraph("Backend created new conversations on first prompt, but <code>RelationshipReport</code> did not serialize <code>conversation_id</code> back to frontend.", body_style),
            Paragraph("Added <code>conversation_id</code> and <code>message_id</code> fields to <code>RelationshipReport</code> in models.py and routes.py. Client locks onto conversation ID immediately.", body_style)
        ],
        [
            Paragraph("<b>Duplicate Rendering</b>", body_style),
            Paragraph("Missing idempotency check during DOM rendering and missing mutex lock on prompt submissions.", body_style),
            Paragraph("Implemented <code>renderedMessageIds = new Set()</code> in <code>ChatMessageList</code> and an <code>isSubmitting</code> guard in <code>MessageComposer</code>.", body_style)
        ],
        [
            Paragraph("<b>Repeated Answers</b>", body_style),
            Paragraph("In <code>ai_assistant.py</code> line 177, non-ID queries fell back to previous history entity even without pronouns.", body_style),
            Paragraph("Constrained context inheritance strictly to pronoun-based queries (<code>has_pronoun and history</code>).", body_style)
        ],
        [
            Paragraph("<b>Welcome Screen Flaws</b>", body_style),
            Paragraph("Welcome hero was rendered inside messages container and reappeared erratically.", body_style),
            Paragraph("Encapsulated <code>WelcomeScreen</code> component: displays ONLY when message count is 0; destroyed on first send; restored on '+ New Chat'.", body_style)
        ],
        [
            Paragraph("<b>Markdown Formatting</b>", body_style),
            Paragraph("Markdown rendered as raw unformatted text without table, list, or code support.", body_style),
            Paragraph("Engineered Markdown parser supporting tables (<code>.tracera-md-table</code>), code blocks (<code>pre code</code>), blockquotes, headings h1-h4, and lists.", body_style)
        ]
    ]

    t_fixes = Table(fixes_table_data, colWidths=[95, 205, 204])
    t_fixes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_bg_subtle),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_fixes)
    story.append(Spacer(1, 14))

    # Page Break for Code Structure & Test Results
    story.append(PageBreak())

    # ==========================================
    # SECTION 4: FILE STRUCTURE & REPOSITORIES
    # ==========================================
    story.append(Paragraph("4. Key Files & Architecture Map", h1_style))

    files_data = [
        [Paragraph("<b>File Path</b>", h2_style), Paragraph("<b>Component / Purpose</b>", h2_style)],
        [Paragraph("<code>frontend/tracera.js</code>", code_style), Paragraph("Client-side modular controller: <code>WelcomeScreen</code>, <code>UserMessage</code>, <code>AssistantMessage</code>, <code>ChatMessageList</code>, <code>MessageComposer</code>, Markdown engine, Cytoscape graph renderer.", body_style)],
        [Paragraph("<code>frontend/tracera.html</code>", code_style), Paragraph("Dedicated HTML page layout for TRACERA assistant, sidebar history, dataset filter tray, messages container.", body_style)],
        [Paragraph("<code>frontend/style.css</code>", code_style), Paragraph("PrivSight design system tokens, flexbox alignment for user/assistant messages, markdown typography, table and code styles.", body_style)],
        [Paragraph("<code>backend/relationships/ai_assistant.py</code>", code_style), Paragraph("TRACERA AI reasoning engine: query intent detection, zero-fabrication factual retrieval, multi-turn context resolution.", body_style)],
        [Paragraph("<code>backend/relationships/models.py</code>", code_style), Paragraph("Pydantic models: <code>RelationshipReport</code>, <code>ChatMessage</code>, <code>ConversationThread</code>, <code>RelationshipGraph</code>.", body_style)],
        [Paragraph("<code>backend/relationships/routes.py</code>", code_style), Paragraph("FastAPI endpoints: <code>/api/relationships/chat</code>, <code>/conversations</code>, <code>/sources</code>, <code>/graph</code>.", body_style)],
        [Paragraph("<code>tests/test_relationships.py</code>", code_style), Paragraph("11 automated backend integration tests verifying auth, lifecycle, context, graph, table, timeline, and titling.", body_style)]
    ]

    t_files = Table(files_data, colWidths=[180, 324])
    t_files.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_bg_subtle),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_files)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 5: VERIFICATION & TEST LOG
    # ==========================================
    story.append(Paragraph("5. Quality Assurance & Test Verification Log", h1_style))
    story.append(Paragraph("All 10 required prompt test scenarios were executed and passed:", body_style))

    test_rows = [
        [Paragraph("<b>Test Case</b>", h2_style), Paragraph("<b>Verification Method</b>", h2_style), Paragraph("<b>Status</b>", h2_style)],
        [Paragraph("TEST 1: User message right alignment", body_style), Paragraph("Single message prompt sent; verified <code>justify-content: flex-end</code> on <code>.tracera-message-row.user</code>.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 2: AI response left alignment", body_style), Paragraph("AI response rendered via <code>.tracera-message-row.assistant</code> with avatar and branding.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 3: Alternating multi-turn alignment", body_style), Paragraph("Consecutive messages verified: User (R) -> AI (L) -> User (R) -> AI (L).", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 4: Welcome screen lifecycle", body_style), Paragraph("Welcome screen disappears on prompt submission; reappears on '+ New Chat'.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 5: Page refresh deduplication", body_style), Paragraph("Refreshed active conversation; verified <code>renderedMessageIds</code> prevented duplicate rendering.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 6: Thread history loading", body_style), Paragraph("Selected older thread; verified chronological message restoration.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 7: Markdown formatting", body_style), Paragraph("Verified headings, code snippets, blockquotes, and tables render with clear vertical spacing.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 8: New chat isolation", body_style), Paragraph("Clicked '+ New Chat'; created isolated thread without old conversation leakage.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 9: Console & Network sanity", body_style), Paragraph("Inspected network calls; 0 duplicate POSTs or render loops.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
        [Paragraph("TEST 10: Fixed bottom composer", body_style), Paragraph("Composer auto-expands from 110px to 250px; Enter key sends; Shift+Enter creates newline.", body_style), Paragraph("<font color='#059669'><b>PASSED</b></font>", body_style)],
    ]

    t_tests = Table(test_rows, colWidths=[170, 260, 74])
    t_tests.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_bg_subtle),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_tests)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 6: COMPLETE CHAT TRANSCRIPT SUMMARY
    # ==========================================
    story.append(Paragraph("6. Chronological Chat Transcript & Handoff Prompts", h1_style))
    story.append(Paragraph("Below is the record of user prompts and agent actions from this session:", body_style))

    chat_logs = [
        ("User Prompt (Initial)", "analyse the project, run the project and give me the link. Make changes in name of functionalities: Fields Scanned -> Data Fields Checked, PII Candidates -> Personal Data Found, Complete Metadata -> Metadata Completed, Evidence Gaps -> Missing Proof. Push to repo."),
        ("Agent Action", "Renamed UI labels in frontend/index.html, frontend/app.js, frontend/inventory.html, docs/demo_checklist.md, and verified backend functionality remained intact. Committed and pushed to GitHub."),
        
        ("User Prompt (Relationship Explorer)", "Add AI Relationship Explorer into PrivSight: real uploaded dataset analysis, SQLite foreign keys, CSV intersection, interactive graph canvas."),
        ("Agent Action", "Implemented backend/relationships/ with Graph Engine, Models, Routes, and Frontend visual Cytoscape graph canvas with 11 unit tests passing."),

        ("User Prompt (TRACERA Integration)", "Integrate TRACERA AI assistant (Trace. Analyze. Understand.) as a dedicated page inside PrivSight. Support persistent threads, format switcher, dataset filtering."),
        ("Agent Action", "Created frontend/tracera.html, backend/relationships/ai_assistant.py, and automated thread management with zero-fabrication evidence provenance."),

        ("User Prompt (Fix Chat Alignment & Duplication)", "Fix chat message alignment (user on right, TRACERA AI on left), repeated/duplicated content, welcome screen lifecycle, markdown rendering, modular component architecture."),
        ("Agent Action", "Completed comprehensive fix across backend models, routes, ai_assistant.py, frontend style.css, tracera.html, and tracera.js. All 10 tests verified in browser. Pushed commit 107e7bb to main.")
    ]

    for sender, text in chat_logs:
        story.append(Paragraph(f"<b>{sender}</b>", chat_user_style if "User" in sender else chat_ai_style))
        story.append(Paragraph(text, body_style))
        story.append(Spacer(1, 4))

    # ==========================================
    # SECTION 7: OPERATIONAL RUNBOOK
    # ==========================================
    story.append(Spacer(1, 8))
    story.append(Paragraph("7. Operational Runbook for the Next Chat Agent", h1_style))
    story.append(Paragraph("To immediately spin up or verify the environment in a new session:", body_style))
    
    runbook_steps = [
        "<b>Run Server:</b> <code>.venv\\Scripts\\python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000</code>",
        "<b>TRACERA URL:</b> <font color='#D4A72C'>http://127.0.0.1:8000/tracera</font>",
        "<b>Workspace URL:</b> <font color='#D4A72C'>http://127.0.0.1:8000/</font>",
        "<b>Auth Credentials:</b> <code>admin</code> / <code>password123</code> or <code>analyst</code> / <code>password123</code>",
        "<b>Run Test Suite:</b> <code>.venv\\Scripts\\pytest tests/test_relationships.py -v</code> (11 passing tests)",
        "<b>Git Remote:</b> <code>https://github.com/aiori-hackathon/A3-PS019-TC303.git</code> on branch <code>main</code>"
    ]
    for step in runbook_steps:
        story.append(Paragraph(f"• {step}", bullet_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] PDF generated at: {filename}")

if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "PrivSight_TRACERA_Chat_Session_Handoff.pdf"
    build_pdf(out_path)
