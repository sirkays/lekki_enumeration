from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class CustomUserManager(BaseUserManager):
    def create_user(self, email, user_id, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set.")
        if not user_id:
            raise ValueError("The User ID field must be set.")

        email = self.normalize_email(email)
        user = self.model(email=email, user_id=user_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, user_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, user_id, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    user_id = models.CharField(max_length=255, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['user_id']

    def __str__(self):
        return f"{self.user_id} ({self.email})"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('visualizer', 'Visualizer'),
        ('agent', 'Field Agent'),
        ('viewer', 'Viewer'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    profile_image = models.ImageField(
        upload_to='profile_images/%Y/%m/',
        blank=True,
        null=True,
    )
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default='viewer',
    )
    full_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"Profile - {self.user.user_id} ({self.role})"

    @property
    def is_visualizer(self):
        return self.role in ('visualizer', 'admin')


class SessionToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_tokens",
    )
    key = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    meta = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.user.user_id}:{self.key[:6]}..."

    @classmethod
    def create_for_user(cls, user, hours_valid: int = 24, **meta):
        key = secrets.token_urlsafe(48)[:64]
        now = timezone.now()
        obj = cls.objects.create(
            user=user,
            key=key,
            created_at=now,
            expires_at=now + timedelta(hours=hours_valid),
            is_active=True,
            meta=meta or {},
        )
        return obj

    def revoke(self):
        self.is_active = False
        self.save(update_fields=["is_active"])

    @classmethod
    def get_valid_token(cls, key):
        try:
            token = cls.objects.select_related('user').get(
                key=key,
                is_active=True,
                expires_at__gt=timezone.now()
            )
            return token
        except cls.DoesNotExist:
            return None