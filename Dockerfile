FROM python:3.11-slim

# Install LaTeX (pdflatex)
RUN apt-get update && \
    apt-get install -y texlive-latex-base texlive-latex-extra && \
    apt-get clean

# Set working directory
WORKDIR /app

# Copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

WORKDIR /app/app

# Expose port
EXPOSE 8000

# Run app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]