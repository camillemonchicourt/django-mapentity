import logging
from urlparse import urlparse
from subprocess import check_output

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in

from . import app_settings


logger = logging.getLogger(__name__)

CONVERSION_SERVER_HOST = urlparse(app_settings['CONVERSION_SERVER']).hostname
CAPTURE_SERVER_HOST = urlparse(app_settings['CAPTURE_SERVER']).hostname
LOCALHOST = check_output(['hostname', '-I']).split() + ['127.0.0.1']


def get_internal_user():
    if not hasattr(get_internal_user, 'instance'):
        username = app_settings['INTERNAL_USER']
        try:
            User = get_user_model()
            internal_user = User.objects.get(username=username)
        except User.DoesNotExist:
            internal_user = User(username=username,
                                 password=settings.SECRET_KEY)
            internal_user.is_active = False
            internal_user.is_staff = False
            internal_user.save()
        get_internal_user.instance = internal_user
    return get_internal_user.instance


class AutoLoginMiddleware(object):
    """
    This middleware enables auto-login for Conversion and Capture servers.

    We could have deployed implemented authentication in ConvertIt and
    django-screamshot, or deployed OpenId, or whatever. But this was a lot easier.
    """
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_anonymous():
            remoteip = request.META.get('REMOTE_ADDR')
            remotehost = request.META.get('REMOTE_HOST')
            is_running_tests = ('FrontendTest' in request.META.get('HTTP_USER_AGENT', '') or
                                getattr(settings, 'TEST', False))
            is_localhost = (remoteip in LOCALHOST or remotehost == 'localhost')
            is_auto_allowed = (is_localhost or
                               (remoteip and remoteip in (CONVERSION_SERVER_HOST,
                                                          CAPTURE_SERVER_HOST)) or
                               (remotehost and remotehost in (CONVERSION_SERVER_HOST,
                                                              CAPTURE_SERVER_HOST)))
            if is_auto_allowed and not is_running_tests:
               logger.debug("Auto-login for %s/%s" % (remoteip, remotehost))
               request.user = get_internal_user()
               user_logged_in.send(self, user=request.user, request=request)
        return None
