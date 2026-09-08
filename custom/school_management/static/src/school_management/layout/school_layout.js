/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";
import { user } from "@web/core/user";

const DASHBOARD_XMLID = "school_management.action_school_dashboard_shell";

const GROUP_SYSTEM = "base.group_system";
const GROUP_USER = "school_management.group_school_user";
const GROUP_ADMIN = "school_management.group_school_admin";
const GROUP_DEAN = "school_management.group_school_dean";
const GROUP_HOD = "school_management.group_school_hod";
const GROUP_TEACHER = "school_management.group_school_teacher";

// Minimal role required to open each action (null = any University staff member).
// Because School HOD/Dean/Admin imply Teacher and base.group_system implies all,
// members of a higher role automatically gain the lower-role items.
const ITEM_GROUP = {
    faculty: GROUP_ADMIN,
    department: GROUP_HOD,
    program: GROUP_DEAN,
    subject: GROUP_TEACHER,
    class_section: GROUP_TEACHER,
    classroom: GROUP_ADMIN,
    student: GROUP_TEACHER,
    enrollment: GROUP_HOD,
    bulk_enrollment: GROUP_ADMIN,
    teacher: GROUP_TEACHER,
    hod: GROUP_HOD,
    dean: GROUP_DEAN,
    assignment: GROUP_HOD,
    academic_year: GROUP_ADMIN,
    semester: GROUP_ADMIN,
    fee: GROUP_ADMIN,
    payment: GROUP_ADMIN,
};

function navGroup(label, items) {
    return { label, items };
}

function navItem(key, label, icon, actionXmlId, adminOnly = false) {
    return { key, label, icon, actionXmlId, adminOnly };
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
                navItem("bulk_enrollment", "Enroll Multiple Students", "fa fa-users", "school_management.action_university_bulk_enrollment_wizard", true),
            ]),
            navGroup("Academic Staff", [
                navItem("teacher", "Teachers", "fa fa-user", "school_management.action_university_teacher"),
                navItem("hod", "Heads of Department", "fa fa-users", "school_management.action_university_hod"),
                navItem("dean", "Heads of Faculty", "fa fa-star", "school_management.action_university_dean"),
                navItem("assignment", "Role Assignments", "fa fa-id-card-o", "school_management.action_university_academic_assignment"),
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
            canBulkEnroll: false,
            visibleNavGroups: [],
        });

        onWillStart(async () => {
            const isSystem = await user.hasGroup(GROUP_SYSTEM);
            this.state.canBulkEnroll =
                (await user.hasGroup(GROUP_ADMIN)) || isSystem;

            const check = async (key) => {
                if (isSystem) {
                    return true;
                }
                const group = ITEM_GROUP[key];
                if (!group) {
                    // No explicit group -> anyone inside the University app.
                    return await user.hasGroup(GROUP_USER);
                }
                return await user.hasGroup(group);
            };

            const accessible = {};
            for (const key of Object.keys(ITEM_GROUP)) {
                accessible[key] = await check(key);
            }

            this.state.visibleNavGroups = this.navGroups
                .map((group) => ({
                    ...group,
                    items: group.items.filter((item) => accessible[item.key]),
                }))
                .filter((group) => group.items.length);
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
