# coding: utf-8
from haystack import indexes

from .models import Top100Articles


class Top100ArticlesIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True, null=True)

    collection = indexes.CharField(model_attr='collection', null=True)
    key_issn = indexes.CharField(model_attr='key_issn', null=False)
    pid = indexes.CharField(model_attr='pid', null=False)
    yop = indexes.CharField(model_attr='yop', null=False)
    total_item_requests = indexes.IntegerField(model_attr='total_item_requests', null=False)
    total_item_investigations = indexes.IntegerField(model_attr='total_item_investigations', null=False)
    unique_item_requests = indexes.IntegerField(model_attr='unique_item_requests', null=False)
    unique_item_investigations = indexes.IntegerField(model_attr='unique_item_investigations', null=False)

    year_month_day = indexes.DateField(model_attr='year_month_day', null=False)

    metric_scope = indexes.CharField(null=False)

    def prepare_metric_scope(self, obj):
        return 'top100articles'

    def get_model(self):
        return Top100Articles

    def index_queryset(self, using=None):
        return self.get_model().objects.all()
