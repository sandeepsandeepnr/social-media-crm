const API_URL = "http://localhost:8000/api/v1";
let currentToken = localStorage.getItem("authToken");
let refreshToken = localStorage.getItem("refreshToken");
let currentUser = null;
let currentInteractionId = null;
let currentInteraction = null;
let currentDraftId = null;
let currentDrafts = [];
let responseBusy = false;
let interactionOffset = 0;
let ticketOffset = 0;
let interactionRequestSequence = 0;
let ticketRequestSequence = 0;
const pageSize = 50;
const activePage = document.body.dataset.page;

document.addEventListener("DOMContentLoaded", async () => {
    try {
        currentUser = JSON.parse(localStorage.getItem("user") || "null");
    } catch {
        currentUser = null;
    }
    if (!currentToken || !currentUser) {
        window.location.href = "/login.html";
        return;
    }

    document.getElementById("userName").textContent =
        currentUser.first_name || currentUser.username || currentUser.email;
    if (document.body.dataset.admin === "true" || activePage === "monitoring") {
        const verifiedUser = await apiCall("/users/me");
        if (!verifiedUser) return;
        currentUser = verifiedUser;
        localStorage.setItem("user", JSON.stringify(verifiedUser));
        if (document.body.dataset.admin === "true" && verifiedUser.role !== "admin") {
            document.querySelectorAll('[data-admin-only="true"]').forEach(item => item.remove());
            document.getElementById("adminAccessDenied").hidden = false;
            return;
        }
        if (document.body.dataset.admin === "true") document.querySelector("main").hidden = false;
    }
    if (currentUser.role !== "admin") {
        document.querySelectorAll('[data-admin-only="true"]').forEach(item => item.remove());
    }

    document.getElementById("searchInput")?.addEventListener("input", debounce(resetInteractionPage, 300));
    document.getElementById("platformFilter")?.addEventListener("change", resetInteractionPage);
    document.getElementById("statusFilter")?.addEventListener("change", resetInteractionPage);
    document.getElementById("monitoringTermSelect")?.addEventListener("change", resetInteractionPage);
    document.getElementById("createUserForm")?.addEventListener("submit", createUser);
    document.getElementById("connectPlatformForm")?.addEventListener("submit", connectPlatform);
    loadDashboardMetrics();
    const loaders = {
        dashboard: loadInteractions,
        inbox: loadInteractions,
        monitoring: loadMonitoring,
        tickets: loadTickets,
        customers: loadCustomers,
        analytics: loadAnalytics,
        settings: loadSettings,
        team: loadUsers,
        integrations: loadPlatforms
    };
    loaders[activePage]?.();
    if (activePage === "dashboard" || activePage === "inbox" || activePage === "monitoring") {
        window.setInterval(() => { loadDashboardMetrics(); loadInteractions(); }, 30000);
    }
});

async function apiCall(endpoint, method = "GET", body = null, retried = false) {
    const options = {
        method,
        headers: { "Authorization": `Bearer ${currentToken}` }
    };
    if (body !== null) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }

    let response;
    try {
        response = await fetch(`${API_URL}${endpoint}`, options);
    } catch (error) {
        showNotification(`Unable to reach the API: ${error.message}`, "danger");
        return null;
    }

    if (response.status === 401 && !retried && refreshToken) {
        const renewed = await renewAccessToken();
        if (renewed) return apiCall(endpoint, method, body, true);
    }
    if (response.status === 401) {
        localStorage.clear();
        window.location.href = "/login.html";
        return null;
    }
    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            const error = await response.json();
            message = error.detail || error.message || error.error || message;
            if (typeof message !== "string") message = JSON.stringify(message);
        } catch {
            // Keep the HTTP status message when the server does not return JSON.
        }
        showNotification(message, "danger");
        return null;
    }
    if (response.status === 204) return true;
    return response.json();
}

