"""Organisations et utilisateurs — voir docs/02-modele-de-donnees.md."""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Organization(models.Model):
    class Kind(models.TextChoices):
        DIGITALIA = "digitalia", "Digitalia"
        CLIENT = "client", "Client"

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CLIENT)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("email obligatoire")
        user = self.model(email=self.normalize_email(email), username=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("job", User.Job.ADMIN)
        return self._create(email, password, **extra)


class User(AbstractUser):
    class Job(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        PM = "pm", "Chef de projet"
        DEV = "dev", "Développeur"
        CLIENT = "client", "Utilisateur client"

    email = models.EmailField(unique=True)
    organization = models.ForeignKey(Organization, null=True, on_delete=models.PROTECT, related_name="users")
    job = models.CharField(max_length=10, choices=Job.choices, default=Job.CLIENT)
    invited_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
    objects = UserManager()  # type: ignore[assignment,misc]  # connexion par e-mail : signature différente

    @property
    def is_digitalia(self) -> bool:
        return bool(self.organization and self.organization.kind == Organization.Kind.DIGITALIA)

    @property
    def is_orbit_admin(self) -> bool:
        return self.is_digitalia and self.job == self.Job.ADMIN

    @property
    def initials(self) -> str:
        parts = (self.get_full_name() or self.email).split()
        return "".join(p[0] for p in parts[:2]).upper()
