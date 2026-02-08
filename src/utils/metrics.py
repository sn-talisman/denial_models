"""Model evaluation metrics and calibration utilities."""

from typing import Optional
import numpy as np
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_curve,
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
from sklearn.calibration import calibration_curve
import structlog

logger = structlog.get_logger()


def calculate_denial_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
) -> dict[str, float]:
    """Calculate comprehensive denial prediction metrics.
    
    Args:
        y_true: True binary labels (0 = paid, 1 = denied)
        y_pred: Predicted binary labels
        y_proba: Predicted probabilities (optional)
        
    Returns:
        Dictionary of metric names and values
    """
    metrics = {}
    
    # Basic classification metrics
    metrics["precision"] = float(precision_score(y_true, y_pred, zero_division=0))
    metrics["recall"] = float(recall_score(y_true, y_pred, zero_division=0))
    metrics["f1_score"] = float(f1_score(y_true, y_pred, zero_division=0))
    
    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    metrics["true_positives"] = int(tp)
    metrics["true_negatives"] = int(tn)
    metrics["false_positives"] = int(fp)
    metrics["false_negatives"] = int(fn)
    
    # Additional derived metrics
    metrics["accuracy"] = float((tp + tn) / (tp + tn + fp + fn)) if (tp + tn + fp + fn) > 0 else 0.0
    metrics["specificity"] = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    metrics["sensitivity"] = metrics["recall"]  # Same as recall
    
    # Probability-based metrics (if probabilities provided)
    if y_proba is not None:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba))
        metrics["pr_auc"] = float(average_precision_score(y_true, y_proba))
        metrics["brier_score"] = float(brier_score_loss(y_true, y_proba))
        
        # Calibration metrics
        try:
            fraction_of_positives, mean_predicted_value = calibration_curve(
                y_true, y_proba, n_bins=10, strategy="uniform"
            )
            # Expected Calibration Error (ECE)
            ece = np.mean(np.abs(fraction_of_positives - mean_predicted_value))
            metrics["ece"] = float(ece)
        except Exception as e:
            logger.warning("Could not calculate ECE", error=str(e))
            metrics["ece"] = None
    
    return metrics


def calculate_calibration_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_bins: int = 10,
) -> dict[str, float]:
    """Calculate detailed calibration metrics.
    
    Args:
        y_true: True binary labels
        y_proba: Predicted probabilities
        n_bins: Number of bins for calibration curve
        
    Returns:
        Dictionary with calibration metrics
    """
    metrics = {}
    
    # Brier score
    metrics["brier_score"] = float(brier_score_loss(y_true, y_proba))
    
    # Calibration curve
    try:
        fraction_of_positives, mean_predicted_value = calibration_curve(
            y_true, y_proba, n_bins=n_bins, strategy="uniform"
        )
        
        # Expected Calibration Error (ECE)
        ece = np.mean(np.abs(fraction_of_positives - mean_predicted_value))
        metrics["ece"] = float(ece)
        
        # Maximum Calibration Error (MCE)
        mce = np.max(np.abs(fraction_of_positives - mean_predicted_value))
        metrics["mce"] = float(mce)
        
        # Mean Absolute Error in calibration
        mae = np.mean(np.abs(fraction_of_positives - mean_predicted_value))
        metrics["calibration_mae"] = float(mae)
        
    except Exception as e:
        logger.warning("Could not calculate calibration metrics", error=str(e))
        metrics["ece"] = None
        metrics["mce"] = None
        metrics["calibration_mae"] = None
    
    return metrics


def calibrate_probabilities(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    method: str = "isotonic",
) -> np.ndarray:
    """Calibrate predicted probabilities.
    
    Args:
        y_true: True binary labels
        y_proba: Uncalibrated probabilities
        method: Calibration method ("isotonic" or "platt")
        
    Returns:
        Calibrated probabilities
    """
    from sklearn.calibration import CalibratedClassifierCV
    
    # Reshape if needed
    if y_proba.ndim == 1:
        y_proba = y_proba.reshape(-1, 1)
    
    # Use isotonic regression or Platt scaling
    if method == "isotonic":
        calibration_method = "isotonic"
    elif method == "platt":
        calibration_method = "sigmoid"
    else:
        raise ValueError(f"Unknown calibration method: {method}")
    
    # Create a dummy classifier wrapper for calibration
    # In practice, this should be done with the actual model
    # For now, return original probabilities with a note
    logger.warning("Direct probability calibration not fully implemented - use CalibratedClassifierCV with model")
    
    return y_proba.flatten()
