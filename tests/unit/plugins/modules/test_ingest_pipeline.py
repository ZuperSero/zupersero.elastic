# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock, call

import pytest

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchResponse,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.pipeline import (
    PipelineService,
)
from ansible_collections.zupersero.elastic.plugins.modules import ingest_pipeline


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


def params(**overrides):
    values = {
        "name": "phase1/pipeline",
        "description": None,
        "processors": None,
        "on_failure": None,
        "version": None,
        "metadata": None,
        "replace": False,
        "state": "present",
    }
    values.update(overrides)
    return values


def pipeline_api(body=None, name="phase1/pipeline"):
    return {
        name: body
        or {
            "description": "Normalize events",
            "processors": [{"set": {"field": "event.kind", "value": "event"}}],
            "on_failure": [{"set": {"field": "error.pipeline", "value": name}}],
            "version": 1,
            "_meta": {"owner": "platform"},
            "future_server_field": {"enabled": True},
        }
    }


def client(*responses):
    transport = Mock()
    transport.request.side_effect = responses
    transport.pipeline = PipelineService(transport)
    return transport


def test_argument_spec_and_service_quote():
    spec = ingest_pipeline.ingest_pipeline_argument_spec()
    assert spec["name"] == {"type": "str", "required": True}
    assert spec["processors"] == {"type": "list", "elements": "dict"}
    assert spec["on_failure"] == {"type": "list", "elements": "dict"}
    assert spec["replace"] == {"type": "bool", "default": False}
    assert spec["password"]["no_log"] is True
    assert PipelineService.path("phase1/pipeline") == "_ingest/pipeline/phase1%2Fpipeline"


def test_service_get_payload_and_delete_preserve_unknown_fields():
    transport = Mock()
    transport.request.side_effect = [
        response(200, pipeline_api()),
        response(200, {"acknowledged": True}),
        response(200, {"acknowledged": True}),
    ]
    service = PipelineService(transport)
    read_response, current = service.get("phase1/pipeline")
    service.create_or_update(
        "phase1/pipeline",
        current=current,
        desired={
            "name": "phase1/pipeline",
            "description": "Updated",
            "processors": [{"set": {"field": "event.kind", "value": "event"}}],
        },
    )
    service.delete("phase1/pipeline")
    assert read_response.status == 200
    assert current["name"] == "phase1/pipeline"
    assert transport.request.call_args_list == [
        call("_ingest/pipeline/phase1%2Fpipeline"),
        call(
            "_ingest/pipeline/phase1%2Fpipeline",
            method="PUT",
            data={
                "description": "Updated",
                "processors": [{"set": {"field": "event.kind", "value": "event"}}],
                "on_failure": [
                    {"set": {"field": "error.pipeline", "value": "phase1/pipeline"}}
                ],
                "version": 1,
                "_meta": {"owner": "platform"},
                "future_server_field": {"enabled": True},
            },
        ),
        call("_ingest/pipeline/phase1%2Fpipeline", method="DELETE"),
    ]


def test_service_replace_removes_omitted_state_and_compare_ignores_unknown():
    current = pipeline_api()["phase1/pipeline"] | {"name": "phase1/pipeline"}
    desired = {
        "name": "phase1/pipeline",
        "processors": [{"drop": {}}],
        "_meta": {},
    }
    changed, diff = PipelineService.compare(current, desired, replace=False)
    assert changed is True
    assert "future_server_field" not in diff["before"]
    assert PipelineService.payload(current, desired, replace=True) == {
        "processors": [{"drop": {}}],
        "_meta": {},
    }


def test_create_requires_processors_and_check_mode_is_non_mutating():
    with pytest.raises(ModuleFailure, match="processors is required"):
        ingest_pipeline.run_module(FakeModule(params()), client(response(404, {})))
    module = FakeModule(
        params(
            processors=[{"set": {"field": "event.kind", "value": "event"}}],
            metadata={"owner": "platform"},
        ),
        check_mode=True,
    )
    transport = client(response(404, {"error": "missing"}))
    with pytest.raises(ModuleExit) as result:
        ingest_pipeline.run_module(module, transport)
    assert result.value.result["changed"] is True
    assert result.value.result["status"] == 404
    assert result.value.result["ingest_pipeline"]["name"] == "phase1/pipeline"
    transport.request.assert_called_once_with("_ingest/pipeline/phase1%2Fpipeline")


