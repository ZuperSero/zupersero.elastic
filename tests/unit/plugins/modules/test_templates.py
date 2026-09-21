# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, call

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.template import (
    ComponentTemplateService,
    IndexTemplateService,
)
from ansible_collections.zupersero.elastic.plugins.modules import (
    component_template,
    index_template,
)


class ModuleExit(Exception):
    def __init__(self, result):
        super().__init__()
        self.result = result


class ModuleFailure(Exception):
    def __init__(self, result):
        super().__init__(result["msg"])
        self.result = result


class FakeModule:
    def __init__(self, params, check_mode=False):
        self.params = params
        self.check_mode = check_mode

    def exit_json(self, **kwargs):
        raise ModuleExit(kwargs)

    def fail_json(self, **kwargs):
        raise ModuleFailure(kwargs)


def response(status, data=None):
    return ElasticsearchResponse(status=status, data=data, headers={})


def component_params(**overrides):
    values = {
        "name": "phase1/component",
        "settings": None,
        "mappings": None,
        "aliases": None,
        "version": None,
        "metadata": None,
        "deprecated": None,
        "replace": False,
        "state": "present",
    }
    values.update(overrides)
    return values


def index_params(**overrides):
    values = {
        "name": "phase1/index-template",
        "index_patterns": None,
        "composed_of": None,
        "settings": None,
        "mappings": None,
        "aliases": None,
        "priority": None,
        "version": None,
        "metadata": None,
        "data_stream": None,
        "lifecycle": None,
        "allow_auto_create": None,
        "ignore_missing_component_templates": None,
        "deprecated": None,
        "replace": False,
        "state": "present",
    }
    values.update(overrides)
    return values


def component_api(body=None, name="phase1/component"):
    return {
        "component_templates": [
            {
                "name": name,
                "component_template": body
                or {
                    "template": {
                        "settings": {"index": {"number_of_replicas": "0"}},
                        "mappings": {
                            "properties": {"event_id": {"type": "keyword"}}
                        },
                    },
                    "version": 1,
                    "_meta": {"owner": "platform"},
                    "created_date_millis": 100,
                    "modified_date_millis": 101,
                },
            }
        ]
    }


def index_api(body=None, name="phase1/index-template"):
    return {
        "index_templates": [
            {
                "name": name,
                "index_template": body
                or {
                    "index_patterns": ["phase1-events-*"],
                    "composed_of": ["phase1/component"],
                    "template": {
                        "settings": {"index": {"number_of_replicas": "0"}},
                        "mappings": {
                            "properties": {"direct": {"type": "keyword"}}
                        },
                    },
                    "priority": 100,
                    "version": 1,
                    "_meta": {"owner": "platform"},
                    "created_date_millis": 100,
                    "modified_date_millis": 101,
                },
            }
        ]
    }


def component_client(*responses):
    client = Mock()
    client.request.side_effect = responses
    client.component_template = ComponentTemplateService(client)
    return client


def index_client(*responses):
    client = Mock()
    client.request.side_effect = responses
    client.index_template = IndexTemplateService(client)
    return client


def test_argument_specs_expose_typed_options_and_secret_marking():
    component_spec = component_template.component_template_argument_spec()
    index_spec = index_template.index_template_argument_spec()

    assert component_spec["name"] == {"type": "str", "required": True}
    assert component_spec["settings"] == {"type": "dict"}
    assert component_spec["deprecated"] == {"type": "bool"}
    assert component_spec["replace"] == {"type": "bool", "default": False}
    assert index_spec["index_patterns"] == {"type": "list", "elements": "str"}
    assert index_spec["composed_of"] == {"type": "list", "elements": "str"}
    assert index_spec["data_stream"] == {"type": "dict"}
    assert index_spec["lifecycle"] == {
        "type": "dict",
        "options": {
            "name": {"type": "str"},
            "rollover_alias": {"type": "str"},
        },
    }
    assert index_spec["replace"] == {"type": "bool", "default": False}
    for spec in (component_spec, index_spec):
        assert spec["state"]["choices"] == ["present", "absent"]
        assert spec["password"]["no_log"] is True
        assert spec["api_key"]["no_log"] is True
        assert spec["bearer_token"]["no_log"] is True


