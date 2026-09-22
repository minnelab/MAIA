from django.conf import settings


def cfg_assets_root(request):
    return {
        "ASSETS_ROOT": settings.ASSETS_ROOT,
        "BACKGROUND_IMAGE_1": settings.BACKGROUND_IMAGE_1,
        "BACKGROUND_IMAGE_2": settings.BACKGROUND_IMAGE_2,
    }