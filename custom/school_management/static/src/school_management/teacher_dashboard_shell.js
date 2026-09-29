/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState, onMounted, useRef } from "@odoo/owl";
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
        ctx.font = `700 ${opts.valueSize || 22}px system-ui, -apple-system, sans-serif`;
        ctx.fillText(String(total), x, y - (opts.label ? 8 : 0));
        if (opts.label) {
            ctx.fillStyle = opts.labelColor || "#64748b";
            ctx.font = "500 11px system-ui, -apple-system, sans-serif";
            ctx.fillText(opts.label, x, y + 14);
        }
        ctx.restore();
    },
};

export class TeacherDashboardShell extends Component {
    static template = "school_management.TeacherDashboardShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartRef = useRef("attendanceChart");
        this.chartInstance = null;

        this.state = useState({
            loading: true,
            error: null,
            teacher: null,
            stats: {
                totalClasses: 0,
                totalAssignments: 0,
                pendingReviews: 0,
                pendingServiceHours: 0,
            },
            noticeBoard: [],
            lessonPlans: [],
            schedule: [],
            pendingSubmissions: [],
            presentCount: 0,
            absentCount: 0,
            lateCount: 0,
            totalAttendance: 0,
            hasAttendanceData: false,
            attendanceRate: 0,
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

        onWillUnmount(() => {
            if (this.chartInstance) {
                this.chartInstance.destroy();
                this.chartInstance = null;
            }
        });
    }

    async loadData() {
        try {
            const teachers = await this.orm.searchRead(
                "university.teacher",
                ["|", ["user_id", "=", user.userId], ["id", "=", user.teacher_id ? user.teacher_id[0] : 0]],
                ["name", "email", "phone", "subject_ids", "section_ids", "department_id"],
                { limit: 1 },
            );
            this.state.teacher = teachers[0] || null;

            if (this.state.teacher) {
                const teacherId = this.state.teacher.id;

                // 1. Fetch KPI counts
                const [totalClasses, totalAssignments, pendingSubmissionsCount, pendingServiceHours] = await Promise.all([
                    this.orm.searchCount("university.timetable.slot", [["teacher_id", "=", teacherId]]),
                    this.orm.searchCount("university.assignment", [["teacher_id", "=", teacherId]]),
                    this.orm.searchCount("university.assignment.submission", [
                        ["assignment_id.teacher_id", "=", teacherId],
                        ["state", "=", "submitted"],
                    ]),
                    this.orm.searchCount("university.service.hour", [
                        ["teacher_id", "=", teacherId],
                        ["state", "=", "pending"],
                    ]),
                ]);

                this.state.stats = {
                    totalClasses,
                    totalAssignments,
                    pendingReviews: pendingSubmissionsCount + pendingServiceHours,
                    pendingServiceHours,
                };

                // 2. Fetch All Slots for teacher (upcoming + recent), sorted by start_time
                this.state.schedule = await this.orm.searchRead(
                    "university.timetable.slot",
                    [["teacher_id", "=", teacherId]],
                    ["name", "section_id", "subject_id", "classroom_id", "start_time", "end_time", "location", "state"],
                    { limit: 8, order: "start_time desc" }
                );

                // 3. Fetch Pending Submissions for quick review
                this.state.pendingSubmissions = await this.orm.searchRead(
                    "university.assignment.submission",
                    [
                        ["assignment_id.teacher_id", "=", teacherId],
                        ["state", "=", "submitted"],
                    ],
                    ["name", "assignment_id", "student_id", "create_date", "state"],
                    { limit: 5, order: "create_date desc" }
                );

                // 4. Fetch Notice Board
                this.state.noticeBoard = await this.orm.searchRead(
                    "university.notice.board",
                    [["active", "=", true]],
                    ["name", "date"],
                    { limit: 5, order: "date desc" }
                );

                // 5. Fetch Lesson Plans
                this.state.lessonPlans = await this.orm.searchRead(
                    "university.lesson.plan",
                    [["teacher_id", "=", teacherId]],
                    ["name", "subject_id", "create_date"],
                    { limit: 5, order: "create_date desc" }
                );

                // 6. Fetch Attendance stats
                const [presentCount, absentCount, lateCount] = await Promise.all([
                    this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "present"]]),
                    this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "absent"]]),
                    this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "late"]]),
                ]);

                this.state.presentCount = presentCount;
                this.state.absentCount = absentCount;
                this.state.lateCount = lateCount;

                const total = presentCount + absentCount + lateCount;
                this.state.totalAttendance = total;
                this.state.hasAttendanceData = total > 0;
                this.state.attendanceRate = total > 0 ? Math.round((presentCount / total) * 100) : 0;
            }
        } catch (error) {
            this.state.error = error.message || "Unable to load your teacher dashboard.";
        } finally {
            this.state.loading = false;
        }
    }

    renderChart() {
        if (!this.chartRef.el || !window.Chart) return;
        if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
        }

        if (!this.state.hasAttendanceData) {
            return;
        }

        const present = Number(this.state.presentCount) || 0;
        const late = Number(this.state.lateCount) || 0;
        const absent = Number(this.state.absentCount) || 0;

        this.chartInstance = new window.Chart(this.chartRef.el, {
            type: "doughnut",
            data: {
                labels: ["Present", "Late", "Absent"],
                datasets: [{
                    data: [present, late, absent],
                    backgroundColor: [
                        "#10b981", // Emerald
                        "#f59e0b", // Amber
                        "#ef4444", // Crimson
                    ],
                    borderWidth: 2,
                    borderColor: "#ffffff",
                    hoverOffset: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "70%",
                plugins: {
                    centerText: {
                        label: "Total Logged",
                        valueColor: "#1e293b",
                        labelColor: "#64748b",
                    },
                    legend: {
                        position: "bottom",
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            usePointStyle: true,
                            pointStyle: "circle",
                            padding: 14,
                            font: { size: 12, weight: "500", family: "system-ui, -apple-system, sans-serif" },
                        }
                    },
                    tooltip: {
                        backgroundColor: "#1e293b",
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

    // Direct Actionable Attendance Trigger
    trackAttendanceForSlot(slot) {
        // Use today's date for attendance (slots may have historical dates)
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const sectionId = slot.section_id ? slot.section_id[0] : false;
        this.action.doAction("school_management.action_university_attendance_sheet", {
            additionalContext: {
                default_section_id: sectionId,
                section_id: sectionId,
                default_date: todayStr,
                date: todayStr,
            }
        });
    }

    openAttendanceSheet() {
        this.action.doAction("school_management.action_university_attendance_sheet");
    }

    openAttendanceRecords() {
        this.action.doAction("school_management.action_university_attendance");
    }

    openTimetable() {
        this.action.doAction("school_management.action_university_timetable_slot");
    }

    openAssignments() {
        this.action.doAction("school_management.action_university_grade_assignment");
    }

    openSubmissions() {
        this.action.doAction("school_management.action_university_assignment_submission");
    }

    openSubmission(submissionId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "university.assignment.submission",
            res_id: submissionId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openLessonPlans() {
        this.action.doAction("school_management.action_university_lesson_plan");
    }

    createLessonPlan() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "university.lesson.plan",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_teacher_id: this.state.teacher?.id,
            },
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

    formatTime(dateTimeStr) {
        if (!dateTimeStr) return "";
        try {
            const d = new Date(dateTimeStr.replace(" ", "T") + "Z");
            return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
        } catch {
            return dateTimeStr.split(" ")[1]?.substring(0, 5) || dateTimeStr;
        }
    }

    formatDate(dateStr) {
        if (!dateStr) return "";
        try {
            const d = new Date(dateStr.replace(" ", "T"));
            const now = new Date();
            const opts = { month: "short", day: "numeric" };
            if (d.getFullYear() !== now.getFullYear()) {
                opts.year = "numeric";
            }
            return d.toLocaleDateString([], opts);
        } catch {
            return dateStr;
        }
    }
}

registry.category("actions").add("teacher_dashboard_shell", TeacherDashboardShell);

export default TeacherDashboardShell;
