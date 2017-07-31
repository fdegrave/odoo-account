{
    "name": "Accounting Reports Template Engine",
    "version": "0.3a",
    "depends": ["report_table", "account"],
    "author": "University of Namur",
    "category": "Accounting",
    "description": """
    This is a module doing the same things as the official Odoo module for accounting reports, but the inner working is
    completely different (the authors have never seen the code of the closed-source module).
    It depends on the generic table_report module (https://github.com/unamur-dev/odoo-tools).

    THIS IS AN ALPHA VERSION. All feedback is welcome. It should be all finished and tested by September.
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
