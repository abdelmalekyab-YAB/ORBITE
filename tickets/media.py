"""Kinds of files that can be attached to tickets: photos, videos, audio and documents."""
import os

from django.utils.translation import gettext_lazy as _

KINDS = {
    "image": {"png", "jpg", "jpeg", "gif", "webp", "heic", "heif", "bmp", "svg"},
    "video": {"mp4", "webm", "mov", "m4v", "ogv", "avi", "mkv", "3gp"},
    "audio": {"mp3", "wav", "ogg", "oga", "opus", "m4a", "aac", "weba", "flac", "amr"},
    "document": {
        "pdf", "doc", "docx", "odt", "rtf", "txt", "md", "csv", "xls", "xlsx", "ods",
        "ppt", "pptx", "odp", "zip", "rar", "7z", "json", "xml", "log", "eml", "msg",
    },
}
KIND_LABELS = {"image": _("Photo"), "video": _("Video"), "audio": _("Audio"), "document": _("Document")}
ALLOWED_EXTENSIONS = set().union(*KINDS.values())
# What the file pickers offer (the server checks the extension anyway).
ACCEPT = "image/*,video/*,audio/*," + ",".join(f".{ext}" for ext in sorted(KINDS["document"]))


def extension(name):
    return os.path.splitext(name)[1].lower().lstrip(".")


def kind_for(name):
    ext = extension(name)
    for kind, extensions in KINDS.items():
        if ext in extensions:
            return kind
    return "document"


def is_allowed(name):
    return extension(name) in ALLOWED_EXTENSIONS
