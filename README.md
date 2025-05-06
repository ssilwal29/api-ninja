# API Ninja

API Ninja simplifies API testing by allowing users to define test flows in plain English. The framework dynamically generates and executes test steps based on user-defined flows or OpenAPI specifications with a LLM. It validates API responses against expectations and ensures that APIs behave as intended. API Ninja currently only supports OpenAI API and uses it in generating steps, payloads, headers, and other dynamic components.
> **Note:** This alpha version supports only basic JSON requests (`GET`, `POST`, `PUT`, `DELETE`). File uploads via `multipart/form-data` are not yet supported.

---

## Key Features

- **Plain English Test Flows**: Define test flows in simple, human-readable language with expectations, and API Ninja will automatically generate and execute the required steps.
- **Dynamic Step Chaining**: Automatically chains multiple API calls together, passing data between steps as needed.
- **Expectation Validation**: Validates whether API responses meet the defined expectations and provides detailed feedback for failures.
- **OpenAPI Integration**: Requires OpenAPI specifications to generate test flows, payloads, headers, and parameters dynamically.
- **Result Evaluation**: Checks API responses for correctness, schema validation, and status codes.
- **Reporting**: Integrates with pytest for detailed test execution.


---

## Installation

Install via pip:

```bash
pip install api-ninja
```

Or install from source using `uv`:

```bash
git clone https://github.com/ssilwal29/api-ninja.git
cd api-ninja
uv pip install -e .
```

---

## Quick Start

### 1. Define Flows in Plain English

Write test flows in a YAML file, describing the steps and expectations in plain English. Check demo/ for more examples. For example:

```yaml
defaults:
- some default behavior across all the collections

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
uv pytest --config flows.yaml --openapi-spec-url <url-to-openapi-spec> --base-url <api-base-url>
```

---

### 2. Generate Flows from OpenAPI Spec

API Ninja can automatically generate test flows for common scenarios based on an OpenAPI specification. For example:
- **Happy Path**: Ensures endpoints work as expected with valid inputs.
- **Error Handling**: Tests how endpoints handle invalid inputs or missing data.
- **Boundary Values**: Tests edge cases for input parameters.
- **Authentication**: Tests cases related to authentication accessing the endpoint
- **Schema Validation**: Ensures the request and response schema are valid and expected as defined

Run the following command to generate flows:
```
uv run -m api_ninja.cli generate-flows --url <url-to-openapi-json-spec> --out <path-of-the-out-file>
```

---

## Roadmap

- [x] YAML-based test flow definition
- [x] Flow generation via OpenAPI + LLM
- [x] Variable extraction and chaining
- [x] Pytest-based execution
- [x] Docker support
- [ ] Support additional HTTP methods and payload types
- [ ] Looping and conditional logic in flows
- [ ] Checkpointing for generated and verified flows
- [ ] Filter and run specific flows/collections
- [ ] Visual test result analytics
- [ ] Web-based UI for authoring and managing flows
- [ ] Git metadata tracking for traceability
- [ ] Support for multiple LLM providers

---

## Development

### Lint

```bash
uv run ruff check .
```

### Format

```bash
uv run black .
```

---

## Contributing

Contributions are welcome!

1. Fork the repo
2. Create a feature branch
3. Submit a PR with a clear description

Have an idea or suggestion? Open an issue or start a discussion.

**Found a bug? Want to request a feature or ask a question?**  
Please create an issue on [GitHub](https://github.com/ssilwal29/api-ninja/issues).

---

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.

---

## Contact

For questions or support, please contact ssilwal29@gmail.com
