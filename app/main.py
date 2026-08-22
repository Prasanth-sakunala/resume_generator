from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import subprocess, os, json, requests, tempfile, shutil
from google import genai
import time
import asyncio
import uuid

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory store for job progress (lightweight, no DB needed)
job_store = {}

BASE_RESUME_PATH = "resume.tex"
MAX_JD_LENGTH = 15000  # prevent abuse / token blowup


def extract_keywords_grok(jd):
    """Extract structured keywords from JD using Groq with multi-key retry."""
    groq_keys = [
        os.getenv("GROK_API_KEY_1"),
        os.getenv("GROK_API_KEY_2"),
        os.getenv("GROK_API_KEY_3"),
    ]
    groq_keys = [key.strip() for key in groq_keys if key and key.strip()]
    if not groq_keys:
        primary = os.getenv("GROK_API_KEY")
        if primary and primary.strip():
            groq_keys = [primary.strip()]

    if not groq_keys:
        print("[WARN] No Groq API keys found (GROK_API_KEY_1/2/3 or GROK_API_KEY). Skipping extraction.")
        return None

    extraction_prompt = f"""Analyze this job description and extract structured data. Return ONLY valid JSON, no markdown wrapping.

{{
  "job_title": "exact title from JD",
  "hard_skills": ["top 10-15 technical skills in priority order"],
  "soft_skills": ["top 5 soft skills"],
  "domain_terms": ["industry/domain specific terms"],
  "action_verbs": ["key verbs used in JD like architect, optimize, scale"],
  "priorities": ["top 3 things this role cares about most"],
  "experience_level": "junior/mid/senior/staff/principal",
  "tech_stack": {{
    "must_have": ["non-negotiable skills"],
    "nice_to_have": ["preferred/bonus skills"]
  }}
}}

JOB DESCRIPTION:
{jd}"""

    models = [os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")]
    last_error = None

    for key_index, api_key in enumerate(groq_keys):
        print(f"[INFO] Using Groq API key #{key_index + 1}")

        for model in models:
            for attempt in range(3):
                try:
                    response = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": "Extract structured keywords from job descriptions. Return ONLY valid JSON."},
                                {"role": "user", "content": extraction_prompt}
                            ],
                            "temperature": 0.1
                        },
                        timeout=30
                    )

                    # Rate limit / quota hit — switch key
                    if response.status_code == 429:
                        print(f"[WARN] Grok key #{key_index+1} rate limited. Switching key...")
                        last_error = "429 rate limit"
                        break

                    if response.status_code >= 400:
                        print(f"[ERROR] Groq key #{key_index + 1} model:{model} HTTP {response.status_code}: {response.text[:500]}")
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                    content = content.replace("```json", "").replace("```", "").strip()
                    return json.loads(content)

                except requests.exceptions.Timeout:
                    last_error = "timeout"
                    print(f"[WARN] Grok key #{key_index+1} model:{model} attempt:{attempt+1} timed out")
                    continue

                except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
                    last_error = e
                    msg = str(e).lower()
                    print(f"[ERROR] Grok key #{key_index+1} model:{model} attempt:{attempt+1}: {e}")

                    if "429" in msg or "quota" in msg or "rate" in msg:
                        print(f"[WARN] Grok quota hit on key #{key_index+1}. Switching key...")
                        break

                    if "503" in msg or "502" in msg or "unavailable" in msg:
                        time.sleep(2 * (attempt + 1))
                        continue

                    break  # non-retryable error for this model

                except (json.JSONDecodeError, KeyError) as e:
                    last_error = e
                    print(f"[WARN] Grok key #{key_index+1} model:{model} returned invalid JSON: {e}")
                    break  # try next model

                except Exception as e:
                    last_error = e
                    print(f"[ERROR] Grok unexpected error: {e}")
                    break

            # If rate limited, break out of model loop to try next key
            if str(last_error) == "429 rate limit":
                break

        time.sleep(0.5)  # brief pause between keys

    print(f"[WARN] All Grok keys/models failed. Last error: {last_error}")
    return None


