# Intruder Server

This project is a FastAPI-based server designed to handle intrusion detection events and control a DJI drone via a controller API. It provides endpoints for receiving intrusion alerts and sending commands to the drone, such as enabling virtual stick control and executing movement sequences.

## Features

- **Intrusion Event Handling**: Receives and processes intrusion events (e.g., person detected).
- **Drone Control**: Interfaces with a DJI controller to enable virtual stick control and execute movement sequences.
- **Security**: Implements API key authentication and optional LAN-only access restrictions.
- **Rate Limiting**: Prevents flooding of intrusion events from specific devices.

## Project Structure

The project is structured as follows:

### Root Directory

- **`server.py`**: The entry point of the application. It runs the FastAPI app using `uvicorn`.
- **`.env`**: Configuration file for environment variables (e.g., API keys, timeouts).

### `app/` Directory

- **`main.py`**: The core application file. It initializes the FastAPI app, sets up middleware (like clean shutdown for the DJI client), maps the drone router, and defines the `/health` and `/v1/intrusion/events` endpoints.

### `app/api/endpoints/`

- **`drone.py`**: Defines the API routes for drone control:
  - `GET /v1/drone/status`: Checks the status of the drone movement runner.
  - `POST /v1/drone/vs/enable`: Enables or disables virtual stick control.
  - `POST /v1/drone/vs/moveSequence`: Initiates a drone movement sequence.
  - `POST /v1/drone/vs/stop`: Stops any ongoing drone movement.

### `app/schemas/`

- **`drone.py`**: Pydantic models for drone-related requests (`EnableVSRequest`, `MoveSequenceRequest`, `PhotoRequest`).
- **`models.py`**: Pydantic models for intrusion events (`IntrusionEvent`).

### `app/services/`

- **`dji_controller_client.py`**: A singleton client that handles HTTP communication with the DJI controller. It manages the connection and sends commands like `enable_virtual_stick` and `move_sticks`.
- **`move_runner.py`**: Manages the execution of drone movement sequences. It runs the movement logic in a background `asyncio` task to ensure non-blocking operation.
- **`rate_limit.py`**: Implements a sliding window rate limiter to control the frequency of accepted requests from devices.
- **`security.py`**: Contains security utilities, including:
  - `enforce_api_key`: Validates the `x-api-key` header.
  - `enforce_lan_only`: Restricts access to private LAN IP addresses if configured.

## Configuration

The application uses environment variables for configuration. Key variables likely include:

- `API_KEY`: The secret key for authenticating requests.
- `CONTROLLER_BASE_URL`: The URL of the DJI controller API.
- `CONTROLLER_API_KEY`: The API key for the DJI controller.
- `ALLOW_LAN_ONLY`: set to `true` to restrict access to local network.
