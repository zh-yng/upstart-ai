import os
from reportlab.pdfgen import canvas
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("Missing GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")

client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Create a detailed roadmap for a bike company",
)

roadmap_text = response.text or "No roadmap content generated."

file_name = "roadmap.pdf"
pdf = canvas.Canvas(file_name)

text_obj = pdf.beginText(40, 780)
text_obj.setFont("Helvetica", 12)

for line in roadmap_text.splitlines():
    if text_obj.getY() <= 40:
        pdf.drawText(text_obj)
        pdf.showPage()
        text_obj = pdf.beginText(40, 780)
        text_obj.setFont("Helvetica", 12)
    text_obj.textLine(line)

pdf.drawText(text_obj)
pdf.save()
print(roadmap_text)