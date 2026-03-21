from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('scraper', '0011_backfill_3nf_reference_masters'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pcpart_type_price_name ON scraper_pcpart (part_type, price, name);",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_pcpart_type_price_name;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_configuration_is_deleted_created_at ON scraper_configuration (is_deleted, created_at DESC);",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_configuration_is_deleted_created_at;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scraperstatus_updated_at_desc ON scraper_scraperstatus (updated_at DESC);",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_scraperstatus_updated_at_desc;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_configuration_usage_is_deleted_created_at ON scraper_configuration (usage, is_deleted, created_at DESC);",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_configuration_usage_is_deleted_created_at;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pcpart_storage_capacity_price ON scraper_pcpart (capacity_gb, price) WHERE part_type = 'storage';",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_pcpart_storage_capacity_price;",
        ),
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pcpart_name_trgm ON scraper_pcpart USING GIN (name gin_trgm_ops);",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_pcpart_name_trgm;",
        ),
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_pcpart_dospara_code_not_blank "
                "ON scraper_pcpart (dospara_code) "
                "WHERE dospara_code IS NOT NULL AND dospara_code <> '';"
            ),
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS uq_pcpart_dospara_code_not_blank;",
        ),
    ]
