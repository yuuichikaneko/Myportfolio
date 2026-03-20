from datetime import timedelta
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .dospara_scraper import _infer_part_type, get_dospara_scraper_config, scrape_dospara_parts, scrape_dospara_category_parts
from .models import PCPart, ScraperStatus


logger = logging.getLogger(__name__)


def _normalize_part_types():
    changed = 0
    merged = 0
    for part in PCPart.objects.all().order_by('id'):
        inferred = _infer_part_type(part.name, part.url)
        if not inferred or inferred == part.part_type:
            continue

        existing = PCPart.objects.filter(part_type=inferred, name=part.name).exclude(id=part.id).first()
        if existing:
            existing.price = part.price
            existing.url = part.url
            existing.specs = part.specs or existing.specs
            existing.save(update_fields=['price', 'url', 'specs', 'updated_at'])
            part.delete()
            merged += 1
            continue

        part.part_type = inferred
        part.save(update_fields=['part_type', 'updated_at'])
        changed += 1

    return changed, merged


@shared_task
def run_scraper_task():
    """
    定期的に実行されるスクレイパータスク
    """
    status, _ = ScraperStatus.objects.get_or_create(id=1)
    scraper_config = get_dospara_scraper_config()

    try:
        logger.info(
            'scraper_task_started source=dospara_parts env=%s url=%s timeout=%s max_items=%s',
            scraper_config.get('env', 'unknown'),
            scraper_config['url'],
            scraper_config['timeout'],
            scraper_config['max_items'],
        )
        scraped_parts = scrape_dospara_parts(
            timeout=scraper_config['timeout'],
            max_items=scraper_config['max_items'],
        )

        # カテゴリ別ページからも取得し、各パーツ種別の価格帯を網羅する
        category_parts = scrape_dospara_category_parts(
            timeout=scraper_config['timeout'],
            max_items_per_category=80,
        )
        # メインスクレイプ結果とマージ（重複は name+part_type でスキップ）
        main_keys = {(p['part_type'], p['name']) for p in scraped_parts}
        for part in category_parts:
            if (part['part_type'], part['name']) not in main_keys:
                scraped_parts.append(part)
                main_keys.add((part['part_type'], part['name']))

        saved_count = 0
        normalized_count = 0
        merged_count = 0
        with transaction.atomic():
            for part in scraped_parts:
                _, created = PCPart.objects.update_or_create(
                    part_type=part['part_type'],
                    name=part['name'],
                    defaults={
                        'price': part['price'],
                        'url': part['url'],
                        'specs': part.get('specs', {'source': 'dospara'}),
                    },
                )
                saved_count += 1 if created else 0

        normalized_count, merged_count = _normalize_part_types()

        status.last_run = timezone.now()
        status.next_run = timezone.now() + timedelta(days=1)
        status.total_scraped = len(scraped_parts)
        status.success_count += 1
        status.save()

        updated_count = len(scraped_parts) - saved_count
        logger.info(
            'scraper_task_completed source=dospara_parts fetched=%s created=%s updated=%s normalized=%s merged=%s',
            len(scraped_parts),
            saved_count,
            updated_count,
            normalized_count,
            merged_count,
        )

        return {
            'status': 'success',
            'source': 'dospara_parts',
            'fetched': len(scraped_parts),
            'created': saved_count,
            'updated': updated_count,
            'normalized': normalized_count,
            'merged': merged_count,
        }
    except Exception as e:
        status.last_run = timezone.now()
        status.error_count += 1
        status.save(update_fields=['last_run', 'error_count', 'updated_at'])
        logger.exception('scraper_task_failed source=dospara_parts error=%s', e)
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
