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

from mock import MagicMock
import pytest

from apployer import app_compare
from apployer import cf_cli
from apployer.appstack import AppConfig


@pytest.fixture
def mock_cf_cli(monkeypatch):
    mock_cf = MagicMock()
    monkeypatch.setattr('apployer.app_compare.cf_cli', mock_cf)
    mock_cf.CommandFailedError = cf_cli.CommandFailedError
    return mock_cf


@pytest.fixture
def mock_cf_api(monkeypatch):
    cf_api = MagicMock()
    monkeypatch.setattr('apployer.app_compare.cf_api', cf_api)
    return cf_api


@pytest.fixture
def fake_app_summary():
    return {
        "name": "some-app",
        "routes": [
            {
                "guid": "0bb42a5b-2dbf-439a-852e-ea8c686199e7",
                "host": "someapp",
                "domain": {
                    "guid": "7e8c9473-ae02-4567-beb2-8dd67104d3d0",
                    "name": "example.com"
                }
            }
        ],
        "running_instances": 1,
        "services": [
            {
                "guid": "15d10bb0-6b77-44f3-be20-c51857addc3f",
                "name": "service_1"
            },
            {
                "guid": "f7892fac-419f-4d6c-b0c6-6759a619ab87",
                "name": "service_2"
            }
        ],
        "buildpack": "python_buildpack",
        "environment_json": {
            "SOME_VALUE": "FAKE",
            "SOME_OTHER_VALUE": "not present in app config"
        },
        "some_additional_field": True,
        "memory": 64,
        "instances": 2,
        "disk_quota": 1024,
        "command": "python fake_fake/fake_app.py",
    }


@pytest.fixture
def app():
    """App config that is consistent with values in `fake_app_summary`."""
    return AppConfig('some-app', app_properties={
        'buildpack': 'python_buildpack',
        'command': 'python fake_fake/fake_app.py',
        'disk_quota': '1G',
        'env': {'SOME_VALUE': 'FAKE'},
        'instances': 2,
        'memory': '64M',
        'services': ['service_1', 'service_2'],
        'host': 'someapp'
    })


@pytest.mark.parametrize('appstack_version, summary_version, should_update', [
    (None, None, False),
    (None, '0.0.1', False),
    ('0.0.1', None, True),
    ('0.1.2', '0.1.2', False),
    ('0.1.3', '0.1.2', True),
    ('0.1.2', '0.1.3', False),
])
def test_should_update(mock_cf_cli, mock_cf_api, fake_app_summary, app,
                       appstack_version, summary_version, should_update):
    if appstack_version:
        app.app_properties['env']['VERSION'] = appstack_version
    if summary_version:
        fake_app_summary['environment_json']['VERSION'] = summary_version
    app_guid = 'some-fake-guid'
    mock_cf_cli.get_app_guid.return_value = app_guid
    mock_cf_api.get_app_summary.return_value = fake_app_summary

    assert app_compare.should_update(app) == should_update

    mock_cf_cli.get_app_guid.assert_called_with(app.name)
    mock_cf_api.get_app_summary.assert_called_with(app_guid)


def test_should_update_no_app_in_live_env(mock_cf_cli, app):
    mock_cf_cli.get_app_guid.side_effect = cf_cli.CommandFailedError
    assert app_compare.should_update(app)


@pytest.mark.parametrize('app_properties, app_summary, are_different', [
    ({'buildpack': 'python_buildpack'}, {'buildpack': 'python_buildpack'}, False),
    ({'buildpack': 'python_buildpack'}, {'buildpack': 'python_buildpack', 'asdasd': 1}, False),
    ({'buildpack': 'python_buildpack'}, {'buildpack': 'bla_buildpack'}, True),
    ({'instances': 2}, {'instances': 3}, True),
    ({'memory': '64M'}, {'memory': 65}, True),
    ({'memory': '64M'}, {'memory': 64}, False),
    ({'disk_quota': '2G'}, {'disk_quota': 2048}, False),
    ({'env': {'bla': 1}}, {'environment_json': {'bla': 2}}, True),
    ({'host': 'abc'}, {'routes': [{'host': 'qwe'}]}, True),
    ({'host': 'abc'}, {'routes': [{'host': 'qwe'}, {'host': 'abc'}]}, False),
    ({'services': ['service_1', 'service_2']}, {'services': [{'name': 'service_1'}]}, True)
])
def test_compare(app_properties, app_summary, are_different):
    assert app_compare._properties_differ(app_properties, app_summary) == are_different


@pytest.mark.parametrize('dict_a, dict_b, is_part_of', [
    ({'a': 'b'}, {'a': 'b'}, True),
    ({'a': 'b'}, {'a': 'b', 'c': 1}, False),
    ({'a': 'b', 'c': 1}, {'a': 'b'}, True),
    ({'a': 'c'}, {'a': 'b'}, False),
])
def test_dict_is_part_of(dict_a, dict_b, is_part_of):
    assert app_compare._dict_is_part_of(dict_a, dict_b) == is_part_of


@pytest.mark.parametrize('value_string, megabytes', [
    ('400M', 400),
    ('2MB', 2),
    ('4G', 4096),
    ('1GB', 1024),
])
def test_normalize_to_megabytes(value_string, megabytes):
    assert app_compare._normalize_to_megabytes(value_string) == megabytes
