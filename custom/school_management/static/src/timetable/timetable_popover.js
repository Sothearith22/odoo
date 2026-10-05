/** @odoo-module **/

import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useState } from "@odoo/owl";

patch(CalendarCommonPopover.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.ormService = useService("orm");
        this.attendanceState = useState({
            canTrackAttendance: false,
        });

        if (this.isTimetableSlot && this.timetableRecordId) {
            onWillStart(async () => {
                await this._checkAttendancePermission();
            });
        }
    },

    get isTimetableSlot() {
        return this.props.model?.resModel === "university.timetable.slot";
    },

    get timetableRecordId() {
        const id = this.props.record?.id;
        if (typeof id === "number") {
            return id;
        }
        const parsed = parseInt(id, 10);
        return isNaN(parsed) ? null : parsed;
    },

    get canTrackAttendance() {
        return Boolean(this.isTimetableSlot && this.attendanceState.canTrackAttendance);
    },

    get hasFooter() {
        return super.hasFooter || this.canTrackAttendance;
    },

    async _checkAttendancePermission() {
        try {
            const canManage = await this.ormService.call(
                "university.timetable.slot",
                "check_can_manage_attendance",
                [[this.timetableRecordId]]
            );
            this.attendanceState.canTrackAttendance = Boolean(canManage);
        } catch {
            this.attendanceState.canTrackAttendance = false;
        }
    },

    async onTrackAttendance() {
        this.props.close();
        await this.actionService.doActionButton({
            name: "action_track_attendance",
            type: "object",
            resModel: this.props.model.resModel,
            resId: this.timetableRecordId,
        });
    },
});
