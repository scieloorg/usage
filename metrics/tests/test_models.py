from django.db.utils import IntegrityError
from django.test import TestCase

from core.models import User
from .models import Top100Articles


class Top100ArticlesModelTestCase(TestCase):
    
    def setUp(self):
        self.user = User.objects.create(username='testuser')
    
    def test_create_valid_article(self):
        article = Top100Articles.create(
            user=self.user,
            key_issn='2448-6132',
            year_month_day='2024-06-01',
            print_issn='2007-428X',
            online_issn='2448-6132',
            collection='mex',
            pid='S2448-61322023000100101',
            yop=2023,
            total_item_requests=10,
            total_item_investigations=5,
            unique_item_requests=8,
            unique_item_investigations=4,
        )
        self.assertIsNotNone(article)
        
        self.assertEqual(article.key_issn, '2448-6132')
        self.assertEqual(article.year_month_day,  '2024-06-01')
        self.assertEqual(article.print_issn, '2007-428X')
        self.assertEqual(article.online_issn, '2448-6132')
        self.assertEqual(article.collection, 'mex')
        self.assertEqual(article.pid, 'S2448-61322023000100101')
        self.assertEqual(article.yop, 2023)
        self.assertEqual(article.total_item_requests, 10)
        self.assertEqual(article.total_item_investigations, 5)
        self.assertEqual(article.unique_item_requests, 8)
        self.assertEqual(article.unique_item_investigations, 4)
    
    def test_unique_together_constraint(self):
        Top100Articles.create(
            user=self.user,
            key_issn='2448-6132',
            year_month_day='2024-06-01',
            print_issn='2007-428X',
            online_issn='2448-6132',
            collection='mex',
            pid='S2448-61322023000100101',
            yop=2024,
            total_item_requests=10,
            total_item_investigations=5,
            unique_item_requests=8,
            unique_item_investigations=4,
        )
        with self.assertRaises(IntegrityError):
            Top100Articles.create(
                user=self.user,
                key_issn='2448-6132',
                year_month_day='2024-06-01',
                print_issn='2007-428X',
                online_issn='2448-6132',
                collection='mex',
                pid='S2448-61322023000100101',
                yop=2023,
                total_item_requests=10,
                total_item_investigations=5,
                unique_item_requests=8,
                unique_item_investigations=4,
            )
    
    def test_str_method(self):
        article = Top100Articles(
            key_issn='2448-6132',
            year_month_day='2024-06-01',
            print_issn='2007-428X',
            online_issn='2448-6132',
            collection='mex',
            pid='S2448-61322023000100101',
            yop=2023,
            total_item_requests=10,
            total_item_investigations=5,
            unique_item_requests=8,
            unique_item_investigations=4,
        )
        self.assertEqual(str(article), '2448-6132, S2448-61322023000100101, 10')
