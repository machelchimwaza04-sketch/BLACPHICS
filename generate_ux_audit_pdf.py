#!/usr/bin/env python3
"""
Generate PDF from UX Audit markdown for Blacphics.
"""
import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

BASE_DIR = Path(__file__).resolve().parent
MD_FILE = BASE_DIR / "UX_AUDIT_ASIS_AND_V2_VISION.md"
PDF_FILE = BASE_DIR / "UX_AUDIT_ASIS_AND_V2_VISION.pdf"

doc = SimpleDocTemplate(
    str(PDF_FILE),
    pagesize=letter,
    rightMargin=0.75*inch,
    leftMargin=0.75*inch,
    topMargin=0.75*inch,
    bottomMargin=0.75*inch,
)

styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=22,
    textColor=colors.HexColor('#1a1a1a'),
    spaceAfter=6,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold',
)
heading1_style = ParagraphStyle(
    'CustomHeading1',
    parent=styles['Heading1'],
    fontSize=13,
    textColor=colors.HexColor('#d32f2f'),
    spaceAfter=10,
    spaceBefore=12,
    fontName='Helvetica-Bold',
)
heading2_style = ParagraphStyle(
    'CustomHeading2',
    parent=styles['Heading2'],
    fontSize=10.5,
    textColor=colors.HexColor('#1976d2'),
    spaceAfter=8,
    spaceBefore=10,
    fontName='Helvetica-Bold',
)
heading3_style = ParagraphStyle(
    'CustomHeading3',
    parent=styles['Heading3'],
    fontSize=9.5,
    textColor=colors.HexColor('#555555'),
    spaceAfter=6,
    spaceBefore=6,
    fontName='Helvetica-Bold',
)
body_style = ParagraphStyle(
    'CustomBody',
    parent=styles['BodyText'],
    fontSize=8.5,
    alignment=TA_JUSTIFY,
    spaceAfter=8,
    leading=11,
)

story = []

def add_title(text):
    story.append(Paragraph(text, title_style))
    story.append(Spacer(1, 0.12*inch))

def add_heading1(text):
    story.append(Paragraph(text, heading1_style))

def add_heading2(text):
    story.append(Paragraph(text, heading2_style))

def add_heading3(text):
    story.append(Paragraph(text, heading3_style))

def add_para(text):
    if text.strip():
        story.append(Paragraph(text, body_style))

def add_space(height=0.08):
    story.append(Spacer(1, height*inch))

def add_page_break():
    story.append(PageBreak())

with open(MD_FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

i = 0
page_count = 0
while i < len(lines):
    line = lines[i].rstrip()
    
    if line.startswith('# ') and i == 0:
        add_title(line[2:])
    elif line.startswith('## '):
        page_count += 1
        if page_count > 1:
            add_page_break()
        add_heading1(line[3:])
    elif line.startswith('### '):
        add_heading2(line[4:])
    elif line.startswith('#### '):
        add_heading3(line[5:])
    elif line.startswith('```'):
        code_lines = []
        i += 1
        while i < len(lines) and not lines[i].startswith('```'):
            code_lines.append(lines[i].rstrip())
            i += 1
        add_para(
            '<font face="Courier" size="7">' + 
            '<br/>'.join([l[:60] for l in code_lines[:12]]) + 
            '</font>'
        )
    elif line.startswith('|'):
        table_lines = [line]
        i += 1
        while i < len(lines) and lines[i].startswith('|'):
            table_lines.append(lines[i].rstrip())
            i += 1
        
        rows = []
        for tline in table_lines:
            cells = [c.strip() for c in tline.split('|')[1:-1]]
            rows.append(cells)
        
        if len(rows) > 2:
            table_data = rows[::2]
            col_widths = [1.8*inch, 1.8*inch] if len(table_data[0]) == 2 else [1.2*inch] * len(table_data[0])
            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d32f2f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ]))
            story.append(table)
            story.append(add_space(0.1))
        i -= 1
    elif line.strip() and not line.startswith('---'):
        add_para(line)
    elif line.startswith('---'):
        add_space(0.1)
    else:
        add_space(0.06)
    
    i += 1

doc.build(story)
print(f"✓ PDF generated: {PDF_FILE}")
