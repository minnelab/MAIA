from django import forms

from .models import GPUBooking
from django.conf import settings
from apps.models import MAIAProject
from MAIA.keycloak_utils import get_groups_in_keycloak
from MAIA.dashboard_utils import get_pending_projects, verify_gpu_booking_policy


class GPUBookingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(GPUBookingForm, self).__init__(*args, **kwargs)
        maia_groups = get_groups_in_keycloak(settings=settings)
        pending_projects = get_pending_projects(settings=settings, maia_project_model=MAIAProject)

        for pending_project in pending_projects:
            maia_groups[pending_project] = pending_project + " (Pending)"

        self.fields["namespace"] = forms.ChoiceField(
            choices=[(maia_group, maia_group) for maia_group in maia_groups.values()],
            widget=forms.Select(
                attrs={
                    "class": "form-select text-center fw-bold",
                    "style": "max-width: auto;",
                }
            ),
        )
        self.fields["user_email"] = forms.EmailField(
            widget=forms.EmailInput(attrs={"placeholder": "Your Email.", "class": "form-control", "readonly": "readonly"})
        )

        self.fields["gpu"] = forms.ChoiceField(
            choices=[(gpu["name"], gpu["name"]) for gpu in settings.GPU_SPECS if "replicas" in gpu and "count" in gpu],
            widget=forms.Select(
                attrs={
                    "class": "form-select text-center fw-bold",
                    "style": "max-width: auto;",
                }
            ),
        )

        self.fields["start_date"] = forms.DateField(widget=forms.TextInput(attrs={"class": "form-control", "type": "date"}))

        self.fields["end_date"] = forms.DateField(widget=forms.TextInput(attrs={"class": "form-control", "type": "date"}))

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        user_email = cleaned_data.get("user_email")
        gpu = cleaned_data.get("gpu")

        if start_date and end_date:
            if end_date <= start_date:
                self.add_error("end_date", "End date must be after start date.")
            else:
                existing_bookings = GPUBooking.objects.filter(user_email=user_email)
                booking_data = {
                    "starting_time": start_date.strftime("%Y-%m-%d  %H:%M:%S"),
                    "ending_time": end_date.strftime("%Y-%m-%d  %H:%M:%S"),
                    "gpu": gpu,
                }
                is_bookable, err_msg = verify_gpu_booking_policy(
                    existing_bookings,
                    booking_data,
                    global_existing_bookings=GPUBooking.objects.all().values(),
                    gpu_specs=settings.GPU_SPECS,
                )
                # Check existing bookings for the same user

                if not is_bookable:
                    self.add_error("end_date", err_msg)

        return cleaned_data

    class Meta:
        model = GPUBooking
        fields = ("namespace", "gpu", "user_email", "start_date", "end_date")
