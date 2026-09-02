/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class SchoolLayout extends Component {
    static template = "school_management.SchoolLayout";
    static props = {
        slots: { type: Object, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.state = useState({
            collapsed: false,
        });
    }

    toggleSidebar() {
        this.state.collapsed = !this.state.collapsed;
    }

    openDashboard() {
        this.action.doAction("school_management.action_school_dashboard_shell", {
            clearBreadcrumbs: true,
        });
    }

    navigate(actionXmlId) {
        this.action.doAction(actionXmlId, { clearBreadcrumbs: true });
    }
}

export default SchoolLayout;