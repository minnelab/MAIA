from http import HTTPStatus
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny


from apps.api.serializers import BookSerializer
from apps.models import Book
from django.conf import settings
from rest_framework.throttling import UserRateThrottle


class BookView(APIView):

    permission_classes = (IsAuthenticatedOrReadOnly,)

    def post(self, request):
        serializer = BookSerializer(data=request.POST)
        if not serializer.is_valid():
            return Response(data={**serializer.errors, "success": False}, status=HTTPStatus.BAD_REQUEST)
        serializer.save()
        return Response(data={"message": "Record Created.", "success": True}, status=HTTPStatus.OK)

    def get(self, request, pk=None):
        if not pk:
            return Response(
                {"data": [BookSerializer(instance=obj).data for obj in Book.objects.all()], "success": True}, status=HTTPStatus.OK
            )
        try:
            obj = get_object_or_404(Book, pk=pk)
        except Http404:
            return Response(data={"message": "object with given id not found.", "success": False}, status=HTTPStatus.NOT_FOUND)
        return Response({"data": BookSerializer(instance=obj).data, "success": True}, status=HTTPStatus.OK)

    def put(self, request, pk):
        try:
            obj = get_object_or_404(Book, pk=pk)
        except Http404:
            return Response(data={"message": "object with given id not found.", "success": False}, status=HTTPStatus.NOT_FOUND)
        serializer = BookSerializer(instance=obj, data=request.POST, partial=True)
        if not serializer.is_valid():
            return Response(data={**serializer.errors, "success": False}, status=HTTPStatus.BAD_REQUEST)
        serializer.save()
        return Response(data={"message": "Record Updated.", "success": True}, status=HTTPStatus.OK)

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(Book, pk=pk)
        except Http404:
            return Response(data={"message": "object with given id not found.", "success": False}, status=HTTPStatus.NOT_FOUND)
        obj.delete()
        return Response(data={"message": "Record Deleted.", "success": True}, status=HTTPStatus.OK)


class WellKnownView(APIView):
    throttle_classes = [UserRateThrottle]
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        data = {
            "issuer": settings.OIDC_ISSUER_URL,
            "client_id": settings.OIDC_RP_PUBLIC_CLIENT_ID,
            "realm": settings.OIDC_REALM_NAME,
        }
        return Response(data=data, status=HTTPStatus.OK)