def test_services_quote_names_and_unwrap_exact_template_envelopes():
    component_transport = Mock()
    component_transport.request.return_value = response(200, component_api())
    index_transport = Mock()
    index_transport.request.return_value = response(200, index_api())

    component_response, current_component = ComponentTemplateService(
        component_transport
    ).get("phase1/component")
    index_response, current_index = IndexTemplateService(index_transport).get(
        "phase1/index-template"
    )

    assert component_response.status == index_response.status == 200
    assert current_component["name"] == "phase1/component"
    assert current_index["name"] == "phase1/index-template"
    component_transport.request.assert_called_once_with(
        "_component_template/phase1%2Fcomponent"
    )
    index_transport.request.assert_called_once_with(
        "_index_template/phase1%2Findex-template"
    )


def test_service_comparison_normalizes_settings_and_ignores_unknown_server_fields():
    current = component_api()["component_templates"][0]["component_template"]
    current["name"] = "phase1/component"
    current["future_server_field"] = {"value": True}
    desired = {
        "name": "phase1/component",
        "template": {
            "settings": {"number_of_replicas": 0},
            "mappings": {"properties": {"event_id": {"type": "keyword"}}},
        },
        "version": 1,
    }

    changed, diff = ComponentTemplateService.compare(current, desired)

    assert changed is False
    assert diff["before"] == diff["after"]
    assert "future_server_field" not in diff["before"]


def test_service_update_payload_preserves_omitted_fields_and_strips_timestamps():
    current = index_api()["index_templates"][0]["index_template"]
    current["future_writable_field"] = {"enabled": True}
    desired = {
        "name": "phase1/index-template",
        "template": {
            "settings": {"refresh_interval": "5s"},
            "mappings": {
                "properties": {"description": {"type": "text"}}
            },
        },
        "_meta": {"purpose": "integration"},
    }

    payload = IndexTemplateService.payload(current, desired)

    assert payload["index_patterns"] == ["phase1-events-*"]
    assert payload["composed_of"] == ["phase1/component"]
    assert payload["template"]["settings"] == {
        "number_of_replicas": "0",
        "refresh_interval": "5s",
    }
    assert payload["template"]["mappings"]["properties"]["direct"]["type"] == "keyword"
    assert payload["template"]["mappings"]["properties"]["description"]["type"] == "text"
    assert payload["_meta"] == {"owner": "platform", "purpose": "integration"}
    assert payload["future_writable_field"] == {"enabled": True}
    assert "created_date_millis" not in payload
    assert "modified_date_millis" not in payload


def test_service_replace_payload_sends_only_explicit_writable_fields():
    current = index_api()["index_templates"][0]["index_template"]
    desired = {
        "name": "phase1/index-template",
        "index_patterns": ["phase1-replaced-*"],
        "template": {
            "settings": {},
            "mappings": {},
            "aliases": {},
        },
        "_meta": {},
    }

    payload = IndexTemplateService.payload(current, desired, replace=True)

    assert payload == {
        "index_patterns": ["phase1-replaced-*"],
        "template": {
            "settings": {},
            "mappings": {},
            "aliases": {},
        },
        "_meta": {},
    }
    assert "composed_of" not in payload
    assert "data_stream" not in payload
    assert "version" not in payload


def test_service_replace_comparison_handles_materialized_api_defaults():
    component_current = {
        "name": "phase1/component",
        "template": {},
        "created_date_millis": 100,
        "modified_date_millis": 101,
    }
    index_current = {
        "name": "phase1/index-template",
        "index_patterns": ["phase1-replaced-*"],
        "composed_of": [],
        "data_stream": {
            "hidden": False,
            "allow_custom_routing": False,
        },
        "created_date_millis": 100,
        "modified_date_millis": 101,
    }

    component_changed, component_diff = ComponentTemplateService.compare(
        component_current,
        {
            "name": "phase1/component",
            "template": {
                "settings": {},
                "mappings": {},
                "aliases": {},
            },
            "_meta": {},
        },
        replace=True,
    )
    index_changed, index_diff = IndexTemplateService.compare(
        index_current,
        {
            "name": "phase1/index-template",
            "index_patterns": ["phase1-replaced-*"],
            "data_stream": {},
            "_meta": {},
        },
        replace=True,
    )

    assert component_changed is False
    assert index_changed is False
    assert component_diff["before"] == component_diff["after"]
    assert index_diff["before"] == index_diff["after"]