async function renewAccessToken() {
    try {
        const response = await fetch(`${API_URL}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        if (!response.ok) return false;
        const data = await response.json();
        currentToken = data.access_token || data.token;
        refreshToken = data.refresh_token;
        localStorage.setItem("authToken", currentToken);
        localStorage.setItem("refreshToken", refreshToken);
        return true;
    } catch {
        return false;
    }
}

async function loadDashboardMetrics() {
    const data = await apiCall("/dashboard/metrics");
    if (!data) return;
    const values = {
        todayInteractions: data.total_interactions_today ?? 0,
        unprocessedCount: data.unprocessed_interactions ?? 0,
        openTickets: data.open_tickets ?? 0,
        unreadBadge: data.unprocessed_interactions ?? 0
    };
    const minutes = data.avg_first_response_time_minutes;
    values.avgResponseTime = minutes == null ? "--" : `${minutes.toFixed(0)}m`;
    Object.entries(values).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    });
}

async function loadMonitoring() {
    document.getElementById("termForm")?.addEventListener("submit", createMonitoringTerm);
    document.getElementById("hashtagTokenForm")?.addEventListener("submit", saveHashtagToken);
    document.getElementById("hashtagSearchForm")?.addEventListener("submit", searchHashtag);
    document.getElementById("hashtagAccount")?.addEventListener("change", () => {
        document.getElementById("hashtagResults").innerHTML = "";
    });
    await loadMonitoringTerms();
    if (currentUser.role === "admin") await loadHashtagAccounts();
}

async function loadMonitoringTerms(selectedId = "") {
    const result = await apiCall("/monitoring/terms");
    if (!result) return;
    const select = document.getElementById("monitoringTermSelect");
    const previous = selectedId || select.value;
    select.innerHTML = result.data.length
        ? result.data.map(item => `<option value="${escapeHtml(item.id)}" data-term="${escapeHtml(item.term)}">${escapeHtml(item.term)}</option>`).join("")
        : `<option value="">No terms configured</option>`;
    if (result.data.some(item => item.id === previous)) select.value = previous;
    interactionOffset = 0;
    await loadInteractions();
}

async function createMonitoringTerm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button");
    button.disabled = true;
    try {
        const result = await apiCall("/monitoring/terms", "POST", {
            term: document.getElementById("newMonitoringTerm").value.trim()
        });
        if (!result) return;
        form.reset();
        await loadMonitoringTerms(result.id);
        showNotification("Monitoring term added.", "success");
    } finally {
        button.disabled = false;
    }
}

async function deleteMonitoringTerm() {
    const select = document.getElementById("monitoringTermSelect");
    if (!select.value) return showNotification("Select a monitoring term first.", "warning");
    if (!window.confirm("Delete this monitoring term? Captured interactions will not be deleted.")) return;
    if (await apiCall(`/monitoring/terms/${select.value}`, "DELETE")) {
        await loadMonitoringTerms();
        showNotification("Monitoring term deleted.", "success");
    }
}

async function loadHashtagAccounts(selectedId = "") {
    const result = await apiCall("/monitoring/instagram-accounts");
    if (!result) return;
    const select = document.getElementById("hashtagAccount");
    const previous = selectedId || select.value;
    select.innerHTML = result.data.length
        ? result.data.map(row => `<option value="${escapeHtml(row.id)}">${escapeHtml(row.account_name || row.account_id)} — ${row.hashtag_token_configured ? "token configured" : "token needed"}</option>`).join("")
        : `<option value="">No active Instagram accounts</option>`;
    if (result.data.some(row => row.id === previous)) select.value = previous;
}

async function saveHashtagToken(event) {
    event.preventDefault();
    const accountId = document.getElementById("hashtagAccount").value;
    if (!accountId) return showNotification("Connect an Instagram account first.", "warning");
    const form = event.currentTarget;
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    try {
        const result = await apiCall(`/monitoring/instagram-accounts/${accountId}/hashtag-token`, "PUT", {
            access_token: document.getElementById("hashtagToken").value.trim()
        });
        if (!result) return;
        form.reset();
        await loadHashtagAccounts(accountId);
        showNotification("Hashtag token saved.", "success");
    } finally {
        button.disabled = false;
    }
}

async function deleteHashtagToken() {
    const accountId = document.getElementById("hashtagAccount").value;
    if (!accountId) return showNotification("Select an Instagram account first.", "warning");
    if (!window.confirm("Remove the hashtag search token for this account?")) return;
    if (await apiCall(`/monitoring/instagram-accounts/${accountId}/hashtag-token`, "DELETE")) {
        await loadHashtagAccounts(accountId);
        showNotification("Hashtag token removed.", "success");
    }
}

async function searchHashtag(event) {
    event.preventDefault();
    const accountId = document.getElementById("hashtagAccount").value;
    if (!accountId) return showNotification("Connect an Instagram account first.", "warning");
    if (!window.confirm("This search may count toward Meta's 30-unique-hashtag limit for seven days. Continue?")) return;
    const button = event.currentTarget.querySelector("button");
    button.disabled = true;
    const root = document.getElementById("hashtagResults");
    root.textContent = "Searching Meta...";
    try {
        const result = await apiCall("/monitoring/instagram-hashtags/search", "POST", {
            credential_id: accountId,
            hashtag: document.getElementById("hashtagSearch").value.trim()
        });
        if (!result) {
            root.textContent = "Search failed. See the error message.";
            return;
        }
        root.innerHTML = `<p>Recent results for #${escapeHtml(result.hashtag)}${result.has_more ? " (first page only; more results available)" : ""}</p>` +
            (result.data.length ? result.data.map(item => `<article class="border rounded p-3 mb-2">
                <p>${escapeHtml(item.caption || "(No caption)")}</p>
                <small>${escapeHtml(item.media_type || "")} ${escapeHtml(item.timestamp || "")}</small>
                ${item.permalink ? `<a class="d-block" href="${safeLink(item.permalink)}" target="_blank" rel="noopener noreferrer">Open on Instagram</a>` : ""}
            </article>`).join("") : `<p class="text-muted">No recent public media returned.</p>`);
    } finally {
        button.disabled = false;
    }
}

async function loadInteractions() {
    const spinner = document.getElementById("loadingSpinner");
    const tableBody = document.getElementById("interactionsBody");
    if (!tableBody) return;
    const requestSequence = ++interactionRequestSequence;
    spinner?.classList.add("show");

    const params = new URLSearchParams({ limit: String(pageSize), offset: String(interactionOffset), sort: "captured_at", order: "desc" });
    if (activePage === "monitoring") {
        const selected = document.getElementById("monitoringTermSelect")?.selectedOptions[0];
        if (!selected?.value) {
            spinner?.classList.remove("show");
            tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">Add or select a monitoring term.</td></tr>`;
            document.getElementById("interactionPagination").innerHTML = "";
            return;
        }
        params.set("content_search", selected.dataset.term);
    }
    const search = document.getElementById("searchInput")?.value.trim();
    const platform = document.getElementById("platformFilter")?.value;
    const status = document.getElementById("statusFilter")?.value;
    if (search) params.set("search", search);
    if (platform) params.set("platform", platform);
    if (status) params.set("status", status);

    const result = await apiCall(`/interactions?${params}`);
    if (requestSequence !== interactionRequestSequence) return;
    spinner?.classList.remove("show");
    if (!result) return;
    if (interactionOffset > 0 && interactionOffset >= result.total) {
        interactionOffset = Math.max(0, Math.ceil(result.total / pageSize) - 1) * pageSize;
        return loadInteractions();
    }
    tableBody.innerHTML = interactionRows(result.data);
    renderPagination("interactionPagination", result, "changeInteractionPage");
}

function renderPagination(id, result, handler) {
    const root = document.getElementById(id);
    if (!root) return;
    const start = result.total ? result.offset + 1 : 0;
    const end = Math.min(result.offset + result.data.length, result.total);
    root.innerHTML = `<span>${start}–${end} of ${result.total}</span><div>
        <button class="btn btn-sm btn-outline-secondary me-2" onclick="${handler}(-1)" ${result.offset === 0 ? "disabled" : ""}>Previous</button>
        <button class="btn btn-sm btn-outline-secondary" onclick="${handler}(1)" ${end >= result.total ? "disabled" : ""}>Next</button></div>`;
}

function resetInteractionPage() { interactionOffset = 0; loadInteractions(); }
function changeInteractionPage(direction) { interactionOffset = Math.max(0, interactionOffset + direction * pageSize); loadInteractions(); }
function resetTicketPage() { ticketOffset = 0; loadTickets(); }
function changeTicketPage(direction) { ticketOffset = Math.max(0, ticketOffset + direction * pageSize); loadTickets(); }

function interactionRows(rows) {
    if (!rows?.length) return `<tr><td colspan="7" class="text-center text-muted py-4">No interactions found.</td></tr>`;
    return rows.map(item => {
        const label = item.ticket_id ? item.status : (item.is_processed ? "processed" : "unprocessed");
        const customer = escapeHtml(item.customer_name || "Unknown");
        const content = escapeHtml(item.content || "");
        return `<tr class="interaction-row" role="button" tabindex="0" onclick="openInteractionModal('${item.id}')" onkeydown="if(event.key==='Enter')openInteractionModal('${item.id}')">
            <td><div class="d-flex align-items-center gap-2"><img src="${safeImage(item.customer_avatar)}" alt="" style="width:32px;height:32px;border-radius:50%"><span>${customer}</span></div></td>
            <td><span class="platform-badge badge-${safeClass(item.platform)}">${escapeHtml(item.platform)}</span></td>
            <td class="text-truncate" style="max-width:300px" title="${content}">${truncateText(content, 70)}</td>
            <td><small>${escapeHtml(item.interaction_type)}</small></td>
            <td><span class="status-badge badge-${safeClass(label)}">${escapeHtml(label.replaceAll("_", " "))}</span></td>
            <td><small>${escapeHtml(formatTimeAgo(new Date(item.captured_at)))}</small></td>
            <td><button class="btn btn-sm btn-outline-primary" onclick="event.stopPropagation();openInteractionModal('${item.id}')" aria-label="View interaction"><i class="bi bi-arrow-right"></i></button></td>
        </tr>`;
    }).join("");
}

async function openInteractionModal(interactionId) {
    currentInteractionId = interactionId;
    currentInteraction = null;
    currentDraftId = null;
    currentDrafts = [];
    const modalElement = document.getElementById("interactionModal");
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    const modalBody = document.getElementById("modalBody");
    const createButton = document.getElementById("createTicketButton");
    modalBody.innerHTML = `<div class="text-center p-4"><div class="spinner-border text-primary" role="status"></div></div>`;
    createButton.disabled = true;
    modal.show();

    const data = await apiCall(`/interactions/${interactionId}`);
    if (!data || currentInteractionId !== interactionId) return;
    currentInteraction = data;
    const customer = data.customer || {};
    const ticket = data.ticket;
    const conversation = (data.conversation_thread || []).map(message => `
        <div class="mb-2"><div class="rounded p-3 ${message.type === "customer" ? "bg-light" : "bg-primary text-white"}">
            <p class="mb-1">${escapeHtml(message.content || "")}</p><small>${escapeHtml(new Date(message.timestamp).toLocaleString())}</small>
        </div></div>`).join("");
    const history = ticket ? await apiCall(`/tickets/${ticket.id}/responses`) : null;
    if (currentInteractionId !== interactionId) return;
    currentDrafts = (history?.data || []).filter(row => row.responding_to_interaction_id === interactionId && row.status !== "published");
    const draftList = currentDrafts.map(row => `<div class="border rounded p-2 mb-2">
        <strong>${escapeHtml(row.status)}</strong> · ${escapeHtml(row.agent)}
        <p class="mb-1">${escapeHtml(row.content)}</p>
        ${row.error_message ? `<small class="text-danger d-block">${escapeHtml(row.error_message)}</small>` : ""}
        ${["draft", "failed"].includes(row.status) ? `<button class="btn btn-sm btn-outline-secondary" onclick="loadDraft('${row.id}')">Edit draft</button>` : ""}
    </div>`).join("");
    const supportedReply = ["message", "comment"].includes(data.interaction_type);
    const composer = ticket && history ? `<div class="mt-4 border-top pt-3">
        ${draftList ? `<h6>Saved responses</h6>${draftList}` : ""}
        ${supportedReply ? `
        <label for="responseContent" class="form-label fw-semibold">Reply</label>
        <textarea id="responseContent" class="form-control mb-2" rows="3" maxlength="63206" placeholder="Write a response..."></textarea>
        <p class="text-muted">${data.interaction_type === "message" ? "Reply privately to this message." : "Reply publicly to this comment."}</p>
        <button class="btn btn-outline-primary me-2" data-response-action onclick="saveDraft()" ${responseBusy ? "disabled" : ""}>Save draft</button>
        <button class="btn btn-primary" data-response-action onclick="sendResponse()" ${responseBusy ? "disabled" : ""}>Send response</button>` : `<p class="text-muted">Publishing for this interaction type is not implemented.</p>`}
    </div>` : ticket ? `<p class="text-warning">Response history is unavailable.</p>` : "";
    modalBody.innerHTML = `<div class="card mb-3"><div class="card-body d-flex align-items-center gap-3">
        <img src="${safeImage(customer.avatar)}" alt="" style="width:48px;height:48px;border-radius:50%">
        <div><h5 class="mb-0">${escapeHtml(customer.name || "Unknown")}</h5><small class="text-muted">${customer.follower_count ?? 0} followers</small></div>
    </div></div>
    <div class="mb-3"><strong>${escapeHtml(data.platform)} · ${escapeHtml(data.interaction_type)}</strong><p class="mt-2">${escapeHtml(data.content || "")}</p>
        ${data.post_url ? `<a href="${safeLink(data.post_url)}" target="_blank" rel="noopener noreferrer">Open original post</a>` : ""}
    </div>
    ${conversation ? `<h6>Conversation</h6><div class="mb-3" style="max-height:240px;overflow:auto">${conversation}</div>` : ""}
    ${ticket ? `<div class="alert alert-info mb-2">Ticket ${escapeHtml(ticket.ticket_number)} · ${escapeHtml(ticket.status)}</div>` : `<div class="alert alert-warning">No ticket is linked to this interaction.</div>`}
    ${composer}`;
    createButton.disabled = Boolean(ticket);
    createButton.textContent = ticket ? "Ticket created" : "Create Ticket";
}

function loadDraft(id) {
    const draft = currentDrafts.find(row => row.id === id);
    if (!draft) return;
    currentDraftId = draft.id;
    document.getElementById("responseContent").value = draft.content;
    document.getElementById("responseContent").focus();
}

function setResponseBusy(busy) {
    responseBusy = busy;
    document.querySelectorAll("[data-response-action]").forEach(button => { button.disabled = busy; });
}

async function createTicket() {
    if (!currentInteractionId) return showNotification("Select an interaction first.", "warning");
    const result = await apiCall("/tickets", "POST", {
        primary_interaction_id: currentInteractionId,
        subject: (currentInteraction?.content || "Customer interaction").slice(0, 500),
        priority: "medium"
    });
    if (!result) return;
    showNotification(`Ticket ${result.ticket_number} created.`, "success");
    await loadInteractions();
    await loadDashboardMetrics();
    await openInteractionModal(currentInteractionId);
}

async function saveDraft() {
    if (responseBusy) return;
    if (!currentInteraction?.ticket?.id) return;
    const content = document.getElementById("responseContent")?.value.trim();
    if (!content) return showNotification("Enter a response before saving.", "warning");
    const interactionId = currentInteractionId;
    setResponseBusy(true);
    try {
        const result = currentDraftId
            ? await apiCall(`/responses/${currentDraftId}`, "PUT", { content })
            : await apiCall("/responses", "POST", {
                ticket_id: currentInteraction.ticket.id,
                responding_to_interaction_id: currentInteractionId,
                content,
                is_private_message: currentInteraction.interaction_type === "message"
            });
        if (result) {
            showNotification("Draft saved.", "success");
            if (currentInteractionId === interactionId) await openInteractionModal(interactionId);
        }
    } finally {
        setResponseBusy(false);
    }
}

async function sendResponse() {
    if (responseBusy) return;
    if (!currentInteraction?.ticket?.id) return;
    const content = document.getElementById("responseContent")?.value.trim();
    if (!content) return showNotification("Enter a response before sending.", "warning");
    const interactionId = currentInteractionId;
    setResponseBusy(true);
    try {
        const draft = currentDraftId
            ? await apiCall(`/responses/${currentDraftId}`, "PUT", { content })
            : await apiCall("/responses", "POST", {
                ticket_id: currentInteraction.ticket.id,
                responding_to_interaction_id: currentInteractionId,
                content,
                is_private_message: currentInteraction.interaction_type === "message"
            });
        if (!draft) return;
        const sent = await apiCall(`/responses/${draft.id}/send`, "POST", {});
        if (sent) {
            showNotification("Response sent.", "success");
            await loadDashboardMetrics();
        }
        if (currentInteractionId === interactionId) await openInteractionModal(interactionId);
    } finally {
        setResponseBusy(false);
    }
}

async function loadTickets() {
    const root = document.getElementById("ticketsContent");
    const requestSequence = ++ticketRequestSequence;
    root.innerHTML = `<p class="text-muted">Loading tickets...</p>`;
    const params = new URLSearchParams({ limit: String(pageSize), offset: String(ticketOffset), sort: "opened_at", order: "desc" });
    const status = document.getElementById("ticketStatusFilter")?.value;
    const platform = document.getElementById("ticketPlatformFilter")?.value;
    if (status) params.set("status", status);
    if (platform) params.set("platform", platform);
    const result = await apiCall(`/tickets?${params}`);
    if (requestSequence !== ticketRequestSequence) return;
    if (!result) return;
    if (ticketOffset > 0 && ticketOffset >= result.total) {
        ticketOffset = Math.max(0, Math.ceil(result.total / pageSize) - 1) * pageSize;
        return loadTickets();
    }
    renderPagination("ticketPagination", result, "changeTicketPage");
    if (!result.data.length) {
        root.innerHTML = `<p class="text-muted py-4">No tickets yet. Create a ticket from an interaction in the inbox.</p>`;
        return;
    }
    root.innerHTML = `<div class="table-responsive"><table class="table align-middle"><thead><tr><th>Ticket</th><th>Customer</th><th>Subject</th><th>Channel</th><th>Priority</th><th>Status</th><th>Opened</th></tr></thead><tbody>
        ${result.data.map(ticket => `<tr role="button" onclick="showTicket('${ticket.id}')">
            <td>${escapeHtml(ticket.ticket_number)}</td><td>${escapeHtml(ticket.customer_name || "Unknown")}</td>
            <td>${escapeHtml(ticket.subject || "")}</td><td>${escapeHtml(ticket.platform)}</td>
            <td>${escapeHtml(ticket.priority)}</td><td><span class="status-badge badge-${safeClass(ticket.status)}">${escapeHtml(ticket.status.replaceAll("_", " "))}</span></td>
            <td>${escapeHtml(new Date(ticket.opened_at).toLocaleString())}</td></tr>`).join("")}
    </tbody></table></div>`;
}

async function showTicket(ticketId) {
    const ticket = await apiCall(`/tickets/${ticketId}`);
    if (!ticket) return;
    let assignmentField = "";
    if (currentUser.role === "admin") {
        const users = await apiCall("/users?role=agent&limit=100");
        if (!users) return;
        const agents = users.data.map(agent => `<option value="${agent.id}" ${ticket.assigned_to_agent_id === agent.id ? "selected" : ""}>${escapeHtml(agent.username)}</option>`).join("");
        assignmentField = `<label class="form-label mt-3" for="ticketAssignee">Assigned agent</label>
            <select class="form-select" id="ticketAssignee"><option value="">Unassigned</option>${agents}</select>`;
    }
    const content = `<h5>${escapeHtml(ticket.ticket_number)} · ${escapeHtml(ticket.status)}</h5>
        <p><strong>${escapeHtml(ticket.subject || "")}</strong><br>${escapeHtml(ticket.customer?.name || "Unknown")} · ${escapeHtml(ticket.platform)}</p>
        <p>${escapeHtml(ticket.description || "")}</p><hr>
        ${(ticket.conversation || []).map(message => `<div class="mb-2 p-2 rounded ${message.source === "customer" ? "bg-light" : "bg-primary text-white"}">
            <small>${escapeHtml(message.source)} · ${escapeHtml(new Date(message.timestamp).toLocaleString())}</small><div>${escapeHtml(message.content || "")}</div></div>`).join("")}
        <div class="row g-3 mt-2">
        <div class="col-md-6"><label class="form-label" for="ticketStatus">Status</label><select class="form-select" id="ticketStatus">
        ${["open", "in_progress", "pending", "resolved", "closed"].map(value => `<option value="${value}" ${ticket.status === value ? "selected" : ""}>${value.replaceAll("_", " ")}</option>`).join("")}
        </select></div>
        <div class="col-md-6"><label class="form-label" for="ticketPriority">Priority</label><select class="form-select" id="ticketPriority">
        ${["low", "medium", "high", "urgent"].map(value => `<option value="${value}" ${ticket.priority === value ? "selected" : ""}>${value}</option>`).join("")}
        </select></div></div>
        ${assignmentField}
        <label class="form-label mt-3" for="ticketTags">Tags (comma separated)</label>
        <input class="form-control" id="ticketTags" value="${escapeHtml((ticket.tags || []).join(", "))}">
        <label class="form-label mt-3" for="ticketNotes">Internal notes</label>
        <textarea class="form-control" id="ticketNotes" rows="3">${escapeHtml(ticket.internal_notes || "")}</textarea>
        <label class="form-label mt-3" for="resolutionSummary">Resolution summary (required to resolve)</label>
        <textarea class="form-control" id="resolutionSummary" rows="2">${escapeHtml(ticket.resolution_summary || "")}</textarea>
        <button class="btn btn-primary mt-3" onclick="updateTicket('${ticket.id}')">Save ticket</button>`;
    showDetailsModal(content, `Ticket ${ticket.ticket_number}`);
}

async function updateTicket(ticketId) {
    const status = document.getElementById("ticketStatus")?.value;
    const summary = document.getElementById("resolutionSummary")?.value.trim();
    if (status === "resolved" && !summary) {
        return showNotification("Enter a resolution summary before resolving this ticket.", "warning");
    }
    const payload = {
        priority: document.getElementById("ticketPriority").value,
        internal_notes: document.getElementById("ticketNotes").value,
        tags: document.getElementById("ticketTags").value.split(",").map(tag => tag.trim()).filter(Boolean)
    };
    const assignee = document.getElementById("ticketAssignee");
    if (assignee) payload.assigned_to_agent_id = assignee.value || null;
    if (status !== "resolved") payload.status = status;
    const updated = await apiCall(`/tickets/${ticketId}`, "PUT", payload);
    if (!updated) return;
    if (status === "resolved") {
        const resolved = await apiCall(`/tickets/${ticketId}/resolve`, "PUT", { resolution_summary: summary });
        if (!resolved) return;
    }
    bootstrap.Modal.getInstance(document.getElementById("detailsModal"))?.hide();
    showNotification(status === "resolved" ? "Ticket resolved." : "Ticket updated.", "success");
    await loadTickets();
    await loadDashboardMetrics();
}

async function loadCustomers() {
    const root = document.getElementById("customersContent");
    root.innerHTML = `<div class="d-flex gap-2 mb-3"><input class="form-control" id="customerSearch" placeholder="Search name or social profile ID"><button class="btn btn-primary" onclick="searchCustomers()">Search</button></div><div id="customerResults">Loading...</div>`;
    await searchCustomers();
}

async function searchCustomers() {
    const root = document.getElementById("customerResults");
    if (!root) return;
    const search = document.getElementById("customerSearch")?.value.trim();
    const result = await apiCall(`/customers?limit=50${search ? `&search=${encodeURIComponent(search)}` : ""}`);
    if (!result) return;
    root.innerHTML = result.data.length ? `<div class="table-responsive"><table class="table align-middle"><thead><tr><th>Name</th><th>Platform</th><th>Interactions</th><th>Last interaction</th></tr></thead><tbody>
        ${result.data.map(customer => `<tr role="button" onclick="showCustomer('${customer.id}')"><td>${escapeHtml(customer.name)}</td><td>${escapeHtml(customer.platform || "")}</td><td>${customer.total_interactions ?? ""}</td><td>${customer.last_interaction_at ? escapeHtml(new Date(customer.last_interaction_at).toLocaleString()) : "—"}</td></tr>`).join("")}
        </tbody></table></div>` : `<p class="text-muted">No customers found.</p>`;
}

async function showCustomer(customerId) {
    const customer = await apiCall(`/customers/${customerId}`);
    if (!customer) return;
    const history = customer.interaction_history.map(row => `<li class="list-group-item"><small>${escapeHtml(row.type)} · ${escapeHtml(new Date(row.timestamp).toLocaleString())}</small><div>${escapeHtml(row.content)}</div></li>`).join("");
    showDetailsModal(`<p>${escapeHtml(customer.platform)} profile · ${customer.total_interactions} interactions · ${customer.open_tickets} open tickets</p>
        <h6>Interaction history</h6><ul class="list-group">${history || "<li class='list-group-item'>No history yet.</li>"}</ul>`, customer.name);
}

async function loadAnalytics() {
    const root = document.getElementById("analyticsContent");
    root.innerHTML = `<p class="text-muted">Loading analytics...</p>`;
    const result = await apiCall("/analytics/platforms");
    if (!result) return;
    root.innerHTML = `<div class="table-responsive"><table class="table"><thead><tr><th>Platform</th><th>Interactions</th><th>Tickets</th><th>Avg first response</th><th>Avg resolution</th></tr></thead><tbody>
        ${result.data.map(item => `<tr><td>${escapeHtml(item.platform)}</td><td>${item.total_interactions}</td><td>${item.total_tickets}</td><td>${item.avg_response_time_minutes == null ? "—" : `${item.avg_response_time_minutes} min`}</td><td>${item.avg_resolution_time_minutes == null ? "—" : `${item.avg_resolution_time_minutes} min`}</td></tr>`).join("")}
        </tbody></table></div>`;
}

async function loadSettings() {
    const root = document.getElementById("settingsContent");
    const result = await apiCall("/settings");
    if (!result) return;
    const settings = result.data;
    root.innerHTML = `<p class="alert alert-warning text-start">Automatic ticket creation applies to accounts owned by this administrator. Automated sync, assignment, and response approval are not yet enforced.</p>
        <form id="settingsForm" class="text-start" style="max-width:560px">
        <label class="form-label" for="syncInterval">Platform sync interval (minutes)</label>
        <input class="form-control mb-3" type="number" min="1" max="1440" id="syncInterval" value="${settings.platform_sync_interval_minutes}">
        ${[
            ["auto_create_tickets", "Automatically create tickets"],
            ["ticket_auto_assign", "Enable automatic assignment"],
            ["require_response_approval", "Require approval before sending responses"]
        ].map(([key, label]) => `<div class="form-check mb-2"><input class="form-check-input" type="checkbox" id="${key}" ${settings[key] ? "checked" : ""}><label class="form-check-label" for="${key}">${label}</label></div>`).join("")}
        <button class="btn btn-primary mt-3" type="submit">Save settings</button></form>`;
    document.getElementById("settingsForm").addEventListener("submit", saveSettings);
}

async function saveSettings(event) {
    event.preventDefault();
    const values = {
        platform_sync_interval_minutes: Number(document.getElementById("syncInterval").value),
        auto_create_tickets: document.getElementById("auto_create_tickets").checked,
        ticket_auto_assign: document.getElementById("ticket_auto_assign").checked,
        require_response_approval: document.getElementById("require_response_approval").checked
    };
    if (await apiCall("/settings", "PUT", values)) showNotification("Settings saved.", "success");
}

async function loadUsers() {
    const root = document.getElementById("usersContent");
    root.innerHTML = `<p class="text-muted">Loading team members...</p>`;
    const result = await apiCall("/users?limit=100&offset=0");
    if (!result) return;
    if (!result.data.length) {
        root.innerHTML = `<p class="text-muted">No team members found.</p>`;
        return;
    }
    root.innerHTML = `<div class="table-responsive"><table class="table align-middle">
        <thead><tr><th>Username</th><th>Email</th><th>Role</th><th>Account</th><th>Created</th><th>Actions</th></tr></thead>
        <tbody>${result.data.map(user => {
            const self = user.id === currentUser.id;
            return `<tr>
                <td>${escapeHtml(user.username)}${self ? " (you)" : ""}</td>
                <td>${escapeHtml(user.email)}</td>
                <td><select class="form-select form-select-sm" id="userRole-${user.id}" ${self ? "disabled" : ""}>
                    ${["agent", "team_leader", "admin"].map(role => `<option value="${role}" ${user.role === role ? "selected" : ""}>${role.replaceAll("_", " ")}</option>`).join("")}
                </select></td>
                <td><select class="form-select form-select-sm" id="userActive-${user.id}" ${self ? "disabled" : ""}>
                    <option value="true" ${user.is_active ? "selected" : ""}>Active</option>
                    <option value="false" ${!user.is_active ? "selected" : ""}>Inactive</option>
                </select></td>
                <td>${user.created_at ? escapeHtml(new Date(user.created_at).toLocaleDateString()) : "—"}</td>
                <td><button class="btn btn-sm btn-outline-primary me-1" onclick="editUserProfile('${user.id}')">Profile</button>
                    ${self ? "" : `<button class="btn btn-sm btn-outline-primary me-1" onclick="updateUser('${user.id}')">Save</button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteUser('${user.id}')">Delete</button>`}</td>
            </tr>`;
        }).join("")}</tbody></table></div>`;
}

async function createUser(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector("button[type='submit']");
    submit.disabled = true;
    const result = await apiCall("/auth/register", "POST", {
        username: document.getElementById("newUsername").value.trim(),
        email: document.getElementById("newUserEmail").value.trim(),
        password: document.getElementById("newUserPassword").value,
        role: "agent"
    });
    submit.disabled = false;
    if (!result) return;
    form.reset();
    showNotification(`Agent ${result.username} added.`, "success");
    await loadUsers();
}

async function editUserProfile(userId) {
    const user = await apiCall(`/users/${userId}`);
    if (!user) return;
    showDetailsModal(`<form id="userProfileForm">
        <label class="form-label" for="profileFirstName">First name</label>
        <input class="form-control mb-3" id="profileFirstName" maxlength="100" value="${escapeHtml(user.first_name || "")}">
        <label class="form-label" for="profileLastName">Last name</label>
        <input class="form-control mb-3" id="profileLastName" maxlength="100" value="${escapeHtml(user.last_name || "")}">
        <label class="form-label" for="profileTimezone">Timezone</label>
        <input class="form-control mb-3" id="profileTimezone" maxlength="100" value="${escapeHtml(user.timezone || "")}">
        <label class="form-label" for="profileLanguage">Language preference</label>
        <input class="form-control mb-3" id="profileLanguage" maxlength="20" value="${escapeHtml(user.language_preference || "")}">
        <button class="btn btn-primary" type="submit">Save profile</button>
    </form>`, `Profile: ${user.username}`);
    document.getElementById("userProfileForm").addEventListener("submit", async event => {
        event.preventDefault();
        const submit = event.currentTarget.querySelector("button[type='submit']");
        submit.disabled = true;
        const result = await apiCall(`/users/${userId}`, "PUT", {
            first_name: document.getElementById("profileFirstName").value.trim(),
            last_name: document.getElementById("profileLastName").value.trim(),
            timezone: document.getElementById("profileTimezone").value.trim(),
            language_preference: document.getElementById("profileLanguage").value.trim()
        });
        submit.disabled = false;
        if (!result) return;
        if (userId === currentUser.id) {
            currentUser = result;
            localStorage.setItem("user", JSON.stringify(result));
            document.getElementById("userName").textContent = result.first_name || result.username || result.email;
        }
        bootstrap.Modal.getInstance(document.getElementById("detailsModal"))?.hide();
        showNotification("Profile updated.", "success");
        await loadUsers();
    });
}

async function updateUser(userId) {
    const payload = {
        role: document.getElementById(`userRole-${userId}`).value,
        is_active: document.getElementById(`userActive-${userId}`).value === "true"
    };
    const result = await apiCall(`/users/${userId}`, "PUT", payload);
    if (!result) return;
    showNotification(`Updated ${result.username}.`, "success");
    await loadUsers();
}

async function deleteUser(userId) {
    if (!window.confirm("Delete this user? Users with response history must be deactivated instead.")) return;
    const result = await apiCall(`/users/${userId}`, "DELETE");
    if (!result) return;
    showNotification("User deleted.", "success");
    await loadUsers();
}

async function loadPlatforms() {
    const root = document.getElementById("platformsContent");
    root.innerHTML = `<p class="text-muted">Loading connected accounts...</p>`;
    const [platformResult, credentialResult] = await Promise.all([
        apiCall("/platforms"),
        apiCall("/platform-credentials")
    ]);
    if (!platformResult || !credentialResult) return;
    const available = platformResult.data.filter(platform => platform.is_active);
    document.getElementById("platformSelect").innerHTML = available.map(platform =>
        `<option value="${platform.id}">${escapeHtml(platform.display_name)}</option>`
    ).join("");
    const form = document.getElementById("connectPlatformForm");
    const connectButton = form.querySelector("button[type='submit']");
    connectButton.disabled = available.length === 0;
    root.innerHTML = credentialResult.data.length ? `<div class="table-responsive"><table class="table align-middle">
        <thead><tr><th>Platform</th><th>Account</th><th>Account ID</th><th>Status</th><th>Last sync</th><th>Actions</th></tr></thead>
        <tbody>${credentialResult.data.map(account => `<tr>
            <td>${escapeHtml(account.platform)}</td>
            <td>${escapeHtml(account.business_account_name || "Unnamed account")}</td>
            <td>${escapeHtml(account.business_account_id)}</td>
            <td>${escapeHtml(account.is_active ? (account.sync_status || "active") : "paused")}</td>
            <td>${account.last_sync_at ? escapeHtml(new Date(account.last_sync_at).toLocaleString()) : "Not synced"}</td>
            <td><button class="btn btn-sm btn-outline-primary me-1" onclick="editPlatform('${account.id}')">Edit</button>
                <button class="btn btn-sm btn-outline-primary me-1" onclick="verifyPlatform('${account.id}')" ${account.is_active ? "" : "disabled"}>Verify access</button>
                <button class="btn btn-sm btn-outline-primary me-1" onclick="setPlatformActive('${account.id}', ${!account.is_active})">${account.is_active ? "Pause" : "Resume"}</button>
                <button class="btn btn-sm btn-outline-danger" onclick="disconnectPlatform('${account.id}')">Disconnect</button></td>
        </tr>`).join("")}</tbody></table></div>` : `<p class="text-muted">No platform accounts are connected.</p>`;
}

async function verifyPlatform(credentialId) {
    const result = await apiCall(`/monitoring/accounts/${credentialId}/verify`, "POST", {});
    if (result) showNotification(result.scope, "success");
}

async function connectPlatform(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector("button[type='submit']");
    submit.disabled = true;
    const result = await apiCall("/platform-credentials", "POST", {
        platform_id: document.getElementById("platformSelect").value,
        business_account_id: document.getElementById("businessAccountId").value.trim(),
        business_account_name: document.getElementById("businessAccountName").value.trim() || null,
        access_token: document.getElementById("platformAccessToken").value,
        scope: document.getElementById("platformScope").value.trim() || null
    });
    submit.disabled = false;
    if (!result) return;
    form.reset();
    showNotification(`${result.platform} account connected.`, "success");
    await loadPlatforms();
}

async function editPlatform(credentialId) {
    const result = await apiCall("/platform-credentials");
    if (!result) return;
    const account = result.data.find(item => item.id === credentialId);
    if (!account) return showNotification("Platform account not found. Refresh the list and try again.", "danger");
    showDetailsModal(`<form id="editPlatformForm">
        <label class="form-label" for="editAccountName">Account name</label>
        <input class="form-control mb-3" id="editAccountName" maxlength="255" value="${escapeHtml(account.business_account_name || "")}">
        <label class="form-label" for="editScope">Granted scopes</label>
        <input class="form-control mb-3" id="editScope" maxlength="1000" value="${escapeHtml(account.scope || "")}">
        <label class="form-label" for="editAccessToken">New access token (optional)</label>
        <input class="form-control mb-3" id="editAccessToken" type="password" maxlength="2000" autocomplete="off">
        <p class="text-muted small">Leave the token empty to keep the current token. Existing tokens cannot be displayed.</p>
        <button class="btn btn-primary" type="submit">Save account</button>
    </form>`, `Edit ${account.platform} account`);
    document.getElementById("editPlatformForm").addEventListener("submit", async event => {
        event.preventDefault();
        const submit = event.currentTarget.querySelector("button[type='submit']");
        const accessToken = document.getElementById("editAccessToken").value;
        const payload = {
            business_account_name: document.getElementById("editAccountName").value.trim(),
            scope: document.getElementById("editScope").value.trim()
        };
        if (accessToken) payload.access_token = accessToken;
        submit.disabled = true;
        const updated = await apiCall(`/platform-credentials/${credentialId}`, "PUT", payload);
        submit.disabled = false;
        if (!updated) return;
        document.getElementById("editAccessToken").value = "";
        bootstrap.Modal.getInstance(document.getElementById("detailsModal"))?.hide();
        showNotification("Platform account updated.", "success");
        await loadPlatforms();
    });
}

async function setPlatformActive(credentialId, isActive) {
    const result = await apiCall(`/platform-credentials/${credentialId}`, "PUT", { is_active: isActive });
    if (!result) return;
    showNotification(`${result.platform} account ${isActive ? "resumed" : "paused"}.`, "success");
    await loadPlatforms();
}

async function disconnectPlatform(credentialId) {
    if (!window.confirm("Disconnect this social account? Its stored access token will be removed.")) return;
    const result = await apiCall(`/platform-credentials/${credentialId}`, "DELETE");
    if (!result) return;
    showNotification("Platform account disconnected.", "success");
    await loadPlatforms();
}

function showDetailsModal(content, title) {
    let modal = document.getElementById("detailsModal");
    if (!modal) {
        document.body.insertAdjacentHTML("beforeend", `<div class="modal" id="detailsModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5 class="modal-title"></h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div><div class="modal-body"></div></div></div></div>`);
        modal = document.getElementById("detailsModal");
    }
    modal.querySelector(".modal-title").textContent = title;
    modal.querySelector(".modal-body").innerHTML = content;
    bootstrap.Modal.getOrCreateInstance(modal).show();
}

function formatTimeAgo(date) {
    if (Number.isNaN(date.getTime())) return "Unknown";
    const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return date.toLocaleDateString();
}

function truncateText(text, length) {
    return text.length > length ? `${text.slice(0, length)}...` : text;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[char]);
}

function safeClass(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9-]/g, "-");
}

function safeImage(value) {
    try {
        const url = new URL(value || "", window.location.origin);
        return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "";
    } catch {
        return "";
    }
}

function safeLink(value) {
    try {
        const url = new URL(value, window.location.origin);
        return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
    } catch {
        return "#";
    }
}

function debounce(callback, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => callback(...args), wait);
    };
}

function showNotification(message, type = "info") {
    let container = document.getElementById("notificationContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "notificationContainer";
        container.className = "position-fixed top-0 end-0 p-3";
        container.style.zIndex = "1080";
        document.body.appendChild(container);
    }
    const alert = document.createElement("div");
    alert.className = `alert alert-${type} shadow`;
    alert.setAttribute("role", "status");
    alert.textContent = message;
    container.appendChild(alert);
    setTimeout(() => alert.remove(), 5000);
}

async function logout() {
    if (!window.confirm("Are you sure you want to logout?")) return;
    await apiCall("/auth/logout", "POST", refreshToken ? { refresh_token: refreshToken } : null);
    localStorage.clear();
    window.location.href = "/login.html";
}
