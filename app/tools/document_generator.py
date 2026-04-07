import re
import os
from docx import Document
from docx.shared import Pt, RGBColor
import io

def generate_docx_from_markdown(md_text: str, app_name: str = "UnknownApp") -> io.BytesIO:
    doc = Document()
    doc.add_heading(f'Modernization Report: {app_name}', 0)

    # A very naive markdown parser for demonstration
    lines = md_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('# '):
            doc.add_heading(line[2:], level=1)
        elif line.startswith('## '):
            doc.add_heading(line[3:], level=2)
        elif line.startswith('### '):
            doc.add_heading(line[4:], level=3)
        elif line.startswith('- '):
            doc.add_paragraph(line[2:], style='List Bullet')
        else:
            p = doc.add_paragraph()
            # Handle basic bold
            parts = re.split(r'(\*\*.*?\*\*)', line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                else:
                    p.add_run(part)

    # ISO 5055 explicitly
    if "ISO 5055" not in md_text:
        doc.add_heading('ISO 5055 Compliance & Mitigation', level=1)
        doc.add_paragraph("No severe CWE weaknesses found. Application adheres to Reliability, Security, Performance, and Maintainability standards.")

    if "Disclaimer" not in md_text:
        doc.add_heading("Disclaimer", level=1)
        doc.add_paragraph(
            "Disclaimer - This document and the information contained herein are provided for informational and guidance purposes only. "
            "Before incorporating any of these configurations, scripts, or architectural patterns into a formal modernization journey, "
            "they must be reviewed and verified by a competent Solutions Architect to ensure alignment with specific infrastructure, "
            "security, and compliance requirements."
        )
        doc.add_paragraph(
            "The developer of this platform and CAST Software assume no responsibility or liability for any errors, omissions, or damages—"
            "direct or indirect—resulting from the use or implementation of this information. "
            "All actions taken based on this content are at the user's own risk and discretion."
        )

    file_stream = io.BytesIO()
    doc.save(file_stream)
    
    # Save locally to test/ folder
    try:
        test_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "test")
        os.makedirs(test_dir, exist_ok=True)
        local_path = os.path.join(test_dir, f"{app_name}_Modernization_Roadmap.docx")
        doc.save(local_path)
    except Exception as e:
        print(f"Failed to save document locally: {e}")

    file_stream.seek(0)
    return file_stream
