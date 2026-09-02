/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class SchoolDashboardShell extends Component {
    static template = "school_management.DashboardShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.chartStatusRef = useRef("chart_status");
        this.chartProgramRef = useRef("chart_program");
        this.charts = [];

        this.state = { dashboard: null, chartData: null };

        onWillStart(async () => {
            await Promise.all([
                loadBundle("web.chartjs_lib"),
                this.loadDashboardData()
            ]);
        });

        onMounted(() => {
            this.renderCharts();
        });

        onWillUnmount(() => {
            this.charts.forEach(chart => chart.destroy());
        });
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
        if (!this.state.chartData) return;

        // Render Student Status Chart
        if (this.chartStatusRef.el) {
            const ctxStatus = this.chartStatusRef.el.getContext("2d");
            this.charts.push(new window.Chart(ctxStatus, {
                type: 'doughnut',
                data: {
                    labels: this.state.chartData.student_status.labels,
                    datasets: [{
                        data: this.state.chartData.student_status.data,
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
                    labels: this.state.chartData.program_distribution.labels,
                    datasets: [{
                        label: 'Students',
                        data: this.state.chartData.program_distribution.data,
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
