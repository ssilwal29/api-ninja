import logging
import json
import requests
from api_ninja.memory_store import MemoryStore
from openai import OpenAI
from api_ninja.agents.request_generator import RequestGeneratorAgent
from api_ninja.agents.planner import PlannerAgent
from api_ninja.agents.result_evaluation import ResultEvaluationAgent
import allure
from urllib.parse import urljoin


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_context(flow: dict) -> str:
    return f"""Flow ID: {flow.get('flow_id')}

Collection: {flow.get('collection')}
Collection Description: {flow.get('collection_description')}

Description:
{flow.get('description', '')}

Notes:
{flow.get('notes', '')}

Expectations:
{flow.get('expectations', '')}

Defaults:
{json.dumps(flow.get('defaults', []), indent=2)}
"""


class APINinja:
    def __init__(self, openapi_spec, api_base_url):
        self.openapi_spec = openapi_spec
        self.api_base_url = api_base_url.rstrip("/")
        self.client = OpenAI()
        self.planner_agent = PlannerAgent()
        self.request_generator_agent = RequestGeneratorAgent()
        self.evaluation_agent = ResultEvaluationAgent()

    def request_api(self, request_details: dict) -> dict:
        url = urljoin(self.api_base_url, request_details["path"].lstrip("/"))
        func = getattr(requests, request_details["method"].lower())
        # Prepare data
        headers = request_details.get("headers", {})
        body = request_details.get("payload", {})
        params = request_details.get("parameters", {})
        resp = func(url, headers=headers, json=body, params=params)
        response_body = ""
        try:
            response_body = resp.json()
        except json.JSONDecodeError:
            if getattr(resp, "text", None) is not None:
                response_body = resp.text
        print(
            f"Requested {request_details['method']} request to {url} with status {resp.status_code}"
        )
        return {
            "response_status": resp.status_code,
            "response_body": response_body,
            "method": request_details["method"],
            "path": request_details["path"],
            "headers": headers,
            "payload": body,
            "parameters": params,
        }

    def plan_and_run(self, flow: dict):
        initial_context = format_context(flow)
        memory = MemoryStore()
        memory.store(initial_context, label="")
        planned_calls = self.planner_agent.run(memory.get_context(), self.openapi_spec)
        print(f"Total Steps: {len(planned_calls)}")
        for i, call in enumerate(planned_calls):
            step_title = f"{call.method} {call.path}"
            with allure.step(f"Step {i+1}: {step_title}"):
                try:
                    request_details = self.request_generator_agent.run(
                        step=call,
                        context=memory.get_context(),
                        openapi_spec=self.openapi_spec,
                    )
                    result = self.request_api(request_details)
                    result["expected_status"] = call.expected_status
                    result["response_check"] = call.response_check
                    check_result = self.evaluation_agent.run(
                        context=memory.get_context(), result=result
                    )
                    assert (
                        check_result.status == "PASS"
                    ), f"\nReason: {check_result.reason}\nSuggestion: {check_result.suggestion}"
                    step_name = f"{call.method}_{call.path}".replace("/", "_").lower()
                    memory.store(result["response_body"], label=step_name)
                except AssertionError as e:
                    assert (
                        False
                    ), f"Exception {e} while requesting {call.method} to {call.path}."
