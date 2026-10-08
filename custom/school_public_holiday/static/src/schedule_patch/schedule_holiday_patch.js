/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { UniversitySchedule } from "@school_management/schedule/university_schedule";
import { Component, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class HolidayConflictDialog extends Component {
    static template = xml`
        <Dialog title="props.title">
            <div class="p-3">
                <div class="alert alert-danger d-flex align-items-center mb-3">
                    <i class="fa fa-exclamation-triangle fa-2x me-3 text-danger"/>
                    <div>
                        <strong>Public Holiday Conflict Detected</strong>
                        <div class="small" t-esc="props.message"/>
                    </div>
                </div>
                <div class="card p-3 mb-3 bg-light border">
                    <div class="mb-1"><strong>Holiday:</strong> <t t-esc="props.holidayName"/> (<t t-esc="props.holidayDates"/>)</div>
                    <div class="mb-1"><strong>Session:</strong> <t t-esc="props.sessionName"/></div>
                    <div class="mb-1"><strong>Class Section:</strong> <t t-esc="props.sectionName"/></div>
                    <div class="mb-1"><strong>Teacher:</strong> <t t-esc="props.teacherName"/></div>
                    <div><strong>Room:</strong> <t t-esc="props.roomName"/></div>
                </div>
                <p class="text-muted small mb-0">
                    Select an action below. Cancelling will mark the session cancelled due to this holiday.
                    Rescheduling allows selecting a new conflict-free date and time.
                </p>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-danger" t-on-click="onCancelSession">
                    <i class="fa fa-times me-1"/> Cancel Session
                </button>
                <button class="btn btn-primary" t-on-click="onRescheduleSession">
                    <i class="fa fa-calendar me-1"/> Reschedule
                </button>
                <button class="btn btn-secondary" t-on-click="() => this.props.close()">
                    Close
                </button>
            </t>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        title: String,
        message: String,
        holidayName: String,
        holidayDates: String,
        sessionName: String,
        sectionName: String,
        teacherName: String,
        roomName: String,
        onCancel: Function,
        onReschedule: Function,
        close: Function,
    };

    async onCancelSession() {
        await this.props.onCancel();
        this.props.close();
    }

    async onRescheduleSession() {
        await this.props.onReschedule();
        this.props.close();
    }
}

patch(UniversitySchedule.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.holidayIndicators = { holidays: [], holiday_days: {}, slot_conflicts: {} };
    },

    async loadScheduleData() {
        await super.loadScheduleData(...arguments);
        try {
            const bounds = this.getBoundsForView();
            const res = await this.orm.call(
                "university.timetable.slot",
                "get_holiday_schedule_indicators",
                [bounds.start, bounds.end, this.state.filters]
            );
            if (res) {
                this.state.holidayIndicators = res;
            }
        } catch (err) {
            console.error("Error loading holiday schedule indicators:", err);
        }
        this._updateHolidayLegend();
    },

    get weekDays() {
        const days = super.weekDays;
        const holidayDays = this.state.holidayIndicators?.holiday_days || {};
        for (const day of days) {
            const hVal = holidayDays[day.dateStr];
            const holiday = Array.isArray(hVal) ? hVal[0] : (hVal || day.holiday);
            if (holiday && (!holiday.holiday_type || holiday.holiday_type === "public")) {
                day.holiday = holiday;
                const options = { year: "numeric", month: "long", day: "numeric" };
                const formattedDate = day.date.toLocaleDateString("en-US", options);
                day.holidayTooltip = `Public Holiday\nHoliday: ${holiday.name}\nDate: ${formattedDate}\nClasses should not be scheduled on this date.`;
            } else if (day.holiday) {
                const options = { year: "numeric", month: "long", day: "numeric" };
                const formattedDate = day.date.toLocaleDateString("en-US", options);
                day.holidayTooltip = `Public Holiday\nHoliday: ${day.holiday.name}\nDate: ${formattedDate}\nClasses should not be scheduled on this date.`;
            }
        }
        return days;
    },

    async addClass(options = {}) {
        if (options && options.dateStr) {
            const holidayDays = this.state.holidayIndicators?.holiday_days || {};
            const hVal = holidayDays[options.dateStr];
            const holiday = Array.isArray(hVal) ? hVal[0] : (hVal || (this.state.holidays || []).find((h) => {
                const s = h.date_start || h.date_from;
                const e = h.date_end || h.date_to || s;
                return Boolean(s && e && s <= options.dateStr && options.dateStr <= e && (!h.holiday_type || h.holiday_type === "public"));
            }));
            if (holiday) {
                this.notification.add(
                    `Warning: ${options.dateStr} is a public holiday (${holiday.name}). Classes should not be scheduled on this date.`,
                    { type: "warning" }
                );
            }
        }
        return super.addClass(...arguments);
    },

    getSlotColorClass(slot) {
        let cls = super.getSlotColorClass(slot);
        const conflictInfo = this.state.holidayIndicators?.slot_conflicts?.[slot.id];
        if (conflictInfo) {
            if (conflictInfo.is_conflict) {
                cls += " o_slot_holiday_conflict";
            } else if (conflictInfo.is_cancelled) {
                cls += " o_slot_holiday_cancelled";
            } else if (conflictInfo.is_override) {
                cls += " o_slot_holiday_override";
            }
        }
        return cls;
    },

    openSlotSidePanel(slot) {
        const conflictInfo = this.state.holidayIndicators?.slot_conflicts?.[slot.id];
        if (conflictInfo && conflictInfo.is_conflict) {
            this.openHolidayConflictDialog(slot, conflictInfo);
            return;
        }
        super.openSlotSidePanel(slot);
    },

    openHolidayConflictDialog(slot, conflictInfo) {
        this.dialog.add(HolidayConflictDialog, {
            title: `Holiday Conflict: ${conflictInfo.holiday_name}`,
            message: `This session falls on ${conflictInfo.holiday_name} (${conflictInfo.holiday_dates}) and has not been approved for holiday scheduling.`,
            holidayName: conflictInfo.holiday_name,
            holidayDates: conflictInfo.holiday_dates,
            sessionName: slot.subject_name || slot.name || "Class Session",
            sectionName: slot.section_name || "N/A",
            teacherName: slot.teacher_name || "N/A",
            roomName: slot.classroom_name || "N/A",
            onCancel: async () => {
                await this.orm.call("university.timetable.slot", "action_cancel_for_holiday", [
                    [slot.id],
                    conflictInfo.holiday_name,
                ]);
                this.notification.add(`Session cancelled due to ${conflictInfo.holiday_name}.`, {
                    type: "info",
                });
                await this.loadScheduleData();
            },
            onReschedule: async () => {
                await this.action.doAction({
                    name: "Reschedule Conflicting Session",
                    type: "ir.actions.act_window",
                    res_model: "wizard.reschedule.session",
                    view_mode: "form",
                    target: "new",
                    context: {
                        default_slot_id: slot.id,
                        default_start_time: slot.start_time,
                        default_end_time: slot.end_time,
                        default_classroom_id: slot.classroom_id ? (slot.classroom_id.id || slot.classroom_id) : false,
                    },
                });
            },
        });
    },

    _updateHolidayLegend() {
        if (!this.el) return;
        const topBar = this.el.querySelector(".o_schedule_top_bar .d-flex.flex-wrap");
        if (topBar && !topBar.querySelector(".o_holiday_schedule_legend")) {
            const legendEl = document.createElement("div");
            legendEl.className = "o_holiday_schedule_legend ms-auto";
            legendEl.innerHTML = `
                <span class="text-muted fw-bold me-1">Holiday Status:</span>
                <span class="o_holiday_legend_item" title="Public Holiday (shaded day column)"><span class="o_legend_swatch swatch_holiday"></span> Public Holiday</span>
                <span class="o_holiday_legend_item" title="Session in conflict with holiday"><span class="o_legend_swatch swatch_conflict"></span> Conflict</span>
                <span class="o_holiday_legend_item" title="Cancelled on holiday"><span class="o_legend_swatch swatch_cancelled"></span> Cancelled</span>
                <span class="o_holiday_legend_item" title="Admin override allowed"><span class="o_legend_swatch swatch_override"></span> Allowed</span>
            `;
            topBar.appendChild(legendEl);
        }
    },

    exportExcel() {
        const slots = this.filteredSlots;
        if (!slots.length) {
            this.notification.add("No schedule sessions to export.", { type: "warning" });
            return;
        }
        const conflicts = this.state.holidayIndicators?.slot_conflicts || {};
        const headers = ["Date", "Start Time", "End Time", "Subject", "Section", "Room", "Teacher", "Type", "Enrolled", "Capacity", "Status", "Holiday Note"];
        const rows = slots.map((s) => {
            const cInfo = conflicts[s.id];
            const holidayNote = cInfo ? `Public Holiday: ${cInfo.holiday_name} (${cInfo.holiday_dates})` : (s.on_holiday ? `Public Holiday: ${s.holiday_name || ""}` : "");
            return [
                s.date_str || "",
                s.start_time_str || "",
                s.end_time_str || "",
                `"${(s.subject_name || s.subject || "").replace(/"/g, '""')}"`,
                `"${(s.section_name || s.section_code || "").replace(/"/g, '""')}"`,
                `"${(s.classroom_name || s.room || "").replace(/"/g, '""')}"`,
                `"${(s.teacher_name || s.teacher || "").replace(/"/g, '""')}"`,
                s.session_type || "lecture",
                s.enrolled_student_count || 0,
                s.room_capacity || 0,
                s.status || "upcoming",
                `"${holidayNote.replace(/"/g, '""')}"`,
            ];
        });
        const csvContent = "\uFEFF" + [headers.join(","), ...rows.map((r) => r.join(","))].join("\r\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `Class_Schedule_${this.formatDateISO(new Date())}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    },

    exportICal() {
        const slots = this.filteredSlots;
        if (!slots.length) {
            this.notification.add("No schedule sessions to export.", { type: "warning" });
            return;
        }
        const conflicts = this.state.holidayIndicators?.slot_conflicts || {};
        const lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//University Management//Class Schedule//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ];

        for (const s of slots) {
            if (!s.start_utc_dt || !s.end_utc_dt) continue;
            const startStr = s.start_utc_dt.replace(/[-:]/g, "").replace(".000", "");
            const endStr = s.end_utc_dt.replace(/[-:]/g, "").replace(".000", "");
            const uid = `session-${s.id}-${Date.now()}@university`;
            const cInfo = conflicts[s.id];
            const holidayNote = cInfo ? `\\n[Public Holiday: ${cInfo.holiday_name}]` : "";

            lines.push("BEGIN:VEVENT");
            lines.push(`UID:${uid}`);
            lines.push(`DTSTAMP:${this.formatDateISO(new Date()).replace(/-/g, "")}T000000Z`);
            lines.push(`DTSTART:${startStr}`);
            lines.push(`DTEND:${endStr}`);
            lines.push(`SUMMARY:${s.subject_name || "Class"} (${s.section_name || ""})`);
            lines.push(`LOCATION:${s.classroom_name || ""}`);
            lines.push(`DESCRIPTION:Teacher: ${s.teacher_name || ""}\\nType: ${s.session_type || ""}${holidayNote}`);
            lines.push("STATUS:CONFIRMED");
            lines.push("END:VEVENT");
        }

        lines.push("END:VCALENDAR");
        const icsContent = lines.join("\r\n");
        const blob = new Blob([icsContent], { type: "text/calendar;charset=utf-8;" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `Class_Schedule_${this.formatDateISO(new Date())}.ics`;
        link.click();
        URL.revokeObjectURL(link.href);
    },
});
