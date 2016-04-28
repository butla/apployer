#
# Copyright (c) 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from mock import call
import pytest

from .fake_cf_outputs import GET_ENV_SUCCESS, GET_SERVICE_INFO_SUCCESS
from apployer import cf_cli
from apployer.cf_cli import CommandFailedError, CfInfo


def test_run_command_output_without_redirection_fail(mock_popen):
    mock_popen.set_command('cf bla', returncode=1)
    with pytest.raises(CommandFailedError):
        cf_cli._run_command([cf_cli.CF, 'bla'], redirect_output=False)


def test_get_app_env(mock_popen):
    app_name = 'FAKYFAKE'
    mock_popen.set_command('cf env ' + app_name, stdout=GET_ENV_SUCCESS)

    assert cf_cli.env(app_name) == GET_ENV_SUCCESS


def test_get_app_env_fail(mock_popen):
    app_name = 'bla'
    mock_popen.set_command('cf env ' + app_name, returncode=1)

    with pytest.raises(CommandFailedError):
        cf_cli.env(app_name)


def test_set_api_url_with_validation(mock_popen):
    api_url = 'https://api.example.com'
    mock_popen.set_command('cf api ' + api_url)

    cf_cli.api(api_url, True)


def test_set_api_url_fail(mock_popen):
    api_url = 'https://api.example.com'
    mock_popen.set_command('cf api ' + api_url, returncode=1)

    with pytest.raises(CommandFailedError):
        cf_cli.api(api_url, True)


def test_authorize_fail(mock_popen):
    username, password = 'username', 'password'
    mock_popen.set_command('cf auth {} {}'.format(username, password), returncode=1)

    with pytest.raises(CommandFailedError):
        cf_cli.auth(username, password)


@pytest.mark.parametrize('function, cf_option', [
    (cf_cli.bind_service, 'bind-service'),
    (cf_cli.unbind_service, 'unbind-service'),
])
def test_bind_and_unbind_service(function, cf_option, mock_popen):
    app_name = 'some_app'
    instance_name = 'some_service_instance'

    mock_popen.set_command('cf {} {} {}'.format(cf_option, app_name, instance_name))

    function(app_name, instance_name)


@pytest.mark.parametrize('function, cf_option', [
    (cf_cli.create_service_broker, 'create-service-broker'),
    (cf_cli.update_service_broker, 'update-service-broker'),
])
def test_create_and_update_service_broker(function, cf_option, mock_popen):
    name = 'some_broker_name'
    user = 'broker_user_name'
    password = 'broker_password'
    url = 'https://some-broker.example.com'
    mock_popen.set_command('cf {} {} {} {} {}'
                           .format(cf_option, name, user, password, url))

    function(name, user, password, url)


@pytest.mark.parametrize('function, cf_option', [
    (cf_cli.create_user_provided_service, 'create-user-provided-service'),
    (cf_cli.update_user_provided_service, 'update-user-provided-service'),
])
def test_create_and_update_user_provided_service(function, cf_option, mock_popen):
    service_name = 'some_service'
    credentials = '{"key1": "value", "key2": 13}'
    mock_popen.set_command('cf {} {} -p {}'
                           .format(cf_option, service_name, credentials))

    function(service_name, credentials)


def test_create_service_instance(mock_popen):
    service, plan, instance_name = 'hdfs', 'shared', 'hdfs-instance'
    mock_popen.set_command('cf create-service {} {} {}'.format(service, plan, instance_name))

    cf_cli.create_service(service, plan, instance_name)


def test_enable_service_access(mock_popen):
    service_name = 'hdfs'
    mock_popen.set_command('cf enable-service-access ' + service_name)

    cf_cli.enable_service_access(service_name)


def test_get_service_info(mock_popen):
    service_name = 'some-service'
    mock_popen.set_command('cf service ' + service_name, stdout=GET_SERVICE_INFO_SUCCESS)

    assert cf_cli.service(service_name) == GET_SERVICE_INFO_SUCCESS


def test_login(mock_popen):
    cf_info = CfInfo('https://api.example.com', 'password')
    mock_popen.set_command('cf api --skip-ssl-validation ' + cf_info.api_url)
    mock_popen.set_command('cf auth {} {}'.format(cf_info.user, cf_info.password))
    mock_popen.set_command('cf target -o {} -s {}'.format(cf_info.org, cf_info.space))

    cf_cli.login(cf_info)

    # there should be three method invocations, three waits
    assert len(mock_popen.mock.method_calls) == 6