def test_component_create_check_mode_is_non_mutating():
    module = FakeModule(
        component_params(
            settings={"number_of_replicas": 0},
            mappings={"properties": {"event_id": {"type": "keyword"}}},
            metadata={"owner": "platform"},
        ),
        check_mode=True,
    )
    client = component_client(response(404, {"error": "missing"}))

    with pytest.raises(ModuleExit) as exit_result:
        component_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["status"] == 404
    assert result["component_template"]["name"] == "phase1/component"
    assert result["diff"]["before"] == {}
    client.request.assert_called_once_with(
        "_component_template/phase1%2Fcomponent"
    )


def test_component_create_refreshes_current_state():
    module = FakeModule(
        component_params(
            settings={"number_of_replicas": 0},
            mappings={"properties": {"event_id": {"type": "keyword"}}},
            version=1,
        )
    )
    client = component_client(
        response(404, {"error": "missing"}),
        response(200, {"acknowledged": True}),
        response(200, component_api()),
    )

    with pytest.raises(ModuleExit) as exit_result:
        component_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["status"] == 200
    assert result["component_template"]["created_date_millis"] == 100
    assert client.request.call_args_list[1] == call(
        "_component_template/phase1%2Fcomponent",
        method="PUT",
        data={
            "template": {
                "settings": {"number_of_replicas": 0},
                "mappings": {
                    "properties": {"event_id": {"type": "keyword"}}
                },
            },
            "version": 1,
        },
    )


def test_component_existing_state_is_idempotent_and_readable():
    module = FakeModule(
        component_params(
            settings={"number_of_replicas": 0},
            mappings={"properties": {"event_id": {"type": "keyword"}}},
            version=1,
        )
    )
    client = component_client(response(200, component_api()))

    with pytest.raises(ModuleExit) as exit_result:
        component_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is False
    assert result["component_template"]["modified_date_millis"] == 101
    assert result["diff"]["before"] == result["diff"]["after"]
    client.request.assert_called_once()

    read_module = FakeModule(component_params())
    read_client = component_client(response(200, component_api()))
    with pytest.raises(ModuleExit) as read_exit:
        component_template.run_module(read_module, read_client)
    assert read_exit.value.result["changed"] is False
    assert read_exit.value.result["component_template"]["name"] == "phase1/component"


def test_component_update_check_mode_predicts_merge_without_mutation():
    module = FakeModule(
        component_params(
            settings={"refresh_interval": "5s"},
            mappings={"properties": {"description": {"type": "text"}}},
            metadata={"purpose": "integration"},
        ),
        check_mode=True,
    )
    client = component_client(response(200, component_api()))

    with pytest.raises(ModuleExit) as exit_result:
        component_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["component_template"]["template"]["settings"] == {
        "number_of_replicas": "0",
        "refresh_interval": "5s",
    }
    properties = result["component_template"]["template"]["mappings"]["properties"]
    assert properties["event_id"]["type"] == "keyword"
    assert properties["description"]["type"] == "text"
    assert result["component_template"]["_meta"] == {
        "owner": "platform",
        "purpose": "integration",
    }
    client.request.assert_called_once()


def test_component_update_sends_preserving_payload_and_refreshes():
    after = component_api()
    body = after["component_templates"][0]["component_template"]
    body["template"]["settings"]["index"]["refresh_interval"] = "5s"
    body["template"]["mappings"]["properties"]["description"] = {"type": "text"}
    module = FakeModule(
        component_params(
            settings={"refresh_interval": "5s"},
            mappings={"properties": {"description": {"type": "text"}}},
        )
    )
    client = component_client(
        response(200, component_api()),
        response(200, {"acknowledged": True}),
        response(200, after),
    )

    with pytest.raises(ModuleExit) as exit_result:
        component_template.run_module(module, client)

    assert exit_result.value.result["changed"] is True
    payload = client.request.call_args_list[1].kwargs["data"]
    assert payload["template"]["settings"] == {
        "number_of_replicas": "0",
        "refresh_interval": "5s",
    }
    assert payload["version"] == 1
    assert payload["_meta"] == {"owner": "platform"}
    assert "created_date_millis" not in payload