def build_tailoring_prompt(latex_code, jd, jd_keywords):
    """Build the resume tailoring prompt with extracted keywords."""
    if jd_keywords:
        keyword_section = f"""## EXTRACTED JD ANALYSIS:
- Job Title: {jd_keywords.get('job_title', 'N/A')}
- Must-Have Skills: {', '.join(jd_keywords.get('tech_stack', {}).get('must_have', []))}
- Nice-to-Have Skills: {', '.join(jd_keywords.get('tech_stack', {}).get('nice_to_have', []))}
- Hard Skills (priority order): {', '.join(jd_keywords.get('hard_skills', []))}
- Soft Skills: {', '.join(jd_keywords.get('soft_skills', []))}
- Domain Terms: {', '.join(jd_keywords.get('domain_terms', []))}
- Action Verbs to Mirror: {', '.join(jd_keywords.get('action_verbs', []))}
- Role Priorities: {', '.join(jd_keywords.get('priorities', []))}
- Experience Level: {jd_keywords.get('experience_level', 'N/A')}"""
        job_title = jd_keywords.get('job_title', 'the target role')
        must_have = ', '.join(jd_keywords.get('tech_stack', {}).get('must_have', []))
        priorities = ', '.join(jd_keywords.get('priorities', []))
        action_verbs = ', '.join(jd_keywords.get('action_verbs', []))
    else:
        keyword_section = f"""## JOB DESCRIPTION (extract keywords yourself):
{jd}"""
        job_title = "the target role"
        must_have = "skills from JD"
        priorities = "role priorities from JD"
        action_verbs = "action verbs from JD"

    prompt = f"""You are an expert resume strategist specializing in ATS optimization and recruiter psychology.
Your task: adapt the resume below to align with the given job description using the pre-extracted keyword analysis.

{keyword_section}

## CURRENT RESUME (LaTeX):
{latex_code}

## TAILORING STRATEGY (follow in order):

### Step 1: Metadata Optimization
Update ALL LaTeX metadata fields for ATS parsing:
- \\title{{}} → "{job_title}"
- \\hypersetup{{pdftitle=...}} → "Candidate Name - {job_title}"
- \\hypersetup{{pdfsubject=...}} → one-line value prop using JD keywords
- \\hypersetup{{pdfkeywords=...}} → comma-separated top skills from JD that the candidate ACTUALLY possesses
- \\hypersetup{{pdfauthor=...}} → keep candidate's name unchanged
- Any custom metadata commands → align with JD terminology

### Step 2: Professional Summary Rewrite
Rewrite the summary/objective section to:
- Open with: "[Years] experience [JD's core domain] professional"
- Include the EXACT job title "{job_title}" naturally
- Mention 3-4 top skills from must-have list ({must_have}) that the candidate demonstrably has
- End with a value statement tied to role priorities: {priorities}
- Keep to 2-3 lines maximum
- Do NOT claim experience the candidate doesn't have

### Step 3: Skill Mapping
Map JD requirements to EXISTING resume content:
- DIRECT MATCH: Skill explicitly stated in resume → emphasize/move higher
- INFERRABLE MATCH: Skill clearly implied by existing experience → surface it
  Valid inference examples:
    - "system design" experience → can mention "distributed systems"
    - "REST API development" → can mention "microservices architecture"
    - "led team of 5" → can mention "cross-functional collaboration"
    - "deployed on AWS EC2/S3" → can mention "cloud infrastructure"
  The candidate MUST demonstrably possess the skill based on their listed work.
- NO MATCH: Skill not present or inferable → DO NOT ADD

### Step 4: Skills Section Optimization
- Reorder skill categories: most JD-relevant category first
- Within each category: lead with JD-matched skills
- Use the EXACT terminology from the JD (e.g., if JD says "Kubernetes" don't write "K8s")
- Group skills to mirror JD's own categorization if possible
- Do NOT add any skill the candidate hasn't demonstrated

### Step 5: Bullet Point Optimization (Harvard Action-Result Format)
Rewrite bullets using: [Action Verb] + [Task/Skill] + [Quantified Result/Impact]
- Use action verbs from: {action_verbs}
- Lead each bullet with a strong action verb matching JD language
- Integrate matched keywords naturally (not keyword-stuffed)
- Preserve all metrics, numbers, and quantified achievements exactly
- Where possible, add context connecting the work to JD priorities
- Mirror JD phrasing: if JD says "optimize performance" use that phrase, not "improved speed"

### Step 6: Section Prioritization
- Reorder bullet points within each role: most JD-relevant first
- Do NOT reorder job entries (chronology must stay intact)
- If resume has a projects section, prioritize projects most relevant to JD

## ABSOLUTE CONSTRAINTS:
1. NEVER add skills/technologies the candidate doesn't demonstrably have
2. NEVER change: company names, client names, job titles, project names, dates, metrics
3. NEVER fabricate achievements or responsibilities
4. NEVER add new job entries or projects
5. ALL factual claims must trace back to the original resume
6. Keep the resume to the same length (do not inflate)
7. LaTeX must compile without errors — preserve all custom commands and packages

## QUALITY CHECKLIST (verify before responding):
- [ ] Metadata reflects JD job title and relevant keywords
- [ ] Summary mentions the exact role and top JD skills candidate has
- [ ] Every keyword added traces back to existing experience
- [ ] No new technologies invented
- [ ] All numbers/metrics unchanged
- [ ] Company/role/project names unchanged
- [ ] Skills section uses JD's exact terminology
- [ ] LaTeX compiles without errors

Return ONLY the complete, valid LaTeX code. No explanations or markdown wrapping."""

    return prompt