def test_push_app(mock_popen):
    app_location = '/some/app/path'
    manifest_location = '/some/app/app_manifest.yml'
    timeout = 100
    command = ['cf', 'push', '-t', str(timeout),
               '-f', manifest_location, '--no-start', '--no-hostname']
    mock_popen.set_command(' '.join(command))

    cf_cli.push(app_location, manifest_location, ' '.join(command[-2:]), timeout)

    assert call.Popen(command, cwd=app_location) in mock_popen.mock.method_calls


def test_restage_app(mock_popen):
    app_name = 'some_app'
    mock_popen.set_command('cf restage ' + app_name)
    cf_cli.restage(app_name)


def test_restart_app(mock_popen):
    app_name = 'some_app'
    mock_popen.set_command('cf restart ' + app_name)
    cf_cli.restart(app_name)


def test_set_target_fail(mock_popen):
    org, space = 'seedorg', 'seedspace'
    mock_popen.set_command('cf target -o {} -s {}'.format(org, space), returncode=1)

    with pytest.raises(CommandFailedError):
        cf_cli.target(org, space)


def test_buildpack_create(mock_popen):
    buildpack_name = 'some-buildpack'
    buildpack_path = '/bla/ble/some-buildpack-1.2.3.zip'
    position = 1
    mock_popen.set_command('cf create-buildpack {} {} {} --enable'
                           .format(buildpack_name, buildpack_path, position))

    cf_cli.create_buildpack(buildpack_name, buildpack_path, position)


def test_buildpack_update(mock_popen):
    buildpack_name = 'some-buildpack'
    buildpack_path = '/bla/ble/some-buildpack-1.2.3.zip'
    mock_popen.set_command('cf update-buildpack {} -p {}'.format(buildpack_name, buildpack_path))

    cf_cli.update_buildpack(buildpack_name, buildpack_path)


def test_create_org(mock_popen):
    org_name = 'some-org'
    mock_popen.set_command('cf create-org {}'.format(org_name))

    cf_cli.create_org(org_name)


def test_create_space(mock_popen):
    org_name = 'some-org'
    space_name = 'some-space'
    mock_popen.set_command('cf create-space {} -o {}'.format(space_name, org_name))

    cf_cli.create_space(space_name, org_name)


def test_get_brokers(mock_popen):
    cmd_output = """Getting service brokers as admin...

name                 url
application-broker   http://application-broker.example.com
cdh                  http://cdh-broker.example.com
"""
    mock_popen.set_command('cf service-brokers', stdout=cmd_output)

    assert cf_cli.service_brokers() == {'application-broker', 'cdh'}


def test_get_buildpacks(mock_popen):
    cmd_output = """Getting buildpacks...

buildpack              position   enabled   locked   filename
tap-java-buildpack     1          true      false    tap-java-buildpack-v3.4-5.zip
staticfile_buildpack   2          true      false    staticfile_buildpack-cached-v1.1.0.zip
"""
    mock_popen.set_command('cf buildpacks', stdout=cmd_output)
    proper_buildpacks = [cf_cli.BuildpackDescription('tap-java-buildpack', '1', 'true', 'false',
                                                     'tap-java-buildpack-v3.4-5.zip'),
                         cf_cli.BuildpackDescription('staticfile_buildpack', '2', 'true', 'false',
                                                     'staticfile_buildpack-cached-v1.1.0.zip')]

    assert cf_cli.buildpacks() == proper_buildpacks


def test_get_oauth_token(mock_popen):
    cmd_output = """Getting OAuth token...
OK

bearer abcdf.1233456789.fdcba
"""
    mock_popen.set_command('cf oauth-token', stdout=cmd_output)

    assert cf_cli.oauth_token() == 'bearer abcdf.1233456789.fdcba'


def test_get_app_and_service_guid(mock_popen):
    guid = '8b89a54b-b292-49eb-a8c4-2396ec038120'
    cmd_output = guid + '\n'
    name = 'something'
    mock_popen.set_command('cf service --guid {}'.format(name), stdout=cmd_output)
    mock_popen.set_command('cf app --guid {}'.format(name), stdout=cmd_output)

    assert cf_cli.get_app_guid(name) == guid
    assert cf_cli.get_service_guid(name) == guid
