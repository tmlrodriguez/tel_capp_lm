{
    'name': 'Prestamos',
    'version': '1.0.0',
    'summary': 'Administrador de prestamos otorgados por ADDICAPP',
    'description': 'Diseñado para gestionar programas internos de préstamos dentro de una asociación. Permite a los '
                   'administradores definir tipos de préstamos, registrar los préstamos otorgados a los asociados, '
                   'calcular planes de pago con cuotas fijas utilizando distintos métodos de amortización, y generar '
                   'reportes oficiales de los préstamos.',
    'author': 'Telematica',
    'category': 'Accounting',
    'depends': ['base', 'accountant', 'mail'],
    'data': [
        # Data
        'data/ir_sequence_data.xml',
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        # Views
        'views/res_partner_view.xml',
        'views/loan_manager_requirements_view.xml',
        'views/loan_manager_types_view.xml',
        'views/loan_loans_view.xml',
        'views/loan_dashboard_view.xml',
        'views/account_move_view.xml',
        'views/loan_manager_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'tel_capp_lm/static/src/css/global.css',
            'tel_capp_lm/static/img/icon.png',
        ],
    },
    'images': ['static/description/icon.png'],
    'license': 'AGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}