const page = document.body.dataset.page;
const adminPages = ["admin", "team", "integrations", "settings"];
const navigation = [
    ["dashboard", "Dashboard", "speedometer2"],
    ["inbox", "Inbox", "inbox"],
    ["monitoring", "Monitoring", "search"],
    ["tickets", "Tickets", "ticket"],
    ["customers", "Customers", "people"],
    ["analytics", "Analytics", "graph-up"]
];
const adminNavigation = [
    ["admin", "Admin overview", "shield-lock"],
    ["team", "Team", "person-gear"],
    ["integrations", "Integrations", "plug"],
    ["settings", "Settings", "gear"]
];

function navItem([name, label, icon], adminOnly = false) {
    const active = name === page;
    return `<div class="nav-item"${adminOnly ? ' data-admin-only="true"' : ""}>
        <a href="${name}.html" class="nav-link${active ? " active" : ""}"${active ? ' aria-current="page"' : ""} title="${label}">
            <i class="bi bi-${icon}" aria-hidden="true"></i><span>${label}</span>
            ${name === "inbox" ? '<span class="badge badge-warning ms-auto" id="unreadBadge"></span>' : ""}
        </a>
    </div>`;
}

document.getElementById("sidebar").innerHTML = `
    <div class="sidebar-logo"><h4><i class="bi bi-chat-dots" aria-hidden="true"></i> CRM</h4></div>
    <nav aria-label="Main navigation">
        ${navigation.map(item => navItem(item)).join("")}
        <hr data-admin-only="true">
        ${adminPages.includes(page) ? adminNavigation.map(item => navItem(item, true)).join("") : navItem(["admin", "Admin", "shield-lock"], true)}
    </nav>`;
