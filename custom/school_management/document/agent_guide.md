# Agent Guide — Odoo 19.0

This document helps AI agents understand and navigate this codebase.

---

## Project Overview

**Odoo 19.0** is a full-licensed ERP/CRM suite — Python backend, OWL (Odoo Web Library) frontend, PostgreSQL-only database. Version `19.0.0 FINAL`. License: LGPL-3.

Entry point: `odoo-bin` → `odoo.cli.main()`.

---

## Directory Structure

```
C:\Odoo\odoo\
├── odoo/                  # Core library (ORM, HTTP, CLI, services, tools)
│   ├── orm/               # ORM: models, fields, domains, environments, registry
│   ├── cli/               # CLI commands (server, shell, scaffold, db, module, etc.)
│   ├── http.py            # HTTP/WSGI layer, Controller base, @route decorator
│   ├── sql_db.py          # PostgreSQL connector (psycopg2 wrapper)
│   ├── tests/             # Core test framework (TransactionCase, HttpCase, Form)
│   ├── tools/             # Utilities (config, translate, sql, image, safe_eval, etc.)
│   ├── modules/           # Module loading, registry, migration, manifest parsing
│   ├── service/           # RPC service layer, server implementation
│   ├── release.py         # Version: (19, 0, 0, FINAL, 0)
│   └── exceptions.py      # UserError, AccessError, ValidationError, etc.
├── addons/                # ~632 standard addons (sale, account, stock, crm, web, etc.)
│   └── <module>/
│       ├── __manifest__.py
│       ├── __init__.py
│       ├── models/        # ORM model definitions
│       ├── views/         # XML view definitions
│       ├── security/      # ir.model.access.csv, record rules
│       ├── data/          # Data files loaded on install
│       ├── demo/          # Demo data
│       ├── controllers/   # HTTP routes
│       ├── wizard/        # Transient models
│       ├── static/        # Frontend assets (JS, SCSS, XML templates)
│       ├── tests/         # Python tests
│       └── i18n/          # Translations (.po/.pot)
├── odoo/addons/           # Core addons (base + ~24 test modules)
├── custom/                # Custom addons (user-defined, currently school_management/)
├── setup/                 # Packaging (deb, rpm, win32, wsgi example)
├── debian/                # Debian/Ubuntu packaging
├── doc/                   # Documentation
├── venv/                  # Python 3.12.8 virtual environment
├── odoo-bin               # Main entry point
├── odoo.conf              # Runtime configuration
├── requirements.txt       # Pinned Python dependencies
├── ruff.toml              # Ruff linter config
├── setup.py               # Package setup
├── setup.cfg              # Flake8 config
├── SETUP_GUIDE.md         # Windows setup guide
├── CONTRIBUTING.md        # Contribution guidelines
└── LICENSE                # LGPL-3
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10–3.14 (venv: 3.12.8) |
| Database | PostgreSQL ≥ 13 (psycopg2) |
| Web/WSGI | Werkzeug + gevent/greenlet |
| Templating | Jinja2 |
| ORM | Custom (`../../../odoo/orm`) |
| Frontend | OWL (Odoo Web Library), SCSS, custom asset bundling |
| XML/HTML | lxml |
| Image | Pillow |
| PDF | reportlab, PyPDF2 |
| i18n | Babel, polib, num2words |
| Excel | openpyxl, xlrd, xlwt, xlsxwriter |
| Testing | unittest + freezegun + custom Odoo test framework |
| Linting | Ruff (primary), Flake8 (secondary) |

---

## ORM Architecture (`../../../odoo/orm`)

This is the heart of Odoo. All business objects extend `BaseModel`.

### Key files

| File | Lines | Purpose |
|------|-------|---------|
| `models.py` | ~7130 | BaseModel: CRUD, search, compute, constraints, caching, recordsets |
| `fields.py` | ~1938 | Field base class with storage, computation, defaults, constraints |
| `fields_relational.py` | ~1779 | Many2one, One2many, Many2many |
| `domains.py` | ~2043 | Domain expression AST (AND, OR, NOT, conditions) |
| `environments.py` | ~964 | Environment (cr, uid, context, su, transaction/cache) |
| `registry.py` | ~1296 | Per-database model registry, cache layers, schema ops |
| `commands.py` | — | Command enum: CREATE(0), UPDATE(1), DELETE(2), UNLINK(3), LINK(4), CLEAR(5), SET(6) |
| `decorators.py` | — | @api.depends, @api.constrains, @api.onchange, @api.ondelete, @api.model |

### Core concepts

- **Models** — define `_name` (table), `_description`, `_inherit` (inheritance), CRUD methods
- **Fields** — Char, Text, Html, Integer, Float, Monetary, Boolean, Date, Datetime, Selection, Binary, Image, Json, Many2one, One2many, Many2many
- **Domains** — first-order logical expressions for filtering records
- **Environments** — each request runs in an Environment with cursor, user ID, context, and superuser flag
- **Registry** — singleton per database holding all model classes and cache layers
- **Recordsets** — set-like objects returned by search/browse, support record manipulation

### Field options (common)

`compute`, `store`, `default`, `required`, `readonly`, `copy`, `groups`, `company_dependent`, `tracking` (chatter), `index`, `unique`, `ondelete`

---

## Module Structure

Every addon follows this pattern:

```
module_name/
├── __manifest__.py      # Metadata: name, version, depends, data, demo, assets, hooks
├── __init__.py          # Python package init (imports models/, controllers/, etc.)
├── models/              # ORM model files (imported from __init__.py)
├── views/               # XML view definitions (form, tree, kanban, search, etc.)
├── security/            # ir.model.access.csv + record rule XML
├── data/                # Default data loaded on install (XML, CSV)
├── demo/                # Demo data (loaded with --without-demo=False)
├── controllers/         # HTTP routes (Python, inherits web.controllers)
├── wizard/              # Transient models (wizard forms)
├── static/              # Frontend assets
│   └── src/             # JS, SCSS, XML templates, images
├── tests/               # Python tests (test_*.py)
│   └── __init__.py
├── i18n/                # Translations (.po, .pot)
└── README.md
```

### Manifest (`__manifest__.py`) key fields

```python
{
    'name': 'Module Name',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Short description',
    'description': 'Long description',
    'depends': ['sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_views.xml',
        'data/sequence_data.xml',
    ],
    'demo': ['demo/sale_demo.xml'],
    'assets': {
        'web.assets_backend': [
            'module_name/static/src/**/*.js',
            'module_name/static/src/**/*.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'external_dependencies': {'python': ['openpyxl']},
    'license': 'LGPL-3',
}
```

---

## Configuration

### `odoo.conf` (runtime)

```ini
db_name = odoo
db_host = localhost
db_port = 5432
db_user = odoo
addons_path = addons,custom,odoo/addons
http_port = 8070
gevent_port = 8072
```

### `../../../requirements.txt`

106 lines of pinned dependencies. Supports Python 3.10–3.14 with version-conditional pins.

### `../../../ruff.toml`

- Target: Python 3.10
- Preview mode enabled
- Rule sets: E, F, W, I (isort), UP, SIM, TRY, PLC/PLE/PLW, and many more
- `F401` (unused import) suppressed in all `__init__.py` files
- isort: `odoo` = first-party, `odoo.addons` = local-folder

---

## Development Commands

### Start server

```powershell
python odoo-bin -c odoo.conf
```

### Initialize database

```powershell
python odoo-bin -c odoo.conf -d <dbname> -i base --stop-after-init
```

### Install/upgrade a module

```powershell
python odoo-bin -c odoo.conf -d <dbname> -i <module> --stop-after-init   # install
python odoo-bin -c odoo.conf -d <dbname> -u <module> --stop-after-init   # upgrade
```

### Interactive shell

```powershell
python odoo-bin shell -c odoo.conf -d <dbname> --no-http
```

### Scaffold a new module

```powershell
python odoo-bin scaffold <module_name> custom/
```

### Run tests

```powershell
# All tests for a module
python odoo-bin -c odoo.conf -d <dbname> --test-enable -i <module> --stop-after-init

# Specific test tags
python odoo-bin -c odoo.conf -d <dbname> --test-enable --test-tags=<tag> -i <module> --stop-after-init
```

### Linting

```powershell
ruff check .          # lint
ruff format .         # format
```

### List databases

```powershell
python odoo-bin db -c odoo.conf --list
```

---

## Test Framework

Tests live inside each addon in `tests/` subdirectories.

### Base classes (`../../../odoo/tests/common.py`)

- **`TransactionCase`** — each test gets a fresh transaction, rolled back after
- **`HttpCase`** — tests HTTP endpoints (starts a test server)
- **`BaseCase`** — common utilities
- **`tagged('tag1', 'tag2')`** — decorator for selective test execution

### Form test helper (`../../../odoo/tests/form.py`)

Server-side Form view simulator — writes field values, triggers onchange, validates constraints without a browser.

### Test conventions

- Files: `tests/test_<topic>.py`
- Classes: `class TestSomething(TransactionCase):`
- Methods: `def test_<behavior>(self):`
- Tags: `@tagged('standard', 'fast')` or `@tagged('-at_install', 'post_install')`

### Dedicated test addons

- `../../../odoo/addons`: `test_orm/`, `test_rpc/`, `test_http/`, `test_access_rights/`, etc.
- `../../../addons`: `test_crm_full/`, `test_discuss_full/`, `test_mail_full/`, `test_website/`, etc.

---

## Key Exception Types (`../../../odoo/exceptions.py`)

| Exception | Use |
|-----------|-----|
| `UserError` | User-facing error (displayed in UI alert) |
| `ValidationError` | Constraint violation on record values |
| `AccessError` | Insufficient permissions |
| `AccessDenied` | Authentication failure |
| `MissingError` | Record not found |
| `LockError` | Database lock timeout |
| `ConcurrencyError` | Record modified by another user |
| `CacheMiss` | Field value not in cache |

---

## HTTP Layer (`../../../odoo/http.py`)

- **`Controller`** — base class for HTTP controllers
- **`@route('/path', type='http', auth='user', methods=['POST'])`** — route decorator
- **`request`** — thread-local object with `env`, `cr`, `uid`, `context`, `session`, `params`
- Auth types: `none`, `public`, `user`, `internal`
- Static files served from addon `static/` directories

---

## Important Patterns

### Inheritance

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # mixin inheritance
```

### Computed fields

```python
total = fields.Float(compute='_compute_total')

@api.depends('line_ids.price')
def _compute_total(self):
    for rec in self:
        rec.total = sum(rec.line_ids.mapped('price'))
```

### Constraints

```python
@api.constrains('date_start', 'date_end')
def _check_dates(self):
    for rec in self:
        if rec.date_start > rec.date_end:
            raise ValidationError("Start must be before end.")
```

### Onchange (client-side only)

```python
@api.onchange('partner_id')
def _onchange_partner_id(self):
    self.email = self.partner_id.email
```

### Relational field commands

```python
# Write to one2many/many2many
order.write({'line_ids': [
    (0, 0, {'name': 'New line', 'price': 100}),   # CREATE
    (1, existing_id, {'price': 200}),               # UPDATE
    (2, existing_id),                                # DELETE (remove + unlink)
    (3, existing_id),                                # UNLINK (remove only)
    (4, existing_id),                                # LINK
    (5, 0, 0),                                      # CLEAR all
    (6, 0, [id1, id2]),                             # SET (replace all)
]})
```

---

## Addon Categories (high-level)

| Category | Key addons |
|----------|-----------|
| Core | `web`, `mail`, `bus`, `http_routing` |
| Business | `sale`, `purchase`, `account`, `stock`, `mrp`, `crm`, `project`, `hr` |
| eCommerce | `website`, `website_sale`, `website_slides` |
| POS | `point_of_sale`, `pos_restaurant`, `pos_*` (~30 modules) |
| Marketing | `mass_mailing`, `marketing_card`, `social_media` |
| Localization | `l10n_*` (~200+ country modules) |
| Payment | `payment_stripe`, `payment_paypal`, `payment_adyen`, `payment_*` (~20+) |
| Integrations | `google_*`, `microsoft_*`, `sms_twilio` |
| Spreadsheets | `spreadsheet`, `spreadsheet_dashboard_*` |
| Testing | `test_*` (~15+ dedicated test modules) |

---

## Git & CI

- **No CI workflows** in repo — Odoo uses internal runbot
- **No `.pre-commit-config.yaml`** — uses custom git hooks via `../../../addons/web/tooling/enable.sh`
- **Pre-commit hook** runs `npm run format-staged` (ESLint --fix on staged JS files)
- **JS tooling**: ESLint 8.x + Prettier 2.x + lint-staged (template in `addons/web/tooling/_package.json`)
- Enable JS tooling: `bash addons/web/tooling/enable.sh`

---

## Custom Addons

Custom addons go in `../..`. Currently contains `..` — a working School Management module.

### `..` structure

```
school_management/
├── __manifest__.py          # name, version 19.0.1.0.0, depends ['base'], application: True
├── __init__.py              # from . import models
├── models/
│   ├── __init__.py          # from . import student
│   └── student.py           # school.student model (name, student_id, image_1920, date_of_birth, gender, email, phone, address, notes, active)
├── views/
│   ├── student_view.xml     # search, kanban (card template), form views + window action + menus
│   └── menu_views.xml       # list view (school.student.list)
├── security/
│   └── ir.model.access.csv  # access_school_student -> base.group_user (read/write/create/unlink)
└── document/
    └── project_structure.md.md
```

### Notes / gotchas (Odoo 19 specifics)

- Kanban templates use `t-name="card"` (renamed from `kanban-box`).
- Kanban images use `<field name="image_1920" widget="image" .../>` — the legacy `kanban_image()` JS helper was removed in Odoo 19.
- `<group>` inside a `<search>` view does **not** accept `expand` or `string` attributes.
- Manifest `data` must list **every** XML file (e.g. `menu_views.xml`), or those views silently won't load.
- `<i class="fa-...">` icons must have a `title` attribute (accessibility warning otherwise).

---

## External References

- [Odoo Documentation](https://www.odoo.com/documentation/master)
- [Developer Tutorials](https://www.odoo.com/documentation/master/developer/howtos.html)
- [Coding Guidelines](https://www.odoo.com/documentation/latest/contributing/development/coding_guidelines.html)
- [CONTRIBUTING.md](../../../CONTRIBUTING.md)
- [SETUP_GUIDE.md](SETUP_GUIDE.md) — detailed Windows setup instructions
