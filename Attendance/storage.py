from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)
