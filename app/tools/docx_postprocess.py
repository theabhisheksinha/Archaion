from typing import Optional
from app.tools.document_generator import generate_docx_from_markdown

def generate(app_name: str, markdown: str):
    return generate_docx_from_markdown(markdown, app_name)

