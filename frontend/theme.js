const theme = document.createElement("style");
theme.type = "text/tailwindcss";
theme.textContent = `
body {
            @apply bg-slate-50 text-slate-900 antialiased;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .sidebar {
            @apply z-30 border-r border-slate-200 bg-white shadow-none;
            width: 256px;
            padding: 20px 12px;
        }

        .sidebar-logo {
            @apply mb-6 flex items-center border-b border-slate-100 px-3 pb-5;
        }

        .sidebar-logo h4 {
            @apply flex items-center gap-2 text-base font-semibold tracking-tight text-slate-950;
        }

        .sidebar-logo .bi {
            @apply flex h-8 w-8 items-center justify-center rounded-lg bg-slate-950 text-sm text-white;
        }

        .nav-item {
            @apply mb-1 px-1;
        }

        .nav-link {
            @apply rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 transition-colors;
            gap: 12px;
        }

        .nav-link .bi {
            @apply text-base text-slate-400;
        }

        .nav-link:hover {
            @apply bg-slate-100 text-slate-950;
        }

        .nav-link.active {
            @apply bg-slate-100 text-slate-950;
            background-image: none;
        }

        .nav-link.active .bi {
            @apply text-slate-900;
        }

        .sidebar hr {
            @apply my-4 border-slate-200;
        }

        .main-content {
            margin-left: 256px;
            padding: 28px 36px 40px;
        }

        .top-bar {
            @apply mb-7 rounded-none border-b border-slate-200 bg-transparent px-0 pb-5 pt-0 shadow-none;
        }

        .top-bar h1 {
            @apply text-2xl font-semibold tracking-tight text-slate-950;
        }

        .user-menu {
            @apply gap-3 text-sm font-medium text-slate-700;
        }

        .btn-logout {
            @apply flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-100 hover:text-slate-950;
        }

        .metrics-row {
            @apply mb-6 gap-4;
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .metric-card {
            @apply relative rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition;
        }

        .metric-card:hover {
            @apply -translate-y-0.5 border-slate-300 shadow-md;
        }

        .metric-icon {
            @apply mb-5 flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-base;
        }

        .icon-primary, .icon-success, .icon-warning, .icon-danger {
            @apply text-slate-700;
        }

        .metric-label {
            @apply mb-1 text-xs font-medium normal-case tracking-wide text-slate-500;
        }

        .metric-value {
            @apply text-2xl font-semibold tracking-tight text-slate-950;
        }

        .interactions-container {
            @apply mb-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm;
        }

        .interactions-header {
            @apply mb-5;
        }

        .interactions-header h2,
        .interactions-container > h2 {
            @apply text-base font-semibold tracking-tight text-slate-950;
        }

        .filter-controls {
            @apply gap-2;
        }

        .filter-select, .search-input {
            @apply rounded-lg border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200;
        }

        .search-input {
            min-width: 220px;
        }

        .table-responsive {
            @apply overflow-x-auto;
        }

        table {
            @apply w-full border-collapse text-sm;
        }

        thead {
            @apply bg-slate-50;
        }

        th {
            @apply whitespace-nowrap border-b border-slate-200 px-4 py-3 text-left text-xs font-medium normal-case tracking-wide text-slate-500;
        }

        td {
            @apply border-b border-slate-100 px-4 py-3 text-sm text-slate-700;
        }

        tr:hover {
            @apply bg-slate-50;
        }

        .interaction-row {
            @apply cursor-pointer transition-colors;
        }

        .interaction-row:hover {
            @apply bg-slate-50;
        }

        .platform-badge, .status-badge {
            @apply inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium;
        }

        .badge-facebook { @apply bg-blue-50 text-blue-700; }
        .badge-instagram { @apply bg-pink-50 text-pink-700; }
        .badge-twitter, .badge-x { @apply bg-slate-100 text-slate-700; }
        .badge-open, .badge-pending { @apply bg-amber-50 text-amber-700; }
        .badge-in-progress { @apply bg-blue-50 text-blue-700; }
        .badge-resolved, .badge-processed { @apply bg-emerald-50 text-emerald-700; }
        .badge-closed { @apply bg-slate-100 text-slate-600; }
        .badge-unprocessed { @apply bg-orange-50 text-orange-700; }

        .btn {
            @apply inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium shadow-sm transition focus:outline-none focus:ring-2 focus:ring-slate-300 focus:ring-offset-2 disabled:pointer-events-none disabled:opacity-50;
        }

        .btn-primary {
            @apply border border-slate-900 bg-slate-900 text-white hover:bg-slate-800;
            background-image: none;
        }

        .btn-primary:hover {
            @apply bg-slate-800 text-white;
            background-image: none;
        }

        .btn-outline-primary {
            @apply border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950;
        }

        .btn-outline-danger {
            @apply border border-rose-200 bg-white text-rose-700 hover:bg-rose-50;
        }

        .btn-secondary {
            @apply border border-slate-200 bg-white text-slate-700 hover:bg-slate-50;
        }

        .btn-sm {
            @apply rounded-md px-2.5 py-1.5 text-xs;
        }

        .form-label {
            @apply mb-1.5 block text-sm font-medium text-slate-700;
        }

        .form-control, .form-select, textarea.form-control {
            @apply rounded-lg border-slate-200 bg-white text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200;
        }

        .form-control, .form-select {
            @apply min-h-10 px-3 py-2;
        }

        .form-control:disabled, .form-select:disabled {
            @apply cursor-not-allowed bg-slate-50 text-slate-500;
        }

        .text-muted {
            @apply text-slate-500;
        }

        .modal-content {
            @apply overflow-hidden rounded-xl border border-slate-200 shadow-2xl;
        }

        .modal-header {
            @apply border-b border-slate-200 bg-white px-5 py-4 text-slate-950;
            background-image: none;
        }

        .modal-header .btn-close {
            filter: none;
        }

        .modal-body {
            @apply p-5;
        }

        .modal-footer {
            @apply border-t border-slate-200 bg-slate-50 px-5 py-4;
        }

        .alert {
            @apply rounded-lg border px-4 py-3 text-sm;
        }

        .alert-info { @apply border-blue-200 bg-blue-50 text-blue-900; }
        .alert-warning { @apply border-amber-200 bg-amber-50 text-amber-900; }

        .list-group-item {
            @apply border-b border-slate-100 py-3 text-sm text-slate-700;
        }

        .loading-spinner {
            @apply py-6 text-center text-slate-500;
        }

        .spinner-border {
            @apply inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-slate-700;
            border-right-color: transparent;
        }

        .position-fixed.top-0.end-0 {
            @apply z-50;
        }

        #notificationContainer .alert {
            @apply mb-2 border-slate-200 bg-white text-slate-800 shadow-lg;
        }

        @media (max-width: 1024px) {
            .main-content { padding: 24px; }
            .metrics-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }

        @media (max-width: 768px) {
            .sidebar { width: 68px; padding: 12px 6px; }
            .sidebar-logo { justify-content: center; padding: 0 0 16px; }
            .sidebar-logo h4 { font-size: 0; }
            .sidebar-logo .bi { font-size: 14px; }
            .nav-item { padding: 0; }
            .nav-link { justify-content: center; padding: 11px 8px; }
            .nav-link span { display: none; }
            .nav-link .bi { font-size: 18px; }
            .main-content { margin-left: 68px; padding: 20px 14px; }
            .top-bar { align-items: flex-start; }
            .top-bar h1 { font-size: 20px; }
            .metrics-row { grid-template-columns: 1fr 1fr; gap: 10px; }
            .metric-card { padding: 15px; }
            .metric-value { font-size: 21px; }
            .interactions-container { padding: 15px; }
            .interactions-header { align-items: stretch; }
            .filter-controls { width: 100%; }
            .search-input { min-width: 0; width: 100%; }
        }

        @media (max-width: 480px) {
            .metrics-row { grid-template-columns: 1fr; }
            .user-menu { gap: 8px; }
        }
`;
document.head.appendChild(theme);
