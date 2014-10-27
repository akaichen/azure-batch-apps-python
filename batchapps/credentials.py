#-------------------------------------------------------------------------
# The Azure Batch Apps Python Client ver. 0.1.0
#
# Copyright (c) Microsoft Corporation. All rights reserved. 
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the ""Software""), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#--------------------------------------------------------------------------

import keyring
import requests_oauthlib
from oauthlib import oauth2
from oauthlib.oauth2 import BackendApplicationClient

import time
import ast
from .config import Configuration
from . import utils
from .exceptions import (
    AuthenticationException,
    InvalidConfigException)

import logging

CRED_STORE = 'AzureBatchApps'


def _http(base_uri, *extra):
    """Combine URL components in the an http url"""

    parts = [str(e) for e in extra]
    return "http://{0}{1}".format(str(base_uri), ''.join(parts))

def _https(base_uri, *extra):
    """Combine URL components in the an https url"""

    parts = [str(e) for e in extra]
    return "https://{0}{1}".format(str(base_uri), ''.join(parts))


class AzureOAuth(object):
    """
    Static class for setting up an Azure Active Directory authenticated
    session.
    """

    session = None
    config = None
    LOG = logging.getLogger('batch_apps')

    @staticmethod
    def _setup_session(auth, client, state=None):
        """Apply configuration info to set up a new OAuth2 session."""

        AzureOAuth.LOG.debug("Configuring session. Client: {0}, Cfg: "
                  "{1}".format(str(client), str(auth)))

        if (not utils.valid_keys(client, ['client_id', 'redirect_uri']) or
            not 'token_uri' in auth):

            raise InvalidConfigException(
                "Correct authentication configuration not found")

        if not AzureOAuth.session:
            redirect = _http(client.get('redirect_uri'))

            if isinstance(state, str):
                AzureOAuth.session = requests_oauthlib.OAuth2Session(
                    client.get('client_id'),
                    redirect_uri=redirect,
                    state=state)

            else:
                AzureOAuth.session = requests_oauthlib.OAuth2Session(
                    client.get('client_id'),
                    redirect_uri=redirect)

    @staticmethod
    def get_session(config=None):
        """Continue an existing session if one exists.

        :Kwargs:
            - config (:class:`.Configuration`): A custom configuration
              object. Default is `None` where a default
              :class:`.Configuration` will be created.

        :Returns:
            - An authenticated :class:`.Credentials` object.

        :Raises:
            - A :class:`.InvalidConfigException` if the supplied,
              or default configuration does not contain the necessary
              authentication data.
            - A :class:`.AuthenticationException` if there's not existing
              stored session or the token is invalid.
        """
        AzureOAuth.config = config if config else Configuration()
        return Credentials(AzureOAuth.config,
                           AzureOAuth.config.get('client_id'))

    @staticmethod
    def get_authorization_url(config=None, msa=False, prompt=False, **additional_args):
        """
        Construct client-specific authentication URL. This URL can be used
        in a web browser to direct the user to log in and authenticate
        the client session.

        :Kwargs:
            - config (:class:`.Configuration`): A custom configuration object.
              Default is `None` where a default :class:`.Configuration` will
              be created.
            - msa (bool): Authenticate with MSA. Default is ``False``.
            - prompt (bool): Force login prompt regardless of existing session.
              Default is ``False``.
            - additional_args (dict): Any additional AAD parameters to include
              in the URL

        :Returns:
            - A URL (str) that can be used to direct the user to a login page.
            - A guid (str) for validating the state of the server
              communication.

        :Raises:
            - A :class:`.InvalidConfigException` if the supplied, or default
              configuration does not contain the necessary authentication
              data.
            - A :class:`.AuthenticationException` if there was an error
              generating the URL.
        """

        AzureOAuth.config = config if config else Configuration()

        if not hasattr(AzureOAuth.config, "aad_config"):
            raise InvalidConfigException(
                "Correct authentication configuration not found")

        auth = AzureOAuth.config.aad_config()
        AzureOAuth._setup_session(auth, AzureOAuth.config.default_params())

        if msa:
            additional_args['domain_hint'] = 'live.com'
        if prompt:
            additional_args['prompt'] = 'login'

        try:
            auth_url, state = AzureOAuth.session.authorization_url(
                _https(auth['auth_uri']),
                resource=_https(auth['resource']),
                **additional_args)

            return auth_url, state

        except Exception as exp:
            raise AuthenticationException(
                "Failed to generate auth url. Error: {0}".format(str(exp)))

    @staticmethod
    def get_authorization_token(auth_url, config=None, state=None):
        """Retrieve access token from AAD server.

        :Args:
            - auth_url (str): The redirect URL generated from a successfull
              browser sign-in.

        :Kwargs:
            - config (:class:`.Configuration`): A custom configuration object.
              Default is `None` where a default :class:`.Configuration` will
              be created.
            - state (str): A state guid for auth server validation.

        :Returns:
            - An authenticated :class:`.Credentials` object.

        :Raises:
            - A :class:`.InvalidConfigException` if the supplied, or default
              configuration does not contain the necessary authentication
              data.
            - A :class:`.AuthenticationException` if the supplied ``auth_url``
              is invalid (e.g. has expired).
        """

        AzureOAuth.config = config if config else Configuration()

        if not hasattr(AzureOAuth.config, "aad_config"):
            raise InvalidConfigException(
                "Correct authentication configuration not found")

        auth = AzureOAuth.config.aad_config()
        AzureOAuth._setup_session(auth,
                                  AzureOAuth.config.default_params(),
                                  state=state)

        redirect = AzureOAuth.config.get('redirect_uri')

        if auth_url.startswith(_http(redirect)):
            auth_url = auth_url.replace('http', 'https')

        elif not auth_url.startswith(_https(redirect)):
            auth_url = _https(redirect) + auth_url

        try:
            AzureOAuth.LOG.debug("Fetching token with token_uri: "
                                 "{0}".format(_https(auth['token_uri'])))

            token = AzureOAuth.session.fetch_token(
                _https(auth['token_uri']),
                authorization_response=auth_url)

        except oauth2.rfc6749.errors.InvalidGrantError as excp:
            raise AuthenticationException(excp.description)

        except oauth2.rfc6749.errors.OAuth2Error as excp:
            raise AuthenticationException(excp.description)

        except oauth2.rfc6749.errors.MismatchingStateError as excep:
            raise AuthenticationException(excp.description)

        authorized_creds = Credentials(AzureOAuth.config,
                                       AzureOAuth.config.get('client_id'),
                                       token=token)
        return authorized_creds

    @staticmethod
    def get_principal_token(config=None):
        """Retrieve a Service Principal access token from AAD server.

        :Kwargs:
            - config (:class:`.Configuration`): A custom configuration object.
              Default is `None` where a default :class:`.Configuration`
              will be created.

        :Returns:
            - An authenticated :class:`.Credentials` object.

        :Raises:
            - A :class:`.InvalidConfigException` if the supplied, or default
              configuration does not contain the necessary authentication
              data.
            - A :class:`.AuthenticationException` if the supplied credentials
              are invalid (e.g. have expired).
        """

        AzureOAuth.config = config if config else Configuration()

        if not hasattr(AzureOAuth.config, "aad_config"):
            raise InvalidConfigException(
                "Correct authentication configuration not found")

        auth = AzureOAuth.config.aad_config()

        try:
            secret = auth['service_principal_key']
            service = auth['service_principal'].split('@')
            client_id = service[0]
            tenant = service[1]
            token_uri = auth['token_uri'].replace("common", tenant)

        except KeyError:
            raise InvalidConfigException(
                "Supplied config does not contain Service Principal auth.")

        except (AttributeError, IndexError):
            raise InvalidConfigException(
                "service_principal must be in the format {client_id}@{tenant}")

        silent_session = requests_oauthlib.OAuth2Session(
            client_id,
            client=BackendApplicationClient(client_id))

        try:
            AzureOAuth.LOG.debug("Fetching token with token_uri: "
                                 "{0}".format(_https(token_uri)))

            token = silent_session.fetch_token(
                _https(token_uri),
                client_id=client_id,
                resource=_https(auth['resource']),
                client_secret=secret,
                response_type="client_credentials")

        except oauth2.rfc6749.errors.InvalidGrantError as excp:
            raise AuthenticationException(excp.description)

        except oauth2.rfc6749.errors.OAuth2Error as excp:
            raise AuthenticationException(excp.description)

        authorized_creds = Credentials(AzureOAuth.config,
                                       client_id,
                                       token=token)
        return authorized_creds


