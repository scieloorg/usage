from django.utils.translation import gettext_lazy as _


APPLICATION_CONFIG_TYPE_DIRECTORY_SUPPLIES = 'SUP'
APPLICATION_CONFIG_TYPE_PATH_SUPPLY_MMDB = 'GEO'
APPLICATION_CONFIG_TYPE_PATH_SUPPLY_ROBOTS = 'ROB'
APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_ISSN_ACRONYM = 'ACR'
APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_PID_DATES = 'DAT'
APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_PID_ISSN = 'ISS'
APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_PID_FORMAT_LANG = 'LAN'
APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_PDF_PID = 'PDF'
APPLICATION_CONFIG_TYPE_LOG_FILE_FORMAT = 'LFF'

APLLICATION_CONFIG_TYPE = [
    (APPLICATION_CONFIG_TYPE_DIRECTORY_SUPPLIES, _('Supplies Directory')),
    (APPLICATION_CONFIG_TYPE_PATH_SUPPLY_MMDB, _('Supply Geolocation Map Path')),
    (APPLICATION_CONFIG_TYPE_PATH_SUPPLY_ROBOTS, _('Supply Counter Robots Path')),
    (APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_ISSN_ACRONYM, _('Dictionary ISSN-ACRONYM Path')),
    (APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_PID_DATES, _('Dictionary PID-DATES Path')),
    (APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_PID_ISSN, _('Dictionary PID-ISSN Path')),
    (APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_PID_FORMAT_LANG, _('Dictionary PID-FORMAT-LANG Path')),
    (APPLICATION_CONFIG_TYPE_PATH_DICTIONARY_PDF_PID, _('Dictionary PDF-PID Path')),
    (APPLICATION_CONFIG_TYPE_LOG_FILE_FORMAT, _('Log File Supported Format')),
]


COLLECTION_CONFIG_TYPE_DIRECTORY_LOGS = 'LOG'
COLLECTION_CONFIG_TYPE_DIRECTORY_PROCESSED_DATA = 'PRO'
COLLECTION_CONFIG_TYPE_DIRECTORY_METRICS = 'MTS'
COLLECTION_CONFIG_TYPE_FILES_PER_DAY = 'DAY'
COLLECTION_CONFIG_TYPE_EMAIL = 'EMA'

COLLECTION_CONFIG_TYPE = [
    (COLLECTION_CONFIG_TYPE_DIRECTORY_LOGS, _('Logs')),
    (COLLECTION_CONFIG_TYPE_DIRECTORY_PROCESSED_DATA, _('Processed Data')),
    (COLLECTION_CONFIG_TYPE_DIRECTORY_METRICS, _('Metrics')),
    (COLLECTION_CONFIG_TYPE_FILES_PER_DAY, _('Files per Day')),
    (COLLECTION_CONFIG_TYPE_EMAIL, _('E-mail')),
]


LOG_FILE_STATUS_CREATED = 'CRE'
LOG_FILE_STATUS_QUEUED = 'QUE'
LOG_FILE_STATUS_PARSING = 'PAR'
LOG_FILE_STATUS_PROCESSED = 'PRO'
LOG_FILE_STATUS_INVALIDATED = 'INV'

LOG_FILE_STATUS = [
    (LOG_FILE_STATUS_CREATED, _("Created")),
    (LOG_FILE_STATUS_QUEUED, _("Queued")),
    (LOG_FILE_STATUS_PARSING, _("Parsing")),
    (LOG_FILE_STATUS_PROCESSED, _("Processed")),
    (LOG_FILE_STATUS_INVALIDATED, _("Invalidated")),
]


TEMPORAL_REFERENCE_TWO_DAYS_AGO = 'two days ago'
TEMPORAL_REFERENCE_YESTERDAY = 'yesterday'
TEMPORAL_REFERENCE_LAST_WEEK = 'last week'
TEMPORAL_REFERENCE_LAST_MONTH = 'last month'
