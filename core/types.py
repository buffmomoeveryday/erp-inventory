from django.http import HttpRequest as HttpRequestBase
from django_htmx.middleware import HtmxDetails


class HttpRequest(HttpRequestBase):
    htmx: HtmxDetails
