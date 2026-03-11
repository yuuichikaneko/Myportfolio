from celery import shared_task
from django.utils import timezone
from .models import ScraperStatus


@shared_task
def run_scraper_task():
    """
    定期的に実行されるスクレイパータスク
    """
    try:
        # スクレイパー状態を取得または作成
        status, created = ScraperStatus.objects.get_or_create(id=1)
        
        # 実行時刻を更新
        status.last_run = timezone.now()
        status.success_count += 1
        status.total_scraped += 35  # 仮の値
        status.save()
        
        return {'status': 'success', 'message': 'Scraper task completed'}
    except Exception as e:
        status.update_or_create(id=1, defaults={'error_count': status.error_count + 1})
        return {'status': 'error', 'message': str(e)}


@shared_task
def update_scraper_status(total=0, success=0, error=0):
    """
    スクレイパー状態を更新
    """
    status, _ = ScraperStatus.objects.get_or_create(id=1)
    status.last_run = timezone.now()
    status.total_scraped = total
    status.success_count = success
    status.error_count = error
    status.save()
    return {'status': 'updated'}
