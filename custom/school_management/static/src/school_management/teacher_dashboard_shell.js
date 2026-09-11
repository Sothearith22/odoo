/** @odoo-module **/

import { Component, onWillStart, useState, onMounted, useRef } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Inline plugin drawing the attendance total in the doughnut centre.
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

class TeacherDashboardShell extends Component {
    static template = "school_management.TeacherDashboardShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartRef = useRef("attendanceChart");
        this.state = useState({
            loading: true,
            error: null,
            teacher: null,
            stats: {
                totalClasses: 0,
                assignedAssignments: 0,
                studentAssignments: 0,
                pendingServiceHours: 0,
            },
            noticeBoard: [],
            lessonPlans: [],
            schedule: [],
            presentCount: 0,
            absentCount: 0,
        });

        onWillStart(async () => {
            const isStudent = await user.hasGroup("school_management.group_school_student");
            const isTeacher = await user.hasGroup("school_management.group_school_teacher");
            if (isStudent && !isTeacher) {
                await this.action.doAction("school_management.action_student_dashboard_shell", { clearBreadcrumbs: true });
                return;
            }
            await loadBundle("web.chartjs_lib");
            await this.loadData();
        });
        onMounted(() => this.renderChart());
    }

    async loadData() {
        try {
            const teachers = await this.orm.searchRead(
                "university.teacher",
                ["|", ["user_id", "=", user.userId], ["id", "=", user.teacher_id ? user.teacher_id[0] : 0]],
                ["name", "email", "phone", "subject_ids", "section_ids"],
                { limit: 1 },
            );
            this.state.teacher = teachers[0] || null;

            if (this.state.teacher) {
                const teacherId = this.state.teacher.id;
                
                // Fetch stats
                const [totalClasses, assignedAssignments, studentAssignments, pendingServiceHours] = await Promise.all([
                    this.orm.searchCount("university.timetable.slot", [["teacher_id", "=", teacherId]]),
                    this.orm.searchCount("university.assignment", [["teacher_id", "=", teacherId], ["assignment_type", "=", "class"]]),
                    this.orm.searchCount("university.assignment", [["teacher_id", "=", teacherId], ["assignment_type", "=", "student"]]),
                    this.orm.searchCount("university.service.hour", [["teacher_id", "=", teacherId], ["state", "=", "pending"]]),
                ]);
                
                this.state.stats = {
                    totalClasses,
                    assignedAssignments,
                    studentAssignments,
                    pendingServiceHours,
                };

                // Fetch Lists
                this.state.noticeBoard = await this.orm.searchRead(
                    "university.notice.board",
                    [["active", "=", true]],
                    ["name", "date"],
                    { limit: 5, order: "date desc" }
                );

                this.state.lessonPlans = await this.orm.searchRead(
                    "university.lesson.plan",
                    [["teacher_id", "=", teacherId]],
                    ["name", "subject_id"],
                    { limit: 5, order: "create_date desc" }
                );

                this.state.schedule = await this.orm.searchRead(
                    "university.timetable.slot",
                    [["teacher_id", "=", teacherId]],
                    ["name", "section_id", "start_time", "location", "state"],
                    { limit: 5, order: "start_time asc" }
                );

                // Fetch Attendance
                const presentCount = await this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "present"]]);
                const absentCount = await this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "absent"]]);
                
                this.state.presentCount = presentCount;
                this.state.absentCount = absentCount;
            }
        } catch (error) {
            this.state.error = error.message || "Unable to load your teacher dashboard.";
        } finally {
            this.state.loading = false;
        }
    }

    renderChart() {
        if (!this.chartRef.el || !window.Chart) return;

        const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        const present = Number(this.state.presentCount) || 0;
        const absent = Number(this.state.absentCount) || 0;

        new window.Chart(this.chartRef.el, {
            type: "doughnut",
            data: {
                labels: ["Present", "Absent"],
                datasets: [{
                    data: [present, absent],
                    backgroundColor: [
                        token("--status-success") || "#1f7a5c",
                        token("--status-danger") || "#dc2626",
                    ],
                    borderWidth: 2,
                    borderColor: "#ffffff",
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "72%",
                plugins: {
                    centerText: { label: "Attendance" },
                    legend: {
                        position: "bottom",
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            usePointStyle: true,
                            pointStyle: "circle",
                            padding: 12,
                            font: { size: 11, family: "system-ui, -apple-system, sans-serif" },
                        }
                    },
                    tooltip: {
                        backgroundColor: token("--brand-primary") || "#1b2a4a",
                        titleFont: { size: 13, weight: "600" },
                        bodyFont: { size: 12 },
                        padding: 10,
                        cornerRadius: 8,
                    }
                }
            },
            plugins: [doughnutCenterText]
        });
    }

    navigate(actionXmlId, domain = []) {
        this.action.doAction(actionXmlId, {
            additionalContext: { search_default_teacher_id: this.state.teacher?.id },
            clearBreadcrumbs: true,
        });
    }

    openMyProfile() {
        if (!this.state.teacher) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "My Profile",
            res_model: "university.teacher",
            res_id: this.state.teacher.id,
            views: [[false, "form"]],
            view_mode: "form",
            context: { create: false, delete: false },
        });
    }
}

registry.category("actions").add("teacher_dashboard_shell", TeacherDashboardShell);

export default TeacherDashboardShell;