def generate_resume_text(prompt):
    models = [
        "gemini-3.6-flash",        # primary (best)
        "gemini-3.1-flash",        # fallback
        "gemini-2.5-flash"         # last fallback
    ]
    last_error = None

    # Collect keys from environment (add more variables if you want)
    gemini_keys = [
        os.getenv("GEMINI_API_KEY_1"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3"),
    ]
    # fallback to single GEMINI_API_KEY if none of the multi keys provided
    gemini_keys = [k for k in gemini_keys if k]
    if not gemini_keys:
        primary = os.getenv("GEMINI_API_KEY")
        if primary:
            gemini_keys = [primary]

    if not gemini_keys:
        raise Exception("No Gemini API keys found in environment (GEMINI_API_KEY_1/2/3 or GEMINI_API_KEY).")

    # Try each key in order
    for key_index, api_key in enumerate(gemini_keys):
        print(f"[INFO] Using Gemini API key #{key_index+1}")
        client_for_key = genai.Client(api_key=api_key)

        # Try each model for this key
        for model in models:
            quota_hit = False
            for attempt in range(3):  # up to 3 attempts per model
                try:
                    response = client_for_key.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    return response.text

                except Exception as e:
                    last_error = e
                    msg = str(e).lower()
                    print(f"[ERROR] Key#{key_index+1} Model:{model} Attempt:{attempt+1} Error: {e}")

                    # If quota/rate -> switch to next API key immediately
                    if ("429" in msg) or ("quota" in msg) or ("rate" in msg):
                        print(f"[WARN] Quota/rate limit detected on key #{key_index+1} (model {model}). Switching key...")
                        quota_hit = True
                        break

                    # Transient server errors -> retry with backoff
                    if ("503" in msg) or ("unavailable" in msg):
                        sleep_seconds = 2 * (attempt + 1)
                        print(f"[INFO] Transient error, retrying after {sleep_seconds}s...")
                        time.sleep(sleep_seconds)
                        continue

                    # Unknown/non-retryable error for this model -> stop retrying model
                    break

            # if quota was hit for this model, break to try next key
            if quota_hit:
                break

        # Try next API key
        print(f"[INFO] Key #{key_index+1} exhausted or skipped. Trying next key if available...")
        # small backoff between switching keys (optional)
        time.sleep(1)

    # nothing worked
    raise Exception(f"All Gemini keys/models failed. Last error: {last_error}")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/generate")
def generate(jd: str = Form(...), background_tasks: BackgroundTasks = None):

    if len(jd.strip()) < 50:
        return {"error": "Job description too short. Paste the full JD."}
    if len(jd) > MAX_JD_LENGTH:
        return {"error": f"Job description too long ({len(jd)} chars). Max {MAX_JD_LENGTH}."}

    # Create a job ID for progress tracking
    job_id = str(uuid.uuid4())
    job_store[job_id] = {"stage": "started", "progress": 0}

    with open(BASE_RESUME_PATH, "r", encoding="utf-8") as f:
        latex_code = f.read()

    # Step 1: Extract keywords from JD using Grok
    job_store[job_id] = {"stage": "extracting", "progress": 20}
    print("[INFO] Extracting keywords from JD via Grok...")
    jd_keywords = extract_keywords_grok(jd)
    if jd_keywords:
        print(f"[INFO] Extracted job title: {jd_keywords.get('job_title')}")
        print(f"[INFO] Must-have skills: {jd_keywords.get('tech_stack', {}).get('must_have', [])}")
    else:
        print("[WARN] Grok extraction failed, Gemini will handle full analysis")

    # Step 2: Build tailoring prompt with extracted keywords
    job_store[job_id] = {"stage": "tailoring", "progress": 40}
    prompt = build_tailoring_prompt(latex_code, jd, jd_keywords)

    # Step 3: Generate tailored resume via Gemini
    job_store[job_id] = {"stage": "generating", "progress": 60}
    try:
        response_text = generate_resume_text(prompt)
    except Exception as e:
        print("GEMINI ERROR:", e)
        response_text = latex_code  # fallback

    # Clean markdown wrapping from LLM response
    clean_tex = response_text.replace("```latex", "").replace("```", "").strip()

    # Step 4: Compile PDF
    job_store[job_id] = {"stage": "compiling", "progress": 80}

    # Use temp directory for concurrent-safe compilation
    work_dir = tempfile.mkdtemp(prefix="resume_")
    tex_path = os.path.join(work_dir, "output.tex")
    pdf_path = os.path.join(work_dir, "output.pdf")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(clean_tex)

    # Compile with security: disable shell-escape to prevent command injection
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-no-shell-escape", "output.tex"],
        capture_output=True,
        text=True,
        cwd=work_dir,
        timeout=30
    )

    if result.returncode != 0:
        print("LATEX ERROR:\n", result.stdout[-2000:])  # last 2000 chars only
        job_store.pop(job_id, None)
        return {"error": "PDF generation failed. LaTeX compilation error."}

    if not os.path.exists(pdf_path):
        job_store.pop(job_id, None)
        return {"error": "PDF not created"}

    # Done
    job_store[job_id] = {"stage": "done", "progress": 100}

    # Clean up temp directory after response is sent
    background_tasks.add_task(shutil.rmtree, work_dir, ignore_errors=True)
    background_tasks.add_task(lambda: job_store.pop(job_id, None))

    return FileResponse(
        pdf_path,
        filename="tailored_resume.pdf",
        media_type="application/pdf",
        headers={"X-Job-Id": job_id}
    )


