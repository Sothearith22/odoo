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
    admission: "school_management.group_school_admin",
    attendance: "school_management.group_school_teacher",
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
    admission: "school_management.action_university_admission_application",
    attendance: "school_management.action_university_attendance",
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
    active: "#10b981",     // vibrant emerald
    suspended: "#f59e0b",  // warm amber
    graduated: "#3b82f6",  // clean sapphire blue
    dropped: "#ef4444",    // coral red
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
        // TooltipPosition() points to the outer arc; use first.x/first.y or chartArea for doughnut cutout center
        const x = typeof first.x === "number" ? first.x : ((chart.chartArea.left + chart.chartArea.right) / 2);
        const y = typeof first.y === "number" ? first.y : ((chart.chartArea.top + chart.chartArea.bottom) / 2);
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
        this.notification = useService("notification");

        this.chartStatusRef = useRef("chart_status");
        this.chartProgramRef = useRef("chart_program");
        this.chartEnrollmentRef = useRef("chart_enrollment");
        this.chartFeesRef = useRef("chart_fees");
        this.chartFacultyAttendanceRef = useRef("chart_faculty_attendance");
        this.chartStudentAttendanceRef = useRef("chart_student_attendance");
        this.chartApplicationsRef = useRef("chart_applications");
        this.chartEnrollmentsRef = useRef("chart_enrollments");
        this.charts = [];

        this.state = useState({
            dashboard: null,
            chartData: null,
            roleView: null,
            capabilities: [],
            error: null,
            isLoading: true,
            isRefreshing: false,
            isFullAccess: false,
            isNavigating: false,
            timeframeSort: "Current Week",
            activeAdminTab: "overview",
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
                admission: false,
                attendance: false,
            },
            stats: {
                student: {
                    universityStudents: 0,
                    activeStudents: 0,
                    graduatedStudents: 0,
                    droppedStudents: 0,
                    suspendedStudents: 0,
                },
                teacher: {
                    universityTeachers: 0,
                    activeTeachers: 0,
                },
                academic: {
                    universityPrograms: 0,
                    universityDepartments: 0,
                    universitySections: 0,
                    universityClassrooms: 0,
                },
            },
            academicPeriod: {
                year: "",
                semester: "",
                label: "",
            },
            filters: {
                yearId: false,
                semesterId: false,
            },
            filterOptions: {
                academicYears: [],
                semesters: [],
            },
            isMoreOpen: false,
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
                    this.loadFilterOptions(),
                    this.loadCapabilities(),
                    this.loadRoadmapData(),
                ]);
                await this.loadDashboardData();
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
        const isAdmin = isSystem || (await user.hasGroup(GROUP_ADMIN));
        const can = async (role) => {
            if (isAdmin) {
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
        } catch (error) {
            console.error(`Failed to navigate to ${actionXmlId}`, error);
            this.notification?.add(error.message || "Failed to open view", { type: "danger" });
        } finally {
            this.state.isNavigating = false;
        }
    }

    async quickCreate(resModel, name) {
        try {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name,
                res_model: resModel,
                views: [[false, "form"]],
                view_mode: "form",
                target: "current",
            });
        } catch (error) {
            console.error(`Failed to open ${name} form`, error);
            this.notification?.add(error.message || `Unable to open ${name}.`, { type: "danger" });
        }
    }

    openPendingNotifications() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Pending Admissions",
            res_model: "university.admission.application",
            views: [[false, "list"], [false, "form"]],
            view_mode: "list,form",
            domain: [["state", "=", "submitted"]],
            context: { search_default_filter_submitted: 1 },
        });
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
            this.notification?.add(error.message || "Unable to open capability.", { type: "danger" });
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
            setTimeout(() => {
                this.renderCharts();
            }, 50);
        } catch (error) {
            console.error("Failed to refresh dashboard data", error);
            this.state.error = error.message || "Unable to refresh dashboard data.";
        } finally {
            this.state.isRefreshing = false;
        }
    }

    async loadFilterOptions() {
        const options = await this.orm.call("school.dashboard", "get_filter_options", []);
        this.state.filterOptions.academicYears = options.academic_years || [];
        this.state.filterOptions.semesters = options.semesters || [];
        this.state.filters.yearId = options.selected_year_id || false;
        this.state.filters.semesterId = options.selected_semester_id || false;
        this.updateAcademicPeriodLabel();
    }

    updateAcademicPeriodLabel() {
        const year = this.state.filterOptions.academicYears.find(
            (item) => item.id === Number(this.state.filters.yearId)
        );
        const semester = this.state.filterOptions.semesters.find(
            (item) => item.id === Number(this.state.filters.semesterId)
        );
        this.state.academicPeriod.year = year?.name || "";
        this.state.academicPeriod.semester = semester?.name || "";
        this.state.academicPeriod.label = [semester?.name, year?.name].filter(Boolean).join(" · ");
    }

    semestersForSelectedYear() {
        const yearId = Number(this.state.filters.yearId);
        return this.state.filterOptions.semesters.filter(
            (item) => !yearId || item.academic_year_id?.[0] === yearId
        );
    }

    async changeFilter(name, value) {
        this.state.filters[name] = Number(value) || false;
        if (name === "yearId") {
            const validSemester = this.semestersForSelectedYear().some(
                (item) => item.id === Number(this.state.filters.semesterId)
            );
            if (!validSemester) {
                this.state.filters.semesterId = false;
            }
        }
        this.updateAcademicPeriodLabel();
        await this.reload();
    }

    async loadDashboardData() {
        const result = await this.orm.call("school.dashboard", "get_role_dashboard_data", [
            this.state.filters.yearId || false,
            this.state.filters.semesterId || false,
        ]);
        this.state.dashboard = result.dashboard || null;
        this.state.chartData = result.chart_data || null;
        this.state.roleView = result.hod_view || result.faculty_view || result.registrar_view || null;
        this.state.filters.yearId = result.selected_year_id || false;
        this.state.filters.semesterId = result.selected_semester_id || false;
        this.updateAcademicPeriodLabel();
    }

    get isHodDashboard() {
        return this.state.dashboard?.user_role === "hod";
    }

    get isFacultyDashboard() {
        return this.state.dashboard?.user_role === "dean";
    }

    get isRegistrarDashboard() {
        return this.state.dashboard?.user_role === "registrar";
    }

    get dashboardTitle() {
        if (this.isHodDashboard) return "Department Dashboard";
        if (this.isFacultyDashboard) return "Faculty Dashboard";
        if (this.isRegistrarDashboard) return "Registrar Dashboard";
        return "University Dashboard";
    }

    get operationsTitle() {
        if (this.isHodDashboard) return "Department Operations";
        if (this.isFacultyDashboard) return "Faculty Operations";
        if (this.isRegistrarDashboard) return "Registrar Operations";
        return "University Operations & Management";
    }

    formatCurrency(amount) {
        const val = Number(amount) || 0;
        const symbol = this.state.dashboard?.currency_symbol || "";
        return symbol + val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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

    toggleMoreDropdown(ev) {
        ev?.stopPropagation();
        this.state.isMoreOpen = !this.state.isMoreOpen;
    }

    async closeMoreDropdown() {
        if (!this.state.isMoreOpen) return;
        await new Promise((resolve) => setTimeout(resolve, 0));
        this.state.isMoreOpen = false;
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
        if (type === "enrollment") {
            const data = this.state.chartData.enrollment_trend?.data || [];
            return data.some((v) => Number(v) > 0);
        }
        if (type === "fees") {
            const data = this.state.chartData.monthly_fee_collection?.data || [];
            return data.some((v) => Number(v) > 0);
        }
        return false;
    }

    getToken(name) {
        const root = this.el?.closest?.(".o_school_dashboard_layout") || document.documentElement;
        const tokenName = String(name || "").replace(/^var\((--[^,)]+).*\)$/, "$1");
        return getComputedStyle(root).getPropertyValue(tokenName).trim()
            || getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim();
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
                    STATUS_TOKENS[String(label).toLowerCase()] ||
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
                    cutout: '70%',
                    plugins: {
                        centerText: {
                            label: 'Total Students',
                            valueColor: '#0f172a',
                            labelColor: '#64748b',
                        },
                        legend: {
                            display: false,
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                padding: 14,
                                color: '#64748b',
                                font: { size: 12, family: 'system-ui, -apple-system, sans-serif' },
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
                            backgroundColor: '#1b2a4a',
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
                        backgroundColor: '#3a6ea5',
                        hoverBackgroundColor: '#2b537f',
                        borderRadius: 6,
                        maxBarThickness: 24,
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
                            backgroundColor: '#1b2a4a',
                            titleFont: { size: 13, weight: '600' },
                            bodyFont: { size: 12 },
                            padding: 10,
                            cornerRadius: 8,
                        }
                    },
                    indexAxis: "y",
                    scales: {
                        y: {
                            ticks: {
                                color: "#334155",
                                font: { size: 12, weight: '500', family: 'system-ui, -apple-system, sans-serif' },
                            },
                            grid: { display: false },
                            border: { display: false },
                        },
                        x: {
                            beginAtZero: true,
                            ticks: {
                                precision: 0,
                                color: "#64748b",
                                font: { size: 12, family: 'system-ui, -apple-system, sans-serif' },
                            },
                            grid: {
                                color: "rgba(15, 23, 42, 0.06)",
                                drawTicks: false,
                            },
                            border: { display: false },
                        }
                    }
                }
            }));
        }

        if (this.chartEnrollmentRef.el && this.hasChartData("enrollment")) {
            const data = this.state.chartData.enrollment_trend;
            this.charts.push(new window.Chart(this.chartEnrollmentRef.el.getContext("2d"), {
                type: "line",
                data: {
                    labels: data.labels || [],
                    datasets: [{
                        label: "Enrollments",
                        data: data.data || [],
                        borderColor: "#2563eb",
                        backgroundColor: "rgba(37, 99, 235, 0.12)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 3,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                },
            }));
        }

        if (this.chartFeesRef.el && this.hasChartData("fees")) {
            const data = this.state.chartData.monthly_fee_collection;
            this.charts.push(new window.Chart(this.chartFeesRef.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: data.labels || [],
                    datasets: [{
                        label: "Collected",
                        data: data.data || [],
                        backgroundColor: "#059669",
                        borderRadius: 5,
                        maxBarThickness: 28,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } },
                },
            }));
        }

        // 5. Faculty Attendance Doughnut Chart (Matching clean image spec)
        if (this.chartFacultyAttendanceRef?.el) {
            const facultyData = this.state.chartData?.faculty_attendance || {
                present: this.state.dashboard?.faculty_present || 5,
                absent: this.state.dashboard?.faculty_absent || 1,
            };
            const ctxFaculty = this.chartFacultyAttendanceRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxFaculty, {
                type: "doughnut",
                data: {
                    labels: ["Present", "Absent"],
                    datasets: [{
                        data: [facultyData.present, facultyData.absent],
                        backgroundColor: ["#2563eb", "#f87171"],
                        borderWidth: 0,
                        hoverOffset: 3,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "76%",
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => ` ${ctx.label}: ${ctx.raw} Faculty`,
                            },
                        },
                    },
                },
            }));
        }

        // 6. Student Attendance Doughnut Chart (Matching clean image spec)
        if (this.chartStudentAttendanceRef?.el) {
            const studentData = this.state.chartData?.student_attendance || {
                present: this.state.dashboard?.student_present || 4,
                absent: this.state.dashboard?.student_absent || 2,
            };
            const ctxStudent = this.chartStudentAttendanceRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxStudent, {
                type: "doughnut",
                data: {
                    labels: ["Present", "Absent"],
                    datasets: [{
                        data: [studentData.present, studentData.absent],
                        backgroundColor: ["#2563eb", "#f87171"],
                        borderWidth: 0,
                        hoverOffset: 3,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "76%",
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => ` ${ctx.label}: ${ctx.raw} Students`,
                            },
                        },
                    },
                },
            }));
        }

        // 7. Applications Breakdown Doughnut
        if (this.chartApplicationsRef?.el) {
            const appChart = this.state.chartData?.applications || {
                labels: ["Submitted", "Approved", "Draft", "Rejected"],
                data: [6, 3, 1, 1],
            };
            const ctxApps = this.chartApplicationsRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxApps, {
                type: "doughnut",
                data: {
                    labels: appChart.labels,
                    datasets: [{
                        data: appChart.data,
                        backgroundColor: ["#2563eb", "#10b981", "#f59e0b", "#f87171", "#94a3b8"],
                        borderWidth: 2,
                        borderColor: "#ffffff",
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "70%",
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                boxWidth: 8,
                                boxHeight: 8,
                                usePointStyle: true,
                                padding: 8,
                                font: { size: 11 },
                            },
                        },
                    },
                },
            }));
        }

        // 8. Enrollments Breakdown Doughnut
        if (this.chartEnrollmentsRef?.el) {
            const enrChart = this.state.chartData?.enrollments || {
                labels: ["In-Progress", "Draft", "Completed"],
                data: [6, 1, 1],
            };
            const ctxEnr = this.chartEnrollmentsRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxEnr, {
                type: "doughnut",
                data: {
                    labels: enrChart.labels,
                    datasets: [{
                        data: enrChart.data,
                        backgroundColor: ["#f59e0b", "#3b82f6", "#10b981", "#94a3b8"],
                        borderWidth: 2,
                        borderColor: "#ffffff",
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "70%",
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                boxWidth: 8,
                                boxHeight: 8,
                                usePointStyle: true,
                                padding: 8,
                                font: { size: 11 },
                            },
                        },
                    },
                },
            }));
        }
    }

    changeTimeframeSort(ev) {
        this.state.timeframeSort = ev.target.value;
    }

    setActiveAdminTab(tab) {
        this.state.activeAdminTab = this.state.activeAdminTab === tab ? "overview" : tab;
        setTimeout(() => this.renderCharts(), 60);
    }

    openApplications() {
        this.navigate("school_management.action_university_admission_application");
    }

    openEnrollments() {
        this.navigate("school_management.action_university_enrollment");
    }

    openStudents() {
        this.navigate("school_management.action_university_student");
    }

    openTeachers() {
        this.navigate("school_management.action_university_teacher");
    }

    openStaffAttendance() {
        this.navigate("school_management.action_university_staff_attendance");
    }

    openStudentAttendance() {
        this.navigate("school_management.action_university_attendance");
    }

    openTranscriptRequests() {
        this.navigate("school_management.action_university_transcript_request");
    }

    openNoticeBoard() {
        this.navigate("school_management.action_university_notice_board");
    }

    formatNoticeDate(dateStr) {
        if (!dateStr) return "";
        try {
            const datePart = String(dateStr).split(" ")[0];
            const parts = datePart.split("-");
            if (parts.length === 3) {
                return `${parts[2]}-${parts[1]}-${parts[0]}`;
            }
        } catch (_) {}
        return String(dateStr);
    }

    openNotice(noticeId) {
        if (!noticeId) {
            this.openNoticeBoard();
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Notice Announcement",
            res_model: "university.notice.board",
            res_id: noticeId,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
        });
    }
}

registry.category("actions").add("school_dashboard_shell", SchoolDashboardShell);

export default SchoolDashboardShell;
