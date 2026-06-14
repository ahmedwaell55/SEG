from io import BytesIO

from app.models import Meeting
from app.services.serializers import serialize_meeting


def _write_wrapped(canvas, text: str, x: int, y: int, max_chars: int = 95, line_height: int = 14) -> int:  # noqa: ANN001
    words = text.split()
    line = ""
    for word in words:
        if len(line) + len(word) + 1 > max_chars:
            canvas.drawString(x, y, line)
            y -= line_height
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        canvas.drawString(x, y, line)
        y -= line_height
    return y


def generate_meeting_pdf(meeting: Meeting) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("reportlab is required for PDF export") from exc

    payload = serialize_meeting(meeting)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = int(height) - 54

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(54, y, "AI Closer Meeting Report")
    y -= 30

    pdf.setFont("Helvetica", 10)
    pdf.drawString(54, y, f"Meeting date: {payload['meeting_date']} | Acceptance: {payload['acceptance_label']} ({payload['acceptance_probability']}%)")
    y -= 28

    sections = [
        ("Summary", payload.get("summary") or "No summary generated."),
        ("Sentiment", f"{payload.get('sentiment')} | Tone: {payload.get('emotional_tone')} | Urgency: {payload.get('urgency_level')}"),
        ("Pain Points", "\n".join(f"- {item}" for item in payload.get("pain_points", [])) or "None detected."),
        ("Objections", "\n".join(f"- {item}" for item in payload.get("objections", [])) or "None detected."),
        ("Buying Signals", "\n".join(f"- {item}" for item in payload.get("buying_signals", [])) or "None detected."),
        ("Recommendations", "\n".join(f"- {item}" for item in payload.get("recommendations", [])) or "None generated."),
        ("Next Steps", "\n".join(f"- {item}" for item in payload.get("next_steps", [])) or "None generated."),
    ]

    for title, body in sections:
        if y < 110:
            pdf.showPage()
            y = int(height) - 54
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(54, y, title)
        y -= 18
        pdf.setFont("Helvetica", 9)
        for paragraph in body.splitlines():
            y = _write_wrapped(pdf, paragraph, 54, y)
            if y < 70:
                pdf.showPage()
                y = int(height) - 54
                pdf.setFont("Helvetica", 9)
        y -= 10

    pdf.save()
    buffer.seek(0)
    return buffer.read()

