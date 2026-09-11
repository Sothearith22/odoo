/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const GROUP_SYSTEM = "base.group_system";
const GROUP_ADMIN = "school_management.group_school_admin";
const GROUP_HOD = "school_management.group_school_hod";

// Key -> minimal role required to open the target action.
const ACTION_ROLE = {
    student: "school_management.group_school_teacher",
    teacher: "school_management.group_school_teacher",
    program: "school_management.group_school_dean",
    department: "school_management.group_school_hod",
    faculty: "school_management.group_school_admin",
    section: "school_management.group_school_teacher",
    subject: "school_management.group_school_teacher",
    classroom: "school_management.group_school_admin",
    enrollment: "school_management.group_school_hod",
    academic_year: "school_management.group_school_admin",
    fee: "school_management.group_school_admin",
    payment: "school_management.group_school_admin",
};

// Key -> action_id (XMLID) to open for the dashboard quick links.
const ACTION_XMLID = {
    student: "school_management.action_university_student",
    teacher: "school_management.action_university_teacher",
    program: "school_management.action_university_program",
    department: "school_management.action_university_department",
    faculty: "school_management.action_university_faculty",
    section: "school_management.action_university_class_section",
    subject: "school_management.action_university_subject",
    classroom: "school_management.action_university_classroom",
    enrollment: "school_management.action_university_enrollment",
    academic_year: "school_management.action_university_academic_year",
    fee: "school_management.action_university_fee",
    payment: "school_management.action_university_payment",
};

// Catalog metadata for the System Capabilities & Roadmap panel.
const CAPABILITY_CATEGORIES = {
    structure: { label: "Academic Structure", icon: "fa-university" },
    students: { label: "Students", icon: "fa-graduation-cap" },
    staff: { label: "Academic Staff", icon: "fa-user" },
    academic: { label: "Academic Operations", icon: "fa-calendar-check-o" },
    finance: { label: "Finance", icon: "fa-money" },
    system: { label: "System", icon: "fa-cube" },
};
const CAPABILITY_ORDER = Object.keys(CAPABILITY_CATEGORIES);

const CAPABILITY_STATUS = {
    active: { label: "Active", badge: "bg-success-subtle text-success border border-success-subtle" },
    beta: { label: "Beta", badge: "bg-info-subtle text-info border border-info-subtle" },
    development: { label: "In Development", badge: "bg-warning-subtle text-warning border border-warning-subtle" },
    planned: { label: "Planned", badge: "bg-light text-muted border" },
};
const LIVE_STATUSES = new Set(["active", "beta"]);

// Semantic status color tokens, mirrored from design_tokens.scss. Chart.js
// draws on canvas so CSS variables are resolved to concrete values at render.
const STATUS_TOKENS = {
    active: "var(--status-success)",
    suspended: "var(--status-warning)",
    graduated: "var(--status-info)",
    dropped: "var(--status-danger)",
};

// Small inline plugin drawing the total count in the centre of a doughnut.
const doughnutCenterText = {
    id: "doughnutCenterText",
    afterDraw(chart) {
        const opts = chart.options?.plugins?.centerText;
        if (!opts || !chart.data?.datasets?.length) return;
        const first = chart.getDatasetMeta(0)?.data?.[0];
        if (!first) return;
        const values = chart.data.datasets[0].data || [];
        const total = values.reduce((sum, v) => sum + (Number(v) || 0), 0);
        const { x, y } = first.tooltipPosition();
        const { ctx } = chart;
        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = opts.valueColor || "#0f172a";
        ctx.font = `700 ${opts.valueSize || 24}px system-ui, -apple-system, sans-serif`;
        ctx.fillText(String(total), x, y - (opts.label ? 9 : 0));
        if (opts.label) {
            ctx.fillStyle = opts.labelColor || "#64748b";
            ctx.font = "500 12px system-ui, -apple-system, sans-serif";
            ctx.fillText(opts.label, x, y + 15);
        }
        ctx.restore();
    },
};

