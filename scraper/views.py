from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import PCPart, Configuration, ScraperStatus
from .serializers import PCPartSerializer, ConfigurationSerializer, ScraperStatusSerializer


class PCPartViewSet(viewsets.ModelViewSet):
    """PC パーツの CRUD API"""
    queryset = PCPart.objects.all()
    serializer_class = PCPartSerializer
    filterset_fields = ['part_type']
    search_fields = ['name']
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        part_type = request.query_params.get('type')
        if not part_type:
            return Response({'error': 'type parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        parts = PCPart.objects.filter(part_type=part_type)
        serializer = self.get_serializer(parts, many=True)
        return Response(serializer.data)


class ConfigurationViewSet(viewsets.ModelViewSet):
    """PC 構成の CRUD API"""
    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer
    filterset_fields = ['usage']
    
    def perform_create(self, serializer):
        """構成作成時に合計金額を計算"""
        config = serializer.save()
        self._calculate_total_price(config)
    
    def perform_update(self, serializer):
        """構成更新時に合計金額を再計算"""
        config = serializer.save()
        self._calculate_total_price(config)
    
    def _calculate_total_price(self, config):
        """合計金額を計算"""
        total = 0
        for part_field in ['cpu', 'gpu', 'motherboard', 'memory', 'storage', 'psu', 'case']:
            part = getattr(config, part_field)
            if part:
                total += part.price
        config.total_price = total
        config.save()


class ScraperStatusViewSet(viewsets.ModelViewSet):
    """スクレイパー状態管理 API"""
    queryset = ScraperStatus.objects.all()
    serializer_class = ScraperStatusSerializer

