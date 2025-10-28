from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib import colors
import os


# make_pdf_template2.py
# This script generates a PDF document for a parent guide on calf pain in children.
# It uses the ReportLab library to create a structured document with headings, paragraphs, and lists.

# After editing, run: ~/Desktop/scripts/run_make_pdf.sh  (or Cmd+Shift+B if you set the VS Code task)
# OR
# source "$HOME/Desktop/virtual_environments/scripts_env/bin/activate"
# python3 "$HOME/Desktop/scripts/make_pdf_template.py"


# =========================
# CONFIG — edit these only
# =========================
child_name = "Henry"
parent_name = "Mark"
output_filename = f"Calf_Pain_Parent_Guide_{child_name}.pdf"
output_path = os.path.expanduser(f"~/Desktop/script_exports/{output_filename}")

presenting_symptoms = [
    "Recent fever/viral illness (about 4 days ago), seemed to improve.",
    "Overnight onset of calf pain, worse on waking.",
    "Pain in both calves (right worse), located in the top third of the calf.",
    "No hip or knee pain; full knee motion; can pull knees to chest and cross legs.",
    "Currently struggling or unable to walk normally.",
]

diagnosis_title = "Post-viral calf muscle inflammation (benign acute childhood myositis)."
follow_up_line = f"{parent_name}, please let me know how {child_name} goes over the next 24–48 hours, or sooner if you’re worried."
title_line = f'Calf pain after a virus: "Sunburn muscles" – Parent guide for {child_name}'

# ==============
# Styles
# ==============
styles = getSampleStyleSheet()
h1 = ParagraphStyle('h1', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#0b3d91'))
h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontSize=14, leading=18)
body = ParagraphStyle('body', parent=styles['BodyText'], fontSize=11, leading=14)

# ==============
# Build content
# ==============
story = []

story.append(Paragraph(title_line, h1))
story.append(Spacer(1, 0.4*cm))

story.append(Paragraph(f"Presenting symptoms ({child_name})", h2))
story.append(ListFlowable([ListItem(Paragraph(x, body)) for x in presenting_symptoms], bulletType='bullet'))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("Diagnosis summary", h2))
story.append(Paragraph(f"Likely diagnosis: {diagnosis_title}", body))
story.append(Paragraph(
    f"What this means: {child_name}’s calf muscles are irritated from the virus, not torn. "
    f"Gentle movement is safe and helps recovery. We’ll still watch for warning signs in case a rarer problem appears "
    f"(muscle infection or muscle breakdown).", body))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("What’s happening (kid-friendly)", h2))
story.append(Paragraph(
    f"{child_name}’s calf muscles are like skin that’s sunburnt from the virus. Sunburn hurts when you touch it, "
    f"but the skin isn’t breaking. It’s the same here: the muscles feel sore, but gentle movement won’t cause damage.",
    body))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph(f"How we’ll help it settle (for {child_name} and {parent_name})", h2))
plan_points = [
    "Shade walking: short, easy walks, ankle pumps, and gentle stretches to let the 'sunburn' calm down.",
    f"Pain guide: if a move makes pain jump and {child_name} wants to cry, that’s too strong — back off and do a smaller/slower version. "
    "If it’s a little sore but talking and breathing are normal, that’s okay.",
    "Routine: every 1–2 hours while awake, do 1–2 minutes of gentle moves, then rest and drink water. Expect improvement over 1–3 days.",
]
story.append(ListFlowable([ListItem(Paragraph(x, body)) for x in plan_points], bulletType='bullet'))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("Green-light ideas for home", h2))
greens = [
    "Ankle pumps, toe raises, short hallway walks, gentle wall calf stretch (heel down).",
    "Cool pack 10–15 minutes if helpful; paracetamol as advised.",
]
story.append(ListFlowable([ListItem(Paragraph(x, body)) for x in greens], bulletType='bullet'))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("Red flags — seek urgent care if", h2))
reds = [
    f"Fever returns or {child_name} looks very unwell.",
    "One calf becomes very swollen, red, or much more painful than the other.",
    "Severe pain with gentle ankle movement or touching the calf.",
    "Dark/cola-coloured urine or not weeing as normal.",
    f"{child_name} still can’t walk after 24–48 hours, or pain is getting worse.",
]
story.append(ListFlowable([ListItem(Paragraph(x, body)) for x in reds], bulletType='bullet'))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("Follow-up", h2))
story.append(Paragraph(follow_up_line, body))

doc = SimpleDocTemplate(
    output_path,
    pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm
)
doc.build(story)
print(output_path)
