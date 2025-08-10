from django.core.management.base import BaseCommand

from article.tasks import task_load_article_from_opac, task_load_article_from_article_meta


class Command(BaseCommand):
    help = 'Generate task requests for loading article data from Article Meta for each year from 1900 to 2025'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-year',
            type=int,
            default=1990,
            help='Start year (default: 1990)'
        )
        parser.add_argument(
            '--end-year',
            type=int,
            default=2025,
            help='End year (default: 2025)'
        )
        parser.add_argument(
            '--collection',
            type=str,
            default='scl',
            help='Collection code (default: scl)'
        )
        parser.add_argument(
            '--task',
            choices=['load_article_from_opac', 'load_article_from_article_meta'],
            default='load_article_from_opac',
            help='Task to execute (default: load_article_from_opac)',
        )

    def handle(self, *args, **options):
        start_year = options['start_year']
        end_year = options['end_year']
        collection = options['collection']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Generating task requests from {start_year} to {end_year} for collection: {collection}'
            )
        )
        
        total_tasks = 0
        
        for year in range(start_year, end_year + 1):
            from_date = f'{year}-01-01'
            until_date = f'{year}-12-31'
            
            self.stdout.write(f'Queuing task for year {year}...')
            
            # Queue the task for each year
            if options['task'] == 'load_article_from_article_meta':
                task_result = task_load_article_from_article_meta.delay(
                    from_date=from_date,
                    until_date=until_date,
                    collection=collection
                )
            else:
                task_result = task_load_article_from_opac.delay(
                    from_date=from_date,
                    until_date=until_date,
                    collection=collection
                )
            
            total_tasks += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Task queued for year {year}: {from_date} to {until_date} (Task ID: {task_result.id})'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted! {total_tasks} tasks have been queued successfully.'
            )
        )
