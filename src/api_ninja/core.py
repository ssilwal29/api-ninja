import json
import logging
from urllib.parse import urljoin

import requests
from openai import OpenAI

from api_ninja.agents.planner import PlannerAgent
from api_ninja.agents.request_generator import RequestGeneratorAgent
from api_ninja.agents.result_evaluation import ResultEvaluationAgent
from api_ninja.color import Colors
from api_ninja.memory_store import MemoryStore

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def format_context(flow: dict) -> str:
    text = f"""
        Flow ID: {flow.get("flow_id")}
        Collection: {flow.get("collection")}
        Collection Description: {flow.get("collection_description")}

        Description:
        {flow.get("description", "")}

        Notes:
        {flow.get("notes", "")}

        Expectations:
        {flow.get("expectations", "")}

        Defaults:
        {json.dumps(flow.get("defaults", []), indent=2)}
    """
    return text.strip()


def format_plans(plans):
    lines = []
    for i, plan in enumerate(plans, 1):
        lines.append(f"    {Colors.CYAN}{i}. {plan.method.upper():<6} {plan.path}{Colors.RESET}")
        lines.append(f"       • Payload     : {plan.payload_description}")
        lines.append(f"       • Headers     : {plan.headers_description}")
        lines.append(f"       • Expectation : {plan.response_check}")
    return "\n".join(lines)


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
        for i, call in enumerate(planned_calls):
            step_name = f"{call.method.upper()} {call.path}"
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
                if check_result.status != "PASS":
                    raise AssertionError(
                        f"  {Colors.YELLOW}Reason     :{Colors.RESET} {check_result.reason.strip()}\n\n"
                        f" {Colors.YELLOW}Suggestion :{Colors.RESET} {check_result.suggestion.strip()}\n\n"
                        f" {Colors.YELLOW}Test Plan  :{Colors.RESET}\n{format_plans(planned_calls)}\n"
                    )
                memory.store(result["response_body"], label=step_name)
            except Exception as e:
                raise AssertionError(
                    f"\n{Colors.RED}Step {i + 1} failed during {step_name}\n"
                    f"{Colors.RESET} {str(e).strip()}"
                )
