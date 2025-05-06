import os
import asyncio
import json
from typing import List
from agents import Agent, Runner
from api_ninja.models import FlowModel

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1")


class FlowGeneratorAgent:
    def prompt(self, method: str, path: str, openapi_spec: dict) -> str:
        return f"""
You are a senior API test designer. You have OpenAPI specification and you are asked to generate test flows describing how to run sequence of API calls to test the endpoint.
considering various scenarios. Your task is to generate at most 5 high-quality test flows 1 each for the following scnearios. But using the same OpenAPI spec to decide if you need to
test the scenario or not. Like if there is no authentication in the OpenAPI spec, you should not generate a test flow for authentication.

- Happy Path
- Error Handling
- Authentication
- Boundary Value
- Schema Validation

---

Endpoint:
- Method: {method}
- Path: {path}

OpenAPI Specification:
{json.dumps(openapi_spec)}

---
Return a JSON array of 5 test flows. Each flow must follow this structure:
- You can generate less than 5 flows if you think it is not needed.
- Think like if this flow will be useful to test if the API is working correctly or not.
- The goal is to test the accuracy and correctness of the API not the system.
- Dont suggest to do something tedius like creating 1000 users but something small and realistic.
- Use the OpenAPI spec to determine what payload to send, what headers to use, and what parameters to include.
- You need to describe the exact flow rather than what is the goal of the flow.
- Suggest realistic flows to be able to execute as a test.
- Use your common sense to determine the test flow. For example: to delete a user, you need to create a user first
- Describe the test flow in plain English, including any setup steps and which path to call and what headers to use or payload to send.
- Anything that could be useful for LLM to generate the flow correctly using the output of this agent.
- For error handling, only consider client-side error scenarios (e.g., missing required fields, invalid types, unauthorized access). Do not include server-side errors like 500 Internal Server Error unless such errors are explicitly defined in the OpenAPI spec's responses section for the endpoint.
- Avoid synthetic or unrealistic tests that require simulating internal server failures. Focus on realistic, reproducible conditions a tester could intentionally trigger.

{{
  "id": "Unique identifier for the test flow using method and path and scenario name all lower case and joined by underscore",
  "description": "Full, plain-English explanation of the test flow. Include any setup (e.g. create user before deleting).",
  "expectations": "What the API should return (e.g., 200 OK, 422 Validation Error)",
  "notes": "Any auth requirements, edge cases, or schema expectations. Something that could be useful for LLM to generate the flow correctly.",
}}

Constraints:
- Only use fields defined in the provided request schema.
- Use realistic field values or intentionally invalid values depending on the test category.
- Ensure the example_request is a valid JSON object, not a string.
- Only return a valid JSON array — no text, markdown, or YAML.
""".strip()

    def generate_flows_for_endpoint(
        self,
        method: str,
        path: str,
        openapi_spec: dict,
    ) -> List[FlowModel]:
        instructions = self.prompt(method, path, openapi_spec)
        agent = Agent(
            model=LLM_MODEL,
            name=f"Flow Generator for {method} {path}",
            instructions=instructions,
            output_type=List[FlowModel],
        )
        result = asyncio.run(
            Runner.run(agent, input="Generate 5 test flows for this endpoint.")
        )
        return result.final_output

    def generate_flows_for_spec(self, openapi_spec: dict) -> dict:
        paths = openapi_spec.get("paths", {})
        print(f"Found {len(paths)} paths in the OpenAPI spec.")
        collections = {}
        flow_restructured = {}
        for path, methods in paths.items():
            for method, entry in methods.items():
                collection_name = method.lower() + path.replace("/", "_").replace(
                    "{", ""
                ).replace("}", "")
                if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                    continue
                print(f"Generating flows for {method.upper()} {path}...")
                try:
                    flows = self.generate_flows_for_endpoint(method, path, openapi_spec)
                    flows = [flow.model_dump() for flow in flows]
                    flow_ids = [flow["id"] for flow in flows]
                    collections[collection_name] = {
                        "flows": flow_ids,
                        "description": f"Flows for {method.upper()} {path}",
                    }
                    for flow in flows:
                        flow_restructured[flow["id"]] = {
                            "description": flow["description"],
                            "expectations": flow["expectations"],
                            "notes": flow["notes"],
                        }
                    print(f"Generated {len(flows)} flows for {method.upper()} {path}.")
                except Exception as e:
                    print(f"Error generating flows for {method} {path}: {e}")
        return {"flows": flow_restructured, "collections": collections}
