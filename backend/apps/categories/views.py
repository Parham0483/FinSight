from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import get_member_org, require_org_param

from .models import Category
from .serializers import CategorySerializer


class CategoryListCreateView(APIView):
    """GET/POST /api/v1/categories/?org={org_id}"""
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        org = require_org_param(request)
        qs = Category.objects.filter(org=org).select_related('parent')
        kind = request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        return Response(CategorySerializer(qs, many=True).data)

    def post(self, request: Request) -> Response:
        org = require_org_param(request)
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(org=org, is_system=False)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/categories/{pk}/?org={org_id}"""
    permission_classes = (IsAuthenticated,)

    def _get(self, request: Request, pk: str) -> Category:
        org = require_org_param(request)
        return Category.objects.get(id=pk, org=org)

    def get(self, request: Request, pk: str) -> Response:
        try:
            category = self._get(request, pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CategorySerializer(category).data)

    def patch(self, request: Request, pk: str) -> Response:
        try:
            category = self._get(request, pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request: Request, pk: str) -> Response:
        try:
            category = self._get(request, pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if category.is_system:
            return Response(
                {'detail': 'System categories cannot be deleted; rename or retype instead.'},
                status=status.HTTP_409_CONFLICT,
            )
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
