from django.urls import re_path, path
from django.views.decorators.csrf import csrf_exempt

from apps.api.views import BookView, WellKnownView

urlpatterns = [
    re_path("books/((?P<pk>\d+)/)?", csrf_exempt(BookView.as_view())),
    path("well-known/", WellKnownView.as_view()),
]
