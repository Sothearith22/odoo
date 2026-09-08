/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const GROUP_SYSTEM = "base.group_system";
const GROUP_ADMIN = "school_management.group_school_admin";
const GROUP_HOD = "school_management.group_school_hod";

// Key -> minimal role required to open the target action.
const ACTION_ROLE = {
    student: "school_management.group_school_teacher",
    teacher: "school_management.group_school_teacher",
    program: "school_management.group_school_dean",
    department: "school_management.group_school_hod",
    section: "school_management.group_school_teacher",
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
    section: "school_management.action_university_class_section",
    enrollment: "school_management.action_university_enrollment",
    academic_year: "school_management.action_university_academic_year",
    fee: "school_management.action_university_fee",
    payment: "school_management.action_university_payment",
};

class SchoolDashboardShell extends Component {
    static template = "school_management.DashboardShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.user = useService("user");

        this.chartStatusRef = useRef("chart_status");
        this.chartProgramRef = useRef("chart_program");
        this.charts = [];

        this.state = useState({
            dashboard: null,
            chartData: null,
            error: null,
            isLoading: true,
            canOpen: {
                student: false,
                teacher: false,
                program: false,
                department: false,
                section: false,
                enrollment: false,
                academic_year: false,
                fee: false,
                payment: false,
            },
        });

        onWillStart(async () => {
            try {
                await Promise.all([
                    loadBundle("web.chartjs_lib"),
                    this.loadDashboardData(),
                    this.loadCapabilities(),
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
            this.charts.forEach(chart => chart.destroy());
        });
    }

    async loadCapabilities() {
        const isSystem = await this.user.hasGroup(GROUP_SYSTEM);
        const can = async (role) => {
            if (isSystem) {
                return true;
            }
            return await this.user.hasGroup(role);
        };
        for (const key of Object.keys(ACTION_ROLE)) {
            this.state.canOpen[key] = await can(ACTION_ROLE[key]);
        }
    }

    canOpen(key) {
        return Boolean(this.state.canOpen[key]);
    }

    go(key) {
        if (!this.canOpen(key)) {
            return;
        }
        this.navigate(ACTION_XMLID[key]);
    }

    navigate(actionXmlId) {
        this.action.doAction(actionXmlId, { clearBreadcrumbs: true });
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

    renderCharts() {
        if (!this.state.chartData || !window.Chart) return;

        // Render Student Status Chart
        if (this.chartStatusRef.el) {
            const ctxStatus = this.chartStatusRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxStatus, {
                type: 'doughnut',
                data: {
                    labels: this.state.chartData.student_status?.labels || [],
                    datasets: [{
                        data: this.state.chartData.student_status?.data || [],
                        backgroundColor: ['#1f7a5c', '#17a2b8', '#ffc107', '#dc3545'],
                        borderWidth: 2,
                        borderColor: '#ffffff',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' }
                    },
                    cutout: '70%'
                }
            }));
        }

        // Render Program Distribution Chart
        if (this.chartProgramRef.el) {
            const ctxProgram = this.chartProgramRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxProgram, {
                type: 'bar',
                data: {
                    labels: this.state.chartData.program_distribution?.labels || [],
                    datasets: [{
                        label: 'Students',
                        data: this.state.chartData.program_distribution?.data || [],
                        backgroundColor: '#3a6ea5',
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { display: false } },
                        x: { grid: { display: false } }
                    }
                }
            }));
        }
    }
}

registry.category("actions").add("school_dashboard_shell", SchoolDashboardShell);

export default SchoolDashboardShell;
