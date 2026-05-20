#!/usr/bin/env python3
"""
Generate PDF from architectural refactor plan markdown.
"""
import os
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime

# Setup
BASE_DIR = Path(__file__).resolve().parent
MD_FILE = BASE_DIR / "ARCHITECTURAL_REFACTOR_PLAN.md"
PDF_FILE = BASE_DIR / "ARCHITECTURAL_REFACTOR_PLAN.pdf"

# Create PDF
doc = SimpleDocTemplate(
    str(PDF_FILE),
    pagesize=letter,
    rightMargin=0.75*inch,
    leftMargin=0.75*inch,
    topMargin=0.75*inch,
    bottomMargin=0.75*inch,
)

# Define styles
styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=24,
    textColor=colors.HexColor('#1a1a1a'),
    spaceAfter=6,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold',
)
heading1_style = ParagraphStyle(
    'CustomHeading1',
    parent=styles['Heading1'],
    fontSize=14,
    textColor=colors.HexColor('#d32f2f'),
    spaceAfter=10,
    spaceBefore=12,
    fontName='Helvetica-Bold',
)
heading2_style = ParagraphStyle(
    'CustomHeading2',
    parent=styles['Heading2'],
    fontSize=11,
    textColor=colors.HexColor('#1976d2'),
    spaceAfter=8,
    spaceBefore=10,
    fontName='Helvetica-Bold',
)
heading3_style = ParagraphStyle(
    'CustomHeading3',
    parent=styles['Heading3'],
    fontSize=10,
    textColor=colors.HexColor('#555555'),
    spaceAfter=6,
    spaceBefore=6,
    fontName='Helvetica-Bold',
)
body_style = ParagraphStyle(
    'CustomBody',
    parent=styles['BodyText'],
    fontSize=9,
    alignment=TA_JUSTIFY,
    spaceAfter=8,
    leading=12,
)
code_style = ParagraphStyle(
    'CodeStyle',
    parent=styles['BodyText'],
    fontSize=8,
    textColor=colors.HexColor('#333333'),
    leftIndent=20,
    rightIndent=20,
    backColor=colors.HexColor('#f5f5f5'),
    spaceAfter=6,
    fontName='Courier',
)

# Parse markdown and build story
story = []

def add_title(text):
    story.append(Paragraph(text, title_style))
    story.append(Spacer(1, 0.15*inch))

def add_heading1(text):
    story.append(Paragraph(text, heading1_style))

def add_heading2(text):
    story.append(Paragraph(text, heading2_style))

def add_heading3(text):
    story.append(Paragraph(text, heading3_style))

def add_para(text):
    if text.strip():
        story.append(Paragraph(text, body_style))

def add_code(text):
    story.append(Paragraph(text, code_style))

def add_space(height=0.1):
    story.append(Spacer(1, height*inch))

def add_page_break():
    story.append(PageBreak())

# Read and parse markdown
with open(MD_FILE, 'r') as f:
    lines = f.readlines()

i = 0
while i < len(lines):
    line = lines[i].rstrip()
    
    # Title
    if line.startswith('# ') and i == 0:
        add_title(line[2:])
    # Heading 1
    elif line.startswith('## '):
        if i > 10:  # Page break after intro sections
            add_page_break()
        add_heading1(line[3:])
    # Heading 2
    elif line.startswith('### '):
        add_heading2(line[4:])
    # Heading 3
    elif line.startswith('#### '):
        add_heading3(line[5:])
    # Code block
    elif line.startswith('```'):
        code_lines = []
        i += 1
        while i < len(lines) and not lines[i].startswith('```'):
            code_lines.append(lines[i].rstrip())
            i += 1
        add_code('<br/>'.join(code_lines[:15]))  # Limit to 15 lines
    # Metadata line
    elif line.startswith('**') and ':' in line:
        add_para(line)
    # Bullet point
    elif line.startswith('- '):
        add_para('• ' + line[2:])
    # Numbered list
    elif line and line[0].isdigit() and line[1:3] == '. ':
        add_para(line)
    # Table
    elif line.startswith('|'):
        table_lines = [line]
        i += 1
        while i < len(lines) and lines[i].startswith('|'):
            table_lines.append(lines[i].rstrip())
            i += 1
        
        # Parse table
        rows = []
        for tline in table_lines:
            cells = [c.strip() for c in tline.split('|')[1:-1]]
            rows.append(cells)
        
        if len(rows) > 2:  # Skip header separator
            table_data = rows[::2]  # Take every other row to skip separators
            table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 2.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d32f2f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            story.append(table)
            story.append(add_space(0.15))
        i -= 1
    # Regular paragraph
    elif line.strip() and not line.startswith('---'):
        add_para(line)
    # Horizontal rule
    elif line.startswith('---'):
        add_space(0.15)
    else:
        add_space(0.08)
    
    i += 1

# Build PDF
doc.build(story)
print(f"✓ PDF generated: {PDF_FILE}")
