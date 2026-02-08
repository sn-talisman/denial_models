"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from src.api.routes import predictions, analytics

logger = structlog.get_logger()

app = FastAPI(
    title="Healthcare Denial Management API",
    version="0.1.0",
    description="API for denial prediction and root cause analysis",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(predictions.router)
app.include_router(analytics.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Healthcare Denial Management API",
        "version": "0.1.0",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json",
        },
        "endpoints": {
            "health": "/health",
            "predictions": {
                "predict": "/api/v1/predict",
                "predict_batch": "/api/v1/predict/batch",
                "model_info": "/api/v1/model/info",
            },
            "analytics": {
                "practices": "/api/v1/analytics/practices",
                "payers": "/api/v1/analytics/payers",
                "practice_payer_combos": "/api/v1/analytics/practice-payer",
                "overall_insights": "/api/v1/analytics/overall-insights",
                "practice_performance_summary": "/api/v1/analytics/practice/{practice_guid}/performance-summary",
                "practice_action_items": "/api/v1/analytics/practice/{practice_guid}/action-items",
                "practice_payer_performance": "/api/v1/analytics/practice/{practice_guid}/payer-performance",
                "practice_cpt_performance": "/api/v1/analytics/practice/{practice_guid}/cpt-performance",
                "practice_high_risk_claims": "/api/v1/analytics/practice/{practice_guid}/high-risk-claims",
                "practice_denial_reasons": "/api/v1/analytics/practice/{practice_guid}/denial-reasons",
                "practice_cpt_carc_correlation": "/api/v1/analytics/practice/{practice_guid}/cpt-carc-correlation",
                "practice_rejection_patterns": "/api/v1/analytics/practice/{practice_guid}/rejection-patterns",
            }
        }
    }

