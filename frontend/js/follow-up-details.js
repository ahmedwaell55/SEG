document.addEventListener("DOMContentLoaded", () => {
  const { apiFetch, formatDate, acceptanceBadge, escapeHtml, toast } = window.AICloser;
  const pathMatch = window.location.pathname.match(/\/follow-ups\/(\d+)/);
  const followupId = pathMatch ? pathMatch[1] : null;

  const detailsTitle = document.getElementById("detailsTitle");
  const clientName = document.getElementById("clientName");
  const followupNumber = document.getElementById("followupNumber");
  const scheduledDate = document.getElementById("scheduledDate");
  const followupStatus = document.getElementById("followupStatus");
  const dealProbability = document.getElementById("dealProbability");
  const fullMessage = document.getElementById("fullMessage");
  const detailsGrid = document.getElementById("detailsGrid");
  const meetingSummaryText = document.getElementById("meetingSummaryText");
  const toggleStatus = document.getElementById("toggleStatus");

  let current;

  async function loadDetails() {
    if (!followupId) {
      toast("Follow-up id is missing.");
      return;
    }
    current = await apiFetch(`/followups/${followupId}`);

    detailsTitle.textContent = `${current.client_name} - Follow-Up #${current.follow_up_number}`;
    clientName.textContent = current.client_name;
    followupNumber.textContent = `${current.follow_up_number}${current.follow_up_number === 1 ? "st" : current.follow_up_number === 2 ? "nd" : "rd"}`;
    scheduledDate.textContent = formatDate(current.scheduled_at.split("T")[0]);
    followupStatus.innerHTML = `<span class="status-pill ${current.status.toLowerCase().replace(/\s+/g, "-")}">${escapeHtml(current.status)}</span>`;
    dealProbability.innerHTML = acceptanceBadge(
      current.deal_probability >= 75 ? "High" : current.deal_probability >= 45 ? "Medium" : "Low",
      current.deal_probability,
    );
    fullMessage.textContent = current.whatsapp_message || "No follow-up message generated yet.";
    meetingSummaryText.textContent = current.meeting_summary || "No meeting summary available.";

    detailsGrid.innerHTML = `
      <div class="insight full">
        <h3>Follow-Up Objective</h3>
        <p>${escapeHtml(current.follow_up_objective || "No objective provided.")}</p>
      </div>
      <div class="insight">
        <h3>Suggested Communication Tone</h3>
        <p>${escapeHtml(current.communication_tone || "Consultative")}</p>
      </div>
      <div class="insight">
        <h3>Transcript Evidence Used</h3>
        <p>${escapeHtml(current.transcript_evidence || "No transcript evidence provided.")}</p>
      </div>
    `;

    toggleStatus.textContent = current.status === "Completed" ? "Mark Upcoming" : "Mark Completed";
  }

  document.getElementById("regenerateMessage").addEventListener("click", async () => {
    await apiFetch(`/followups/${followupId}/generate-message`, { method: "POST" });
    toast("Follow-up message regenerated.");
    await loadDetails();
  });

  toggleStatus.addEventListener("click", async () => {
    const nextStatus = current.status === "Completed" ? "Upcoming" : "Completed";
    await apiFetch(`/followups/${followupId}/status`, {
      method: "PUT",
      body: JSON.stringify({ status: nextStatus }),
    });
    toast(`Follow-up marked as ${nextStatus}.`);
    await loadDetails();
  });

  loadDetails().catch((error) => toast(error.message));
});

