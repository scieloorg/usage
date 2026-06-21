from config import celery_app
from resources import services


@celery_app.task(bind=True, name="[Resources] Load Robots Data")
def task_load_robots(self, url_robots=None):
    return services.load_robots(url_robots=url_robots)


@celery_app.task(bind=True, name="[Resources] Load Geolocation Data")
def task_load_geoip(self, url_geoip=None, validate=True):
    return services.load_geoip(url_geoip=url_geoip, validate=validate)
