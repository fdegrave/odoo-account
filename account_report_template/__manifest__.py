{
    "name": "University Modules Accounting Reports",
    "version": "1.0",
    "depends": ["report_table", "account"],
    "author": "University of Namur",
    "category": "Accounting",
    "description": """
    This is a module doing the same things as the official Odoo module for accounting reports, but the inner working is
    completely different (the authors have never seen the code of the closed-source module).
    It depends on the generic table_report module (https://github.com/unamur-dev/odoo-tools).
    """,
    'demo': [],
    'data': [
        'views/template.xml',
        'views/web_less.xml',
        'report/account_report_template.xml',
        'wizard/print_template.xml'
    ],
    'qweb': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
