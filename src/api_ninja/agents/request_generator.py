import asyncio
import json
from api_ninja.models import ApiCallModel
from agents import Agent, Runner


class RequestGeneratorAgent:
    def prompt(
        self,
        step: ApiCallModel,
        context: str = "",
        openapi_spec: dict = {},
        schema: dict = {},
    ) -> str:
        """
        Generates API request components (payload, parameters, headers, and optionally resolved path)
        based on OpenAPI schema, user goal, and context.
        """
        prompt = f"""
        You are an API request generator used in an automated testing system.

        Your role is to generate the full request structure — `method`, `path`, `payload`, `parameters`, and `headers` — using:
        1. The OpenAPI specification,
        2. The request description,
        3. The provided context (variables, background info, goal, expected result).

        ### 🧠 Context:
        {context}

        ---

        ### 📘 OpenAPI Specification:
        {json.dumps(openapi_spec)}

        ### 📝 Request Details:
        - Method: {step.method}
        - Path: {step.path}
        - Payload Description: {step.payload_description}
        - Headers Description: {step.headers_description}

        ---

        ### 🔧 Instructions:
        - Use the OpenAPI spec as the **primary source of truth** for required fields, types, and parameter locations.
        - Always generate a valid payload, params, etc unless you are expplicitly told not to.
        - Use the **context to resolve all dynamic values** in `path`, `parameters`, and `headers`. Replace placeholders like `/users/{{{{user_id}}}}` with actual values (e.g., `/users/1234`).
        - Automatically construct the request `payload` using schema information from the OpenAPI spec. Use **realistic values** from context where available.
        - Do not make up endpoints, fields, or types. Do not include any values or fields not defined in the OpenAPI spec.
        - If any part (e.g., headers, parameters, payload) is not required, return it as an empty object (`{{{{}}}}`).
        - Output must be **strictly a single JSON object**. Do not include code block syntax (e.g., ```json) or any explanatory text.

        ---
        The expected output schema is as follows:
        {json.dumps(schema)}

        ### ✅ Output JSON Format:
        {{{{  
        "method": "GET" | "POST" | "PUT" | "DELETE",
        "path": "/resolved/endpoint/with/actual/values",
        "payload": {{{{}}}},
        "parameters": {{{{}}}},
        "headers": {{{{}}}}
        }}}}
        
        Make sure you resolve all dynamic values in the path, parameters, and headers using the context. And the generated payload to be valid JSON and realistic fake data.
        """.strip()

        return prompt

    def run(
        self, step: ApiCallModel, context: str = "", openapi_spec: dict = {}
    ) -> dict:
        payload_schema = (
            get_request_body_schema(openapi_spec, step.path, step.method) or ""
        )
        prompt = self.prompt(step, context, openapi_spec, payload_schema)
        agent = Agent(
            name="API Request Agent",
            instructions=prompt,
            output_type=str,
        )
        result = asyncio.run(
            Runner.run(
                agent,
                input="Generate the API request components based on the provided details.",
            )
        )
        if result.final_output.startswith("```json"):
            result.final_output = result.final_output[7:-3]
        return json.loads(result.final_output)


def get_request_body_schema(openapi_spec: dict, path: str, method: str) -> dict | None:
    """
    Returns the JSON schema for the requestBody of a given path and method, if available.

    Parameters:
        openapi_spec (dict): The OpenAPI specification as a dict.
        path (str): The endpoint path (e.g., "/users/{user_id}").
        method (str): HTTP method (e.g., "post", "get").

    Returns:
        dict | None: JSON schema for the payload or None if not found.
    """
    path_item = openapi_spec.get("paths", {}).get(path)
    if not path_item:
        return None

    operation = path_item.get(method.lower())
    if not operation:
        return None

    request_body = operation.get("requestBody")
    if not request_body:
        return None

    # Handle application/json only for now
    content = request_body.get("content", {}).get("application/json")
    if not content:
        return None

    return content.get("schema")
