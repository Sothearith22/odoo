{
    "name": "School Public Holidays",
    "version": "1.0.0",
    "category": "Education",
    "summary": "Cambodia public holiday calendar and holiday work pay rules",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/public_holiday_views.xml",
        "data/public_holiday_data.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}