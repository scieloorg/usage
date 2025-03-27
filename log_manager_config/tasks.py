from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from core.utils.utils import _get_user
from config import celery_app

from . import models


User = get_user_model()


@celery_app.task(bind=True, name=_('Load log manager collection settings'))
def task_load_log_manager_collection_settings(self, data={}, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    if not data:
        data = [
            {'acronym': 'arg', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.ar', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'bol', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.bo', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'chl', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.cl', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'col', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.co', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'cri', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.cr', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'cub', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.cu', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'data', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-dataverse', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'dataverse'},
            {'acronym': 'ecu', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.ec', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'esp', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.es', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'mex', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.mx', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'per', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.pe', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'preprints', 'directory_name': _('Site clássico') , 'path': '/app/logs/submission-node01', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'preprints'},
            {'acronym': 'prt', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.pt', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'}, 
            {'acronym': 'pry', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.py', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'psi', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.pepsic', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'rve', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.revenf', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'rvt', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.revtur', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'scl', 'directory_name': _('Site novo') , 'path': '/app/logs/bkp-ratchet/scielo.nbr', 'quantity': 2, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'opac'},
            {'acronym': 'spa', 'directory_name': _('Site novo - versão prévia') , 'path': '/app/logs/bkp-ratchet/scielo.sp', 'quantity': 2, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'opac_alpha'},
            {'acronym': 'sss', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.ss', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'sza', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.za', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'ury', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.uy', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'ven', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.ve', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
            {'acronym': 'wid', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/scielo.wi', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org', 'translator_class': 'classic'},
        ]

        for i in data:
            i['sample_size'] = 0.1 if i['acronym'] not in ['data', 'preprints', 'wid'] else 1.0
            i['buffer_size'] = 2048

    data_extensions = [
        {'file_extension': '.log', 'description': ''},
        {'file_extension': '.gz', 'description': ''}
    ]

    models.CollectionLogDirectory.load(data, user)
    models.CollectionEmail.load(data, user)
    models.CollectionLogFilesPerDay.load(data, user)
    models.CollectionValidationParameters.load(data, user)
    models.CollectionURLTranslatorClass.load(data, user)
    models.SupportedLogFile.load(data_extensions, user)