def test_component_replace_clears_dict_state_and_is_idempotent():
    replace_params = component_params(
        settings={},
        mappings={},
        aliases={},
        metadata={},
        replace=True,
    )
    after = component_api(body={"template": {}})
    module = FakeModule(replace_params)
    client = component_client(
        response(200, component_api()),
        response(200, {"acknowledged": True}),
        response(200, after),
    )

    with pytest.raises(ModuleExit) as exit_result:
        component_template.run_module(module, client)

    assert exit_result.value.result["changed"] is True
    assert exit_result.value.result["component_template"]["template"] == {}
    assert client.request.call_args_list[1] == call(
        "_component_template/phase1%2Fcomponent",
        method="PUT",
        data={
            "template": {
                "settings": {},
                "mappings": {},
                "aliases": {},
            },
            "_meta": {},
        },
    )

    idempotent_module = FakeModule(replace_params)
    idempotent_client = component_client(response(200, after))
    with pytest.raises(ModuleExit) as idempotent_exit:
        component_template.run_module(idempotent_module, idempotent_client)
    assert idempotent_exit.value.result["changed"] is False
    idempotent_client.request.assert_called_once()


def test_component_delete_check_delete_and_repeated_delete():
    check_module = FakeModule(component_params(state="absent"), check_mode=True)
    check_client = component_client(response(200, component_api()))
    with pytest.raises(ModuleExit) as check_exit:
        component_template.run_module(check_module, check_client)
    assert check_exit.value.result["changed"] is True
    check_client.request.assert_called_once()

    delete_module = FakeModule(component_params(state="absent"))
    delete_client = component_client(
        response(200, component_api()),
        response(200, {"acknowledged": True}),
    )
    with pytest.raises(ModuleExit) as delete_exit:
        component_template.run_module(delete_module, delete_client)
    assert delete_exit.value.result["changed"] is True
    assert delete_client.request.call_args_list[-1] == call(
        "_component_template/phase1%2Fcomponent",
        method="DELETE",
    )

    absent_module = FakeModule(component_params(state="absent"))
    absent_client = component_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleExit) as absent_exit:
        component_template.run_module(absent_module, absent_client)
    assert absent_exit.value.result["changed"] is False
    assert absent_exit.value.result["component_template"] is None


def test_component_api_error_and_malformed_response_are_actionable_and_sanitized():
    failure_module = FakeModule(component_params())
    failure_client = component_client(
        response(403, {"error": "forbidden", "api_key": "must-not-leak"})
    )
    with pytest.raises(ModuleFailure) as failure:
        component_template.run_module(failure_module, failure_client)
    assert "read component template" in failure.value.result["msg"]
    assert failure.value.result["status"] == 403
    assert failure.value.result["response"]["api_key"] == "<redacted>"

    malformed_module = FakeModule(component_params())
    malformed_client = component_client(
        response(200, {"component_templates": [{"name": "different"}]})
    )
    with pytest.raises(ModuleFailure) as malformed:
        component_template.run_module(malformed_module, malformed_client)
    assert "no matching template definition" in malformed.value.result["msg"]
    assert malformed.value.result["status"] == 200


def test_component_update_failure_preserves_sanitized_api_context():
    module = FakeModule(component_params(settings={"refresh_interval": "5s"}))
    client = component_client(
        response(200, component_api()),
        response(
            400,
            {
                "error": {
                    "type": "illegal_argument_exception",
                    "reason": "invalid template setting",
                },
                "token": "must-not-leak",
            },
        ),
    )

    with pytest.raises(ModuleFailure) as failure:
        component_template.run_module(module, client)

    assert "update component template" in failure.value.result["msg"]
    assert failure.value.result["status"] == 400
    assert failure.value.result["response"]["token"] == "<redacted>"
    assert (
        failure.value.result["response"]["error"]["type"]
        == "illegal_argument_exception"
    )


def test_index_create_requires_nonempty_patterns():
    module = FakeModule(index_params())
    client = index_client(response(404, {"error": "missing"}))

    with pytest.raises(ModuleFailure) as failure:
        index_template.run_module(module, client)

    assert "index_patterns must contain at least one pattern" in str(failure.value)
    client.request.assert_called_once()


def test_index_replace_requires_nonempty_patterns_for_existing_template():
    module = FakeModule(index_params(replace=True))
    client = index_client(response(200, index_api()))

    with pytest.raises(ModuleFailure) as failure:
        index_template.run_module(module, client)

    assert "creating or replacing" in str(failure.value)
    client.request.assert_called_once()


def test_index_create_check_mode_is_non_mutating():
    module = FakeModule(
        index_params(
            index_patterns=["phase1-events-*"],
            composed_of=["phase1/component"],
            priority=100,
        ),
        check_mode=True,
    )
    client = index_client(response(404, {"error": "missing"}))

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["status"] == 404
    assert result["index_template"]["index_patterns"] == ["phase1-events-*"]
    assert result["diff"]["before"] == {}
    client.request.assert_called_once()


