/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";

const DASHBOARD_XMLID = "school_management.action_school_dashboard_shell";

function navGroup(label, items) {
    return { label, items };
}

function navItem(key, label, icon, actionXmlId) {
    return { key, label, icon, actionXmlId };
}

export class SchoolLayout extends Component {
    static template = "school_management.SchoolLayout";
    static props = {
        slots: { type: Object, optional: true },
    };

    setup() {
        this.action = useService("action");

        this.navGroups = [
            navGroup("Structure", [
                navItem("faculty", "Faculties", "fa fa-university", "school_management.action_university_faculty"),
                navItem("department", "Departments", "fa fa-building", "school_management.action_university_department"),
                navItem("program", "Programs / Majors", "fa fa-certificate", "school_management.action_university_program"),
                navItem("subject", "Subjects", "fa fa-book", "school_management.action_university_subject"),
                navItem("class_section", "Class Sections", "fa fa-users", "school_management.action_university_class_section"),
                navItem("classroom", "Classrooms", "fa fa-th", "school_management.action_university_classroom"),
            ]),
            navGroup("Students", [
                navItem("student", "All Students", "fa fa-graduation-cap", "school_management.action_university_student"),
                navItem("enrollment", "Student Enrollment", "fa fa-clipboard", "school_management.action_university_enrollment"),
            ]),
            navGroup("Teachers", [
                navItem("teacher", "All Teachers", "fa fa-user", "school_management.action_university_teacher"),
            ]),
            navGroup("Academic", [
                navItem("academic_year", "Academic Years", "fa fa-calendar", "school_management.action_university_academic_year"),
                navItem("semester", "Semesters", "fa fa-calendar-check-o", "school_management.action_university_semester"),
            ]),
            navGroup("Finance", [
                navItem("fee", "Invoices", "fa fa-money", "school_management.action_university_fee"),
                navItem("payment", "Payments", "fa fa-credit-card", "school_management.action_university_payment"),
            ]),
        ];

        this.state = useState({
            collapsed: false,
            activeKey: "dashboard",
        });

        useBus(this.env.bus, "MENUS:APP-CHANGED", this.refreshActive.bind(this));
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", this.refreshActive.bind(this));
        onMounted(() => this.refreshActive());
    }

    get _flatItems() {
        return this.navGroups.flatMap((group) => group.items);
    }

    refreshActive() {
        const currentAction = this.action.currentController?.action || {};
        const xmlid = currentAction.xml_id || null;
        const tag = currentAction.tag || null;

        if (tag === "school_dashboard_shell" || xmlid === DASHBOARD_XMLID) {
            this.state.activeKey = "dashboard";
            return;
        }

        if (xmlid) {
            const matched = this._flatItems.find((item) => item.actionXmlId === xmlid);
            if (matched) {
                this.state.activeKey = matched.key;
                return;
            }
        }
    }

    isActive(key) {
        return this.state.activeKey === key;
    }

    isGroupActive(group) {
        return group.items.some((item) => this.isActive(item.key));
    }

    toggleSidebar() {
        this.state.collapsed = !this.state.collapsed;
    }

    openDashboard() {
        this.state.activeKey = "dashboard";
        this.action.doAction(DASHBOARD_XMLID, {
            clearBreadcrumbs: true,
        });
    }

    navigate(actionXmlId, key) {
        this.state.activeKey = key;
        this.action.doAction(actionXmlId, { clearBreadcrumbs: true });
    }
}

export default SchoolLayout;
