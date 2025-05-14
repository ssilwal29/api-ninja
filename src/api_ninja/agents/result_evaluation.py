import asyncio
import json
import os

from agents import Agent, Runner

from api_ninja.models import EvaluationResult

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1")


class ResultEvaluationAgent:

    def prompt(self, context: str = "", result: dict = {}) -> str:

        prompt = f"""
            You are an API test evaluator and debugger.
            Your job is to analyze the following request, response, and expectations to determine whether the API behavior is correct.

            ---
            ### Request
            - Method: {result['method']}
            - Path: {result['path']}

            - Headers:
            {json.dumps(result['headers'], indent=2)}
            - Payload:
            {json.dumps(result['payload'], indent=2)}
            - Parameters:
            {json.dumps(result['parameters'], indent=2)}

            ---
            ### Response
            - Status Code: {result['response_status']}
            - Body:
            {json.dumps(result['response_body'], indent=2)}

            ---
            ### Expectations
            - Expected Status Code: {result['expected_status']}
            - Response Check: {result['response_check']}

            ---
            ### Evaluation Task

            You must:
            1. Determine whether the status code matches the expected status.
            2. Determine whether the response body satisfies the natural-language response check.
            3. Provide a clear reason for your evaluation.
            4. If the result is FAIL, suggest what could be fixed or investigated (e.g., wrong headers, missing field, etc.).
            5. Make sure you understand the context of the API call. There could be negative scenarios where the API should return an error code. In that case, you should not suggest to fix it.

            ---
            ### Output Format (required)

            Return ONLY a structured object with the following fields:

            - status: "PASS" or "FAIL"
            - reason: a brief explanation
            - suggestion: a suggested fix or diagnostic step (or null if not needed)

            ---
            ### Example:
            {{
            "status": "FAIL",
            "reason": "Response code was 401 instead of 200. Missing authentication header.",
            "suggestion": "Add the 'x-token' header with a valid token value."
            }}
        """.strip()
        return prompt

    def run(self, context: str, result: dict = {}) -> EvaluationResult:
        prompt = self.prompt(context, result)
        agent = Agent(
            model=LLM_MODEL,
            name="API Evaluator",
            instructions=prompt,
            output_type=EvaluationResult,
        )
        output = asyncio.run(
            Runner.run(agent, input="Evaluate the result of API call to expectations.")
        )
        return output.final_output
