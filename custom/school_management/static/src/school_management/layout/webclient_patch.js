/** @odoo-module **/

import { WebClient } from "@web/webclient/webclient";
import { user } from "@web/core/user";
import { router } from "@web/core/browser/router";
import { patch } from "@web/core/utils/patch";
import { useService, useBus } from "@web/core/utils/hooks";
import { onMounted, useState } from "@odoo/owl";
import { SchoolLayout } from "./school_layout";

const SCHOOL_APP_XMLID = "school_management.menu_school_root";
const STUDENT_APP_XMLID = "school_management.menu_school_student_portal_root";
const SCHOOL_DASHBOARD_XMLID = "school_management.action_school_dashboard_shell";
const TEACHER_ACTION_XMLID = "school_management.action_teacher_dashboard_shell";
const STUDENT_ACTION_XMLID = "school_management.action_student_dashboard_shell";
const SCHOOL_DASHBOARD_TAG = "school_dashboard_shell";
const TEACHER_DASHBOARD_TAG = "teacher_dashboard_shell";
const STUDENT_DASHBOARD_TAG = "student_dashboard_shell";
const STUDENT_GROUP_XMLID = "school_management.group_school_student";
const STAFF_GROUP_XMLID = "school_management.group_school_teacher";

const SCHOOL_APP_XMLIDS = new Set([SCHOOL_APP_XMLID, STUDENT_APP_XMLID]);
const SCHOOL_ACTION_XMLIDS = new Set([SCHOOL_DASHBOARD_XMLID, STUDENT_ACTION_XMLID, TEACHER_ACTION_XMLID]);
const SCHOOL_ACTION_TAGS = new Set([SCHOOL_DASHBOARD_TAG, STUDENT_DASHBOARD_TAG, TEACHER_DASHBOARD_TAG]);
const SCHOOL_MODELS = new Set([
    "school.dashboard",
    "university.academic.assignment",
    "university.academic.year",
    "university.assessment.result",
    "university.assignment",
    "university.assignment.submission",
    "university.attendance",
    "university.bulk.enrollment.wizard",
    "university.capability",
    "university.class.section",
    "university.classroom",
    "university.department",
    "university.document.signature",
    "university.enrollment",
    "university.faculty",
    "university.fee",
    "university.payment",
    "university.program",
    "university.report.card",
    "university.semester",
    "university.semester.subject",
    "university.student",
    "university.student.enrollment.wizard",
    "university.subject",
    "university.teacher",
    "university.timetable.slot",
    "university.transcript",
]);
const STUDENT_SAFE_ACTION_TAGS = new Set([STUDENT_DASHBOARD_TAG]);
const STUDENT_SAFE_MODELS = new Set([
    "university.student",
    "university.enrollment",
    "university.fee",
    "university.payment",
    "university.assignment",
    "university.assignment.submission",
    "university.assessment.result",
    "university.attendance",
    "university.report.card",
    "university.timetable.slot",
    "university.transcript",
]);

function debugNavigation(...args) {
    if (window.odoo?.debug) {
        console.debug(...args);
    }
}

function hasLoadedAction(action = {}) {
    return Boolean(action.type || action.res_model || action.tag || action.xml_id || action.id);
}

function isSchoolModel(model) {
    return (
        SCHOOL_MODELS.has(model) ||
        model === "school.dashboard" ||
        (typeof model === "string" && model.startsWith("university."))
    );
}

