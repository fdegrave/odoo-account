{
    "name": "University Modules Accounting Reports",
    "version": "1.0",
    "depends": ["report_table", "account"],
    "author": "University of Namur",
    "category": "University Management",
    "description": """
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