class SchoolDashboardShell extends Component {
    static template = "school_management.DashboardShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.chartStatusRef = useRef("chart_status");
        this.chartProgramRef = useRef("chart_program");
        this.charts = [];

        this.state = useState({
            dashboard: null,
            chartData: null,
            capabilities: [],
            error: null,
            isLoading: true,
            isRefreshing: false,
            isFullAccess: false,
            isNavigating: false,
            lastUpdated: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            canOpen: {
                student: false,
                teacher: false,
                program: false,
                department: false,
                faculty: false,
                section: false,
                subject: false,
                classroom: false,
                enrollment: false,
                academic_year: false,
                fee: false,
                payment: false,
            },
        });

        onWillStart(async () => {
            try {
                const isSystem = await user.hasGroup(GROUP_SYSTEM);
                const isAdmin = isSystem || (await user.hasGroup(GROUP_ADMIN));
                const isDean = await user.hasGroup("school_management.group_school_dean");
                const isHod = await user.hasGroup(GROUP_HOD);
                const isTeacher = await user.hasGroup("school_management.group_school_teacher");
                const isStudent = await user.hasGroup("school_management.group_school_student");

                if (isStudent && !isTeacher && !isAdmin && !isDean && !isHod) {
                    await this.action.doAction("school_management.action_student_dashboard_shell", { clearBreadcrumbs: true });
                    return;
                }
                if (isTeacher && !isAdmin && !isDean && !isHod) {
                    await this.action.doAction("school_management.action_teacher_dashboard_shell", { clearBreadcrumbs: true });
                    return;
                }

                this.state.isFullAccess = isAdmin;
                await Promise.all([
                    loadBundle("web.chartjs_lib"),
                    this.loadDashboardData(),
                    this.loadCapabilities(),
                    this.loadRoadmapData(),
                ]);
            } catch (error) {
                console.error("Failed to load school dashboard", error);
                this.state.error = error.message || "Unable to load dashboard data.";
            } finally {
                this.state.isLoading = false;
            }
        });

        onMounted(() => {
            this.renderCharts();
        });