def test_index_create_refreshes_current_state():
    module = FakeModule(
        index_params(
            index_patterns=["phase1-events-*"],
            composed_of=["phase1/component"],
            settings={"number_of_replicas": 0},
            priority=100,
            version=1,
        )
    )
    client = index_client(
        response(404, {"error": "missing"}),
        response(200, {"acknowledged": True}),
        response(200, index_api()),
    )

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["index_template"]["created_date_millis"] == 100
    assert client.request.call_args_list[1] == call(
        "_index_template/phase1%2Findex-template",
        method="PUT",
        data={
            "index_patterns": ["phase1-events-*"],
            "composed_of": ["phase1/component"],
            "priority": 100,
            "version": 1,
            "template": {"settings": {"number_of_replicas": 0}},
        },
    )


def test_index_existing_state_is_idempotent_and_readable():
    module = FakeModule(
        index_params(
            index_patterns=["phase1-events-*"],
            composed_of=["phase1/component"],
            settings={"number_of_replicas": 0},
            mappings={"properties": {"direct": {"type": "keyword"}}},
            priority=100,
            version=1,
        )
    )
    client = index_client(response(200, index_api()))

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is False
    assert result["diff"]["before"] == result["diff"]["after"]
    assert result["index_template"]["modified_date_millis"] == 101
    client.request.assert_called_once()

    read_module = FakeModule(index_params())
    read_client = index_client(response(200, index_api()))
    with pytest.raises(ModuleExit) as read_exit:
        index_template.run_module(read_module, read_client)
    assert read_exit.value.result["changed"] is False
    assert read_exit.value.result["index_template"]["name"] == "phase1/index-template"


def test_index_update_check_mode_predicts_merge_without_mutation():
    module = FakeModule(
        index_params(
            index_patterns=["phase1-updated-*"],
            settings={"refresh_interval": "5s"},
            mappings={"properties": {"description": {"type": "text"}}},
            metadata={"purpose": "integration"},
        ),
        check_mode=True,
    )
    client = index_client(response(200, index_api()))

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["index_template"]["index_patterns"] == ["phase1-updated-*"]
    assert result["index_template"]["composed_of"] == ["phase1/component"]
    settings = result["index_template"]["template"]["settings"]
    assert settings == {
        "number_of_replicas": "0",
        "refresh_interval": "5s",
    }
    properties = result["index_template"]["template"]["mappings"]["properties"]
    assert properties["direct"]["type"] == "keyword"
    assert properties["description"]["type"] == "text"
    client.request.assert_called_once()


def test_index_update_sends_preserving_payload_and_refreshes():
    after = index_api()
    body = after["index_templates"][0]["index_template"]
    body["index_patterns"] = ["phase1-updated-*"]
    body["template"]["settings"]["index"]["refresh_interval"] = "5s"
    module = FakeModule(
        index_params(
            index_patterns=["phase1-updated-*"],
            settings={"refresh_interval": "5s"},
        )
    )
    client = index_client(
        response(200, index_api()),
        response(200, {"acknowledged": True}),
        response(200, after),
    )

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    assert exit_result.value.result["changed"] is True
    payload = client.request.call_args_list[1].kwargs["data"]
    assert payload["index_patterns"] == ["phase1-updated-*"]
    assert payload["composed_of"] == ["phase1/component"]
    assert payload["template"]["settings"] == {
        "number_of_replicas": "0",
        "refresh_interval": "5s",
    }
    assert payload["template"]["mappings"]["properties"]["direct"]["type"] == "keyword"
    assert payload["version"] == 1
    assert "modified_date_millis" not in payload


def test_index_replace_clears_dict_state_and_removes_data_stream():
    module = FakeModule(
        index_params(
            index_patterns=["phase1-replaced-*"],
            settings={},
            mappings={},
            aliases={},
            metadata={},
            replace=True,
        ),
        check_mode=True,
    )
    current_body = index_api()["index_templates"][0]["index_template"]
    current_body["data_stream"] = {
        "hidden": False,
        "allow_custom_routing": False,
    }
    current_body["allow_auto_create"] = True
    client = index_client(response(200, index_api(body=current_body)))

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    result = exit_result.value.result
    assert result["changed"] is True
    assert result["index_template"] == {
        "name": "phase1/index-template",
        "index_patterns": ["phase1-replaced-*"],
        "template": {
            "settings": {},
            "mappings": {},
            "aliases": {},
        },
        "_meta": {},
    }
    assert "data_stream" not in result["index_template"]
    assert "composed_of" not in result["index_template"]
    assert "version" not in result["index_template"]
    client.request.assert_called_once()


