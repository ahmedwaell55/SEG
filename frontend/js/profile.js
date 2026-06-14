document.addEventListener("DOMContentLoaded", () => {
  const { apiFetch, apiBase, formatDate, acceptanceBadge, escapeHtml, getToken, listMarkup, toast } = window.AICloser;
  const pathMatch = window.location.pathname.match(/\/client\/(\d+)/);
  const params = new URLSearchParams(window.location.search);
  const clientId = pathMatch ? pathMatch[1] : params.get("id");

  const title = document.getElementById("clientTitle");
  const profileName = document.getElementById("profileName");
  const profilePhone = document.getElementById("profilePhone");
  const profileDate = document.getElementById("profileDate");
  const profileLeadStage = document.getElementById("profileLeadStage");
  const profileAcceptance = document.getElementById("profileAcceptance");
  const transcriptBox = document.getElementById("transcriptBox");
  const meetingMeta = document.getElementById("meetingMeta");
  const analysisGrid = document.getElementById("analysisGrid");
  const timeline = document.getElementById("meetingTimeline");
  const exportPdf = document.getElementById("exportPdf");
  const reprocessButton = document.getElementById("reprocessMeeting");
  const editDialog = document.getElementById("editDialog");
  const editForm = document.getElementById("editForm");
  const editName = document.getElementById("editName");
  const editPhone = document.getElementById("editPhone");

  let client;
  let selectedMeetingId = Number(params.get("meeting")) || null;

  function renderProfile(data) {
    title.textContent = data.name;
    profileName.textContent = data.name;
    profilePhone.textContent = data.phone;
    profileDate.textContent = formatDate(data.last_meeting_date);
    
    // Modern lead stage badge rendering
    const stage = data.lead_stage || "Discovery";
    profileLeadStage.innerHTML = `<span class="badge stage-${stage.toLowerCase()}">${stage}</span>`;
    profileAcceptance.innerHTML = acceptanceBadge(data.acceptance_label, data.acceptance_probability);
    
    editName.value = data.name;
    editPhone.value = data.phone;
  }

  function renderAnalysis(meeting) {
    const prob = meeting.acceptance_probability ?? 0;
    const probClass = prob >= 75 ? 'high' : (prob >= 45 ? 'medium' : 'low');
    
    // Stakeholders pill markup
    const stakeholderTags = Array.isArray(meeting.stakeholders) && meeting.stakeholders.length
      ? meeting.stakeholders.map(s => `<span class="stakeholder-tag">${escapeHtml(s)}</span>`).join("")
      : '<span class="muted text-sm">No stakeholders identified</span>';

    analysisGrid.innerHTML = `
      <!-- Executive Summary (Full Width) -->
      <div class="insight full summary-panel">
        <div class="panel-icon-header">
          <span class="panel-icon">💡</span>
          <h3>Executive Intent Summary</h3>
        </div>
        <p class="summary-text">${escapeHtml(meeting.summary || "No summary generated.")}</p>
      </div>

      <!-- Probability & Urgency Progress Card -->
      <div class="insight deal-health-card">
        <h3>Deal Probability Scorecard</h3>
        <div class="progress-bar-wrap">
          <div class="progress-bar-fill ${probClass}" style="width: ${prob}%"></div>
        </div>
        <div class="progress-bar-text">
          <strong class="text-lg">${prob}% Close Likelihood</strong>
          <span class="badge ${probClass}">${meeting.acceptance_label} Lead</span>
        </div>
        <div class="meta-metrics">
          <div class="meta-metric">
            <span>Client Urgency</span>
            <strong class="urgency-${(meeting.urgency_level || 'Medium').toLowerCase()}">${escapeHtml(meeting.urgency_level || "Medium")}</strong>
          </div>
          <div class="meta-metric">
            <span>AI Confidence</span>
            <strong>${escapeHtml(meeting.confidence_score ?? "-")}%</strong>
          </div>
        </div>
      </div>

      <!-- Buying Committee (Stakeholders) -->
      <div class="insight stakeholders-card">
        <h3>Buying Committee / Stakeholders</h3>
        <p class="text-sm muted margin-bottom-sm">Key decision makers and evaluators involved:</p>
        <div class="stakeholders-list">
          ${stakeholderTags}
        </div>
      </div>

      <!-- Risks & Opportunities Side-by-Side (Full Width Grid Card) -->
      <div class="insight full grid-two-columns">
        <div class="commercial-card risks">
          <div class="card-title-header red">
            <span class="card-icon">⚠️</span>
            <h4>Critical Deal Risks</h4>
          </div>
          ${listMarkup(meeting.risks)}
        </div>
        <div class="commercial-card opportunities">
          <div class="card-title-header green">
            <span class="card-icon">🚀</span>
            <h4>Expansion Opportunities</h4>
          </div>
          ${listMarkup(meeting.opportunities)}
        </div>
      </div>

      <!-- Pain Points & Objections & Buying Signals -->
      <div class="insight">
        <div class="panel-icon-header font-bold text-success">
          <span>🎯</span>
          <h3>Pain Points & Signals</h3>
        </div>
        <div class="inner-block">
          <h4 class="sub-header">Pain Points</h4>
          ${listMarkup(meeting.pain_points)}
          <h4 class="sub-header margin-top-md">Buying Signals</h4>
          ${listMarkup(meeting.buying_signals)}
        </div>
      </div>

      <div class="insight">
        <div class="panel-icon-header font-bold text-danger">
          <span>🛡️</span>
          <h3>Objections & Concerns</h3>
        </div>
        <div class="inner-block">
          <h4 class="sub-header">Objections</h4>
          ${listMarkup(meeting.objections)}
        </div>
      </div>

      <!-- Recommendations & Strategy -->
      <div class="insight full grid-two-columns bg-accent-soft-panel">
        <div class="strategy-card">
          <h4>Commercial Gameplan</h4>
          <p class="strategy-paragraph"><strong>Sales Strategy:</strong> ${escapeHtml(meeting.sales_strategy || "No strategy generated.")}</p>
          <p class="strategy-paragraph margin-top-sm"><strong>Communication Style:</strong> ${escapeHtml(meeting.communication_style || "No communication guidance generated.")}</p>
        </div>
        <div class="recommendations-card">
          <h4>AI Playbook Recommendations</h4>
          ${listMarkup(meeting.recommendations)}
        </div>
      </div>

      <!-- Post-Meeting Actions & Follow-up blueprint -->
      <div class="insight full follow-up-blueprint-panel">
        <div class="panel-icon-header">
          <span>✉️</span>
          <h3>Post-Call Follow-up Action Blueprint</h3>
        </div>
        <div class="blueprint-content">
          <div class="next-actions-timeline">
            <h4>Concrete Next Actions</h4>
            ${listMarkup(meeting.next_steps)}
          </div>
          <div class="email-blueprint">
            <h4>AI-Generated Email Drafting Blueprint</h4>
            <pre class="email-draft-box">${escapeHtml(meeting.follow_up_strategy || "No follow-up strategy generated.")}</pre>
          </div>
        </div>
      </div>
    `;
  }

  function selectMeeting(meetingId) {
    selectedMeetingId = Number(meetingId);
    const meeting = client.meetings.find((item) => item.id === selectedMeetingId);
    if (!meeting) return;
    transcriptBox.textContent = meeting.transcript || "No transcript stored.";
    
    // Sentiment Indicator Color
    const sent = meeting.sentiment || "Neutral";
    const sentClass = sent.toLowerCase();
    
    meetingMeta.innerHTML = `
      <span class="meta-date">${formatDate(meeting.meeting_date)}</span> | 
      <span class="sentiment-indicator ${sentClass}">${sent} Sentiment</span> | 
      <span class="badge ${probClass(meeting.acceptance_probability)}">${meeting.acceptance_label} (${meeting.acceptance_probability}%)</span>
    `;
    
    exportPdf.href = `${apiBase}/meetings/${meeting.id}/export.pdf?token=${encodeURIComponent(getToken() || "")}`;
    reprocessButton.disabled = false;
    renderAnalysis(meeting);
    renderTimeline();
  }

  function probClass(prob) {
    const val = Number(prob) || 0;
    if (val >= 75) return "high";
    if (val >= 45) return "medium";
    return "low";
  }

  function renderTimeline() {
    if (!client.meetings.length) {
      timeline.innerHTML = '<p class="empty-cell">No meetings saved yet.</p>';
      return;
    }
    
    timeline.innerHTML = client.meetings
      .map(
        (meeting) => {
          const sent = (meeting.sentiment || "Neutral").toLowerCase();
          return `
            <button class="timeline-item ${meeting.id === selectedMeetingId ? "active" : ""}" type="button" data-id="${meeting.id}">
              <div class="timeline-date-col">
                <strong>${formatDate(meeting.meeting_date)}</strong>
                <span class="sentiment-tag ${sent}">${meeting.sentiment || "Neutral"}</span>
              </div>
              <div class="timeline-desc-col">
                <span class="stage-tag mini stage-${(meeting.lead_stage || 'Discovery').toLowerCase()}">${meeting.lead_stage || 'Discovery'}</span>
                <p class="timeline-summary-excerpt">${escapeHtml(meeting.summary || "Meeting analysis")}</p>
              </div>
              <div class="timeline-badge-col">
                ${acceptanceBadge(meeting.acceptance_label, meeting.acceptance_probability)}
              </div>
            </button>
          `;
        },
      )
      .join("");
    timeline.querySelectorAll(".timeline-item").forEach((button) => {
      button.addEventListener("click", () => selectMeeting(button.dataset.id));
    });
  }

  async function loadClient() {
    if (!clientId) {
      toast("Client id is missing.");
      return;
    }
    client = await apiFetch(`/clients/${clientId}`);
    renderProfile(client);
    if (client.meetings.length) {
      const initial = selectedMeetingId || client.meetings[0].id;
      selectMeeting(initial);
    } else {
      transcriptBox.textContent = "No transcript stored yet.";
      analysisGrid.innerHTML = '<p class="empty-cell">No AI analysis available.</p>';
      reprocessButton.disabled = true;
      renderTimeline();
    }
  }

  document.getElementById("editClientButton").addEventListener("click", () => editDialog.showModal());
  document.getElementById("closeDialog").addEventListener("click", () => editDialog.close());

  editForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await apiFetch(`/clients/${clientId}`, {
      method: "PUT",
      body: JSON.stringify({
        name: editName.value.trim(),
        phone: editPhone.value.trim(),
      }),
    });
    editDialog.close();
    toast("Client updated.");
    await loadClient();
  });

  document.getElementById("deleteClientButton").addEventListener("click", async () => {
    const confirmed = window.confirm("Delete this client and all related meetings?");
    if (!confirmed) return;
    await apiFetch(`/clients/${clientId}`, { method: "DELETE" });
    window.location.href = "/";
  });

  reprocessButton.addEventListener("click", async () => {
    if (!selectedMeetingId) {
      toast("Select a meeting first.");
      return;
    }
    reprocessButton.disabled = true;
    reprocessButton.textContent = "Reprocessing...";
    try {
      const meeting = await apiFetch(`/meetings/${selectedMeetingId}/reprocess`, { method: "POST" });
      selectedMeetingId = meeting.id;
      toast("AI analysis regenerated.");
      await loadClient();
    } catch (error) {
      toast(error.message);
    } finally {
      reprocessButton.textContent = "Reprocess AI";
      reprocessButton.disabled = false;
    }
  });

  loadClient().catch((error) => toast(error.message));
});
