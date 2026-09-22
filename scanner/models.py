from django.db import models


class LoginAttempt(models.Model):
    """A failed sign-in, kept for a day so password guessing can be throttled."""

    client = models.CharField(max_length=64)  # IP address, or the /64 network for IPv6
    username = models.CharField(max_length=150)  # as typed, lowercased
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "created_at"]),
            models.Index(fields=["username", "created_at"]),
        ]

    def __str__(self):
        return f"{self.username or '(no username)'} from {self.client}"
