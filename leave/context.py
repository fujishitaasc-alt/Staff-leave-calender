from django.conf import settings


def mode(request):
    return {"demo": settings.DEMO}
