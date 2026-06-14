document.addEventListener("DOMContentLoaded", () => {
  const { apiFetch, formatDate, acceptanceBadge, escapeHtml, toast } = window.AICloser;
  const tableBody = document.getElementById("followupTableBody");
  const summary = document.getElementById("followupSummary");
  const searchInput = document.getElementById("followupSearch");
  const dateInput = document.getElementById("followupDate");
  const filterDateButton = document.getElementById("filterDateButton");
  const todayButton = document.getElementById("todayButton");
  const clearFiltersButton = document.getElementById("clearFiltersButton");

  if (!tableBody || !summary || !searchInput || !dateInput || !filterDateButton || !todayButton || !clearFiltersButton) {
    toast("Follow-up table could not start. Refresh the page and try again.");
    return;
  }

  let followups = [];
  let activeDate = "";

  function statusBadge(status) {
    const normalized = (status || "Upcoming").toLowerCase().replace(/\s+/g, "-");
    return `<span class="status-pill ${normalized}">${escapeHtml(status || "Upcoming")}</span>`;
  }

  function priorityBadge(priority) {
    const normalized = (priority || "Medium").toLowerCase();
    return `<span class="priority-pill ${normalized}">${escapeHtml(priority || "Medium")}</span>`;
  }

  function scheduledDate(row) {
    return row.scheduled_at ? row.scheduled_at.split("T")[0] : "";
  }

  function scheduledTime(row) {
    if (!row.scheduled_at) return "-";
    const value = new Date(row.scheduled_at);
    if (Number.isNaN(value.getTime())) return "-";
    return value.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }

  function daysLabel(row) {
    if (row.status === "Completed") return "Completed";
    const days = Number(row.days_remaining);
    if (!Number.isFinite(days)) return "-";
    if (days === 0) return "Due today";
    if (days === 1) return "Tomorrow";
    if (days > 1) return `${days} days`;
    const overdue = Math.abs(days);
    return `${overdue} ${overdue === 1 ? "day" : "days"} overdue`;
  }

  function probabilityLabel(probability) {
    const value = Number(probability);
    if (value >= 75) return "High";
    if (value >= 45) return "Medium";
    return "Low";
  }

  function todayValue() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function sortRows(rows) {
    return [...rows].sort((a, b) => {
      const aCompleted = a.status === "Completed" ? 1 : 0;
      const bCompleted = b.status === "Completed" ? 1 : 0;
      if (aCompleted !== bCompleted) return aCompleted - bCompleted;
      return String(a.scheduled_at || "").localeCompare(String(b.scheduled_at || ""));
    });
  }

  function filteredRows() {
    const query = searchInput.value.trim().toLowerCase();
    return sortRows(
      followups.filter((row) => {
        const matchesDate = activeDate ? scheduledDate(row) === activeDate : true;
        const haystack = `${row.client_name || ""} ${row.client_phone || ""}`.toLowerCase();
        const matchesSearch = query ? haystack.includes(query) : true;
        return matchesDate && matchesSearch;
      })
    );
  }

  function renderSummary(rows) {
    const dateLabel = activeDate ? formatDate(activeDate) : "All days";
    const searchLabel = searchInput.value.trim() ? ` matching "${searchInput.value.trim()}"` : "";
    summary.textContent = `${rows.length} follow-up${rows.length === 1 ? "" : "s"} shown for ${dateLabel}${searchLabel}.`;
  }

  function renderTable() {
    const rows = filteredRows();
    renderSummary(rows);

    if (!rows.length) {
      tableBody.innerHTML = '<tr><td class="empty-cell" colspan="9">No follow-ups match this filter.</td></tr>';
      return;
    }

    tableBody.innerHTML = rows
      .map(
        (row) => `
          <tr class="followup-table-row" data-id="${row.id}">
            <td>
              <strong>${formatDate(scheduledDate(row))}</strong>
              <span class="cell-subtext">${scheduledTime(row)}</span>
            </td>
            <td>
              <strong>${escapeHtml(row.client_name || "Unknown Client")}</strong>
              <span class="cell-subtext">${escapeHtml(row.lead_stage || "No lead stage")}</span>
            </td>
            <td>${escapeHtml(row.client_phone || "-")}</td>
            <td>${statusBadge(row.status)}</td>
            <td>${escapeHtml(daysLabel(row))}</td>
            <td>${priorityBadge(row.priority_level)}</td>
            <td>${acceptanceBadge(probabilityLabel(row.deal_probability), row.deal_probability)}</td>
            <td class="followup-preview-cell">${escapeHtml(row.whatsapp_preview || "No generated WhatsApp preview yet.")}</td>
            <td>
              <div class="table-actions">
                <button class="secondary-button table-button" type="button" data-action="details" data-id="${row.id}">Details</button>
                <button class="primary-button table-button" type="button" data-action="profile" data-client-id="${row.client_id}">Profile</button>
              </div>
            </td>
          </tr>
        `
      )
      .join("");
  }

  function applyDateFilter() {
    activeDate = dateInput.value;
    renderTable();
  }

  tableBody.addEventListener("click", (event) => {
    const actionButton = event.target.closest("[data-action]");
    if (actionButton) {
      const action = actionButton.dataset.action;
      if (action === "profile") {
        window.location.href = `/client/${actionButton.dataset.clientId}`;
      } else {
        window.location.href = `/follow-ups/${actionButton.dataset.id}`;
      }
      return;
    }

    const row = event.target.closest(".followup-table-row");
    if (row) {
      window.location.href = `/follow-ups/${row.dataset.id}`;
    }
  });

  searchInput.addEventListener("input", renderTable);
  filterDateButton.addEventListener("click", applyDateFilter);
  dateInput.addEventListener("change", applyDateFilter);
  todayButton.addEventListener("click", () => {
    dateInput.value = todayValue();
    applyDateFilter();
  });
  clearFiltersButton.addEventListener("click", () => {
    searchInput.value = "";
    dateInput.value = "";
    activeDate = "";
    renderTable();
  });

  async function loadFollowups() {
    const data = await apiFetch("/followups");
    followups = sortRows([...(data.items || [])]);
    renderTable();
  }

  loadFollowups().catch((error) => toast(error.message));
});
