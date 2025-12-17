{
    'name': 'OKR Tracker',
    'version': '1.0',
    'category': 'Productivity',
    'summary': 'Track Objectives and Key Results',
    'description': 'A module to manage OKRs with hierarchical structure using tree and form views.',
    'author': 'Your Name',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/okr_views.xml',
        'views/okr_menus.xml',
    ],
    'installable': True,
    'application': True,
}