import base64
import csv
import io
import logging
from datetime import date, datetime

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None


class PublicHolidayImportWizard(models.TransientModel):
    _name = "public.holiday.import.wizard"
    _description = "Import Public Holidays Wizard"

    file = fields.Binary(string="File (.csv, .xlsx)", required=True)
    filename = fields.Char(string="File Name")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Done"),
        ],
        string="State",
        default="draft",
    )
    created_count = fields.Integer(string="Created Records", default=0, readonly=True)
    skipped_count = fields.Integer(string="Skipped Records", default=0, readonly=True)
    error_count = fields.Integer(string="Errors", default=0, readonly=True)
    result_summary = fields.Text(string="Result Summary", readonly=True)

    def action_download_template(self):
        """Generate and return sample CSV template."""
        csv_content = (
            "name,name_km,date_from,date_to,holiday_type\n"
            "International New Year,ទិវាចូលឆ្នាំសកល,2026-01-01,2026-01-01,fixed\n"
            "Victory over Genocide Day,ទិវាជ័យជម្នះលើរបបប្រល័យពូជសាសន៍,2026-01-07,2026-01-07,fixed\n"
            "International Women's Day,ទិវាអន្តរជាតិនារី,2026-03-08,2026-03-08,fixed\n"
            "Khmer New Year,ពិធីបុណ្យចូលឆ្នាំថ្មីប្រពៃណីជាតិ,2026-04-14,2026-04-16,fixed\n"
            "International Labour Day,ទិវាពលកម្មអន្តរជាតិ,2026-05-01,2026-05-01,fixed\n"
            "King's Birthday,ព្រះរាជពិធីបុណ្យចម្រើនព្រះជន្មព្រះមហាក្សត្រ,2026-05-14,2026-05-14,fixed\n"
            "Royal Plowing Ceremony,ព្រះរាជពិធីច្រត់ព្រះនង្គ័ល,2026-05-04,2026-05-04,special\n"
            "Constitution Day,ទិវាប្រកាសរដ្ឋធម្មនុញ្ញ,2026-09-24,2026-09-24,fixed\n"
            "Pchum Ben,ពិធីបុណ្យភ្ជុំបិណ្ឌ,2026-10-10,2026-10-12,lunar\n"
            "King Father's Memorial Day,ទិវារំលឹកវិញ្ញាណក្ខន្ធព្រះបរមរតនកោដ្ឋ,2026-10-15,2026-10-15,fixed\n"
            "Coronation Day,ព្រះរាជពិធីគ្រងរាជសម្បត្តិ,2026-10-29,2026-10-29,fixed\n"
            "Independence Day,ទិវាបុណ្យឯករាជ្យជាតិ,2026-11-09,2026-11-09,fixed\n"
            "Water Festival,ព្រះរាជពិធីបុណ្យអុំទូក បណ្តែតប្រទីប និងសំពះព្រះខែ,2026-11-23,2026-11-25,lunar\n"
        )
        attachment = self.env["ir.attachment"].create({
            "name": "cambodia_public_holidays_template.csv",
            "type": "binary",
            "datas": base64.b64encode(csv_content.encode("utf-8")),
            "mimetype": "text/csv",
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def _parse_date(self, val):
        if not val:
            return None
        if isinstance(val, (datetime, date)):
            return val.date() if isinstance(val, datetime) else val
        val_str = str(val).strip()
        if not val_str:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(val_str, fmt).date()
            except ValueError:
                pass
        return None

    def _extract_rows(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("Please upload a CSV or XLSX file."))
        content = base64.b64decode(self.file)
        fname = (self.filename or "").lower()
        rows = []
        if fname.endswith(".xlsx"):
            if not openpyxl:
                raise UserError(_("openpyxl library is required to read .xlsx files."))
            wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
            ws = wb.active
            headers = None
            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if row_idx == 0:
                    headers = [str(c).strip().lower() if c is not None else "" for c in row]
                    continue
                if not any(row):
                    continue
                row_dict = {}
                for idx, val in enumerate(row):
                    if idx < len(headers) and headers[idx]:
                        row_dict[headers[idx]] = val
                rows.append((row_idx + 1, row_dict))
        else:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = content.decode("latin-1")
            reader = csv.DictReader(io.StringIO(text))
            for row_idx, row in enumerate(reader, start=2):
                cleaned = {k.strip().lower(): v for k, v in row.items() if k}
                rows.append((row_idx, cleaned))
        return rows

    def action_import(self):
        self.ensure_one()
        rows = self._extract_rows()
        PublicHoliday = self.env["public.holiday"]

        created_cnt = 0
        skipped_cnt = 0
        error_cnt = 0
        messages = []

        valid_types = {"fixed", "lunar", "special"}

        for row_num, data in rows:
            name = (data.get("name") or data.get("holiday_name") or data.get("holiday") or "").strip()
            name_km = (data.get("name_km") or data.get("khmer_name") or "").strip()
            raw_date_from = data.get("date_from") or data.get("from_date") or data.get("start_date") or data.get("date")
            raw_date_to = data.get("date_to") or data.get("to_date") or data.get("end_date") or raw_date_from
            raw_type = (data.get("holiday_type") or data.get("type") or "fixed").strip().lower()

            if not name:
                error_cnt += 1
                messages.append(f"Row {row_num}: Missing holiday name.")
                continue

            d_from = self._parse_date(raw_date_from)
            d_to = self._parse_date(raw_date_to) or d_from

            if not d_from or not d_to:
                error_cnt += 1
                messages.append(f"Row {row_num} ('{name}'): Invalid date format.")
                continue

            if d_to < d_from:
                error_cnt += 1
                messages.append(f"Row {row_num} ('{name}'): date_to ({d_to}) is before date_from ({d_from}).")
                continue

            h_type = raw_type if raw_type in valid_types else "fixed"

            # Check duplicate: same name (case-insensitive) and overlapping date
            existing = PublicHoliday.search([
                ("active", "=", True),
                ("date_from", "<=", d_to),
                ("date_to", ">=", d_from),
            ])
            is_dup = any(h.name.strip().lower() == name.lower() for h in existing)
            if is_dup:
                skipped_cnt += 1
                messages.append(f"Row {row_num} ('{name}'): Duplicate skipped (already exists).")
                continue

            try:
                with self.env.cr.savepoint():
                    PublicHoliday.create({
                        "name": name,
                        "name_km": name_km or False,
                        "date_from": d_from,
                        "date_to": d_to,
                        "holiday_type": h_type,
                        "affects_classes": True,
                        "active": True,
                    })
                    created_cnt += 1
            except Exception as e:
                error_cnt += 1
                messages.append(f"Row {row_num} ('{name}'): Failed to create ({str(e)}).")

        summary_lines = [
            f"Import Summary:",
            f"- Created: {created_cnt}",
            f"- Skipped (duplicates): {skipped_cnt}",
            f"- Errors: {error_cnt}",
            "",
            "Details:",
        ] + (messages[:50] if messages else ["All rows processed cleanly."])

        self.write({
            "state": "done",
            "created_count": created_cnt,
            "skipped_count": skipped_cnt,
            "error_count": error_cnt,
            "result_summary": "\n".join(summary_lines),
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "public.holiday.import.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
