import asyncio
import json
import os
from typing import List

from agents import Agent, Runner
from langchain_openai import ChatOpenAI
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerAccuracy

from api_ninja.models import FlowModel

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1")


def evaluate_flow(flow: FlowModel, method: str, path: str, openapi_spec: dict, scorer) -> tuple:
    sample = SingleTurnSample(
        user_input=f"Generate test flow for {method} {path}",
        response=f"{flow.description}\n{flow.expectations}\n{flow.notes}",
        reference=f"This is a reference flow for {method} {path}.\nOpenAPI Spec:\n{json.dumps(openapi_spec)}",
    )
    score = asyncio.run(scorer.single_turn_ascore(sample))
    return score, sample


def regenerate_failed_flow(
    method: str,
    path: str,
    scenario: str,
    openapi_spec: dict,
    failed_flow: dict,
) -> FlowModel:
    improvement_prompt = f"""
        You are an expert API test flow designer. A test flow was generated for the scenario: \"{scenario}\" for the endpoint `{method.upper()} {path}`,
        but it was rated poorly (score: {failed_flow['score']:.2f}).

        ## Reason for failure:
        {failed_flow.get('feedback', 'No feedback provided.')}

        ## Your task:
        Regenerate a **single improved test flow** for the scenario: \"{scenario}\". You MUST address the feedback above and ensure the flow is:
        - Accurate
        - Clear in setup steps
        - Has realistic payloads and headers
        - Includes proper expectations and validations
        - Aligns strictly with the OpenAPI spec


        ## OpenAPI Spec:
        {json.dumps(openapi_spec)}

        ## Previous (failed) flow:
        - Description: {failed_flow['description']}
        - Expectations: {failed_flow['expectations']}
        - Notes: {failed_flow['notes']}

        - Instead of vague goals, describe each test as a series of concrete steps and LLM should be able to generate the flow from the output. For example:

        1. Make a POST request to `/users` with a valid JSON body to create a user.
        2. Capture the returned `id` from the response.
        3. Make a GET request to `/users/{id}` using the captured ID.
        4. Assert that the response matches the schema and includes the expected values.

        - Be step-oriented. Each test flow should describe what exact sequence of API calls are made, with sample data, and how the tester knows the API is working as expected.

        Return a valid JSON object like:
        {{
        "id": "{failed_flow['id']}",
        "description": "...",
        "expectations": "...",
        "notes": "..."
        }}
    """

    agent = Agent(
        model=LLM_MODEL,
        name=f"Regenerator for {failed_flow['id']}",
        instructions=improvement_prompt,
        output_type=FlowModel,
    )

    result = asyncio.run(Runner.run(agent, input="Regenerate the improved flow."))
    return result.final_output


def self_correct_flows(
    method: str,
    path: str,
    openapi_spec: dict,
    flows: List[FlowModel],
    threshold: float = 0.9,
    max_retries: int = 3,
) -> List[FlowModel]:
    evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model=LLM_MODEL))
    scorer = AnswerAccuracy(llm=evaluator_llm)
    evaluated_flows = []
    failed_flows = []

    for flow in flows:
        score, _ = evaluate_flow(flow, method, path, openapi_spec, scorer)
        print(f"Flow ID: {flow.id}, Score: {score:.2f}")
        if score >= threshold:
            evaluated_flows.append(flow)
        else:
            scenario_name = " ".join(flow.id.split("_")[-2:])
            failed_flows.append(
                {
                    "id": flow.id,
                    "scenario": scenario_name,
                    "description": flow.description,
                    "expectations": flow.expectations,
                    "notes": flow.notes,
                    "score": score,
                    "feedback": "Expectation unclear. Please make expected result more specific.",
                }
            )

    for failed in failed_flows:
        retries = 0
        while retries < max_retries:
            improved_flow = regenerate_failed_flow(
                method=method,
                path=path,
                scenario=failed["scenario"],
                openapi_spec=openapi_spec,
                failed_flow=failed,
            )
            score, _ = evaluate_flow(improved_flow, method, path, openapi_spec, scorer)
            print(f"Improved Flow ID: {improved_flow.id}, Score: {score:.2f}")
            if score >= threshold:
                evaluated_flows.append(improved_flow)
                break
            else:
                failed["score"] = score
                failed["feedback"] = (
                    "Still vague expectations or missing schema reference. Improve clarity."
                )
                retries += 1

    return evaluated_flows


