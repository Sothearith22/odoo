/** @odoo-module **/

import { Component, onWillStart, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const DASHBOARD_XMLID = "school_management.action_school_dashboard_shell";
const SETTINGS_XMLID = "school_management.action_university_settings";
const APPS_XMLID = "base.open_module_tree";
const CAPABILITY_XMLID = "school_management.action_university_capability";

const GROUP_SYSTEM = "base.group_system";
const GROUP_USER = "school_management.group_school_user";
const GROUP_STUDENT = "school_management.group_school_student";
const GROUP_ADMIN = "school_management.group_school_admin";
const GROUP_DEAN = "school_management.group_school_dean";
const GROUP_HOD = "school_management.group_school_hod";
const GROUP_TEACHER = "school_management.group_school_teacher";
const STUDENT_DASHBOARD_XMLID = "school_management.action_student_dashboard_shell";

function debugNavigation(...args) {
    if (window.odoo?.debug) {
        console.debug(...args);
    }
}

const ACTION_ACTIVE_KEY = {
    [DASHBOARD_XMLID]: "dashboard",
    [STUDENT_DASHBOARD_XMLID]: "dashboard",
    "school_management.action_university_faculty": "faculty",
    "school_management.action_university_department": "department",
    "school_management.action_university_program": "program",
    "school_management.action_university_subject": "subject",
    "school_management.action_university_class_section": "class_section",
    "school_management.action_university_classroom": "classroom",
    "school_management.action_university_student": "student",
    "school_management.action_university_enrollment": "enrollment",
    "school_management.action_university_enrollment_student": "enrollment",
    "school_management.action_university_bulk_enrollment_wizard": "bulk_enrollment",
    "school_management.action_university_teacher": "teacher",
    "school_management.action_university_hod": "hod",
    "school_management.action_university_dean": "dean",
    "school_management.action_university_academic_assignment": "assignment",
    "school_management.action_university_academic_year": "academic_year",
    "school_management.action_university_semester": "semester",
    "school_management.action_university_semester_subject": "semester_subject",
    "school_management.action_university_fee": "fee",
    "school_management.action_university_fee_student": "fee",
    "school_management.action_university_payment": "payment",
    "school_management.action_university_payment_student": "payment",
    [CAPABILITY_XMLID]: "capability",
    "school_management.action_university_document_signature": "document_signature",
};

const MODEL_ACTIVE_KEY = {
    "school.dashboard": "dashboard",
    "university.faculty": "faculty",
    "university.department": "department",
    "university.program": "program",
    "university.subject": "subject",
    "university.class.section": "class_section",
    "university.classroom": "classroom",
    "university.student": "student",
    "university.enrollment": "enrollment",
    "university.bulk.enrollment.wizard": "bulk_enrollment",
    "university.teacher": "teacher",
    "university.academic.assignment": "assignment",
    "university.academic.year": "academic_year",
    "university.semester": "semester",
    "university.semester.subject": "semester_subject",
    "university.fee": "fee",
    "university.payment": "payment",
    "university.capability": "capability",
    "university.document.signature": "document_signature",
};

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
    semester_subject: GROUP_ADMIN,
    fee: GROUP_ADMIN,
    payment: GROUP_ADMIN,
    document_signature: GROUP_ADMIN,
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
                navItem("semester_subject", "Semester Subjects", "fa fa-bookmark", "school_management.action_university_semester_subject"),
            ]),
            navGroup("Finance", [
                navItem("fee", "Fee Invoices", "fa fa-money", "school_management.action_university_fee"),
                navItem("payment", "Payments & Receipts", "fa fa-credit-card", "school_management.action_university_payment"),
                navItem("document_signature", "Document Signatures", "fa fa-pencil-square-o", "school_management.action_university_document_signature"),
            ]),
        ];

        this.settingsItem = navItem("settings", "Settings", "fa fa-cog", SETTINGS_XMLID);
        this.appsItem = navItem("apps", "Apps", "fa fa-th-large", APPS_XMLID, true);
        this.capabilityItem = navItem(
            "capability",
            "Capabilities & Roadmap",
            "fa fa-cubes",
            CAPABILITY_XMLID,
            true
        );

        this.state = useState({
            collapsed: false,
            mobileOpen: false,
            activeKey: "dashboard",
            canBulkEnroll: false,
            canManageSettings: false,
            canManageModules: false,
            canManageRoadmap: false,
            canSwitchStudentView: false,
            isStudentView: false,
            visibleNavGroups: [],
            searchQuery: "",
            collapsedGroups: {},
            showUserMenu: false,
            userName: "User",
            userRole: "Staff",
            userInitials: "U",
        });

        onWillStart(async () => {
            const isSystem = await user.hasGroup(GROUP_SYSTEM);
            this.state.canManageSettings = isSystem;
            this.state.canManageModules = isSystem;
            this.state.canBulkEnroll = (await user.hasGroup(GROUP_ADMIN)) || isSystem;
            this.state.canManageRoadmap =
                (await user.hasGroup(GROUP_ADMIN)) || isSystem;
            this.state.canSwitchStudentView =
                (await user.hasGroup(GROUP_STUDENT)) && (await user.hasGroup(GROUP_TEACHER));

            this.state.userName = user.name || "Administrator";
            this.state.userInitials = this.computeInitials(this.state.userName);

            const isAdmin = isSystem || (await user.hasGroup(GROUP_ADMIN));
            const isDean = await user.hasGroup(GROUP_DEAN);
            const isHod = await user.hasGroup(GROUP_HOD);
            const isTeacher = await user.hasGroup(GROUP_TEACHER);

            if (isAdmin) {
                this.state.userRole = "Administrator";
            } else if (isDean) {
                this.state.userRole = "Dean of Faculty";
            } else if (isHod) {
                this.state.userRole = "Head of Department";
            } else if (isTeacher) {
                this.state.userRole = "Teacher";
            } else {
                this.state.userRole = "Staff";
            }

            const check = async (key) => {
                if (isSystem) {
                    return true;
                }
                const group = ITEM_GROUP[key];
                if (!group) {
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
        this._destroyed = false;
        onWillUnmount(() => {
            this._destroyed = true;
        });
    }

    computeInitials(name) {
        if (!name || typeof name !== "string") return "U";
        const clean = name.replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s+/i, "");
        const parts = clean.trim().split(/\s+/);
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }

    get _flatItems() {
        return [
            ...this.navGroups.flatMap((group) => group.items),
            this.settingsItem,
            this.appsItem,
            this.capabilityItem,
        ];
    }

    get filteredNavGroups() {
        const query = (this.state.searchQuery || "").trim().toLowerCase();
        if (!query) {
            return this.state.visibleNavGroups;
        }
        return this.state.visibleNavGroups
            .map((group) => ({
                ...group,
                items: group.items.filter((item) =>
                    item.label.toLowerCase().includes(query)
                ),
            }))
            .filter((group) => group.items.length > 0);
    }

    refreshActive() {
        requestAnimationFrame(() => {
            if (this._destroyed) {
                return;
            }
            const currentAction = this.action.currentController?.action || {};
            const xmlid = currentAction.xml_id || null;
            const tag = currentAction.tag || null;

            this.state.isStudentView =
                tag === "student_dashboard_shell" || xmlid === STUDENT_DASHBOARD_XMLID;
            this.state.activeKey = null;

            if (tag === "school_dashboard_shell" || tag === "student_dashboard_shell") {
                this.state.activeKey = "dashboard";
                this._expandGroupForActive();
                return;
            }

            if (xmlid && ACTION_ACTIVE_KEY[xmlid]) {
                this.state.activeKey = ACTION_ACTIVE_KEY[xmlid];
                this._expandGroupForActive();
                return;
            }

            if (xmlid) {
                const matched = this._flatItems.find((item) => item.actionXmlId === xmlid);
                if (matched) {
                    this.state.activeKey = matched.key;
                    this._expandGroupForActive();
                    return;
                }
            }

            const modelKey = MODEL_ACTIVE_KEY[currentAction.res_model];
            if (modelKey) {
                this.state.activeKey = modelKey;
                this._expandGroupForActive();
            }
        });
    }

    _expandGroupForActive() {
        if (!this.state.activeKey) {
            return;
        }
        for (const group of this.state.visibleNavGroups) {
            if (group.items.some((item) => item.key === this.state.activeKey)) {
                this.state.collapsedGroups[group.label] = false;
                break;
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
        if (window.innerWidth < 992) {
            this.state.mobileOpen = !this.state.mobileOpen;
        } else {
            this.state.collapsed = !this.state.collapsed;
        }
    }

    closeMobileDrawer() {
        this.state.mobileOpen = false;
        this.state.showUserMenu = false;
    }

    toggleGroup(groupLabel) {
        this.state.collapsedGroups[groupLabel] = !this.state.collapsedGroups[groupLabel];
    }

    isGroupCollapsed(groupLabel) {
        if (this.state.searchQuery.trim()) return false;
        return Boolean(this.state.collapsedGroups[groupLabel]);
    }

    toggleUserMenu() {
        this.state.showUserMenu = !this.state.showUserMenu;
    }

    async openDashboard() {
        this.closeMobileDrawer();
        debugNavigation("[University Sidebar] clicked menu", {
            id: "dashboard",
            name: "Dashboard",
            actionXmlId: DASHBOARD_XMLID,
        });
        await this.action.doAction(DASHBOARD_XMLID, { clearBreadcrumbs: true });
        this.refreshActive();
    }

    async switchView(view) {
        if (!this.state.canSwitchStudentView) {
            return;
        }
        this.closeMobileDrawer();
        this.state.isStudentView = view === "student";
        await this.action.doAction(
            view === "student" ? STUDENT_DASHBOARD_XMLID : DASHBOARD_XMLID,
            { clearBreadcrumbs: true },
        );
        this.refreshActive();
    }

    async navigate(actionXmlId, key) {
        this.closeMobileDrawer();
        const item = this._flatItems.find((navItem) => navItem.key === key);
        debugNavigation("[University Sidebar] clicked menu", {
            id: key,
            name: item?.label || key,
            actionXmlId,
        });
        await this.action.doAction(actionXmlId);
        this.refreshActive();
    }

    openApps() {
        this.navigate(APPS_XMLID, this.appsItem.key);
    }

    openProfile() {
        this.state.showUserMenu = false;
        this.action.doAction("base.action_res_users_my");
    }

    logout() {
        window.location.href = "/web/session/logout";
    }
}

export default SchoolLayout;