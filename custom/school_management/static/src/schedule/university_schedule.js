/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class UniversitySchedule extends Component {
    static template = "school_management.UniversitySchedule";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        const actionContext = this.props.action?.context || this.props.context || {};
        const initialSectionId = actionContext.default_section_id || actionContext.filters?.section_id || "";

        const today = new Date();
        this.state = useState({
            currentDate: today,
            viewMode: "week", // 'week' | 'day' | 'resource'
            colorBy: "subject", // 'subject' | 'teacher' | 'classroom'
            loading: true,
            role: "student", // 'student' | 'teacher' | 'admin'
            unlinkedProfileMessage: "",
            slots: [],
            holidays: [],
            assignmentMarkers: [],
            examMarkers: [],
            nextClass: null,
            studentInfo: null,
            teacherInfo: null,
            weeklyTeachingHours: 0,
            filtersData: {
                subjects: [],
                classrooms: [],
                sections: [],
                teachers: [],
                semesters: [],
                faculties: [],
                programs: [],
            },
            filters: {
                faculty_id: "",
                program_id: "",
                semester_id: "",
                teacher_id: "",
                section_id: initialSectionId ? String(initialSectionId) : "",
                classroom_id: "",
                subject_id: "",
                session_type: "",
            },
            searchTerm: "",
            showGaps: true,
            showInactive: false,
            tableFilter: "available", // 'available' | 'all'
            selectedSlot: null,
            hoveredSlotId: null,
            activeNoteInput: "",
            isRescheduling: false,
            rescheduleForm: {
                date: "",
                start_time: "09:00",
                end_time: "10:30",
                classroom_id: "",
            },
            currentTime: new Date(),
        });

        this.timeInterval = null;

        onWillStart(async () => {
            await this.loadScheduleData();
        });

        onMounted(() => {
            this.timeInterval = setInterval(() => {
                this.state.currentTime = new Date();
            }, 60000);
        });

        onWillUnmount(() => {
            if (this.timeInterval) {
                clearInterval(this.timeInterval);
            }
        });
    }

    // =========================================================================
    // Date Helpers & Navigation
    // =========================================================================

    formatDateISO(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, "0");
        const d = String(date.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
    }

    getBoundsForView() {
        const base = new Date(this.state.currentDate);
        if (this.state.viewMode === "day") {
            const dateStr = this.formatDateISO(base);
            return { start: dateStr, end: dateStr };
        } else {
            // Week / Resource (Mon - Sun)
            const dayOfWeek = base.getDay(); // 0 is Sun, 1 is Mon
            const distanceToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
            const monday = new Date(base);
            monday.setDate(base.getDate() + distanceToMonday);

            const sunday = new Date(monday);
            sunday.setDate(monday.getDate() + 6);

            return {
                start: this.formatDateISO(monday),
                end: this.formatDateISO(sunday),
            };
        }
    }

    get headerTitle() {
        const base = this.state.currentDate;
        if (this.state.viewMode === "day") {
            return base.toLocaleDateString(undefined, {
                weekday: "long",
                month: "short",
                day: "numeric",
                year: "numeric",
            });
        } else {
            const bounds = this.getBoundsForView();
            const sParts = bounds.start.split("-");
            const eParts = bounds.end.split("-");
            const sDate = new Date(sParts[0], sParts[1] - 1, sParts[2]);
            const eDate = new Date(eParts[0], eParts[1] - 1, eParts[2]);
            return `${sDate.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })} – ${eDate.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" })}`;
        }
    }

    get currentTermLabel() {
        const d = this.state.currentDate;
        const year = d.getFullYear();
        const month = d.getMonth() + 1;
        if (month >= 8 && month <= 12) {
            return `${year} Fall Term (Sept – Dec)`;
        } else if (month >= 1 && month <= 5) {
            return `${year} Spring Term (Jan – May)`;
        } else {
            return `${year} Summer Term (Jun – Aug)`;
        }
    }

    async prev() {
        const d = new Date(this.state.currentDate);
        if (this.state.viewMode === "day") {
            d.setDate(d.getDate() - 1);
        } else {
            d.setDate(d.getDate() - 7);
        }
        this.state.currentDate = d;
        await this.loadScheduleData();
    }

    async next() {
        const d = new Date(this.state.currentDate);
        if (this.state.viewMode === "day") {
            d.setDate(d.getDate() + 1);
        } else {
            d.setDate(d.getDate() + 7);
        }
        this.state.currentDate = d;
        await this.loadScheduleData();
    }

    async today() {
        this.state.currentDate = new Date();
        await this.loadScheduleData();
    }

    async setViewMode(mode) {
        this.state.viewMode = mode;
        await this.loadScheduleData();
    }

    setColorBy(colorBy) {
        this.state.colorBy = colorBy;
    }

    // =========================================================================
    // Data Loading & Filtering
    // =========================================================================

    async loadScheduleData() {
        this.state.loading = true;
        try {
            const bounds = this.getBoundsForView();
            const res = await this.orm.call(
                "university.timetable.slot",
                "get_schedule_view_data",
                [bounds.start, bounds.end, this.state.filters]
            );

            if (res.error === "no_linked_profile") {
                this.state.unlinkedProfileMessage = res.message || "Profile not linked.";
            } else {
                this.state.unlinkedProfileMessage = "";
            }

            this.state.role = res.role || "student";
            this.state.slots = res.slots || [];
            this.state.holidays = res.holidays || [];
            this.state.assignmentMarkers = res.assignment_markers || [];
            this.state.examMarkers = res.exam_markers || [];
            this.state.nextClass = res.next_class || null;
            this.state.studentInfo = res.student_info || null;
            this.state.teacherInfo = res.teacher_info || null;
            this.state.weeklyTeachingHours = res.weekly_teaching_hours || 0;
            this.state.filtersData = res.filters_data || {
                subjects: [],
                classrooms: [],
                sections: [],
                teachers: [],
                semesters: [],
                faculties: [],
                programs: [],
            };

            if (this.state.selectedSlot) {
                const refreshed = this.state.slots.find((s) => s.id === this.state.selectedSlot.id);
                if (refreshed) {
                    this.state.selectedSlot = refreshed;
                    this.state.activeNoteInput = refreshed.notes || "";
                }
            }
        } catch (err) {
            console.error("Error loading schedule data:", err);
            this.notification.add("Could not load schedule data. Please try again.", {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async onFilterChange(field, ev) {
        this.state.filters[field] = ev.target.value;
        await this.loadScheduleData();
    }

    async clearAllFilters() {
        this.state.filters = {
            faculty_id: "",
            program_id: "",
            semester_id: "",
            teacher_id: "",
            section_id: "",
            classroom_id: "",
            subject_id: "",
            session_type: "",
        };
        this.state.searchTerm = "";
        await this.loadScheduleData();
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value.toLowerCase();
    }

    toggleShowGaps() {
        this.state.showGaps = !this.state.showGaps;
    }

    toggleShowInactive() {
        this.state.showInactive = !this.state.showInactive;
    }

    setTableFilter(filter) {
        this.state.tableFilter = filter;
    }

    // =========================================================================
    // KPI Stat Computations
    // =========================================================================

    get filteredSlots() {
        let list = this.state.slots;
        if (!this.state.showInactive) {
            list = list.filter((s) => s.state !== "cancelled" && s.status !== "cancelled");
        }
        if (this.state.searchTerm) {
            const term = this.state.searchTerm;
            list = list.filter((s) =>
                (s.subject_name && s.subject_name.toLowerCase().includes(term)) ||
                (s.subject_code && s.subject_code.toLowerCase().includes(term)) ||
                (s.section_name && s.section_name.toLowerCase().includes(term)) ||
                (s.teacher_name && s.teacher_name.toLowerCase().includes(term)) ||
                (s.classroom_name && s.classroom_name.toLowerCase().includes(term))
            );
        }
        return list;
    }

    get kpiClassesCount() {
        return this.filteredSlots.length;
    }

    get kpiEnrolledCount() {
        return this.filteredSlots.reduce((acc, s) => acc + (s.enrolled_student_count || 0), 0);
    }

    get kpiCapacityCount() {
        return this.filteredSlots.reduce((acc, s) => acc + (s.room_capacity || 0), 0);
    }

    // =========================================================================
    // Right Table: Classes With Available Spaces
    // =========================================================================

    get tableClasses() {
        const slots = this.filteredSlots;
        if (this.state.tableFilter === "available") {
            return slots.filter((s) => (s.room_capacity > 0 && s.enrolled_student_count < s.room_capacity));
        }
        return slots;
    }

    get availableSpacesCount() {
        return this.filteredSlots.filter((s) => (s.room_capacity > 0 && s.enrolled_student_count < s.room_capacity)).length;
    }

    // =========================================================================
    // Week Grid Layout & Time Calculation
    // =========================================================================

    get timeHours() {
        // Dynamic time bounds (8:00 to 20:00)
        return [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];
    }

    get weekDays() {
        const bounds = this.getBoundsForView();
        const start = new Date(bounds.start + "T00:00:00");
        const days = [];
        const todayStr = this.formatDateISO(new Date());

        const numDays = this.state.viewMode === "day" ? 1 : 7;
        const currentRef = this.state.viewMode === "day" ? new Date(this.state.currentDate) : start;

        for (let i = 0; i < numDays; i++) {
            const d = new Date(currentRef);
            if (this.state.viewMode !== "day") {
                d.setDate(start.getDate() + i);
            }
            const dateStr = this.formatDateISO(d);
            const isToday = dateStr === todayStr;

            const daySlots = this.filteredSlots
                .filter((s) => s.date_str === dateStr)
                .sort((a, b) => (a.start_hour_decimal > b.start_hour_decimal ? 1 : -1));

            const dayHoliday = (this.state.holidays || []).find(
                (h) => h.date_start <= dateStr && dateStr <= h.date_end
            );

            days.push({
                date: d,
                dateStr: dateStr,
                dayName: d.toLocaleDateString(undefined, { weekday: "short" }),
                fullDayName: d.toLocaleDateString(undefined, { weekday: "long" }),
                dayNumber: d.getDate(),
                formattedDate: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
                isToday: isToday,
                slots: daySlots,
                hasSlots: daySlots.length > 0,
                holiday: dayHoliday || null,
            });
        }
        return days;
    }

    get resourceClassrooms() {
        const rooms = this.state.filtersData.classrooms || [];
        const slots = this.filteredSlots;
        const days = this.weekDays;

        return rooms.map((room) => {
            const roomSlots = slots.filter((s) => s.classroom_id === room.id);
            const dayMap = {};
            days.forEach((day) => {
                dayMap[day.dateStr] = roomSlots.filter((s) => s.date_str === day.dateStr);
            });
            return {
                id: room.id,
                name: room.name,
                building: room.building || "Campus",
                slots: roomSlots,
                dayMap: dayMap,
                totalSlots: roomSlots.length,
            };
        });
    }

    get currentTimeMarkerPosition() {
        const now = this.state.currentTime;
        const hour = now.getHours();
        const minute = now.getMinutes();
        const decimal = hour + minute / 60.0;
        if (decimal < 8.0 || decimal > 20.0) {
            return null;
        }
        return ((decimal - 8.0) / 12.0) * 100;
    }

    get currentTimeFormatted() {
        return this.state.currentTime.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    getSlotStyle(slot) {
        // Calculate top & height in 8:00 - 20:00 range (12 hours total)
        const startH = Math.max(8.0, Math.min(20.0, slot.start_hour_decimal || 8.0));
        const endH = Math.max(8.0, Math.min(20.0, slot.end_hour_decimal || (startH + 1.0)));
        const durationHours = Math.max(0.4, endH - startH);

        const topPercent = ((startH - 8.0) / 12.0) * 100;
        const heightPercent = Math.max(4.0, (durationHours / 12.0) * 100);

        return `top: ${topPercent}%; height: calc(${heightPercent}% - 3px);`;
    }

    getSlotDayShort(slot) {
        try {
            const [y, m, d] = slot.date_str.split("-").map((v) => parseInt(v, 10));
            const dateObj = new Date(y, m - 1, d);
            return dateObj.toLocaleDateString(undefined, { weekday: "short" });
        } catch {
            return "Day";
        }
    }

    getSlotColorClass(slot) {
        if (slot.session_type === "lab") return "o_slot_palette_teal";
        if (slot.session_type === "exam") return "o_slot_palette_amber";

        const palettes = [
            "o_slot_palette_purple",
            "o_slot_palette_indigo",
            "o_slot_palette_sapphire",
            "o_slot_palette_emerald",
        ];

        let seed = slot.subject_id || 0;
        if (this.state.colorBy === "teacher") {
            seed = slot.teacher_id || 0;
        } else if (this.state.colorBy === "classroom") {
            seed = slot.classroom_id || 0;
        }
        return palettes[Math.abs(seed) % palettes.length];
    }

    getStatusBadgeClass(status) {
        switch (status) {
            case "ongoing":
                return "badge bg-warning text-dark border";
            case "completed":
                return "badge bg-success-subtle text-success border border-success-subtle";
            case "cancelled":
                return "badge bg-danger-subtle text-danger border border-danger-subtle";
            case "upcoming":
            default:
                return "badge bg-primary-subtle text-primary border border-primary-subtle";
        }
    }

    // =========================================================================
    // Interactive Selection & Offcanvas
    // =========================================================================

    openSlotSidePanel(slot) {
        this.state.selectedSlot = slot;
        this.state.activeNoteInput = slot.notes || "";
        this.state.isRescheduling = false;
    }

    openSlotById(slotId) {
        const slot = this.state.slots.find((s) => s.id === slotId);
        if (slot) {
            this.openSlotSidePanel(slot);
        }
    }

    closeSlotSidePanel() {
        this.state.selectedSlot = null;
        this.state.isRescheduling = false;
    }

    onHoverSlot(slotId) {
        this.state.hoveredSlotId = slotId;
    }

    onLeaveSlot() {
        this.state.hoveredSlotId = null;
    }

    // =========================================================================
    // Actions: + Add Class, Attendance, Notes, Materials
    // =========================================================================

    async addClass() {
        if (this.state.role !== "admin") return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Schedule Class Session",
            res_model: "university.timetable.slot",
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
        }, {
            onClose: async () => {
                await this.loadScheduleData();
            },
        });
    }

    async takeAttendance(slot) {
        try {
            const action = await this.orm.call(
                "university.timetable.slot",
                "action_track_attendance",
                [[slot.id]]
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch (err) {
            this.notification.add(err.message || "Failed to launch attendance tracker.", {
                type: "danger",
            });
        }
    }

    async saveSlotNotes() {
        if (!this.state.selectedSlot) return;
        try {
            await this.orm.call(
                "university.timetable.slot",
                "action_save_notes",
                [[this.state.selectedSlot.id], this.state.activeNoteInput]
            );
            this.state.selectedSlot.notes = this.state.activeNoteInput;
            this.notification.add("Session notes saved.", {
                type: "success",
            });
        } catch (err) {
            this.notification.add(err.message || "Could not save notes.", {
                type: "danger",
            });
        }
    }

    async openMaterials(slot) {
        try {
            const action = await this.orm.call(
                "university.timetable.slot",
                "action_upload_material",
                [[slot.id]]
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch (err) {
            this.notification.add("Could not open course materials.", { type: "danger" });
        }
    }

    async openAssignments(slot) {
        try {
            const action = await this.orm.call(
                "university.timetable.slot",
                "action_view_assignments",
                [[slot.id]]
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch (err) {
            this.notification.add("Could not open course assignments.", { type: "danger" });
        }
    }

    openClassSection(sectionId) {
        if (!sectionId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Class Section Details",
            res_model: "university.class.section",
            res_id: sectionId,
            views: [[false, "form"]],
            view_mode: "form",
        });
    }

    // =========================================================================
    // Export Functions: iCal, CSV/Excel, PDF
    // =========================================================================

    exportICal() {
        const slots = this.filteredSlots;
        if (!slots.length) {
            this.notification.add("No schedule sessions to export.", { type: "warning" });
            return;
        }
        const formatDT = (dtStr) => {
            if (!dtStr) return "";
            return dtStr.replace(/[-:]/g, "").replace(" ", "T") + "Z";
        };

        const ics = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//University Management//Timetable//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ];
        for (const s of slots) {
            ics.push("BEGIN:VEVENT");
            ics.push(`UID:session-${s.id}@university.edu`);
            ics.push(`DTSTAMP:${formatDT(new Date().toISOString())}`);
            ics.push(`DTSTART:${formatDT(s.start || s.start_time)}`);
            ics.push(`DTEND:${formatDT(s.end || s.end_time)}`);
            ics.push(`SUMMARY:${(s.subject_name || s.subject || "Class")} (${s.section_name || s.section_code || "Section"})`);
            ics.push(`LOCATION:${s.classroom_name || s.room || "Room TBA"}`);
            ics.push(`DESCRIPTION:Instructor: ${s.teacher_name || s.teacher || "TBA"}\\nStatus: ${s.status || "Scheduled"}`);
            ics.push("END:VEVENT");
        }
        ics.push("END:VCALENDAR");

        const blob = new Blob([ics.join("\r\n")], { type: "text/calendar;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `university_schedule_${this.formatDateISO(new Date())}.ics`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        this.notification.add("iCal calendar exported successfully.", { type: "success" });
    }

    exportExcel() {
        const slots = this.filteredSlots;
        if (!slots.length) {
            this.notification.add("No schedule sessions to export.", { type: "warning" });
            return;
        }
        const headers = ["Date", "Start Time", "End Time", "Subject", "Section", "Room", "Teacher", "Type", "Enrolled", "Capacity", "Status"];
        const rows = slots.map((s) => [
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
        ]);
        const csvContent = "\uFEFF" + [headers.join(","), ...rows.map((r) => r.join(","))].join("\r\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `university_schedule_${this.formatDateISO(new Date())}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        this.notification.add("Schedule exported to CSV/Excel successfully.", { type: "success" });
    }

    exportPDF() {
        window.print();
    }
}

registry.category("actions").add("university_schedule_view", UniversitySchedule);
export default UniversitySchedule;
