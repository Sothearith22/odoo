/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const STATUS_OPTIONS = [
    { value: "present", label: "Present",  key: "P", icon: "fa-check" },
    { value: "absent",  label: "Absent",   key: "A", icon: "fa-times" },
    { value: "late",    label: "Late",     key: "L", icon: "fa-clock-o" },
    { value: "leave",   label: "On Leave", key: "E", icon: "fa-plane" },
];

const FILTERS = [
    { value: "all",    label: "All" },
    { value: "absent", label: "Absent" },
    { value: "late",   label: "Late" },
    { value: "leave",  label: "On Leave" },
];

function today() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function clockTime(value) {
    if (!value) return "";
    if (value instanceof Date) {
        const pad = (n) => String(n).padStart(2, "0");
        return `${pad(value.getHours())}:${pad(value.getMinutes())}`;
    }
    const match = String(value).match(/(\d{2}):(\d{2})/);
    return match ? `${match[1]}:${match[2]}` : "";
}

function initials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
    return `${parts[0][0]}${last}`.toUpperCase();
}

function nameTone(name) {
    let sum = 0;
    for (const c of String(name || "")) sum += c.charCodeAt(0);
    return sum % 4;
}

function fmtHours(h) {
    if (!h || h <= 0) return "—";
    const hrs = Math.floor(h);
    const mins = Math.round((h - hrs) * 60);
    if (hrs === 0) return `${mins}m`;
    return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
}

class StaffAttendanceSheet extends Component {
    static template = "school_management.StaffAttendanceSheet";
    static props = ["*"];

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");
        this.action       = useService("action");
        this.rootRef      = useRef("root");
        this._baseline    = "";
        this._pendingFocus = null;

        this.statusOptions = STATUS_OPTIONS;
        this.filters       = FILTERS;

        const context = this.props.action?.context || {};

        this.state = useState({
            date:         context.default_date || context.date || today(),
            departmentId: context.default_department_id || context.department_id || "",
            departments:  [],
            lines:        [],
            taken:        false,
            lastSaved:    "",
            loading:      false,
            saving:       false,
            error:        null,
            query:        "",
            filter:       "all",
            activeId:     false,
            openNoteId:   false,
            isAdmin:      true,
        });

