# Resume Generator 📄

A web application that automatically tailors your LaTeX resume to a specific job description using AI.

![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Google GenAI](https://img.shields.io/badge/Google_GenAI-4285F4?style=for-the-badge&logo=google-generative-ai&logoColor=white)

---

## Table of Contents 📜

*   [About](#about-the-project-%F0%9F%A7%BE)
*   [Features](#features-%E2%9C%A8)
*   [Tech Stack](#tech-stack-%F0%9F%AA%A9)
*   [Installation](#installation-%E2%9A%99%EF%B8%8F)
*   [Usage](#usage-%E2%9A%A1%EF%B8%8F)
*   [Project Structure](#project-structure-%F0%9F%97%BA%EF%B8%8F)
*   [Contributing](#contributing-%F0%9F%AA%90)
*   [License](#license-%F0%9F%93%9C)
*   [Important Links](#important-links-%F2%9C%A3)

---

## About the Project 🏗️

This project is a sophisticated web application designed to streamline the resume tailoring process. It leverages AI models (Groq and Gemini) to analyze a given job description, extract key information, and then adapt a base LaTeX resume to match the requirements of that specific job. The goal is to create a highly optimized resume that is more likely to pass through Applicant Tracking Systems (ATS) and appeal to recruiters.

The application is containerized with Docker, making it easy to set up and run. It provides a user-friendly web interface where users can paste their job descriptions and receive a custom-tailored resume PDF.

---

## Features ✨

*   🤖 **AI-Powered Tailoring:** Utilizes Google Gemini and Groq AI models to intelligently adapt resume content.
*   🔍 **Job Description Analysis:** Extracts crucial information like job title, hard skills, soft skills, and priorities from the job description.
*   📄 **LaTeX Resume Generation:** Takes an existing `resume.tex` file and modifies it to align with the target job.
*   ⚡ **Fast Compilation:** Compiles the tailored LaTeX into a PDF resume efficiently.
*   🐳 **Docker Support:** Easy deployment and execution using Docker.
*   📊 **Real-time Progress Tracking:** Provides visual feedback on the generation process through a step-by-step progress bar.
*   ✅ **Secure Compilation:** Employs safe LaTeX compilation by disabling shell-escape.
*   💨 **Asynchronous Processing:** Handles PDF generation in the background to keep the UI responsive.

---

## Tech Stack 💻

*   **Backend:** Python, FastAPI
*   **AI/ML:** Google GenAI, Groq API
*   **Frontend:** HTML, CSS, JavaScript
*   **Templating:** Jinja2
*   **Containerization:** Docker
*   **Dependencies:** Uvicorn, python-multipart, requests
*   **Document Compilation:** LaTeX (pdflatex)

---

## Installation 🛠️

### Prerequisites

*   Docker (for easy setup)
*   Python 3.11 (if running without Docker)
*   Google GenAI API Key (set as `GEMINI_API_KEY` or `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3` environment variable)
*   Groq API Key (set as `GROQ_API_KEY` or `GROQ_API_KEY_1`, `GROQ_API_KEY_2`, `GROQ_API_KEY_3` environment variable)

### Using Docker (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Prasanth-sakunala/resume_generator.git
    cd resume_generator
    ```

2.  **Set up environment variables:**
    Create a `.env` file in the root directory with your API keys:
    ```dotenv
    GEMINI_API_KEY=YOUR_GEMINI_API_KEY
    GROQ_API_KEY=YOUR_GROQ_API_KEY
    # Optional: for multiple keys
    # GEMINI_API_KEY_1=...
    # GEMINI_API_KEY_2=...
    # GROQ_API_KEY_1=...
    ```

3.  **Build and run the Docker container:**
    ```bash
    docker-compose build
    docker-compose up
    ```

### Local Installation (Without Docker)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Prasanth-sakunala/resume_generator.git
    cd resume_generator
    ```

2.  **Set up a virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install LaTeX:**
    Ensure you have a LaTeX distribution installed on your system (e.g., TeX Live).
    *   **Debian/Ubuntu:** `sudo apt-get update && sudo apt-get install texlive-latex-base texlive-latex-extra`
    *   **macOS (using Homebrew):** `brew install --cask mactex`
    *   **Windows:** Download and install MiKTeX or TeX Live.

5.  **Set environment variables:**
    Set your API keys as environment variables:
    ```bash
    export GEMINI_API_KEY='YOUR_GEMINI_API_KEY'
    export GROQ_API_KEY='YOUR_GROQ_API_KEY'
    # Or use multi-key variants if configured
    ```

6.  **Run the FastAPI application:**
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```

---

## Usage 🚀

1.  **Access the Web Interface:** Open your web browser and navigate to `http://localhost:8000` (or the port specified if using Docker).

2.  **Paste Job Description:** In the provided text area, paste the full text of the job description you are targeting.

3.  **Generate Resume:** Click the "Generate Resume" button.

4.  **Monitor Progress:** A progress panel will appear, showing the different stages of the resume generation process (analyzing, tailoring, compiling).

5.  **Download PDF:** Once complete, your tailored `tailored_resume.pdf` will be automatically downloaded.

**Example Workflow:**

*   You have a general LaTeX resume file (`resume.tex`).
*   You find a job posting online.
*   You copy the entire job description text.
*   You paste it into the web interface and click "Generate Resume."
*   The AI analyzes the job description, identifies keywords, and modifies your `resume.tex` to better match the role's requirements (e.g., updating skills, summary, and bullet points).
*   A new PDF file, `tailored_resume.pdf`, is generated and downloaded.

---

## Project Structure 📂

```
resume_generator/
├── app/
│   ├── static/
│   │   ├── app.js
│   │   └── style.css
│   ├── templates/
│   │   └── index.html
│   ├── main.py
│   └── resume.tex  <-- Base resume template
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## API Reference ⚙️

This application exposes the following API endpoints (primarily for internal use by the frontend):

*   **`GET /`**: Renders the main HTML page for the resume generator.
*   **`POST /generate-with-progress`**: Initiates a resume generation job, returning a `job_id` for tracking.
    *   **Request Body:** `jd` (string) - The job description.
    *   **Response:** `{

---
**<p align="center">Generated by [ReadmeCodeGen](https://www.readmecodegen.com/)</p>**
