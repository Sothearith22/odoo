/** @odoo-module **/

import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";
import { useService, useBus } from "@web/core/utils/hooks";
import { onMounted, useState } from "@odoo/owl";
import { SchoolLayout } from "./school_layout";

const SCHOOL_APP_XMLID = "school_management.menu_school_root";
const SCHOOL_ACTION_TAGS = new Set(["school_dashboard_shell"]);
const SCHOOL_MODELS = new Set([
    "school.dashboard",
    "university.academic.year",
    "university.class.section",
    "university.classroom",
    "university.department",
    "university.enrollment",
    "university.enrollment.wizard",
    "university.faculty",
    "university.fee",
    "university.payment",
    "university.program",
    "university.semester",
    "university.student",
    "university.student.enrollment.wizard",
    "university.subject",
    "university.teacher",
]);

WebClient.components = {
    ...WebClient.components,
    SchoolLayout,
};

patch(WebClient.prototype, {
    setup() {
        super.setup();
        this.menuService = useService("menu");
        this.schoolState = useState({ isActive: false });

        const checkSchoolApp = () => {
            const currentApp = this.menuService.getCurrentApp();
            const currentAction = this.actionService.currentController?.action || {};
            const actionModel = currentAction.res_model;
            const isSchoolApp = currentApp?.xmlid === SCHOOL_APP_XMLID;
            const isSchoolAction =
                SCHOOL_ACTION_TAGS.has(currentAction.tag) ||
                SCHOOL_MODELS.has(actionModel) ||
                (typeof actionModel === "string" && actionModel.startsWith("university."));

            this.schoolState.isActive = Boolean(isSchoolApp || isSchoolAction);

            if (this.schoolState.isActive) {
                document.body.classList.add("o_school_management_active");
            } else {
                document.body.classList.remove("o_school_management_active");
            }
        };

        useBus(this.env.bus, "MENUS:APP-CHANGED", checkSchoolApp);
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", checkSchoolApp);
        onMounted(() => setTimeout(checkSchoolApp));
        checkSchoolApp();
    },
});