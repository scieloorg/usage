# coding: utf-8
import reverse_geocode

from haystack import indexes

from .models import LogProcessedRow


class LogProcessedRowIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True, null=True)

    server_date = indexes.CharField(null=False)
    server_hour = indexes.IntegerField(null=False)

    # user agent
    browser_name = indexes.CharField(model_attr="browser_name", null=False)
    browser_version = indexes.CharField(model_attr="browser_version", null=False)

    # geolocation
    ip = indexes.CharField(model_attr="ip", null=False)
    country_code = indexes.CharField(null=False)

    action_name = indexes.CharField(model_attr="action_name", null=False)

    user_session = indexes.CharField(null=False)

    # Foreign key
    collection = indexes.CharField(null=True)

    def prepare_server_date(self, obj):
        return obj.server_time.strftime('%Y-%m-%d')

    def prepare_server_hour(self, obj):
        return obj.server_time.strftime('%H')
    
    def prepare_country_code(self, obj):
        geo = reverse_geocode.search([[obj.latitude, obj.longitude]])
        if geo:
            return geo.pop().get('country_code', 'UN')
        else:
            return 'UN'
    
    def prepare_user_session(self, obj):
        return f'{obj.ip}|{obj.browser_name}|{obj.browser_version}|{self.prepare_server_date(obj)}|{self.prepare_server_hour(obj)}'
    
    def prepare_collection(self, obj):
        return obj.log_file.collection.acron2

    def get_model(self):
        return LogProcessedRow

    def index_queryset(self, using=None):
        return self.get_model().objects.all()