def test_index_replace_is_idempotent_with_empty_composed_of_default():
    module = FakeModule(
        index_params(
            index_patterns=["phase1-replaced-*"],
            settings={},
            mappings={},
            aliases={},
            metadata={},
            replace=True,
        )
    )
    current = index_api(
        body={
            "index_patterns": ["phase1-replaced-*"],
            "composed_of": [],
            "created_date_millis": 100,
            "modified_date_millis": 101,
        }
    )
    client = index_client(response(200, current))

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    assert exit_result.value.result["changed"] is False
    client.request.assert_called_once()


def test_index_delete_check_delete_and_repeated_delete():
    check_module = FakeModule(index_params(state="absent"), check_mode=True)
    check_client = index_client(response(200, index_api()))
    with pytest.raises(ModuleExit) as check_exit:
        index_template.run_module(check_module, check_client)
    assert check_exit.value.result["changed"] is True
    check_client.request.assert_called_once()

    delete_module = FakeModule(index_params(state="absent"))
    delete_client = index_client(
        response(200, index_api()),
        response(200, {"acknowledged": True}),
    )
    with pytest.raises(ModuleExit) as delete_exit:
        index_template.run_module(delete_module, delete_client)
    assert delete_exit.value.result["changed"] is True
    assert delete_client.request.call_args_list[-1] == call(
        "_index_template/phase1%2Findex-template",
        method="DELETE",
    )

    absent_module = FakeModule(index_params(state="absent"))
    absent_client = index_client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleExit) as absent_exit:
        index_template.run_module(absent_module, absent_client)
    assert absent_exit.value.result["changed"] is False
    assert absent_exit.value.result["index_template"] is None


def test_index_api_error_and_malformed_response_are_actionable_and_sanitized():
    failure_module = FakeModule(index_params())
    failure_client = index_client(
        response(403, {"error": "forbidden", "password": "must-not-leak"})
    )
    with pytest.raises(ModuleFailure) as failure:
        index_template.run_module(failure_module, failure_client)
    assert "read index template" in failure.value.result["msg"]
    assert failure.value.result["status"] == 403
    assert failure.value.result["response"]["password"] == "<redacted>"

    malformed_module = FakeModule(index_params())
    malformed_client = index_client(
        response(200, {"index_templates": [{"name": "different"}]})
    )
    with pytest.raises(ModuleFailure) as malformed:
        index_template.run_module(malformed_module, malformed_client)
    assert "no matching template definition" in malformed.value.result["msg"]
    assert malformed.value.result["status"] == 200


def test_index_update_failure_preserves_sanitized_api_context():
    module = FakeModule(index_params(priority=200))
    client = index_client(
        response(200, index_api()),
        response(
            400,
            {
                "error": {
                    "type": "invalid_index_template_exception",
                    "reason": "invalid index template",
                },
                "password": "must-not-leak",
            },
        ),
    )

    with pytest.raises(ModuleFailure) as failure:
        index_template.run_module(module, client)

    assert "update index template" in failure.value.result["msg"]
    assert failure.value.result["status"] == 400
    assert failure.value.result["response"]["password"] == "<redacted>"
    assert (
        failure.value.result["response"]["error"]["type"]
        == "invalid_index_template_exception"
    )


def test_index_typed_lifecycle_attachment_projects_into_settings():
    module = FakeModule(
        index_params(
            index_patterns=["phase1-events-*"],
            lifecycle={
                "name": "phase1-policy",
                "rollover_alias": "phase1-events",
            },
        ),
        check_mode=True,
    )
    client = index_client(response(404, {"error": "missing"}))

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    settings = exit_result.value.result["index_template"]["template"]["settings"]
    assert settings == {
        "index.lifecycle.name": "phase1-policy",
        "index.lifecycle.rollover_alias": "phase1-events",
    }
    assert exit_result.value.result["changed"] is True