def test_create_refreshes_and_existing_pipeline_is_idempotent():
    desired = params(
        description="Normalize events",
        processors=[{"set": {"field": "event.kind", "value": "event"}}],
        on_failure=[{"set": {"field": "error.pipeline", "value": "phase1/pipeline"}}],
        version=1,
        metadata={"owner": "platform"},
    )
    create_client = client(
        response(404, {}),
        response(200, {"acknowledged": True}),
        response(200, pipeline_api()),
    )
    with pytest.raises(ModuleExit) as create_result:
        ingest_pipeline.run_module(FakeModule(desired), create_client)
    assert create_result.value.result["changed"] is True
    assert create_client.request.call_args_list[1].kwargs["data"]["_meta"] == {
        "owner": "platform"
    }
    idempotent_client = client(response(200, pipeline_api()))
    with pytest.raises(ModuleExit) as unchanged:
        ingest_pipeline.run_module(FakeModule(desired), idempotent_client)
    assert unchanged.value.result["changed"] is False


def test_partial_update_check_predicts_preserved_fields_without_mutation():
    module = FakeModule(
        params(description="Updated", metadata={"purpose": "integration"}),
        check_mode=True,
    )
    transport = client(response(200, pipeline_api()))
    with pytest.raises(ModuleExit) as result:
        ingest_pipeline.run_module(module, transport)
    predicted = result.value.result["ingest_pipeline"]
    assert predicted["description"] == "Updated"
    assert predicted["processors"] == pipeline_api()["phase1/pipeline"]["processors"]
    assert predicted["_meta"] == {"owner": "platform", "purpose": "integration"}
    transport.request.assert_called_once()


def test_update_and_replace_and_delete_lifecycle():
    desired = params(description="Updated", processors=[{"drop": {}}])
    after = pipeline_api()
    after["phase1/pipeline"]["description"] = "Updated"
    after["phase1/pipeline"]["processors"] = [{"drop": {}}]
    update_client = client(
        response(200, pipeline_api()),
        response(200, {"acknowledged": True}),
        response(200, after),
    )
    with pytest.raises(ModuleExit) as updated:
        ingest_pipeline.run_module(FakeModule(desired), update_client)
    assert updated.value.result["changed"] is True
    replace_client = client(
        response(200, pipeline_api()),
        response(200, {"acknowledged": True}),
        response(200, pipeline_api({"processors": [{"drop": {}}], "_meta": {}})),
    )
    with pytest.raises(ModuleExit) as replaced:
        ingest_pipeline.run_module(
            FakeModule(params(replace=True, processors=[{"drop": {}}], metadata={})),
            replace_client,
        )
    assert replaced.value.result["changed"] is True
    delete_client = client(response(200, pipeline_api()), response(200, {}))
    with pytest.raises(ModuleExit) as deleted:
        ingest_pipeline.run_module(FakeModule(params(state="absent")), delete_client)
    assert deleted.value.result["changed"] is True
    absent_client = client(response(404, {}))
    with pytest.raises(ModuleExit) as absent:
        ingest_pipeline.run_module(FakeModule(params(state="absent")), absent_client)
    assert absent.value.result["changed"] is False


def test_api_errors_and_malformed_responses_are_sanitized():
    with pytest.raises(ModuleFailure) as failure:
        ingest_pipeline.run_module(
            FakeModule(params()),
            client(response(403, {"error": "forbidden", "token": "secret"})),
        )
    assert "read ingest pipeline" in failure.value.result["msg"]
    assert failure.value.result["response"]["token"] == "<redacted>"
    with pytest.raises(ModuleFailure, match="no matching pipeline definition"):
        ingest_pipeline.run_module(
            FakeModule(params()),
            client(response(200, {"other": {"processors": []}})),
        )
