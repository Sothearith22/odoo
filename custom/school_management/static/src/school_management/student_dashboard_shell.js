/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class StudentDashboardShell extends Component {
    static template = "school_management.StudentDashboardShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            student: null,
            enrollmentCount: 0,
            feeCount: 0,
            paymentCount: 0,
        });

        onWillStart(async () => {
            const isStudent = await user.hasGroup("school_management.group_school_student");
            const isTeacher = await user.hasGroup("school_management.group_school_teacher");
            const isAdmin = (await user.hasGroup("base.group_system")) || (await user.hasGroup("school_management.group_school_admin"));
            const isDean = await user.hasGroup("school_management.group_school_dean");
            const isHod = await user.hasGroup("school_management.group_school_hod");

            if (!isStudent) {
                if (isTeacher && !isAdmin && !isDean && !isHod) {
                    await this.action.doAction("school_management.action_teacher_dashboard_shell", { clearBreadcrumbs: true });
                    return;
                } else if (isAdmin || isDean || isHod) {
                    await this.action.doAction("school_management.action_school_dashboard_shell", { clearBreadcrumbs: true });
                    return;
                }
            }
            await this.loadStudentData();
        });
    }

    async loadStudentData() {
        try {
            const students = await this.orm.searchRead(
                "university.student",
                [["user_id", "=", user.userId]],
                [
                    "name",
                    "student_id",
                    "status",
                    "program_id",
                    "department_id",
                    "faculty_id",
                    "academic_year_id",
                    "current_semester_id",
                    "fee_total",
                    "fee_paid",
                    "fee_balance",
                    "email",
                    "phone",
                    "gender",
                    "date_of_birth",
                    "address",
                    "image_1920",
                ],
                { limit: 1 },
            );
            this.state.student = students[0] || null;

            if (this.state.student) {
                const studentId = this.state.student.id;
                const [enrollmentCount, feeCount, paymentCount] = await Promise.all([
                    this.orm.searchCount("university.enrollment", [["student_id", "=", studentId]]),
                    this.orm.searchCount("university.fee", [["student_id", "=", studentId]]),
                    this.orm.searchCount("university.payment", [["student_id", "=", studentId]]),
                ]);
                this.state.enrollmentCount = enrollmentCount;
                this.state.feeCount = feeCount;
                this.state.paymentCount = paymentCount;
            }
        } catch (error) {
            this.state.error = error.message || "Unable to load your student dashboard.";
        } finally {
            this.state.loading = false;
        }
    }

    relationLabel(value) {
        return value?.[1] || "Not assigned";
    }

    navigate(actionXmlId) {
        this.action.doAction(actionXmlId, { clearBreadcrumbs: true });
    }

    openMyProfile() {
        if (!this.state.student) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "My Profile",
            res_model: "university.student",
            res_id: this.state.student.id,
            views: [[false, "form"]],
            view_mode: "form",
            context: { student_self_view: true },
        });
    }
}

registry.category("actions").add("student_dashboard_shell", StudentDashboardShell);

export default StudentDashboardShell;