@app.post("/generate-with-progress")
async def generate_with_progress(jd: str = Form(...)):
    """Start generation and return a job ID for progress tracking."""
    if len(jd.strip()) < 50:
        return {"error": "Job description too short. Paste the full JD."}
    if len(jd) > MAX_JD_LENGTH:
        return {"error": f"Job description too long ({len(jd)} chars). Max {MAX_JD_LENGTH}."}

    job_id = str(uuid.uuid4())
    job_store[job_id] = {"stage": "queued", "progress": 0, "jd": jd}
    return {"job_id": job_id}


@app.post("/run/{job_id}")
def run_job(job_id: str, background_tasks: BackgroundTasks = None):
    """Execute the resume generation job."""
    job = job_store.get(job_id)
    if not job:
        return {"error": "Job not found"}

    jd = job.get("jd", "")

    with open(BASE_RESUME_PATH, "r", encoding="utf-8") as f:
        latex_code = f.read()

    # Stage 1: Extract keywords
    job_store[job_id] = {"stage": "extracting", "progress": 20}
    jd_keywords = extract_keywords_grok(jd)
    if jd_keywords:
        print(f"[INFO] Extracted job title: {jd_keywords.get('job_title')}")
    else:
        print("[WARN] Grok extraction failed")

    # Stage 2: Building prompt
    job_store[job_id] = {"stage": "tailoring", "progress": 40}
    prompt = build_tailoring_prompt(latex_code, jd, jd_keywords)

    # Stage 3: Generate via Gemini
    job_store[job_id] = {"stage": "generating", "progress": 60}
    try:
        response_text = generate_resume_text(prompt)
    except Exception as e:
        print("GEMINI ERROR:", e)
        response_text = latex_code

    clean_tex = response_text.replace("```latex", "").replace("```", "").strip()

    # Stage 4: Compile PDF
    job_store[job_id] = {"stage": "compiling", "progress": 80}
    work_dir = tempfile.mkdtemp(prefix="resume_")
    tex_path = os.path.join(work_dir, "output.tex")
    pdf_path = os.path.join(work_dir, "output.pdf")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(clean_tex)

    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-no-shell-escape", "output.tex"],
        capture_output=True, text=True, cwd=work_dir, timeout=30
    )

    if result.returncode != 0:
        job_store[job_id] = {"stage": "error", "progress": 0, "error": "LaTeX compilation failed"}
        background_tasks.add_task(shutil.rmtree, work_dir, ignore_errors=True)
        return {"error": "PDF generation failed"}

    if not os.path.exists(pdf_path):
        job_store[job_id] = {"stage": "error", "progress": 0, "error": "PDF not created"}
        background_tasks.add_task(shutil.rmtree, work_dir, ignore_errors=True)
        return {"error": "PDF not created"}

    job_store[job_id] = {"stage": "done", "progress": 100, "pdf_path": pdf_path, "work_dir": work_dir}
    return {"status": "done"}


