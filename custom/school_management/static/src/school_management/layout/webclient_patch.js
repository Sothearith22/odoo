/** @odoo-module **/

import { WebClient } from "@web/webclient/webclient";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { useService, useBus } from "@web/core/utils/hooks";
import { onMounted, useState } from "@odoo/owl";
import { SchoolLayout } from "./school_layout";

const SCHOOL_APP_XMLID = "school_management.menu_school_root";
const STUDENT_GROUP_XMLID = "school_management.group_school_student";
const STUDENT_ACTION_XMLID = "school_management.action_student_dashboard_shell";
const STUDENT_DASHBOARD_TAG = "student_dashboard_shell";
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
const STUDENT_SAFE_ACTION_TAGS = new Set([STUDENT_DASHBOARD_TAG]);
const STUDENT_SAFE_MODELS = new Set([
    "university.student",
    "university.enrollment",
    "university.fee",
    "university.payment",
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
        this.studentRedirecting = false;

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

        const refreshSchoolRoute = () => {
            checkSchoolApp();
            this.redirectStudentToDashboard();
        };

        useBus(this.env.bus, "MENUS:APP-CHANGED", refreshSchoolRoute);
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", refreshSchoolRoute);
        onMounted(() => {
            setTimeout(checkSchoolApp);
            setTimeout(() => this.redirectStudentToDashboard());
        });
        checkSchoolApp();
    },

    async redirectStudentToDashboard() {
        if (this.studentRedirecting) {
            return;
        }
        if (!(await user.hasGroup(STUDENT_GROUP_XMLID))) {
            return;
        }

        const currentAction = this.actionService.currentController?.action || {};
        const actionModel = currentAction.res_model;
        const isStudentSafeAction =
            STUDENT_SAFE_ACTION_TAGS.has(currentAction.tag) || STUDENT_SAFE_MODELS.has(actionModel);

        if (isStudentSafeAction) {
            return;
        }

        this.studentRedirecting = true;
        try {
            await this.actionService.doAction(STUDENT_ACTION_XMLID, {
                clearBreadcrumbs: true,
            });
        } finally {
            this.studentRedirecting = false;
        }
    },
});