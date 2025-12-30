from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import GPUBooking
from django.conf import settings
from datetime import datetime, timezone
from .forms import GPUBookingForm
from MAIA.kubernetes_utils import get_namespaces, label_pod_for_deletion
from MAIA.dashboard_utils import verify_gpu_booking_policy, get_project, verify_gpu_availability
from MAIA.maia_fn import convert_username_to_jupyterhub_username
from django import forms
from MAIA.kubernetes_utils import generate_kubeconfig
from pathlib import Path
import os
import yaml
from apps.models import MAIAProject
from loguru import logger


@method_decorator(csrf_exempt, name="dispatch")  # 🚀 This disables CSRF for this API
class GPUSchedulabilityAPIView(APIView):
    permission_classes = [AllowAny]  # 🚀 Allow requests without authentication or CSRF

    def get(self, request, *args, **kwargs):
        try:
            booking_data = request.data.get("booking")
            if not booking_data:
                return Response({"error": "Missing booking data"}, status=400)
            if not booking_data.get("starting_time") or not booking_data.get("ending_time") or not booking_data.get("gpu"):
                return Response({"error": "Missing starting_time, ending_time or gpu"}, status=400)
            if booking_data.get("gpu") not in [gpu["name"] for gpu in settings.GPU_SPECS]:
                return Response({"error": "Invalid gpu"}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
        overlapping_time_slots, gpu_availability_per_slot, total_replicas = verify_gpu_availability(
            global_existing_bookings=GPUBooking.objects.all().values(),
            new_booking=request.data.get("booking"),
            gpu_specs=settings.GPU_SPECS,
        )
        return Response(
            {
                "overlapping_time_slots": overlapping_time_slots,
                "gpu_availability_per_slot": gpu_availability_per_slot,
                "total_replicas": total_replicas,
                "EXISTING_BOOKINGS": GPUBooking.objects.all().values(),
            },
            status=200,
        )

    def post(self, request, *args, **kwargs):
        try:
            user_email = request.data.get("user_email")
            namespace = request.data.get("namespace")
            if not user_email:
                return Response({"error": "Missing user_email"}, status=400)
            if not namespace:
                return Response({"error": "Missing namespace"}, status=400)

            secret_token = request.data.get("token")
            if not secret_token or secret_token != settings.SECRET_KEY:
                return Response({"error": "Invalid or missing secret token"}, status=403)

            if "booking" in request.data:
                booking_data = request.data["booking"]
                gpu = booking_data["gpu"]
                # Calculate the total number of days for existing bookings
                existing_bookings = GPUBooking.objects.filter(user_email=user_email)
                is_bookable, err_msg = verify_gpu_booking_policy(
                    existing_bookings,
                    booking_data,
                    global_existing_bookings=GPUBooking.objects.all().values(),
                    gpu_specs=settings.GPU_SPECS,
                )

                if not is_bookable:
                    return Response({"error": err_msg}, status=400)
                # Create the new booking
                GPUBooking.objects.create(
                    user_email=user_email,
                    start_date=booking_data["starting_time"],
                    end_date=booking_data["ending_time"],
                    namespace=namespace,
                    gpu=gpu,
                )
                return Response({"message": "Booking created successfully"})

            try:
                user_statuses = GPUBooking.objects.filter(user_email=user_email)

                is_schedulable = False

                current_time = datetime.now(timezone.utc)
                is_schedulable = any(
                    status.start_date <= current_time
                    and status.end_date >= current_time
                    and status.namespace.lower().replace("_", "-") == namespace.lower().replace("_", "-")
                    for status in user_statuses
                )
                if is_schedulable:
                    status = next(
                        status
                        for status in user_statuses
                        if status.start_date <= current_time and status.end_date >= current_time
                    )
                    return Response({"schedulable": is_schedulable, "until": status.end_date, "gpu": status.gpu})
                else:
                    return Response({"schedulable": is_schedulable, "until": None})
            except GPUBooking.DoesNotExist:
                return Response({"schedulable": False, "until": None})  # Default to not schedulable if not found

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


@login_required(login_url="/maia/login/")
def admin_delete_booking(request, id):

    id_token = request.session.get("oidc_id_token")

    booking = GPUBooking.objects.get(id=id)
    if not request.user.is_superuser:
        return JsonResponse({"error": "You do not have permission to delete this booking."}, status=403)

    booking.delete()
    pod_name = "jupyter-" + convert_username_to_jupyterhub_username(booking.user_email)

    _, cluster_id = get_project(booking.namespace, settings=settings, maia_project_model=MAIAProject)
    local_kubeconfig_dict = generate_kubeconfig(id_token, request.user.username, "default", cluster_id, settings=settings)

    with open(Path("/tmp").joinpath("kubeconfig-project-local"), "w") as f:
        yaml.dump(local_kubeconfig_dict, f)

        os.environ["KUBECONFIG_LOCAL"] = str(Path("/tmp").joinpath("kubeconfig-project-local"))

    label_pod_for_deletion(booking.namespace.lower().replace("_", "-"), pod_name=pod_name)
    return redirect("/maia/gpu-booking/my-bookings/")


@login_required(login_url="/maia/login/")
def delete_booking(request, id):

    id_token = request.session.get("oidc_id_token")

    booking = GPUBooking.objects.get(id=id)
    if request.user.email != booking.user_email and not request.user.is_superuser:
        return JsonResponse({"error": "You do not have permission to delete this booking."}, status=403)
    if booking.start_date < datetime.now(timezone.utc):
        # Create a new booking starting from the start date and ending now
        GPUBooking.objects.create(
            user_email=booking.user_email,
            start_date=booking.start_date,
            end_date=datetime.now(timezone.utc),
            namespace=booking.namespace,
            gpu=booking.gpu,
        )
    booking.delete()
    pod_name = "jupyter-" + convert_username_to_jupyterhub_username(booking.user_email)

    _, cluster_id = get_project(booking.namespace, settings=settings, maia_project_model=MAIAProject)
    local_kubeconfig_dict = generate_kubeconfig(id_token, request.user.username, "default", cluster_id, settings=settings)

    with open(Path("/tmp").joinpath("kubeconfig-project-local"), "w") as f:
        yaml.dump(local_kubeconfig_dict, f)

        os.environ["KUBECONFIG_LOCAL"] = str(Path("/tmp").joinpath("kubeconfig-project-local"))

    label_pod_for_deletion(booking.namespace.lower().replace("_", "-"), pod_name=pod_name)
    return redirect("/maia/gpu-booking/my-bookings/")


@login_required(login_url="/maia/login/")
def book_gpu(request):
    msg = None
    success = False

    email = request.user.email

    id_token = request.session.get("oidc_id_token")
    groups = request.user.groups.all()

    namespaces = []

    if request.user.is_superuser:
        namespaces = get_namespaces(id_token, api_urls=settings.API_URL, private_clusters=settings.PRIVATE_CLUSTERS)

    if namespaces is None or len(namespaces) == 0:
        namespaces = []
        for group in groups:
            if str(group) != "MAIA:users":
                namespaces.append(str(group).split(":")[-1].lower().replace("_", "-"))

    initial_data = {"user_email": email, "namespace": namespaces[0] if namespaces else None}

    if request.method == "POST":
        form = GPUBookingForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            msg = "Request for GPU Booking submitted successfully."
            success = True
            return redirect("/maia/gpu-booking/my-bookings/")
        else:
            logger.error(form.errors)
            msg = "Form is not valid"
    else:
        form = GPUBookingForm(request.POST or None, request.FILES or None, initial=initial_data)
        if not request.user.is_superuser:
            form.fields["namespace"].choices = [(ns, ns) for ns in namespaces]
        form.fields["user_email"] = forms.EmailField(
            widget=forms.EmailInput(
                attrs={
                    "placeholder": "Your Email.",
                    "class": "form-control",
                }
            )
        )
    context = {
        "namespaces": namespaces,
        "dashboard_version": settings.DASHBOARD_VERSION,
        "form": form,
        "msg": msg,
        "success": success,
    }
    if request.user.is_superuser:
        context["username"] = request.user.username + " [ADMIN]"
        context["user"] = ["admin"]
    else:
        context["username"] = request.user.username
    return render(request, "accounts/gpu_booking.html", context=context)


@login_required(login_url="/maia/login/")
def gpu_booking_info(request):

    id_token = request.session.get("oidc_id_token")
    groups = request.user.groups.all()
    namespaces = []
    if request.user.is_superuser:
        namespaces = get_namespaces(id_token, api_urls=settings.API_URL, private_clusters=settings.PRIVATE_CLUSTERS)

    else:
        for group in groups:
            if str(group) != "MAIA:users":
                namespaces.append(str(group).split(":")[-1].lower().replace("_", "-"))

    if request.user.is_superuser:
        bookings = GPUBooking.objects.all()
    else:
        bookings = GPUBooking.objects.filter(user_email=request.user.email)

    bookings_dict = []
    total_days = 0

    for booking in bookings:
        if booking.start_date <= datetime.now(timezone.utc) and booking.end_date >= datetime.now(timezone.utc):
            status = "Active"
        elif booking.end_date < datetime.now(timezone.utc):
            status = "Expired"
        else:
            status = "Waiting"
        booking_item = {
            "start_date": booking.start_date,
            "end_date": booking.end_date,
            "gpu": booking.gpu,
            "status": status,
            "email": booking.user_email,
            "namespace": booking.namespace,
            "id": booking.id,
        }
        total_days += (booking.end_date - booking.start_date).days
        bookings_dict.append(booking_item)

    context = {
        "namespaces": namespaces,
        "dashboard_version": settings.DASHBOARD_VERSION,
        "bookings": bookings_dict,
        "total_days": total_days,
    }
    if request.user.is_superuser:
        context["username"] = request.user.username + " [ADMIN]"
        context["user"] = ["admin"]
    else:
        context["username"] = request.user.username
    if "BACKEND" in os.environ:
        backend = os.environ["BACKEND"]
    else:
        backend = "default"
    context["BACKEND"] = backend
    return render(request, "accounts/gpu_booking_info.html", context=context)
