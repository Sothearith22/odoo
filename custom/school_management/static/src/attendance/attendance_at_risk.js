/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

function localToday() {
    const today = new Date();
    return { year: today.getFullYear(), month: today.getMonth() + 1 };
}

class AttendanceAtRisk extends Component {
    static template = "school_management.AttendanceAtRisk";
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
            data: null,
        });

        onWillStart(async () => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call(
                "university.attendance",
                "get_at_risk_data",
                [this.state.month, this.state.year, []]
            );
            this.state.data = data;
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

    rateLabel(student) {
        return `${student.rate}%`;
    }

    barWidth(student) {
        return `${Math.min(Math.max(Math.round(student.rate), 2), 100)}%`;
    }
}

registry.category("actions").add("university_attendance_at_risk", AttendanceAtRisk);

export { AttendanceAtRisk };