class FlowGeneratorAgent:
    def prompt(
        self,
        method: str,
        path: str,
        openapi_spec: dict,
        scenarios: str,
    ) -> str:
        text = f"""
            You are a senior API test designer. You have OpenAPI specification and you are asked to generate test flows describing how to run sequence of API calls to test the endpoint.
            considering various scenarios. Your task is to generate at most 5 high-quality test flows 1 each for the following scnearios. But using the same OpenAPI spec to decide if you need to
            test the scenario or not. Like if there is no authentication in the OpenAPI spec, you should not generate a test flow for authentication.

            {scenarios}:

            ---

            Endpoint:
            - Method: {method}
            - Path: {path}

            OpenAPI Specification:
            {json.dumps(openapi_spec)}

            ---
            Return a JSON array of test flows. Each flow must follow this structure:
            - Decide which scenarios are relevant to test based on the available fields like:
            - `security` → if present, include an "authentication" test
            - `requestBody` schema with required/optional fields → include "schema validation", "boundary value" tests
            - defined 4XX or 5XX responses → include "error handling"
            - Generate 1 high-quality test flow per scenario, for at most 5 key scenarios
            - Skip any scenario that doesn't apply to the endpoint based on the OpenAPI spec. 

            - Instead of vague goals, describe each test as a series of concrete steps. For example:

            1. Make a POST request to `/users` with a valid JSON body to create a user.
            2. Capture the returned `id` from the response.
            3. Make a GET request to `/users/{id}` using the captured ID.
            4. Assert that the response matches the schema and includes the expected values.

            - Be step-oriented. Each test flow should describe what exact sequence of API calls are made, with sample data, and how the tester knows the API is working as expected.

            - Think like this flow will used by LLM to generate executable methods to test if the API is working correctly or not.
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
        return text

    def generate_flows_for_endpoint(
        self,
        method: str,
        path: str,
        openapi_spec: dict,
        scenarios: List[str] = [
            "happy path",
            "error handling",
            "authentication",
            "boundary value",
            "schema validation",
        ],
    ) -> List[FlowModel]:
        instructions = self.prompt(method, path, openapi_spec, "\n".join(scenarios))
        agent = Agent(
            model=LLM_MODEL,
            name=f"Flow Generator for {method} {path}",
            instructions=instructions,
            output_type=List[FlowModel],
        )
        result = asyncio.run(
            Runner.run(
                agent,
                input=f"Generate test flows maximum of one for each scenario. {method} {path}",
            )
        )
        return result.final_output

    def generate_and_correct_flows(
        self,
        method: str,
        path: str,
        openapi_spec: dict,
        scenarios: List[str] = [
            "happy path",
            "error handling",
            "authentication",
            "boundary value",
            "schema validation",
        ],
    ) -> List[FlowModel]:
        raw_flows = self.generate_flows_for_endpoint(
            method=method, path=path, openapi_spec=openapi_spec, scenarios=scenarios
        )
        corrected_flows = self_correct_flows(
            method=method, path=path, openapi_spec=openapi_spec, flows=raw_flows
        )
        return corrected_flows

    def generate_flows_for_spec(self, openapi_spec: dict) -> dict:
        paths = openapi_spec.get("paths", {})
        print(f"Found {len(paths)} paths in the OpenAPI spec.")
        collections = {}
        flow_restructured = {}
        for path, methods in paths.items():
            for method, entry in methods.items():
                collection_name = method.lower() + path.replace("/", "_").replace("{", "").replace(
                    "}", ""
                )
                if path != "/users/{user_id}":
                    continue
                if method.lower() not in ["get", "post", "put", "patch", "delete"]:
                    continue
                print(f"Generating flows for {method.upper()} {path}...")
                try:
                    flows = self.generate_and_correct_flows(
                        method=method, path=path, openapi_spec=openapi_spec
                    )
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
