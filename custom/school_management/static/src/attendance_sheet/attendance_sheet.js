/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

const STATUS_OPTIONS = [
    { value: "present", label: "Present", key: "P" },
    { value: "absent", label: "Absent", key: "A" },
    { value: "late", label: "Late", key: "L" },
    { value: "permission", label: "Permission", key: "E" },
];

const FILTERS = [
    { value: "all", label: "All" },
    { value: "absent", label: "Absent" },
    { value: "late", label: "Late" },
    { value: "permission", label: "Permission" },
];

const AVATAR_TONES = 4;

function today() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function clockTime(value) {
    if (!value) {
        return "";
    }
    const match = String(value).match(/(\d{2}):(\d{2})/);
    return match ? `${match[1]}:${match[2]}` : "";
}

function initials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) {
        return "?";
    }
    const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
    return `${parts[0][0]}${last}`.toUpperCase();
}

function nameTone(name) {
    let sum = 0;
    for (const character of String(name || "")) {
        sum += character.charCodeAt(0);
    }
    return sum % AVATAR_TONES;
}

class AttendanceSheet extends Component {
    static template = "school_management.AttendanceSheet";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        const context = this.props.action?.context || {};

        this.statusOptions = STATUS_OPTIONS;
        this.filters = FILTERS;
        this.rootRef = useRef("root");
        this._baseline = "";
        this._pendingFocus = null;

        this.state = useState({
            date: context.default_date || context.date || today(),
            sectionId: Number(context.default_section_id || context.section_id || 0) || 0,
            sections: [],
            lines: [],
            taken: false,
            lastSaved: "",
            loading: false,
            saving: false,
            error: null,
            query: "",
            filter: "all",
            activeId: false,
            openNoteId: false,
        });

        // Restore DOM focus after a re-render so keyboard flows are not broken.
        useEffect(() => {
            const selector = this._pendingFocus;
            if (!selector || !this.rootRef.el) {
                return;
            }
            this._pendingFocus = null;
            const node = this.rootRef.el.querySelector(selector);
            if (node) {
                node.focus();
                if (node.type === "text") {
                    node.setSelectionRange(node.value.length, node.value.length);
                }
            }
        });

        this._onKeydown = (ev) => this.onGlobalKeydown(ev);
        document.addEventListener("keydown", this._onKeydown);
        onWillUnmount(() => document.removeEventListener("keydown", this._onKeydown));

