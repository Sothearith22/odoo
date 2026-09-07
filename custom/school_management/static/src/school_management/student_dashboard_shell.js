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

        onWillStart(() => this.loadStudentData());
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
}

registry.category("actions").add("student_dashboard_shell", StudentDashboardShell);

export default StudentDashboardShell;
