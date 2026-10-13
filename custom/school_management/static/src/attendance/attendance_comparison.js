/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

function localToday() {
    return new Date().getFullYear();
}

class AttendanceComparison extends Component {
    static template = "school_management.AttendanceComparison";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            year: localToday(),
            loading: true,
            error: null,
            data: null,
            viewMode: "kanban", // "kanban" or "table"
            departmentFilter: "all",
            statusFilter: "all", // "all", "good", "warn", "bad"
            expandedSections: {},
        });

        onWillStart(async () => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call(
                "university.attendance",
                "get_comparison_data",
                [this.state.year]
            );
            this.state.data = data;
        } catch (error) {
            this.state.error = error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    async onYearChange(event) {
        this.state.year = Number(event.target.value);
        await this.load();
    }

    onDepartmentFilterChange(event) {
        this.state.departmentFilter = event.target.value;
    }

    setStatusFilter(status) {
        this.state.statusFilter = status;
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
    }

    toggleSectionStudents(sectionId) {
        this.state.expandedSections[sectionId] = !this.state.expandedSections[sectionId];
    }

    openSectionSheet(sectionId) {
        this.action.doAction("school_management.action_university_attendance_sheet", {
            additionalContext: {
                default_section_id: sectionId,
                section_id: sectionId,
            },
        });
    }

    getRateStatus(rate) {
        if (rate >= 90) return "good";
        if (rate >= 75) return "warn";
        return "bad";
    }

    getRateStatusLabel(rate) {
        if (rate >= 90) return _t("Excellent");
        if (rate >= 75) return _t("Average");
        return _t("At Risk");
    }

    getRateBadgeClass(rate) {
        if (rate >= 90) return "badge bg-success-subtle text-success border border-success-subtle";
        if (rate >= 75) return "badge bg-warning-subtle text-warning border border-warning-subtle";
        return "badge bg-danger-subtle text-danger border border-danger-subtle";
    }

    getRateProgressBarClass(rate) {
        if (rate >= 90) return "bg-success";
        if (rate >= 75) return "bg-warning";
        return "bg-danger";
    }

    barStyle(rate) {
        return `width: ${Math.min(Math.max(Math.round(rate), 2), 100)}%;`;
    }

    barClass(rate) {
        if (rate < 75) return "o_att_bar--bad";
        if (rate < 90) return "o_att_bar--warn";
        return "o_att_bar--good";
    }

    get summary() {
        if (!this.state.data || !this.state.data.departments) {
            return { totalDepts: 0, totalSections: 0, totalRecords: 0, avgRate: 0 };
        }
        const totalDepts = this.state.data.departments.length;
        let totalSections = 0;
        let totalRecords = 0;
        let rateSum = 0;
        let rateCount = 0;
        for (const dept of this.state.data.departments) {
            totalSections += (dept.sections || []).length;
            totalRecords += (dept.total || 0);
            if (typeof dept.rate === "number") {
                rateSum += dept.rate;
                rateCount++;
            }
        }
        const avgRate = rateCount ? Math.round((rateSum / rateCount) * 10) / 10 : 0;
        return { totalDepts, totalSections, totalRecords, avgRate };
    }

    get filteredDepartments() {
        if (!this.state.data || !this.state.data.departments) {
            return [];
        }
        return this.state.data.departments
            .filter((dept) => {
                if (this.state.departmentFilter !== "all" && String(dept.id) !== String(this.state.departmentFilter)) {
                    return false;
                }
                return true;
            })
            .map((dept) => {
                let sections = dept.sections || [];
                if (this.state.statusFilter !== "all") {
                    sections = sections.filter((s) => {
                        const status = this.getRateStatus(s.rate);
                        return status === this.state.statusFilter;
                    });
                }
                return {
                    ...dept,
                    filteredSections: sections,
                };
            });
    }
}

registry.category("actions").add("university_attendance_comparison", AttendanceComparison);

export { AttendanceComparison };