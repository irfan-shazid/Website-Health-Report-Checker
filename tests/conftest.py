import pytest
from django.core.cache import caches

PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def reset_rate_limits():
    caches["ratelimit"].clear()
    yield
    caches["ratelimit"].clear()


@pytest.fixture
def operator(django_user_model):
    return django_user_model.objects.create_user(username="operator", password=PASSWORD)


@pytest.fixture
def signed_in_client(client, operator):
    client.force_login(operator)
    return client
