{
    "name": "Payments SEPA Export",
    "version": "1.0",
    "depends": ["account"],
    'author': 'University of Namur',
    'category': 'Accounting & Finance',
    "description": """
        """,
    'demo': [],
    'data': [
        'data/sepa_payment_method.xml',
        'views/sepa_file.xml',
        'views/payment.xml',
        'wizard/views/export_sepa.xml',
    ],
    'installable': True,  # not functional yet
    'auto_install': False,
}