        onWillStart(async () => {
            await this.loadSections();
            const passedId = Number(context.default_section_id || context.section_id || 0) || 0;
            if (passedId && this.state.sections.some(s => s.id === passedId)) {
                this.state.sectionId = passedId;
            } else {
                this.state.sectionId = this.state.sections.length
                    ? this.state.sections[0].id
                    : 0;
            }
            if (this.state.sectionId) {
                await this.loadSheet();
            }
        });
    }

    // ------------------------------------------------------------------
    // Derived data
    // ------------------------------------------------------------------
    get counts() {
        const counts = { present: 0, absent: 0, late: 0, total: this.state.lines.length };
        for (const line of this.state.lines) {
            counts[line.status] = (counts[line.status] || 0) + 1;
        }
        return counts;
    }

    get currentSectionName() {
        const sec = this.state.sections.find(s => s.id === this.state.sectionId);
        return sec ? sec.display_name : "";
    }

    get visibleLines() {
        const query = this.state.query.trim().toLowerCase();
        if (!query && this.state.filter === "all") {
            return this.state.lines;
        }
        return this.state.lines.filter((line) => {
            if (this.state.filter === "absent" && line.status !== "absent") {
                return false;
            }
            if (this.state.filter === "late" && line.status !== "late") {
                return false;
            }
            if (!query) {
                return true;
            }
            return (
                (line.name || "").toLowerCase().includes(query) ||
                (line.code || "").toLowerCase().includes(query)
            );
        });
    }

    get activeStudent() {
        const visible = this.visibleLines;
        return visible.find((line) => line.student_id === this.state.activeId) || visible[0] || null;
    }

    get isDirty() {
        return this._baseline !== this.snapshot();
    }

    get isEmpty() {
        return !this.state.loading && !this.state.sectionId && !this.state.lines.length;
    }

    get noStudents() {
        return (
            !this.state.loading &&
            !!this.state.sectionId &&
            !this.state.lines.length
        );
    }

    get hasNoMatch() {
        return !this.state.loading && !!this.state.lines.length && !this.visibleLines.length;
    }

    snapshot() {
        return JSON.stringify(
            this.state.lines.map((line) => [line.student_id, line.status, line.remark || ""])
        );
    }

    // ------------------------------------------------------------------
    // Data loading
    // ------------------------------------------------------------------
    async loadSections() {
        this.state.sections = await this.orm.searchRead(
            "university.class.section",
            [["active", "=", true]],
            ["display_name"],
            { order: "name asc" }
        );
    }

    applySheet(sheet) {
        this.state.taken = Boolean(sheet.taken);
        this.state.lastSaved = clockTime(sheet.last_saved_at);
        this.state.lines = (sheet.lines || []).map((line) => ({
            ...line,
            showRemark: Boolean(line.remark),
        }));
        this.state.activeId = this.state.lines.length ? this.state.lines[0].student_id : false;
        this.state.openNoteId = false;
        this._baseline = this.snapshot();
    }

    async loadSheet() {
        if (!this.state.sectionId || !this.state.date) {
            this.state.lines = [];
            this.state.taken = false;
            this.state.lastSaved = "";
            this.state.activeId = false;
            this._baseline = this.snapshot();
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        try {
            const sheet = await this.orm.call("university.attendance", "get_sheet", [
                this.state.sectionId,
                this.state.date,
            ]);
            this.applySheet(sheet);
        } catch (error) {
            this.state.error = error.message || _t("Unable to load attendance.");
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------
    // Header controls
    // ------------------------------------------------------------------
    onBack() {
        if (this.env.config?.historyBack) {
            this.env.config.historyBack();
        } else {
            this.action.doAction("school_management.action_university_attendance");
        }
    }

    async onDateChange(ev) {
        this.state.date = ev.target.value;
        await this.loadSheet();
    }

    async onSectionChange(ev) {
        this.state.sectionId = Number(ev.target.value) || 0;
        await this.loadSheet();
    }

    // ------------------------------------------------------------------
    // Toolbar
    // ------------------------------------------------------------------
    onSearchInput(ev) {
        this.state.query = ev.target.value;
    }

    setFilter(value) {
        this.state.filter = value;
    }

    filterCount(filter) {
        const counts = this.counts;
        if (filter === "all") {
            return counts.total;
        }
        return counts[filter] || 0;
    }

    // ------------------------------------------------------------------
    // Attendance selection
    // ------------------------------------------------------------------
    setStatus(line, status) {
        this.state.activeId = line.student_id;
        if (line.status !== status) {
            line.status = status;
        }
    }

    setActive(line) {
        this.state.activeId = line.student_id;
    }

    markAllPresent() {
        for (const line of this.state.lines) {
            line.status = "present";
        }
    }

    studentInitial(line) {
        return initials(line.name);
    }

    studentTone(line) {
        return nameTone(line.name);
    }

    studentImageUrl(line) {
        const field = line.image_field || "image_1920";
        return `/web/image/${line.student_model || "university.student"}/${line.student_id}/${field}`;
    }

    // ------------------------------------------------------------------
    // Notes
    // ------------------------------------------------------------------
    toggleRemark(line) {
        const isOpen = this.state.openNoteId === line.student_id;
        this.state.activeId = line.student_id;
        this.state.openNoteId = isOpen ? false : line.student_id;
        this._pendingFocus = isOpen ? null : ".o_att_note_input";
    }

    closeRemark() {
        this.state.openNoteId = false;
    }

    updateRemark(line, ev) {
        line.remark = ev.target.value;
    }

    clearRemark(line) {
        line.remark = "";
        this._pendingFocus = ".o_att_note_input";
    }

    onNoteKeydown(line, ev) {
        if (ev.key === "Enter" || ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.closeRemark();
        }
    }

    // ------------------------------------------------------------------
    // Keyboard
    // ------------------------------------------------------------------
    statusButtonSelector(studentId, status) {
        return `.o_att_seg__btn[data-student="${studentId}"][data-status="${status}"]`;
    }

    onSegKeydown(line, ev) {
        // Left/Right move within the radiogroup; Up/Down are left to the
        // document handler so they can walk between student rows.
        if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const current = this.statusOptions.findIndex(
            (option) => option.value === ev.target.dataset.status
        );
        const step = ev.key === "ArrowRight" ? 1 : -1;
        const next = this.statusOptions[(current + step + this.statusOptions.length) % this.statusOptions.length];
        this.setStatus(line, next.value);
        this._pendingFocus = this.statusButtonSelector(line.student_id, next.value);
    }

    focusDescriptor() {
        const active = this.rootRef.el ? this.rootRef.el.ownerDocument.activeElement : null;
        if (!active || !this.rootRef.el || !this.rootRef.el.contains(active)) {
            return null;
        }
        if (active.classList.contains("o_att_seg__btn")) {
            return this.statusButtonSelector(active.dataset.student, active.dataset.status);
        }
        if (active.classList.contains("o_att_note_input")) {
            return ".o_att_note_input";
        }
        return null;
    }

    onGlobalKeydown(ev) {
        const target = ev.target;
        const tag = (target.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable) {
            return;
        }
        if (ev.ctrlKey || ev.metaKey || ev.altKey) {
            return;
        }
        if (this.state.saving || this.state.loading || !this.state.lines.length) {
            return;
        }

        if (ev.key === "Escape" && this.state.openNoteId) {
            ev.preventDefault();
            this.closeRemark();
            return;
        }

        const visible = this.visibleLines;
        if (!visible.length) {
            return;
        }

        let index = visible.findIndex((line) => line.student_id === this.state.activeId);
        if (index < 0) {
            index = 0;
        }

        const focus = this.focusDescriptor();

        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const next = ev.key === "ArrowDown" ? index + 1 : index - 1;
            this.state.activeId = visible[Math.min(Math.max(next, 0), visible.length - 1)].student_id;
            this._pendingFocus = focus;
            return;
        }

        const option = this.statusOptions.find(
            (item) => item.key.toLowerCase() === ev.key.toLowerCase()
        );
        if (!option) {
            return;
        }

        ev.preventDefault();
        visible[index].status = option.value;
        this.state.activeId =
            index < visible.length - 1 ? visible[index + 1].student_id : visible[index].student_id;
        this._pendingFocus = focus;
    }

    // ------------------------------------------------------------------
    // Save
    // ------------------------------------------------------------------
    async saveAttendance() {
        if (!this.state.sectionId || !this.state.date || !this.state.lines.length) {
            return;
        }
        this.state.saving = true;
        this.state.error = null;
        try {
            const payload = this.state.lines.map((line) => ({
                student_id: line.student_id,
                status: line.status,
                remark: line.remark || "",
            }));
            const sheet = await this.orm.call("university.attendance", "save_sheet", [
                this.state.sectionId,
                this.state.date,
                payload,
            ]);
            this.applySheet(sheet);
            const counts = this.counts;
            const sectionName =
                this.state.sections.find((s) => s.id === this.state.sectionId)?.display_name || "";
            this.notification.add(
                sectionName ? `${_t("Attendance saved for")} ${sectionName}` : _t("Attendance saved"),
                {
                    type: "success",
                    message: `${counts.total} ${_t("students")} · ${counts.present} ${_t("present")} · ${counts.absent} ${_t("absent")} · ${counts.late} ${_t("late")}`,
                }
            );
        } catch (error) {
            this.state.error = error.message || _t("Unable to save attendance.");
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("university_attendance_sheet", AttendanceSheet);

export default AttendanceSheet;
