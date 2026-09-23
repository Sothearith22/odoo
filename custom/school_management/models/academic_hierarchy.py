from odoo import api, fields, models


class UniversityAcademicHierarchy(models.Model):
    _name = "university.academic.hierarchy"
    _description = "Academic Structure Hierarchy"
    _parent_store = True
    _order = "parent_path, sequence, name"

    name = fields.Char(required=True)
    node_type = fields.Selection(
        [
            ("faculty", "Faculty"),
            ("department", "Department"),
            ("program", "Program"),
            ("subject", "Subject"),
        ],
        required=True,
    )
    code = fields.Char()
    source_model = fields.Char(required=True, index=True)
    source_id = fields.Integer(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    parent_id = fields.Many2one(
        "university.academic.hierarchy",
        string="Parent",
        index=True,
        ondelete="cascade",
    )
    child_ids = fields.One2many(
        "university.academic.hierarchy",
        "parent_id",
        string="Children",
    )
    parent_path = fields.Char(index=True)

    _unique_source = models.UniqueIndex(
        "(source_model, source_id)",
        "Each academic record can only have one hierarchy node.",
    )

    @api.model
    def _sync_structure(self):
        Node = self.sudo().with_context(skip_hierarchy_sync=True)
        definitions = []
        faculties = self.env["university.faculty"].sudo().search([])
        departments = self.env["university.department"].sudo().search([])
        programs = self.env["university.program"].sudo().search([])
        subjects = self.env["university.subject"].sudo().search([])

        for record in faculties:
            definitions.append((record, "faculty", False, 10))
        for record in departments:
            definitions.append((record, "department", record.faculty_id, 20))
        for record in programs:
            definitions.append((record, "program", record.department_id, 30))
        for record in subjects:
            parent = record.program_ids[:1] or record.department_id
            definitions.append((record, "subject", parent, 40))

        source_keys = {(record._name, record.id) for record, *_ in definitions}
        existing = {
            (node.source_model, node.source_id): node
            for node in Node.search([])
        }
        for key, node in existing.items():
            if key not in source_keys:
                node.unlink()

        nodes = {}
        for record, node_type, parent_record, sequence in definitions:
            key = (record._name, record.id)
            vals = {
                "name": record.name,
                "node_type": node_type,
                "code": getattr(record, "code", False),
                "source_model": record._name,
                "source_id": record.id,
                "sequence": sequence,
                "active": getattr(record, "active", True),
            }
            node = existing.get(key)
            nodes[key] = node or Node.create(vals)
            if node:
                node.write(vals)

        for record, node_type, parent_record, sequence in definitions:
            node = nodes[(record._name, record.id)]
            parent = False
            if parent_record:
                parent = nodes.get((parent_record._name, parent_record.id))
            if node.parent_id != parent:
                node.parent_id = parent
        return True

    @api.model
    def search(self, domain=None, *args, **kwargs):
        if not self.env.context.get("skip_hierarchy_sync"):
            self._sync_structure()
        return super().search(domain, *args, **kwargs)

    def action_open_source(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.source_model,
            "view_mode": "form",
            "res_id": self.source_id,
        }
