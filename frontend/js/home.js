document.addEventListener("DOMContentLoaded", () => {
  const { apiFetch, formatDate, acceptanceBadge, escapeHtml, toast } = window.AICloser;
  const table = document.getElementById("clientsTable");
  const searchInput = document.getElementById("searchInput");
  const sortBy = document.getElementById("sortBy");
  const sortOrder = document.getElementById("sortOrder");
  const prevPage = document.getElementById("prevPage");
  const nextPage = document.getElementById("nextPage");
  const pageStatus = document.getElementById("pageStatus");

  const state = {
    page: 1,
    pageSize: 10,
    pages: 1,
    search: "",
    sortBy: "date",
    sortOrder: "desc",
  };

  function setLoading() {
    table.innerHTML = '<tr><td colspan="4" class="empty-cell">Loading clients...</td></tr>';
  }

  async function loadAnalytics() {
    const data = await apiFetch("/analytics/summary");
    document.getElementById("totalClients").textContent = data.total_clients;
    document.getElementById("totalMeetings").textContent = data.total_meetings;
    document.getElementById("highAcceptance").textContent = data.high_acceptance_clients;
    document.getElementById("averageSentiment").textContent = data.average_sentiment || "No data";
  }

  function renderRows(clients) {
    if (!clients.length) {
      table.innerHTML = '<tr><td colspan="4" class="empty-cell">No clients found.</td></tr>';
      return;
    }

    table.innerHTML = clients
      .map(
        (client) => `
          <tr data-id="${client.id}">
            <td><strong>${escapeHtml(client.name)}</strong><br><span class="muted">${client.meeting_count} meetings</span></td>
            <td>${escapeHtml(client.phone)}</td>
            <td>${formatDate(client.last_meeting_date)}</td>
            <td>${acceptanceBadge(client.acceptance_label, client.acceptance_probability)}</td>
          </tr>
        `,
      )
      .join("");

    table.querySelectorAll("tr[data-id]").forEach((row) => {
      row.addEventListener("click", () => {
        window.location.href = `/client/${row.dataset.id}`;
      });
    });
  }

  async function loadClients() {
    setLoading();
    const params = new URLSearchParams({
      page: state.page,
      page_size: state.pageSize,
      sort_by: state.sortBy,
      sort_order: state.sortOrder,
    });
    if (state.search) params.set("search", state.search);
    const data = await apiFetch(`/clients?${params.toString()}`);
    state.pages = data.pages;
    renderRows(data.items);
    pageStatus.textContent = `Page ${data.page} of ${data.pages}`;
    prevPage.disabled = data.page <= 1;
    nextPage.disabled = data.page >= data.pages;
  }

  let searchTimer;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = searchInput.value.trim();
      state.page = 1;
      loadClients().catch((error) => toast(error.message));
    }, 240);
  });

  sortBy.addEventListener("change", () => {
    state.sortBy = sortBy.value;
    state.page = 1;
    loadClients().catch((error) => toast(error.message));
  });

  sortOrder.addEventListener("click", () => {
    state.sortOrder = state.sortOrder === "desc" ? "asc" : "desc";
    sortOrder.dataset.order = state.sortOrder;
    sortOrder.textContent = state.sortOrder === "desc" ? "Desc" : "Asc";
    loadClients().catch((error) => toast(error.message));
  });

  prevPage.addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      loadClients().catch((error) => toast(error.message));
    }
  });

  nextPage.addEventListener("click", () => {
    if (state.page < state.pages) {
      state.page += 1;
      loadClients().catch((error) => toast(error.message));
    }
  });

  Promise.all([loadAnalytics(), loadClients()]).catch((error) => toast(error.message));
});

