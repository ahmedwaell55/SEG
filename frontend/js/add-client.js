document.addEventListener("DOMContentLoaded", () => {
  const { apiFetch, acceptanceBadge, escapeHtml, listMarkup, toast } = window.AICloser;
  const form = document.getElementById("processForm");
  const fileInput = document.getElementById("fileInput");
  const uploadButton = document.getElementById("uploadButton");
  const transcript = document.getElementById("transcript");
  const status = document.getElementById("formStatus");
  const processButton = document.getElementById("processButton");
  const resultPanel = document.getElementById("resultPanel");
  const resultPreview = document.getElementById("resultPreview");
  const viewProfileLink = document.getElementById("viewProfileLink");
  const meetingDate = document.getElementById("meetingDate");

  meetingDate.valueAsDate = new Date();

  uploadButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    transcript.value = await file.text();
    toast(`Loaded ${file.name}`);
  });

  function renderPreview(meeting) {
    resultPreview.innerHTML = `
      <div class="insight full">
        <h3>Summary</h3>
        <p>${escapeHtml(meeting.summary || "No summary generated.")}</p>
      </div>
      <div class="insight">
        <h3>Deal Probability</h3>
        <p>${acceptanceBadge(meeting.acceptance_label, meeting.acceptance_probability)}</p>
      </div>
      <div class="insight">
        <h3>Sentiment</h3>
        <p>${escapeHtml(meeting.sentiment || "Neutral")} | ${escapeHtml(meeting.emotional_tone || "No tone")}</p>
      </div>
      <div class="insight">
        <h3>Objections</h3>
        ${listMarkup(meeting.objections)}
      </div>
      <div class="insight">
        <h3>Next Actions</h3>
        ${listMarkup(meeting.next_steps)}
      </div>
    `;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      client_name: document.getElementById("clientName").value.trim(),
      phone: document.getElementById("clientPhone").value.trim(),
      meeting_date: meetingDate.value,
      transcript: transcript.value.trim(),
    };

    if (payload.transcript.length < 10) {
      toast("Transcript is too short to analyze.");
      return;
    }

    processButton.disabled = true;
    status.textContent = "Processing meeting with LangGraph workflow...";
    try {
      const meeting = await apiFetch("/meetings/process", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      status.textContent = "Meeting processed and saved.";
      viewProfileLink.href = `/client/${meeting.client_id}?meeting=${meeting.id}`;
      renderPreview(meeting);
      resultPanel.classList.remove("hidden");
      toast("Meeting analysis completed.");
    } catch (error) {
      status.textContent = "Processing failed.";
      toast(error.message);
    } finally {
      processButton.disabled = false;
    }
  });
});

