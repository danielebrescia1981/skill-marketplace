from django.conf import settings


def site(request):
    return {
        "PRODUCT_NAME": settings.PRODUCT_NAME,
        "APP_VERSION": settings.APP_VERSION,
        "APP_ENVIRONMENT": settings.APP_ENVIRONMENT,
    }
