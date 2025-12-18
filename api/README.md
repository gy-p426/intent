# API Layer Implementation

This directory contains the FastAPI-based HTTP API implementation for the Intent Recognition Service.

## Files

### `models.py`
Defines all Pydantic data models for API requests and responses:
- `IntentEntry`: Knowledge base entry model
- `IntentCandidate`: Retrieval candidate result model  
- `IntentRecognitionRequest`: API request model with validation
- `IntentRecognitionResponse`: Standardized API response model
- `HealthCheckResponse`: Health check endpoint response model
- `ErrorResponse`: Error response model

### `app.py`
Contains the main FastAPI application with:
- `IntentRecognitionAPI` class that encapsulates the FastAPI app
- POST `/api/v1/intent/recognize` endpoint for intent recognition
- GET `/health` endpoint for health checks
- GET `/` root endpoint for service information
- Global exception handlers for HTTP and general exceptions
- CORS middleware configuration

### `__init__.py`
Exports the main API components for easy importing.

## API Endpoints

### Intent Recognition
- **URL**: `POST /api/v1/intent/recognize`
- **Request Body**: 
  ```json
  {
    "question": "User question text (1-500 characters)",
    "top_k": 20  // Optional, 1-100, default 20
  }
  ```
- **Response**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "question": "User question",
      "intents": ["microservice1", "microservice2"],
      "confidence": 0.95,
      "processing_time_ms": 1234
    }
  }
  ```

### Health Check
- **URL**: `GET /health`
- **Response**:
  ```json
  {
    "status": "healthy",
    "service": "intent-recognition-service", 
    "timestamp": "2025-12-09T10:30:00Z",
    "checks": {
      "nacos": "connected",
      "knowledge_base": "loaded",
      "intent_service": "available"
    }
  }
  ```

## Error Handling

The API implements comprehensive error handling:
- **400**: Invalid request parameters (validation errors)
- **500**: Internal server errors
- **503**: Service unavailable (dependencies not ready)

All errors return a standardized format:
```json
{
  "code": 400,
  "message": "Error description",
  "data": null
}
```

## Integration

The API layer integrates with:
- `IntentRecognitionService` from the services layer
- Nacos client for service registration
- Configuration management for settings

## Usage

The API is designed to be started via the main application entry point (`main.py`) which handles:
- Service initialization and dependency injection
- Application lifecycle management
- Graceful startup and shutdown