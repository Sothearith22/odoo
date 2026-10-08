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
        this.notification = useService("notification");

        this.state = useState({
            year: localToday(),
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

    barStyle(rate) {
        return `width: ${Math.min(Math.max(Math.round(rate), 2), 100)}%;`;
    }

    barClass(rate) {
        if (rate < 75) {
            return "o_att_bar--bad";
        }
        if (rate < 90) {
            return "o_att_bar--warn";
        }
        return "o_att_bar--good";
    }
}

registry.category("actions").add("university_attendance_comparison", AttendanceComparison);

export { AttendanceComparison };