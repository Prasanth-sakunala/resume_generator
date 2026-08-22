const STAGES = [
  { id: 'extracting', label: 'Analyzing job description' },
  { id: 'tailoring', label: 'Matching skills & keywords' },
  { id: 'generating', label: 'Tailoring resume with AI' },
  { id: 'compiling', label: 'Compiling PDF document' },
  { id: 'done', label: 'Complete' }
];

const form = document.getElementById('resumeForm');
const textarea = document.getElementById('jd');
const btn = document.getElementById('generateBtn');
const btnText = document.getElementById('btnText');
const progressPanel = document.getElementById('progressPanel');
const progressBar = document.getElementById('progressBar');
const stepList = document.getElementById('stepList');
const statusMsg = document.getElementById('statusMsg');
const successPanel = document.getElementById('successPanel');
const formSection = document.getElementById('formSection');

let currentJobId = null;
let eventSource = null;

form.addEventListener('submit', async function (e) {
  e.preventDefault();

  const jd = textarea.value.trim();
  if (jd.length < 50) {
    showError('Please paste a complete job description (at least 50 characters).');
    return;
  }

  // Start progress UI
  setGenerating(true);
  resetSteps();
  progressPanel.classList.add('active');
  successPanel.classList.remove('active');

  try {
    // Step 1: Create job
    const res = await fetch('/generate-with-progress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ jd })
    });
    const data = await res.json();

    if (data.error) {
      showError(data.error);
      setGenerating(false);
      return;
    }

    currentJobId = data.job_id;

    // Step 2: Start listening for progress via SSE
    startProgressStream(currentJobId);

    // Step 3: Trigger job execution (fire-and-forget, don't await)
    fetch(`/run/${currentJobId}`, { method: 'POST' }).catch(() => {});

  } catch (err) {
    console.error(err);
    showError('Connection error. Please try again.');
    setGenerating(false);
    closeStream();
  }
});

function startProgressStream(jobId) {
  eventSource = new EventSource(`/progress/${jobId}`);

  eventSource.onmessage = function (event) {
    const data = JSON.parse(event.data);
    updateProgress(data.stage, data.progress);

    if (data.stage === 'done') {
      closeStream();
      onComplete(jobId);
    } else if (data.stage === 'error' || data.stage === 'close') {
      closeStream();
      if (data.stage === 'error') {
        showError('Generation failed. Please try again.');
      }
      setGenerating(false);
    }
  };

  eventSource.onerror = function () {
    // SSE connection closed — check if done
    closeStream();
    // Give a moment then try downloading
    setTimeout(() => {
      if (currentJobId) {
        onComplete(currentJobId);
      }
    }, 1000);
  };
}

function updateProgress(stage, progress) {
  progressBar.style.width = progress + '%';

  const stageIndex = STAGES.findIndex(s => s.id === stage);

  STAGES.forEach((s, i) => {
    const el = document.getElementById('step-' + s.id);
    if (!el) return;

    el.classList.remove('active', 'done', 'error');
    if (i < stageIndex) {
      el.classList.add('done');
    } else if (i === stageIndex) {
      el.classList.add('active');
    }
  });

  const current = STAGES[stageIndex];
  if (current && statusMsg) {
    statusMsg.textContent = current.label + '...';
  }
}

async function onComplete(jobId) {
  // Mark all steps done
  STAGES.forEach(s => {
    const el = document.getElementById('step-' + s.id);
    if (el) el.classList.add('done');
  });
  progressBar.style.width = '100%';
  statusMsg.textContent = 'Done!';

  // Download PDF
  try {
    const res = await fetch(`/download/${jobId}`);
    if (!res.ok) throw new Error('Download failed');

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'tailored_resume.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

    // Show success
    setTimeout(() => {
      progressPanel.classList.remove('active');
      successPanel.classList.add('active');
      setGenerating(false);
    }, 600);

  } catch (err) {
    console.error(err);
    showError('Download failed. Please try again.');
    setGenerating(false);
  }
}

function setGenerating(active) {
  btn.disabled = active;
  btnText.textContent = active ? 'Generating...' : 'Generate Resume';
  textarea.disabled = active;
}

function resetSteps() {
  STAGES.forEach(s => {
    const el = document.getElementById('step-' + s.id);
    if (el) el.classList.remove('active', 'done', 'error');
  });
  progressBar.style.width = '0%';
  statusMsg.textContent = 'Starting...';
}

function closeStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function showError(msg) {
  statusMsg.textContent = msg;
  statusMsg.style.color = '#fca5a5';
  setTimeout(() => {
    statusMsg.style.color = '';
  }, 5000);
}

// Reset button
document.getElementById('resetBtn')?.addEventListener('click', function () {
  successPanel.classList.remove('active');
  progressPanel.classList.remove('active');
  textarea.value = '';
  textarea.focus();
});
