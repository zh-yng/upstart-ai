import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("VITE_GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("Missing GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")

client = genai.Client(api_key=api_key)
user_idea = input("Enter idea: ")

prompt = f"""Create a comprehensive, actionable roadmap for the following startup idea: {user_idea}

Structure the roadmap as a step-by-step guide with the following format:

# Startup Roadmap: [Startup Name]

## Phase 1: [Phase Name] (Timeline)
Brief description of this phase's objectives.

### Major Step 1: [Step Title]
- Sub-step 1: Detailed action item
- Sub-step 2: Detailed action item
- Sub-step 3: Detailed action item

### Major Step 2: [Step Title]
- Sub-step 1: Detailed action item
- Sub-step 2: Detailed action item
- Sub-step 3: Detailed action item

## Phase 2: [Phase Name] (Timeline)
Brief description of this phase's objectives.

[Continue pattern...]

Requirements:
- Create 4-6 major phases (e.g., Foundation, Product Development, Market Launch, Growth, Scale)
- Each phase should have 3-5 major steps
- Each major step should have 3-6 detailed sub-steps with specific, actionable tasks
- Include realistic timelines for each phase
- Be specific and practical - avoid generic advice
- Focus on concrete actions, not just concepts
- Do NOT use ** for bold formatting, use plain text only
- Number the phases and major steps clearly

Make it comprehensive but practical for a startup founder to follow."""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
)

roadmap_text = response.text or "No roadmap content generated."

file_name = "roadmap.pdf"

# Create PDF with proper text wrapping
doc = SimpleDocTemplate(
    file_name,
    pagesize=letter,
    rightMargin=0.75*inch,
    leftMargin=0.75*inch,
    topMargin=0.75*inch,
    bottomMargin=0.75*inch
)

# Get styles
styles = getSampleStyleSheet()
style_normal = styles['Normal']
style_heading = styles['Heading1']

# Build the story (content)
story = []

# Process the text and add to story
for line in roadmap_text.splitlines():
    if line.strip():  # Only add non-empty lines
        # Check if line looks like a heading (you can customize this logic)
        if line.startswith('#'):
            # Remove markdown heading markers and use heading style
            clean_line = line.lstrip('#').strip()
            # Remove markdown bold formatting
            clean_line = clean_line.replace('**', '')
            para = Paragraph(clean_line, style_heading)
        else:
            # Remove markdown bold formatting
            clean_line = line.replace('**', '')
            # Replace special characters that might cause issues
            clean_line = clean_line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            para = Paragraph(clean_line, style_normal)
        story.append(para)
        story.append(Spacer(1, 0.1*inch))  # Add small space between paragraphs

# Build the PDF
doc.build(story)

print(f"PDF generated: {file_name}")
print("\nContent:")
print(roadmap_text)