function isSchoolAction(action = {}) {
    return Boolean(
        isSchoolModel(action.res_model) ||
        SCHOOL_ACTION_TAGS.has(action.tag) ||
        SCHOOL_ACTION_XMLIDS.has(action.xml_id)
    );
}

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
            const actionLoaded = hasLoadedAction(currentAction);
            const schoolAction = isSchoolAction(currentAction);
            const routeAction = router.current.action;
            const schoolRouteWithoutAction =
                !actionLoaded && !routeAction && SCHOOL_APP_XMLIDS.has(currentApp?.xmlid);

            this.schoolState.isActive = Boolean(schoolAction || schoolRouteWithoutAction);

            document.body.classList.toggle(
                "o_school_management_active",
                this.schoolState.isActive
            );

            debugNavigation("[University WebClient] layout state", {
                app: currentApp?.xmlid,
                action: currentAction.xml_id || currentAction.tag || currentAction.id,
                model: currentAction.res_model,
                enabled: this.schoolState.isActive,
            });
        };

        const refreshSchoolRoute = async () => {
            checkSchoolApp();
            await this.redirectStudentToDashboard();
        };

        useBus(this.env.bus, "MENUS:APP-CHANGED", async () => {
            checkSchoolApp();
            await this.ensureSchoolDashboardRoute();
            await this.redirectStudentToDashboard();
        });
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", refreshSchoolRoute);
        onMounted(() => {
            setTimeout(checkSchoolApp);
            setTimeout(() => this.ensureSchoolDashboardRoute());
            setTimeout(() => this.redirectStudentToDashboard());
        });
        checkSchoolApp();
    },

    async ensureSchoolDashboardRoute() {
        if (this.dashboardRedirecting) {
            return;
        }

        const currentApp = this.menuService.getCurrentApp();
        if (currentApp?.xmlid !== SCHOOL_APP_XMLID) {
            return;
        }

        const currentAction = this.actionService.currentController?.action || {};
        const routeAction = router.current.action;
        const actionName = (currentAction.name || "").toLowerCase();
        const actionLoaded = hasLoadedAction(currentAction);
        const isDashboardAction =
            currentAction.tag === SCHOOL_DASHBOARD_TAG ||
            currentAction.xml_id === SCHOOL_DASHBOARD_XMLID ||
            currentAction.tag === TEACHER_DASHBOARD_TAG ||
            currentAction.xml_id === TEACHER_ACTION_XMLID ||
            currentAction.tag === STUDENT_DASHBOARD_TAG ||
            currentAction.xml_id === STUDENT_ACTION_XMLID ||
            currentAction.res_model === "school.dashboard" ||
            actionName.includes("dashboard");

        debugNavigation("[University WebClient] route check", {
            app: currentApp?.xmlid,
            currentAction: currentAction.xml_id || currentAction.tag || currentAction.id,
            routeAction,
            actionLoaded,
        });

        // A real loaded action or an explicit dashboard action owns the route.
        // During app selection Odoo can expose a stale router action before the
        // ActionContainer has mounted; in that state the University app would
        // render the shell with an empty content slot and never recover.
        if (isDashboardAction || actionLoaded) {
            return;
        }

        this.dashboardRedirecting = true;
        try {
            const isHod = await user.hasGroup("school_management.group_school_hod");
            const isDean = await user.hasGroup("school_management.group_school_dean");
            const isAdmin = (await user.hasGroup("base.group_system")) || (await user.hasGroup("school_management.group_school_admin"));
            const isTeacher = await user.hasGroup("school_management.group_school_teacher");

            let targetAction = SCHOOL_DASHBOARD_XMLID;
            if (isTeacher && !isAdmin && !isDean && !isHod) {
                targetAction = TEACHER_ACTION_XMLID;
            }

            debugNavigation("[University WebClient] opening Dashboard", {
                action: targetAction,
            });
            await this.actionService.doAction(targetAction, {
                clearBreadcrumbs: true,
            });
        } finally {
            this.dashboardRedirecting = false;
        }
    },

    async redirectStudentToDashboard() {
        if (this.studentRedirecting) {
            return;
        }
        if (!(await user.hasGroup(STUDENT_GROUP_XMLID))) {
            return;
        }
        // A dual-role user can intentionally switch between staff and student
        // views; only student-only users need automatic portal redirection.
        if (await user.hasGroup(STAFF_GROUP_XMLID)) {
            return;
        }

        const currentApp = this.menuService.getCurrentApp();
        const currentAction = this.actionService.currentController?.action || {};
        const actionLoaded = hasLoadedAction(currentAction);
        const routeAction = router.current.action;
        const inSchoolRoute = isSchoolAction(currentAction) ||
            (!actionLoaded && !routeAction && SCHOOL_APP_XMLIDS.has(currentApp?.xmlid));

        if (!inSchoolRoute) {
            return;
        }

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