@app.get("/progress/{job_id}")
async def progress(job_id: str):
    """SSE endpoint to stream progress updates."""
    async def event_stream():
        last_stage = None
        timeout_counter = 0
        while timeout_counter < 300:  # 5 min max
            job = job_store.get(job_id)
            if not job:
                yield f"data: {json.dumps({'stage': 'error', 'progress': 0})}\n\n"
                break
            if job.get("stage") != last_stage:
                last_stage = job.get("stage")
                yield f"data: {json.dumps({'stage': job['stage'], 'progress': job['progress']})}\n\n"
            if job.get("stage") in ("done", "error"):
                break
            await asyncio.sleep(0.5)
            timeout_counter += 1
        yield f"data: {json.dumps({'stage': 'close'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/download/{job_id}")
def download(job_id: str, background_tasks: BackgroundTasks = None):
    """Download the generated PDF."""
    job = job_store.get(job_id)
    if not job or job.get("stage") != "done":
        return {"error": "PDF not ready"}

    pdf_path = job.get("pdf_path")
    work_dir = job.get("work_dir")

    if not pdf_path or not os.path.exists(pdf_path):
        return {"error": "PDF file not found"}

    background_tasks.add_task(shutil.rmtree, work_dir, ignore_errors=True)
    background_tasks.add_task(lambda: job_store.pop(job_id, None))

    return FileResponse(
        pdf_path,
        filename="tailored_resume.pdf",
        media_type="application/pdf"
    )