def test_index_typed_lifecycle_detachment_is_explicit_and_idempotent():
    before = index_api()
    before_settings = before["index_templates"][0]["index_template"]["template"][
        "settings"
    ]
    before_settings["index.lifecycle.name"] = "phase1-policy"
    before_settings["index.lifecycle.rollover_alias"] = "phase1-events"
    after = index_api()
    after_settings = after["index_templates"][0]["index_template"]["template"][
        "settings"
    ]
    after_settings["index.lifecycle.name"] = None
    after_settings["index.lifecycle.rollover_alias"] = None
    module = FakeModule(index_params(lifecycle={}))
    client = index_client(
        response(200, before),
        response(200, {"acknowledged": True}),
        response(200, after),
    )

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    assert exit_result.value.result["changed"] is True
    payload_settings = client.request.call_args_list[1].kwargs["data"]["template"][
        "settings"
    ]
    assert payload_settings["lifecycle.name"] is None
    assert payload_settings["lifecycle.rollover_alias"] is None
    assert payload_settings["number_of_replicas"] == "0"

    idempotent_client = index_client(response(200, after))
    with pytest.raises(ModuleExit) as idempotent_exit:
        index_template.run_module(
            FakeModule(index_params(lifecycle={})),
            idempotent_client,
        )
    assert idempotent_exit.value.result["changed"] is False


def test_index_typed_lifecycle_rejects_raw_setting_conflicts():
    module = FakeModule(
        index_params(
            lifecycle={"name": "phase1-policy"},
            settings={"index": {"lifecycle": {"name": "raw-policy"}}},
        )
    )
    client = index_client(response(200, index_api()))

    with pytest.raises(ModuleFailure) as failure:
        index_template.run_module(module, client)

    assert "duplicate raw settings" in failure.value.result["msg"]
    client.request.assert_called_once()


def test_index_typed_lifecycle_rejects_rollover_alias_for_data_stream():
    existing = index_api()
    existing["index_templates"][0]["index_template"]["data_stream"] = {
        "hidden": False
    }
    module = FakeModule(
        index_params(
            lifecycle={
                "name": "phase1-policy",
                "rollover_alias": "phase1-events",
            }
        )
    )
    client = index_client(response(200, existing))

    with pytest.raises(ModuleFailure) as failure:
        index_template.run_module(module, client)

    assert "not valid for a data-stream template" in failure.value.result["msg"]


def test_index_typed_lifecycle_rejects_duplicate_template_alias():
    existing = index_api()
    existing["index_templates"][0]["index_template"]["template"]["aliases"] = {
        "phase1-events": {}
    }
    module = FakeModule(
        index_params(
            lifecycle={
                "name": "phase1-policy",
                "rollover_alias": "phase1-events",
            }
        )
    )
    client = index_client(response(200, existing))

    with pytest.raises(ModuleFailure) as failure:
        index_template.run_module(module, client)

    assert "must not also be defined in template aliases" in failure.value.result["msg"]


def test_index_lifecycle_replace_ignores_omitted_current_aliases():
    existing = index_api()
    existing["index_templates"][0]["index_template"]["template"]["aliases"] = {
        "phase1-events": {}
    }
    module = FakeModule(
        index_params(
            replace=True,
            index_patterns=["phase1-replaced-*"],
            lifecycle={
                "name": "phase1-policy",
                "rollover_alias": "phase1-events",
            },
        ),
        check_mode=True,
    )
    client = index_client(response(200, existing))

    with pytest.raises(ModuleExit) as exit_result:
        index_template.run_module(module, client)

    predicted = exit_result.value.result["index_template"]
    assert exit_result.value.result["changed"] is True
    assert predicted["index_patterns"] == ["phase1-replaced-*"]
    assert "aliases" not in predicted["template"]
    assert predicted["template"]["settings"] == {
        "index.lifecycle.name": "phase1-policy",
        "index.lifecycle.rollover_alias": "phase1-events",
    }


def test_index_lifecycle_replace_rejects_explicit_duplicate_alias():
    module = FakeModule(
        index_params(
            replace=True,
            index_patterns=["phase1-replaced-*"],
            aliases={"phase1-events": {}},
            lifecycle={
                "name": "phase1-policy",
                "rollover_alias": "phase1-events",
            },
        )
    )
    client = index_client(response(200, index_api()))

    with pytest.raises(ModuleFailure) as failure:
        index_template.run_module(module, client)

    assert "must not also be defined in template aliases" in failure.value.result["msg"]
