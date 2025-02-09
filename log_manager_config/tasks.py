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
            {'acronym': 'arg', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/ar', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'bol', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/bo', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'chl', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/cl', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'col', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/co', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'cri', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/cr', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'cub', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/cu', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'data', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-dataverse', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'ecu', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/ec', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'esp', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/es', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'mex', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/mx', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'per', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/pe', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'preprints', 'directory_name': _('Site clássico') , 'path': '/app/logs/submission-node01', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'prt', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/pt', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'}, 
            {'acronym': 'pry', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/py', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'psi', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/pepsic', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'rve', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/revenf', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'rvt', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/revtur', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'scl', 'directory_name': _('Site novo') , 'path': '/app/logs/bkp-ratchet/nbr', 'quantity': 2, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'spa', 'directory_name': _('Site novo - versão prévia') , 'path': '/app/logs/bkp-ratchet/sp', 'quantity': 2, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'sss', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/ss', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'sza', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/za', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'ury', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/uy', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'ven', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/ve', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
            {'acronym': 'wid', 'directory_name': _('Site clássico') , 'path': '/app/logs/bkp-ratchet/wi', 'quantity': 1, 'start_date': '2020-01-01', 'e-mail': 'tecnologia@scielo.org'},
        ]

    models.CollectionLogDirectory.load(data, user)
    models.CollectionEmail.load(data, user)
    models.CollectionLogFilesPerDay.load(data, user)
