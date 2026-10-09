/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { onWillStart, onWillUpdateProps, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

patch(CalendarCommonRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.isTimetableModel) {
            this.orm = useService("orm");
            this.calendarHolidays = [];
            this.timetableSlotMinTime = "07:00:00";
            this.timetableSlotMaxTime = "20:00:00";
            this.timetableConfigLoaded = false;

            onWillStart(async () => {
                await this.loadTimetableExtras();
            });

            onWillUpdateProps(async () => {
                await this.loadTimetableExtras();
            });

            useEffect(
                () => {
                    const container = this.fc?.el?.closest(".o_calendar_container");
                    if (container) {
                        container.classList.add("o_timetable_calendar_view");
                        return () => container.classList.remove("o_timetable_calendar_view");
                    }
                },
                () => [this.fc?.el]
            );
        }
    },

    get isTimetableModel() {
        return this.props?.model?.resModel === "university.timetable.slot";
    },

    get options() {
        const options = super.options;
        if (this.isTimetableModel) {
            const minTime = this.timetableSlotMinTime || "07:00:00";
            const maxTime = this.timetableSlotMaxTime || "20:00:00";
            options.slotMinTime = minTime;
            options.slotMaxTime = maxTime;
            options.scrollTime = minTime;
        }
        return options;
    },

    viewDidMount({ el, view }) {
        super.viewDidMount(...arguments);
        if (this.isTimetableModel && el) {
            const container = el.closest(".o_calendar_container");
            if (container) {
                container.classList.add("o_timetable_calendar_view");
            }
        }
    },

    eventClassNames({ el, event }) {
        const classesToAdd = super.eventClassNames({ el, event });
        if (this.isTimetableModel) {
            const record = this.props.model.records[event.id];
            if (record?.rawRecord?.has_conflict) {
                classesToAdd.push("o_timetable_slot_conflict");
            }
        }
        return classesToAdd;
    },

    mapRecordsToEvents() {
        const events = super.mapRecordsToEvents();
        if (this.isTimetableModel && this.calendarHolidays?.length) {
            for (const h of this.calendarHolidays) {
                const endDate = luxon.DateTime.fromISO(h.date_end).plus({ days: 1 }).toISODate();
                // 1. All-day title banner at top
                events.push({
                    id: `holiday_banner_${h.id}`,
                    title: `🏖️ ${h.name}`,
                    start: h.date_start,
                    end: endDate,
                    allDay: true,
                    editable: false,
                    display: "block",
                    classNames: ["o_timetable_holiday_event"],
                });
                // 2. Full-day background shading across the column
                events.push({
                    id: `holiday_bg_${h.id}`,
                    start: h.date_start,
                    end: endDate,
                    allDay: true,
                    display: "background",
                    classNames: ["o_timetable_holiday_bg"],
                });
            }
        }
        return events;
    },

    onClick(info) {
        if (this.isTimetableModel && String(info.event?.id || "").startsWith("holiday_")) {
            return;
        }
        super.onClick(...arguments);
    },

    onEventClick(info) {
        if (this.isTimetableModel && String(info.event?.id || "").startsWith("holiday_")) {
            return;
        }
        super.onEventClick(...arguments);
    },

    async loadTimetableExtras() {
        if (!this.isTimetableModel) return;
        try {
            if (!this.timetableConfigLoaded && this.orm) {
                const config = await this.orm.call(
                    "university.timetable.slot",
                    "get_calendar_config",
                    []
                );
                if (config) {
                    this.timetableSlotMinTime = config.slot_min_time || "07:00:00";
                    this.timetableSlotMaxTime = config.slot_max_time || "20:00:00";
                    if (this.fc?.api) {
                        this.fc.api.setOption("slotMinTime", this.timetableSlotMinTime);
                        this.fc.api.setOption("slotMaxTime", this.timetableSlotMaxTime);
                        this.fc.api.setOption("scrollTime", this.timetableSlotMinTime);
                    }
                }
                this.timetableConfigLoaded = true;
            }

            if (this.orm && this.props.model?.date) {
                const date = this.props.model.date;
                const startRange = date.minus({ months: 1 }).toISODate();
                const endRange = date.plus({ months: 1 }).toISODate();
                const holidays = await this.orm.call(
                    "university.timetable.slot",
                    "get_calendar_holidays",
                    [],
                    {
                        start_date: startRange,
                        end_date: endRange,
                    }
                );
                this.calendarHolidays = holidays || [];
                if (this.fc?.api) {
                    this.fc.api.refetchEvents();
                }
            }
        } catch (err) {
            console.error("Error loading timetable calendar extras:", err);
        }
    },
});