        onWillUnmount(() => {
            this.destroyCharts();
        });
    }

    destroyCharts() {
        this.charts.forEach((chart) => {
            try {
                chart.destroy();
            } catch (err) {
                console.warn("Chart destroy warning", err);
            }
        });
        this.charts = [];
    }

    async loadCapabilities() {
        const isSystem = await user.hasGroup(GROUP_SYSTEM);
        const can = async (role) => {
            if (isSystem) {
                return true;
            }
            return await user.hasGroup(role);
        };
        for (const key of Object.keys(ACTION_ROLE)) {
            this.state.canOpen[key] = await can(ACTION_ROLE[key]);
        }
    }

    canOpen(key) {
        return Boolean(this.state.canOpen[key]);
    }

    async loadRoadmapData() {
        try {
            this.state.capabilities = await this.orm.searchRead(
                "university.capability",
                [],
                [
                    "name", "category", "status", "phase", "release_version",
                    "description", "icon", "released_on", "sort_order",
                ],
                { order: "sort_order, id" }
            );
        } catch (error) {
            console.error("Failed to load system capabilities", error);
            this.state.capabilities = [];
        }
    }

    capabilityStatusLabel(status) {
        return CAPABILITY_STATUS[status]?.label || status || "—";
    }

    capabilityBadge(status) {
        return CAPABILITY_STATUS[status]?.badge || "bg-light text-muted border";
    }

    capabilityIconTone(status) {
        const tones = {
            active: "text-success",
            beta: "text-info",
            development: "text-warning",
            planned: "text-muted",
        };
        return tones[status] || "text-muted";
    }

    isLive(status) {
        return LIVE_STATUSES.has(status);
    }

    capabilityCategoryMeta(key) {
        return CAPABILITY_CATEGORIES[key] || CAPABILITY_CATEGORIES.system;
    }

    get _liveCapabilities() {
        return (this.state.capabilities || []).filter((cap) => LIVE_STATUSES.has(cap.status));
    }

    capabilityOverall() {
        const total = this.state.capabilities.length;
        const live = this._liveCapabilities.length;
        return {
            total,
            live,
            pct: total ? Math.round((live / total) * 100) : 0,
        };
    }

    capabilityCategories() {
        const byCategory = this.state.capabilities.reduce((acc, cap) => {
            (acc[cap.category] = acc[cap.category] || []).push(cap);
            return acc;
        }, {});
        return CAPABILITY_ORDER.filter((key) => byCategory[key]).map((key) => {
            const items = byCategory[key];
            const live = items.filter((cap) => LIVE_STATUSES.has(cap.status)).length;
            return {
                key,
                label: this.capabilityCategoryMeta(key).label,
                icon: this.capabilityCategoryMeta(key).icon,
                items,
                total: items.length,
                live,
                pct: items.length ? Math.round((live / items.length) * 100) : 0,
            };
        });
    }

    roadmapPhases() {
        const byPhase = {};
        for (const cap of this.state.capabilities) {
            const phase = cap.phase || 1;
            byPhase[phase] = byPhase[phase] || { phase, count: 0, live: 0 };
            byPhase[phase].count += 1;
            if (LIVE_STATUSES.has(cap.status)) {
                byPhase[phase].live += 1;
            }
        }
        return Object.values(byPhase).sort((a, b) => a.phase - b.phase);
    }

    async go(key) {
        if (!this.canOpen(key)) {
            return;
        }
        await this.navigate(ACTION_XMLID[key]);
    }

    async navigate(actionXmlId) {
        if (this.state.isNavigating || !actionXmlId) {
            return;
        }
        this.state.isNavigating = true;
        try {
            await this.action.doAction(actionXmlId);
        } finally {
            this.state.isNavigating = false;
        }
    }

    async openCapability(cap) {
        if (!this.state.isFullAccess || !cap?.id) {
            return;
        }
        try {
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "university.capability",
                res_id: cap.id,
                view_mode: "form",
                views: [[false, "form"]],
                name: cap.name || "Capability",
            });
        } catch (error) {
            console.error("Failed to open capability", error);
        }
    }

    openCapabilityKeyboard(ev, cap) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openCapability(cap);
        }
    }

    async reload() {
        if (this.state.isRefreshing) return;
        this.state.isRefreshing = true;
        this.state.error = null;
        try {
            await this.loadDashboardData();
            await this.loadRoadmapData();
            this.state.lastUpdated = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            this.renderCharts();
        } catch (error) {
            console.error("Failed to refresh dashboard data", error);
            this.state.error = error.message || "Unable to refresh dashboard data.";
        } finally {
            this.state.isRefreshing = false;
        }
    }

    async loadDashboardData() {
        const records = await this.orm.searchRead(
            "school.dashboard",
            [],
            [
                "student_count", "teacher_count", "program_count", "department_count",
                "faculty_count", "subject_count", "section_count", "classroom_count",
                "active_student_count", "graduated_student_count",
                "suspended_student_count", "dropped_student_count",
                "fee_count", "total_paid_fees", "total_unpaid_fees", "total_scholarships",
            ],
            { limit: 1 }
        );
        const chartData = await this.orm.call("school.dashboard", "get_chart_data", []);
        
        this.state.dashboard = records[0] || null;
        this.state.chartData = chartData || null;
    }

    formatCurrency(amount) {
        const val = Number(amount) || 0;
        return "$" + val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    getStudentInitials(name) {
        if (!name || typeof name !== "string") return "?";
        const parts = name.trim().split(/\s+/);
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }

    getFeeCollectionRate() {
        const paid = Number(this.state.dashboard?.total_paid_fees) || 0;
        const unpaid = Number(this.state.dashboard?.total_unpaid_fees) || 0;
        const total = paid + unpaid;
        if (total <= 0) return 100;
        return Math.round((paid / total) * 100);
    }

    hasChartData(type) {
        if (!this.state.chartData) return false;
        if (type === "status") {
            const data = this.state.chartData.student_status?.data || [];
            return data.some((v) => Number(v) > 0);
        }
        if (type === "program") {
            const data = this.state.chartData.program_distribution?.data || [];
            return data.some((v) => Number(v) > 0);
        }
        return false;
    }

    getToken(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    renderCharts() {
        this.destroyCharts();
        if (!this.state.chartData || !window.Chart) return;

        // 1. Student Status Doughnut Chart
        if (this.chartStatusRef.el && this.hasChartData("status")) {
            const labels = this.state.chartData.student_status?.labels || [];
            const values = this.state.chartData.student_status?.data || [];
            const colors = labels.map(
                (label) =>
                    this.getToken(STATUS_TOKENS[String(label).toLowerCase()]) ||
                    this.getToken("--brand-sapphire") ||
                    "#3a6ea5"
            );
            const total = values.reduce((sum, v) => sum + (Number(v) || 0), 0) || 1;
            const ctxStatus = this.chartStatusRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxStatus, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors,
                        borderWidth: 2,
                        borderColor: '#ffffff',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '72%',
                    plugins: {
                        centerText: { label: 'Students' },
                        legend: {
                            position: 'bottom',
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                padding: 12,
                                font: { size: 11, family: 'system-ui, -apple-system, sans-serif' },
                                generateLabels: (chart) =>
                                    (chart.data.labels || []).map((label, index) => ({
                                        text: `${label} · ${values[index]} (${Math.round((Number(values[index]) / total) * 100)}%)`,
                                        fillStyle: chart.data.datasets[0].backgroundColor[index],
                                        strokeStyle: chart.data.datasets[0].backgroundColor[index],
                                        lineWidth: 0,
                                        hidden: false,
                                        index,
                                    })),
                            }
                        },
                        tooltip: {
                            backgroundColor: this.getToken("--brand-primary") || '#1b2a4a',
                            titleFont: { size: 13, weight: '600' },
                            bodyFont: { size: 12 },
                            padding: 10,
                            cornerRadius: 8,
                            callbacks: {
                                label: (ctx) => {
                                    const value = Number(ctx.parsed) || 0;
                                    return ` ${ctx.label}: ${value} (${Math.round((value / total) * 100)}%)`;
                                },
                            },
                        }
                    },
                },
                plugins: [doughnutCenterText]
            }));
        }

        // 2. Program Distribution Bar Chart
        if (this.chartProgramRef.el && this.hasChartData("program")) {
            const ctxProgram = this.chartProgramRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxProgram, {
                type: 'bar',
                data: {
                    labels: this.state.chartData.program_distribution?.labels || [],
                    datasets: [{
                        label: 'Enrolled Students',
                        data: this.state.chartData.program_distribution?.data || [],
                        backgroundColor: this.getToken("--brand-sapphire") || '#3a6ea5',
                        hoverBackgroundColor: this.getToken("--brand-sapphire-hover") || '#2b537f',
                        borderRadius: 4,
                        maxBarThickness: 28,
                        barPercentage: 0.72,
                        categoryPercentage: 0.62,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: this.getToken("--brand-primary") || '#1b2a4a',
                            titleFont: { size: 13, weight: '600' },
                            bodyFont: { size: 12 },
                            padding: 10,
                            cornerRadius: 8,
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                precision: 0,
                                font: { size: 11, family: 'system-ui, -apple-system, sans-serif' },
                            },
                            grid: { color: 'rgba(15, 23, 42, 0.05)', drawTicks: false },
                            border: { display: false },
                        },
                        x: {
                            ticks: {
                                font: { size: 11, family: 'system-ui, -apple-system, sans-serif' },
                                maxRotation: 0,
                                autoSkip: false,
                                callback: function (val) {
                                    const label = this.getLabelForValue(val);
                                    const text = String(label || "");
                                    return text.length > 12 ? `${text.slice(0, 11)}…` : text;
                                },
                            },
                            grid: { display: false },
                        }
                    }
                }
            }));
        }
    }
}

registry.category("actions").add("school_dashboard_shell", SchoolDashboardShell);

export default SchoolDashboardShell;
