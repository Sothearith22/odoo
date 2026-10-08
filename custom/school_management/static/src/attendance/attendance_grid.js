/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

function pad(value) {
    return String(value).padStart(2, "0");
}

function localToday() {
    const today = new Date();
    return { year: today.getFullYear(), month: today.getMonth() + 1 };
}

class AttendanceGrid extends Component {
    static template = "school_management.AttendanceGrid";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        const today = localToday();
        this.state = useState({
            month: today.month,
            year: today.year,
            loading: true,
            error: null,
            grid: null,
            statuses: [],
            savingCell: false,
        });

        onWillStart(async () => {
            try {
                const options = await this.orm.call(
                    "university.attendance",
                    "get_attendance_options",
                    []
                );
                this.state.statuses = options.statuses;
            } catch (error) {
                this.state.statuses = [
                    { value: "present", label: "Present", key: "P" },
                    { value: "absent", label: "Absent", key: "A" },
                    { value: "late", label: "Late", key: "L" },
                    { value: "excused", label: "Excused", key: "E" },
                ];
            }
            await this.load();
        });
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const grid = await this.orm.call(
                "university.attendance",
                "get_grid_data",
                [[], this.state.month, this.state.year]
            );
            this.state.grid = grid;
        } catch (error) {
            this.state.error = error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    async onMonthChange(event) {
        this.state.month = Number(event.target.value);
        await this.load();
    }

    async onYearChange(event) {
        this.state.year = Number(event.target.value);
        await this.load();
    }

    async refresh() {
        await this.load();
    }

    async updateCell(sectionId, studentId, day, status) {
        if (this.state.savingCell) {
            return;
        }
        if (!status) {
            return;
        }
        this.state.savingCell = true;
        try {
            const date = `${this.state.year}-${pad(this.state.month)}-${pad(day)}`;
            await this.orm.call(
                "university.attendance",
                "update_cell",
                [sectionId, studentId, date, status]
            );
            this.notification.add(_t("Attendance updated"), { type: "success" });
            await this.load();
        } catch (error) {
            this.notification.add(error.message || String(error), { type: "danger" });
        } finally {
            this.state.savingCell = false;
        }
    }

    studentCounts(student) {
        const counts = { present: 0, absent: 0, late: 0, excused: 0 };
        for (const cell of student.cells || []) {
            if (cell.status in counts) {
                counts[cell.status] += 1;
            }
        }
        return counts;
    }

    rate(student) {
        let total = 0;
        let credited = 0;
        for (const cell of student.cells || []) {
            if (!cell.status) {
                continue;
            }
            total += 1;
            if (cell.status !== "absent") {
                credited += 1;
            }
        }
        return total ? Math.round((credited * 1000) / total) / 10 : 100;
    }

    isRisk(student, threshold) {
        const total = (student.cells || []).filter((cell) => cell.status).length;
        return total >= 3 && this.rate(student) < threshold;
    }
}

registry.category("actions").add("university_attendance_grid", AttendanceGrid);

export { AttendanceGrid };