        useEffect(() => {
            const sel = this._pendingFocus;
            if (!sel || !this.rootRef.el) return;
            this._pendingFocus = null;
            const node = this.rootRef.el.querySelector(sel);
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
            // Check Admin authorization
            try {
                const isSystem = await user.hasGroup("base.group_system");
                const isSchoolAdmin = await user.hasGroup("school_management.group_school_admin");
                this.state.isAdmin = Boolean(isSystem || isSchoolAdmin);
            } catch {
                this.state.isAdmin = false;
            }

            // Fetch active departments
            try {
                this.state.departments = await this.orm.searchRead(
                    "university.department",
                    [["active", "=", true]],
                    ["id", "display_name"],
                    { order: "name asc" }
                );
            } catch (err) {
                this.state.departments = [];
            }

            const passedDept = context.default_department_id || context.department_id;
            if (passedDept) {
                this.state.departmentId = passedDept === "all" ? "all" : Number(passedDept);
                await this.loadSheet();
            }
        });
    }

    // ── Derived Properties ────────────────────────────────────
    get counts() {
        const c = { present: 0, absent: 0, late: 0, leave: 0, total: this.state.lines.length };
        for (const l of this.state.lines) {
            if (c[l.status] !== undefined) {
                c[l.status] += 1;
            }
        }
        return c;
    }

    get currentDepartmentName() {
        if (!this.state.departmentId) return "";
        if (this.state.departmentId === "all") return _t("All Departments");
        const dept = this.state.departments.find((d) => d.id === this.state.departmentId);
        return dept ? dept.display_name : "";
    }

    get visibleLines() {
        const q = this.state.query.trim().toLowerCase();
        const f = this.state.filter;
        return this.state.lines.filter((l) => {
            if (f !== "all" && l.status !== f) return false;
            if (!q) return true;
            return (
                (l.name || "").toLowerCase().includes(q) ||
                (l.code || "").toLowerCase().includes(q) ||
                (l.department || "").toLowerCase().includes(q)
            );
        });
    }

    get isDirty() {
        return this._baseline !== this.snapshot();
    }

    get isEmpty() {
        return !this.state.loading && !this.state.departmentId;
    }

    get noStaff() {
        return !this.state.loading && Boolean(this.state.departmentId) && !this.state.lines.length;
    }

    get hasNoMatch() {
        return !this.state.loading && Boolean(this.state.lines.length) && !this.visibleLines.length;
    }

    snapshot() {
        return JSON.stringify(
            this.state.lines.map((l) => [l.teacher_id, l.status, l.check_in || "", l.check_out || "", l.remark || ""])
        );
    }

    filterCount(filter) {
        const c = this.counts;
        return filter === "all" ? c.total : (c[filter] || 0);
    }

    teacherInitial(line) { return initials(line.name); }
    teacherTone(line)    { return nameTone(line.name); }
    fmtHours(h)          { return fmtHours(h); }

    // ── Data Loading ──────────────────────────────────────────
    async loadSheet() {
        if (!this.state.departmentId || !this.state.date) {
            this.state.lines     = [];
            this.state.taken     = false;
            this.state.lastSaved = "";
            this.state.activeId  = false;
            this._baseline       = this.snapshot();
            return;
        }

        this.state.loading = true;
        this.state.error   = null;

        try {
            // 1. Fetch active teachers
            const teacherDomain = [["active", "=", true]];
            if (this.state.departmentId !== "all") {
                teacherDomain.push(["department_id", "=", Number(this.state.departmentId)]);
            }

            const teachers = await this.orm.searchRead(
                "university.teacher",
                teacherDomain,
                ["id", "display_name", "teacher_id", "department_id", "image_1920"],
                { order: "name asc" }
            );

            // 2. Fetch attendance records for this date
            const attDomain = [["date", "=", this.state.date]];
            if (this.state.departmentId !== "all") {
                attDomain.push(["department_id", "=", Number(this.state.departmentId)]);
            }

            const records = await this.orm.searchRead(
                "university.staff.attendance",
                attDomain,
                ["id", "staff_id", "status", "check_in", "check_out", "worked_hours", "remark", "write_date"],
                {}
            );

            const recMap = {};
            let latestWrite = "";
            for (const r of records) {
                recMap[r.staff_id[0]] = r;
                if (r.write_date && (!latestWrite || r.write_date > latestWrite)) {
                    latestWrite = r.write_date;
                }
            }

            this.state.taken = records.length > 0;
            this.state.lastSaved = latestWrite ? clockTime(latestWrite) : (this.state.taken ? _t("Earlier") : "");

            // 3. Assemble staff rows
            this.state.lines = teachers.map((t) => {
                const rec = recMap[t.id] || null;
                const checkIn  = rec?.check_in  ? rec.check_in.substring(11, 16)  : "";
                const checkOut = rec?.check_out ? rec.check_out.substring(11, 16) : "";
                return {
                    teacher_id:   t.id,
                    record_id:    rec?.id || false,
                    name:         t.display_name,
                    code:         t.teacher_id || "",
                    department:   t.department_id ? t.department_id[1] : "",
                    has_image:    Boolean(t.image_1920),
                    status:       rec?.status || "present",
                    check_in:     checkIn,
                    check_out:    checkOut,
                    worked_hours: rec?.worked_hours || 0,
                    remark:       rec?.remark || "",
                    is_new:       !rec,
                };
            });

            this.state.activeId = this.state.lines.length ? this.state.lines[0].teacher_id : false;
            this.state.openNoteId = false;
            this._baseline = this.snapshot();
        } catch (e) {
            this.state.error = e.message || _t("Unable to load staff attendance.");
        } finally {
            this.state.loading = false;
        }
    }

    // ── Header Controls ───────────────────────────────────────
    async onDepartmentChange(ev) {
        const val = ev.target.value;
        this.state.departmentId = val === "all" ? "all" : (Number(val) || "");
        await this.loadSheet();
    }

    async onDateChange(ev) {
        this.state.date = ev.target.value;
        await this.loadSheet();
    }

    onSearchInput(ev) { this.state.query = ev.target.value; }
    setFilter(v) { this.state.filter = v; }
    clearFilters() { this.state.query = ""; this.state.filter = "all"; }
    setActive(line) { this.state.activeId = line.teacher_id; }

    // ── Status Controls ───────────────────────────────────────
    setStatus(line, status) {
        if (!this.state.isAdmin) return;
        this.state.activeId = line.teacher_id;
        line.status = status;
        // If absent or on leave, clear times & worked hours
        if (status === "absent" || status === "leave") {
            line.check_in     = "";
            line.check_out    = "";
            line.worked_hours = 0;
        }
    }

    markAllPresent() {
        if (!this.state.isAdmin) return;
        for (const l of this.state.lines) {
            l.status = "present";
        }
    }

    // ── Time & Hours ──────────────────────────────────────────
    onCheckInChange(line, ev) {
        if (!this.state.isAdmin) return;
        line.check_in = ev.target.value;
        this._recalcHours(line);
    }

    onCheckOutChange(line, ev) {
        if (!this.state.isAdmin) return;
        line.check_out = ev.target.value;
        this._recalcHours(line);
    }

    _recalcHours(line) {
        if (line.check_in && line.check_out) {
            const [h1, m1] = line.check_in.split(":").map(Number);
            const [h2, m2] = line.check_out.split(":").map(Number);
            const mins = (h2 * 60 + m2) - (h1 * 60 + m1);
            line.worked_hours = mins > 0 ? Number((mins / 60).toFixed(2)) : 0;
        } else {
            line.worked_hours = 0;
        }
    }

    // ── Notes ─────────────────────────────────────────────────
    toggleNote(line) {
        const isOpen = this.state.openNoteId === line.teacher_id;
        this.state.activeId   = line.teacher_id;
        this.state.openNoteId = isOpen ? false : line.teacher_id;
        this._pendingFocus    = isOpen ? null : ".o_satt_note_input";
    }

    closeNote() { this.state.openNoteId = false; }
    updateNote(line, ev) { if (this.state.isAdmin) line.remark = ev.target.value; }
    clearNote(line)  { if (this.state.isAdmin) line.remark = ""; }

    // ── Keyboard Navigation ───────────────────────────────────
    onGlobalKeydown(ev) {
        const tag = (ev.target.tagName || "").toLowerCase();
        if (["input", "textarea", "select"].includes(tag) || ev.target.isContentEditable) return;
        if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
        if (this.state.saving || this.state.loading || !this.state.lines.length) return;

        if (ev.key === "Escape" && this.state.openNoteId) {
            ev.preventDefault();
            this.closeNote();
            return;
        }

        const visible = this.visibleLines;
        if (!visible.length) return;
        let idx = visible.findIndex((l) => l.teacher_id === this.state.activeId);
        if (idx < 0) idx = 0;

        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const next = ev.key === "ArrowDown" ? idx + 1 : idx - 1;
            this.state.activeId = visible[Math.min(Math.max(next, 0), visible.length - 1)].teacher_id;
            return;
        }

        if (!this.state.isAdmin) return;

        const opt = this.statusOptions.find((o) => o.key.toLowerCase() === ev.key.toLowerCase());
        if (!opt) return;
        ev.preventDefault();
        this.setStatus(visible[idx], opt.value);
        if (idx < visible.length - 1) {
            this.state.activeId = visible[idx + 1].teacher_id;
        }
    }

    // ── Save Attendance ───────────────────────────────────────
    async saveAttendance() {
        if (!this.state.isAdmin) {
            this.notification.add(_t("Only administrators can record staff attendance."), { type: "danger" });
            return;
        }
        if (!this.state.departmentId || !this.state.date || !this.state.lines.length) return;

        // Front-end validation: check-out must be strictly after check-in
        for (const line of this.state.lines) {
            if (line.check_in && line.check_out && line.check_out <= line.check_in) {
                this.state.error = _t("Check-out must be after check-in for %(name)s.", { name: line.name });
                this.notification.add(this.state.error, { type: "danger" });
                return;
            }
        }

        this.state.saving = true;
        this.state.error  = null;

        try {
            const toCreate = [];
            const toWrite  = [];

            for (const line of this.state.lines) {
                const checkIn  = line.check_in  ? `${this.state.date} ${line.check_in}:00` : false;
                const checkOut = line.check_out ? `${this.state.date} ${line.check_out}:00` : false;

                const vals = {
                    staff_id:  line.teacher_id,
                    date:      this.state.date,
                    status:    line.status,
                    check_in:  checkIn,
                    check_out: checkOut,
                    remark:    line.remark || "",
                };

                if (line.record_id) {
                    toWrite.push([line.record_id, vals]);
                } else {
                    toCreate.push(vals);
                }
            }

            if (toCreate.length) {
                await this.orm.create("university.staff.attendance", toCreate);
            }
            for (const [id, vals] of toWrite) {
                await this.orm.write("university.staff.attendance", [id], vals);
            }

            await this.loadSheet();
            this.state.lastSaved = clockTime(new Date());

            const c = this.counts;
            const deptLabel = this.currentDepartmentName;
            this.notification.add(
                deptLabel ? _t("Attendance saved for %(dept)s", { dept: deptLabel }) : _t("Staff attendance saved"),
                {
                    type: "success",
                    message: `${c.total} staff · ${c.present} present · ${c.absent} absent · ${c.late} late · ${c.leave} on leave`,
                }
            );
        } catch (e) {
            this.state.error = e.message || _t("Unable to save attendance.");
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    onBack() {
        if (this.env.config?.historyBack) {
            this.env.config.historyBack();
        } else {
            this.action.doAction("school_management.action_university_staff_attendance");
        }
    }
}

registry.category("actions").add("university_staff_attendance_sheet", StaffAttendanceSheet);
export default StaffAttendanceSheet;
