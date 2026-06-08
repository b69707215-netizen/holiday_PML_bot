from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime
import os
from database.models import User, Vacation

TEMPLATES_DIR = "2025-20260608T221020Z-3-001/2025"
OUTPUT_DIR = "generated_orders"

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

async def generate_vacation_order(user: User, vacation: Vacation) -> str:
    """Generate a vacation order document."""
    ensure_output_dir()
    
    doc = Document()
    
    # Add header
    header = doc.add_paragraph()
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header.add_run("ПРИКАЗ")
    run.bold = True
    run.font.size = Pt(16)
    
    # Add sub-header
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub.add_run("об предоставлении отпуска")
    sub_run.font.size = Pt(14)
    
    # Add date
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    today = datetime.now().strftime("%d.%m.%Y")
    date_para.add_run(f"от {today} г.")
    
    doc.add_paragraph()
    
    # Main content
    content = doc.add_paragraph()
    content.add_run(
        f"Предоставить отпуск сотруднику:\n\n"
        f"ФИО: {user.full_name}\n"
        f"Телефон: {user.phone}\n\n"
        f"Период отпуска: с {vacation.start_date.strftime('%d.%m.%Y')} по "
        f"{vacation.end_date.strftime('%d.%m.%Y')}\n"
        f"Количество дней: {vacation.days_count}\n\n"
    )
    
    # Add signature section
    doc.add_paragraph()
    sig = doc.add_paragraph()
    sig.add_run("Директор школы: _________________ / Подпись")
    
    # Save document
    filename = f"order_vacation_{user.full_name.replace(' ', '_')}_{vacation.id}.docx"
    filepath = os.path.join(OUTPUT_DIR, filename)
    doc.save(filepath)
    
    return filepath

async def generate_order_from_template(
    template_name: str, 
    variables: dict,
    output_name: str = None
) -> str:
    """Generate an order from a template file."""
    ensure_output_dir()
    
    template_path = os.path.join(TEMPLATES_DIR, template_name)
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    doc = Document(template_path)
    
    # Replace placeholders in paragraphs
    for paragraph in doc.paragraphs:
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in paragraph.text:
                paragraph.text = paragraph.text.replace(placeholder, str(value))
    
    # Replace placeholders in tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for key, value in variables.items():
                    placeholder = f"{{{key}}}"
                    if placeholder in cell.text:
                        cell.text = cell.text.replace(placeholder, str(value))
    
    # Save document
    if not output_name:
        output_name = f"order_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    
    output_path = os.path.join(OUTPUT_DIR, output_name)
    doc.save(output_path)
    
    return output_path

def get_available_templates():
    """Get list of available order templates."""
    if not os.path.exists(TEMPLATES_DIR):
        return []
    
    templates = []
    for file in os.listdir(TEMPLATES_DIR):
        if file.endswith('.docx'):
            templates.append(file)
    
    return templates
