/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";

export class AttendanceListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    _getAttendanceContext() {
        const context = {};
        const domain = this.props.domain || [];
        for (const item of domain) {
            if (Array.isArray(item) && item.length === 3) {
                if (item[0] === "section_id" && item[1] === "=") {
                    context.default_section_id = item[2];
                    context.section_id = item[2];
                }
                if (item[0] === "date" && item[1] === "=") {
                    context.default_date = item[2];
                    context.date = item[2];
                }
            }
        }
        if (this.props.context?.default_section_id) {
            context.default_section_id = this.props.context.default_section_id;
            context.section_id = this.props.context.default_section_id;
        }
        if (this.props.context?.default_date) {
            context.default_date = this.props.context.default_date;
            context.date = this.props.context.default_date;
        }
        return context;
    }

    async createRecord() {
        return this.actionService.doAction("school_management.action_university_attendance_sheet", {
            additionalContext: this._getAttendanceContext(),
        });
    }
}

export const attendanceListView = {
    ...listView,
    Controller: AttendanceListController,
};

registry.category("views").add("university_attendance_list", attendanceListView);

export class AttendanceFormController extends FormController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async create() {
        const dirty = await this.model.root.isDirty();
        const onError = (error, options) => this.onSaveError(error, options, true);
        const canProceed = !dirty || (await this.model.root.save({ onError }));
        if (canProceed) {
            return this.actionService.doAction("school_management.action_university_attendance_sheet");
        }
    }
}

export const attendanceFormView = {
    ...formView,
    Controller: AttendanceFormController,
};

registry.category("views").add("university_attendance_form", attendanceFormView);
