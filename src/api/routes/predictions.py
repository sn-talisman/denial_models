"""Prediction API endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
import pandas as pd
import structlog
from pathlib import Path

from src.api.schemas import (
    PredictionRequest,
    PredictionResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    ModelInfoResponse,
)
from src.models.denial_predictor.predictor import DenialPredictor

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["predictions"])

# Global predictor instance (lazy loaded)
_predictor: Optional[DenialPredictor] = None


def get_predictor() -> DenialPredictor:
    """Get or create predictor instance."""
    global _predictor
    if _predictor is None:
        model_path = Path("models/denial_predictor_lightgbm.pkl")
        if not model_path.exists():
            raise HTTPException(
                status_code=503,
                detail="Model not found. Please train the model first."
            )
        try:
            _predictor = DenialPredictor(model_path=model_path)
            logger.info("Predictor loaded for API")
        except Exception as e:
            logger.error("Failed to load predictor", error=str(e))
            raise HTTPException(
                status_code=503,
                detail=f"Failed to load model: {str(e)}"
            )
    return _predictor


@router.post("/predict", response_model=PredictionResponse)
async def predict_denial(
    request: PredictionRequest,
    predictor: DenialPredictor = Depends(get_predictor),
) -> PredictionResponse:
    """Predict denial probability for a single claim with pre-engineered features.
    
    Args:
        request: Prediction request with claim features
        predictor: Predictor instance (injected)
        
    Returns:
        Prediction response with probability and risk level
    """
    try:
        # Use features from request
        features = request.features
        
        # Make prediction
        result = predictor.predict(
            features=features,
            return_explanations=request.include_explanations,
        )
        
        response = PredictionResponse(
            claim_id=request.claim_id,
            denial_probability=result["probability"],
            denial_prediction=bool(result["prediction"]),
            risk_level=result["risk_level"],
            feature_importance=result.get("feature_importance"),
            explanation_type=result.get("explanation_type"),
        )
        
        logger.info("Prediction made via API",
                   claim_id=request.claim_id,
                   probability=result["probability"],
                   risk_level=result["risk_level"])
        
        return response
        
    except Exception as e:
        logger.error("Prediction error", error=str(e), claim_id=request.claim_id)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(
    request: BatchPredictionRequest,
    predictor: DenialPredictor = Depends(get_predictor),
) -> BatchPredictionResponse:
    """Predict denial probability for multiple claims.
    
    Args:
        request: Batch prediction request
        predictor: Predictor instance (injected)
        
    Returns:
        Batch prediction response
    """
    try:
        if len(request.claims) > request.max_claims:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size too large. Maximum {request.max_claims} claims per batch."
            )
        
        # Convert requests to DataFrame
        features_list = []
        claim_ids = []
        include_explanations = any(req.include_explanations for req in request.claims)
        
        for req in request.claims:
            features_list.append(req.features)
            claim_ids.append(req.claim_id)
        
        features_df = pd.DataFrame(features_list)
        
        # Make batch predictions
        predictions_df = predictor.predict_batch(features_df)
        
        # Build responses
        responses = []
        errors = []
        
        for idx, claim_id in enumerate(claim_ids):
            try:
                response = PredictionResponse(
                    claim_id=claim_id,
                    denial_probability=float(predictions_df.iloc[idx]["denial_probability"]),
                    denial_prediction=bool(predictions_df.iloc[idx]["denial_prediction"]),
                    risk_level=str(predictions_df.iloc[idx]["risk_level"]),
                )
                
                # Add explanations if requested
                if include_explanations:
                    single_result = predictor.predict(
                        features=features_df.iloc[idx].to_dict(),
                        return_explanations=True,
                    )
                    response.feature_importance = single_result.get("feature_importance")
                    response.explanation_type = single_result.get("explanation_type")
                
                responses.append(response)
            except Exception as e:
                errors.append({
                    "claim_id": claim_id,
                    "error": str(e)
                })
                logger.warning("Error processing claim in batch", claim_id=claim_id, error=str(e))
        
        logger.info("Batch prediction made via API", 
                   n_claims=len(request.claims),
                   successful=len(responses),
                   errors=len(errors))
        
        return BatchPredictionResponse(
            predictions=responses,
            total_processed=len(responses),
            errors=errors if errors else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Batch prediction error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@router.get("/model/info", response_model=ModelInfoResponse)
async def get_model_info(
    predictor: DenialPredictor = Depends(get_predictor),
) -> ModelInfoResponse:
    """Get information about the loaded model.
    
    Args:
        predictor: Predictor instance (injected)
        
    Returns:
        Model information response
    """
    try:
        metadata = predictor.metadata or {}
        
        return ModelInfoResponse(
            model_type=predictor.model_type,
            feature_count=len(predictor.feature_columns) if predictor.feature_columns else 0,
            feature_columns=predictor.feature_columns or [],
            training_date=metadata.get("training_date"),
            train_size=metadata.get("train_size"),
            validation_size=metadata.get("val_size"),
            metrics=metadata.get("metrics"),
        )
    except Exception as e:
        logger.error("Error getting model info", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {str(e)}")
