from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import subprocess, os, re
from google import genai
import time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

BASE_RESUME_PATH = "resume.tex"


def generate_resume_text(prompt):
    models = [
        "gemini-3.6-flash",        # primary (best)
        "gemini-3.1-flash",        # fallback
        "gemini-2.5-flash"         # last fallback
    ]
    last_error = None

    for model in models:
        for attempt in range(3):  # retry per model
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text

            except Exception as e:
                last_error = e
                msg = str(e).lower()

                print(f"[ERROR] Model: {model}, Attempt: {attempt+1}, Error: {e}")

                # retry only for transient errors
                if "429" in msg or "quota" in msg or "rate" in msg:
                    time.sleep(2 * (attempt + 1))  # exponential backoff
                    continue
                elif "503" in msg or "unavailable" in msg:
                    time.sleep(2)
                    continue
                else:
                    break  # don't retry for unknown errors

    raise Exception(f"All models failed. Last error: {last_error}")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/generate")
def generate(jd: str = Form(...)):

    with open(BASE_RESUME_PATH, "r", encoding="utf-8") as f:
        latex_code = f.read()

    prompt = f"""
    Adapt this resume to job description:

    JD:
    {jd}

    Resume:
    {latex_code}

    STRICT RULES (DO NOT VIOLATE):
    1. DO NOT add any new skills, technologies, or experience not already present in the resume.
    2. DO NOT modify company names, client names, job titles, or project names.
    3. DO NOT fabricate or assume experience (e.g., do NOT add C++ if not already present).
    4. ONLY rephrase existing bullet points to better align with the JD.
    5. You may reorder or emphasize points, but factual content must remain unchanged.
    6. Maintain 100% factual accuracy.

    Allowed:
    - Improve wording
    - Highlight relevant skills
    - Align phrasing with JD keywords

    Not Allowed:
    - Adding new technologies
    - Changing roles or company names
    - Changing project names

    Return ONLY valid LaTeX code.
    """

    # ✅ Gemini safe call
    try:
        response_text = generate_resume_text(prompt)
    except Exception as e:
        print("GEMINI ERROR:", e)
        response_text = latex_code  # fallback

    # ✅ safer cleaning
    clean_tex = response_text.replace("```latex", "").replace("```", "").strip()

    with open("output.tex", "w", encoding="utf-8") as f:
        f.write(clean_tex)

    # ✅ compile with check
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "output.tex"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("LATEX ERROR:\n", result.stdout)
        return {"error": "PDF generation failed"}

    # ✅ check file exists
    if not os.path.exists("output.pdf"):
        return {"error": "PDF not created"}

    return FileResponse(
        "output.pdf",
        filename="tailored_resume.pdf",
        media_type="application/pdf"
    )