/** @odoo-module **/

import { Component, onWillStart, useState, onMounted, useRef } from "@odoo/owl";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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

        onWillStart(() => this.loadData());
        onMounted(() => this.renderChart());
    }

    async loadData() {
        try {
            const teachers = await this.orm.searchRead(
                "university.teacher",
                [["user_id", "=", user.userId]],
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
        
        new window.Chart(this.chartRef.el, {
            type: "doughnut",
            data: {
                labels: ["Present", "Absent"],
                datasets: [{
                    data: [this.state.presentCount, this.state.absentCount],
                    backgroundColor: ["#4e73df", "#e74a3b"],
                    hoverBackgroundColor: ["#2e59d9", "#e74a3b"],
                    hoverBorderColor: "rgba(234, 236, 244, 1)",
                }]
            },
            options: {
                maintainAspectRatio: false,
                cutoutPercentage: 80,
            }
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
        });
    }
}

registry.category("actions").add("teacher_dashboard_shell", TeacherDashboardShell);

export default TeacherDashboardShell;
