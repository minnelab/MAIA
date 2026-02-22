import os
from MAIA.kubernetes_utils import get_namespace_details
from django.conf import settings


from rest_framework.response import Response
import urllib3

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@method_decorator(csrf_exempt, name="dispatch")  # 🚀 This disables CSRF for this API
class ListSegmentationModelsAPIView(APIView):
    permission_classes = [AllowAny]  # 🚀 Allow requests without authentication or CSRF

    def post(self, request, *args, **kwargs):
        try:
            id_token = request.data.get("id_token")
            username = request.data.get("username")

            if not id_token:
                return Response({"error": "Missing ID Token"}, status=400)
            if not username:
                return Response({"error": "Missing Username"}, status=400)

            namespace_id = os.environ["MAIA_SEGMENTATION_PORTAL_NAMESPACE_ID"]
            (
                maia_workspace_apps,
                remote_desktop_dict,
                ssh_ports,
                monai_models,
                orthanc_list,
                deployed_clusters,
                nvflare_dashboards,
            ) = get_namespace_details(settings, id_token, namespace_id, username, is_admin=False)

            return Response({"models": monai_models}, status=200)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
