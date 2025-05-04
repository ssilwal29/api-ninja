# API Ninja

API Ninja simplifies API testing by allowing users to define test flows in plain English. The framework dynamically generates and executes test steps based on user-defined flows or OpenAPI specifications with a LLM. It validates API responses against expectations and ensures that APIs behave as intended. API Ninja currently only supports OpenAI API and uses it in generating steps, payloads, headers, and other dynamic components.

---

## Key Features

- **Plain English Test Flows**: Define test flows in simple, human-readable language with expectations, and API Ninja will automatically generate and execute the required steps.
- **Dynamic Step Chaining**: Automatically chains multiple API calls together, passing data between steps as needed.
- **Expectation Validation**: Validates whether API responses meet the defined expectations and provides detailed feedback for failures.
- **OpenAPI Integration**: Requires OpenAPI specifications to generate test flows, payloads, headers, and parameters dynamically.
- **Result Evaluation**: Checks API responses for correctness, schema validation, and status codes.
- **Reporting**: Integrates with pytest for detailed test execution.

---

## How It Works

### 1. Define Flows in Plain English

Write test flows in a YAML file, describing the steps and expectations in plain English. For example:

```yaml
collections:
  user_endpoints:
    description: User-related API flows
    flows:
    - create_and_delete_user
    - put_user_with_updated_tag

create_and_delete_user:
  description: Use POST /users to create a user. Retrieve the user with GET, then delete the user.
  expectations: Each step should return 2xx on success. Final DELETE should return 204.
  notes:
    - Use a valid user object for creation.
    - Resolve {user_id} from the POST response.
    - Ensure the user is deleted successfully.

put_user_with_updated_tag:
  description: Use PUT /users/{user_id} to update the user's details, including adding a new tag. Verify the updated details with a GET request.
  expectations: Each step should return 2xx on success. The final GET request should return the updated user details, including the new tag.
  notes:
    - Use a valid user object for the update.
    - Resolve {user_id} from the POST response of the user creation step.
    - Ensure the updated tag is present in the user's details after the PUT request.
    - Validate that the GET request returns the updated user details.
```

API Ninja will:
1. Create a user using POST /users.
2. Retrieve the user using GET /users/{user_id}.
3. Update the user using PUT /users/{user_id}.
4. Validate that all steps meet the defined expectations.

Run the following command to execute the flows:
```
uv run pytest -c flows.yaml
```

---

### 2. Generate Flows from OpenAPI Spec

API Ninja can automatically generate test flows for common scenarios based on an OpenAPI specification. For example:
- **Happy Path**: Ensures endpoints work as expected with valid inputs.
- **Error Handling**: Tests how endpoints handle invalid inputs or missing data.
- **Boundary Values**: Tests edge cases for input parameters.

Run the following command to generate flows:
```
uv run -m api_ninja.cli generate-flows --url http://localhost:8000/openapi.json --out generated_flows.yaml
```

---

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourorg/api-ninja.git
   cd api-ninja
   ```

2. Create a virtual environment and activate it:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

---

## Usage

### Define Your Test Flows

Create a YAML file (e.g., `flows.yaml`) to define your test flows in plain English. For example:

```yaml
user_management_flow:
  description: Test user creation, retrieval, and deletion.
  expectations: All steps should return 2xx status codes.
  steps:
    - POST /users with valid payload
    - GET /users/{user_id} to retrieve the created user
    - DELETE /users/{user_id} to delete the user
```

### Run the Test Flows

Execute the test flows using the CLI:
```
uv run -m api_ninja.cli run-all --config config.yaml
```

### Generate Flows from OpenAPI Spec

Automatically generate test flows for your API:
```
uv run -m api_ninja.cli generate-flows --url http://localhost:8000/openapi.json --out generated_flows.yaml
```

---

## Testing 

API Ninja integrates with Allure for detailed test reporting. To generate and view reports:
1. Run tests with Allure:
   ```
   uv run pytest -c flows.yaml
   ```

---

## Development

### Linting
```
uv run ruff check .
```

### Formatting
```
uv run black .
```

---

## Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a feature branch.
3. Submit a pull request.

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.

---

## Contact

For questions or support, please contact your-email@example.com.