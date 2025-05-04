import asyncio
import json
from agents import Agent, Runner
from api_ninja.models import ApiCallModel, GoalModel


class PlannerAgent:
    def prompt(self, context: str = "", openapi_spec: dict = {}) -> str:
        prompt = f"""
            You are an expert API call planner.

            Here is the OpenAPI specification: Use it to plan the API calls needed to fulfill the user goal.
            {json.dumps(openapi_spec)}

            Information about the flow
            {context}

            Instructions:
            - Plan the sequence of API calls needed to fulfill the goal.
            - For each call, define:
            - method (POST, GET, etc.)
            - path (endpoint URL)
            - payload_description (short description of what payload is needed)
            - headers_description (short description of required headers, like Authorization)
            - expected_status (HTTP status code expected from the call)
            - response_check based on the spec or expectations create instruction for LLM what to check in the response.

            Constraints:
            - Do not invent any endpoints not found in OpenAPI spec.
            - Use provided context wherever possible for realistic values.
            - If a field depends on a previous API call response, mark it using placeholder syntax like {{user_id}} or {{token}}.
            - Only output a pure JSON array of steps.
            - Be smart and try to replicate a realistic flow of API calls.

            Example:
            [
            {{
                "method": "POST",
                "path": "/register",
                "payload_description": "Create a new user with email and password",
                "headers_description": "Set Content-Type application/json",
                "expected_status": 201,
                "response_check": "Check if the response contains a user ID and success message."
            }},
            {{
                "method": "POST",
                "path": "/login",
                "payload_description": "Login with email and password",
                "headers_description": "Set Content-Type application/json",
                "expected_status": 200
                "response_check": "Check if the response contains a valid token."
            }}
            ]
        """.strip()
        return prompt

    def run(self, context: str, openapi_spec: dict = {}) -> list[ApiCallModel]:
        prompt = self.prompt(context, openapi_spec)
        agent = Agent(
            name="API Call Planner", instructions=prompt, output_type=GoalModel
        )
        result = asyncio.run(
            Runner.run(
                agent,
                input="Show me all the steps to do. Refer to the OpenAPI spec for details.",
            )
        )
        return result.final_output.steps