class Credentials(object):
    """
    Container to store and retrieve customer credential information using the
    Keyring lib to access the system keyring service according to operating
    system. See: https://pypi.python.org/pypi/keyring
    """

    def __init__(self, config, client_id, token=None):
        """
        New credentials object. Preferably this class is instantiated by
        :class:`.AzureOAuth` rather than called directly.

        :Args:
            - config (:class:`.Configuration`): A configuration object to
              define the client session.
            - client_id (str): The client ID for the application as defined
              in the Configuration.

        :Kwargs:
            - token (dict): An authentication token, if not provided will try
              to retrieve from a previous session.

        :Raises:
            - :class:`.AuthenticationException` if provided token is formatted
              incorrectly, or if none has been provided and no previously
              stored token exists.
        """

        self._log = logging.getLogger('batch_apps')

        if not hasattr(config, "aad_config"):
            raise InvalidConfigException(
                "Correct authentication configuration not found")

        self.cfg = config.aad_config()
        self._id = client_id

        if not token:
            self._log.debug("No token supplied, attempting to "
                            "retrieve previous session.")

            token = self.get_stored_auth()

        self.token = token

        if not utils.valid_keys(self.token, ['token_type', 'access_token']):
            raise AuthenticationException("Invalid token.")

        self.store_auth(self.token)
        self.get_session()


    def get_session(self):
        """
        Generate the authenticated OAuth2 session.

        :Returns:
            - An authenticated :class:`requests_oauthlib.OAuth2Session`

        :Raises:
            - :class:`.AuthenticationException` if the token is invalid
              or expired.
        """
        resource = _https(self.cfg['resource'])
        refresh = _https(self.cfg['token_uri'])
        countdown = float(self.token['expires_at']) - time.time()

        self.token['expires_in'] = countdown
        self._log.debug("Token expires in: {0}".format(countdown))

        try:
            if 'refresh_token' in self.token:
                return requests_oauthlib.OAuth2Session(
                    self._id,
                    token=self.token,
                    auto_refresh_url=refresh,
                    auto_refresh_kwargs={'client_id':self._id,
                                         'resource':resource},
                    token_updater=self.store_auth)

            else:
                return requests_oauthlib.OAuth2Session(self._id,
                                                       token=self.token)

        except oauth2.rfc6749.errors.TokenExpiredError as excp:
            self._log.info(
                "Token is no longer able to be refreshed, please log in.")

            raise AuthenticationException(
                "Token expired: {0}".format(excp.description))

    def get_stored_auth(self):
        """Retrieve a previous stored access token for refreshing

        :Returns:
            - The token as a dictionary.

        :Raises:
            - :class:`.AuthenticationException` if no stored token is found.
        """
        self._log.debug("Retrieving stored token with {0} "
                        "and {1}".format(CRED_STORE, self._id))
        token = keyring.get_password(CRED_STORE, self._id)

        if token is None:
            raise AuthenticationException(
                "Unable to find stored credentials. Please log in.")

        else:
            self._log.debug("Existing token successfully retrieved "
                            "for client: {0}".format(self._id))

            return ast.literal_eval(str(token))

    def store_auth(self, token):
        """Store an access token for refreshing future sessions.

        :Args:
            - token (dict): The access token to be stored.
        """
        self.token = token
        self._log.debug(
            "Storing updated token for client: {0}".format(self._id))

        keyring.set_password(CRED_STORE, self._id, str(token))

    def clear_auth(self):
        """
        Clear stored credentials.
        Remove the current users credentials from the keyring service.
        A password will need to be supplied for future sessions. This will not
        delete or un-authenticate the current :class:`.Credentials` object.

        :Raises:
            - :class:`OSError` if the stored data cannot be cleared.
        """
        try:
            keyring.delete_password(CRED_STORE, self._id)
        except Exception as ex:
            raise OSError("Unable to clear stored credentials "
                          "from KeyRing: {error}".format(error=ex))