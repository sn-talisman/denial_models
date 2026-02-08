"""Client for local LLM inference via Ollama.

All LLM inference runs locally - no data leaves the environment.
"""

import os
from typing import Optional
from pathlib import Path

import ollama
import structlog

logger = structlog.get_logger(__name__)


class LLMClient:
    """Client for local LLM inference using Ollama.
    
    This client wraps Ollama API calls to provide a clean interface
    for denial reason classification, explanation generation, and
    free-text parsing tasks.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ):
        """Initialize LLM client.
        
        Args:
            base_url: Ollama base URL. Defaults to OLLAMA_BASE_URL env var or http://localhost:11434
            model: Model name (e.g., "mistral", "llama3"). Defaults to OLLAMA_MODEL env var
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "mistral")
        self.temperature = float(os.getenv("OLLAMA_TEMPERATURE", str(temperature)))
        self.max_tokens = int(os.getenv("OLLAMA_MAX_TOKENS", str(max_tokens)))
        
        # Configure Ollama client
        self.client = ollama.Client(host=self.base_url)
        
        logger.info(
            "LLM client initialized",
            base_url=self.base_url,
            model=self.model,
            temperature=self.temperature,
        )
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text completion.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            
        Returns:
            Generated text response
            
        Raises:
            RuntimeError: If LLM request fails
        """
        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                system=system_prompt,
                options={
                    "temperature": temperature if temperature is not None else self.temperature,
                    "num_predict": max_tokens if max_tokens is not None else self.max_tokens,
                },
            )
            
            result = response.get("response", "").strip()
            logger.debug("LLM generation completed", model=self.model, response_length=len(result))
            return result
            
        except Exception as e:
            logger.error("LLM generation failed", error=str(e), model=self.model)
            raise RuntimeError(f"LLM generation failed: {e}") from e
    
    def classify_denial_reason(
        self,
        denial_text: str,
        carc_code: Optional[int] = None,
        rarc_code: Optional[str] = None,
    ) -> dict[str, str]:
        """Classify denial reason into normalized taxonomy category.
        
        Args:
            denial_text: Free-text denial reason
            carc_code: Optional CARC code
            rarc_code: Optional RARC code
            
        Returns:
            Dictionary with 'category' and 'confidence' keys
        """
        # Load classification prompt
        prompt_path = Path(__file__).parent / "prompts" / "denial_reason_classification.txt"
        if prompt_path.exists():
            with open(prompt_path, "r") as f:
                system_prompt = f.read()
        else:
            system_prompt = """You are a healthcare denial management expert. 
            Classify denial reasons into standardized categories based on CARC codes, 
            RARC codes, and free-text descriptions."""
        
        user_prompt = f"""Classify the following denial reason into one of these categories:
- eligibility_coverage
- authorization
- coding_errors
- medical_necessity
- duplicate_claim
- timely_filing
- bundling_unbundling
- missing_information
- coordination_of_benefits
- contractual
- other

Denial text: {denial_text}
CARC code: {carc_code or 'N/A'}
RARC code: {rarc_code or 'N/A'}

Respond with only the category name and a confidence score (0.0 to 1.0) in JSON format:
{{"category": "category_name", "confidence": 0.95}}"""
        
        try:
            response = self.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1,  # Lower temperature for classification
            )
            
            # Parse JSON response (simple extraction)
            import json
            # Try to extract JSON from response
            if "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
            else:
                # Fallback: extract category name
                result = {"category": "other", "confidence": 0.5}
            
            return result
            
        except Exception as e:
            logger.warning("Denial classification failed, using fallback", error=str(e))
            return {"category": "other", "confidence": 0.0}
    
    def generate_explanation(self, claim_id: str, denial_probability: float, top_features: list[dict]) -> str:
        """Generate human-readable explanation for denial prediction.
        
        Args:
            claim_id: Claim identifier
            denial_probability: Predicted denial probability (0.0 to 1.0)
            top_features: List of dicts with 'feature', 'value', 'shap_value' keys
            
        Returns:
            Human-readable explanation text
        """
        prompt_path = Path(__file__).parent / "prompts" / "explanation_generation.txt"
        if prompt_path.exists():
            with open(prompt_path, "r") as f:
                system_prompt = f.read()
        else:
            system_prompt = """You are a healthcare denial management expert. 
            Generate clear, actionable explanations for denial risk predictions."""
        
        features_text = "\n".join([
            f"- {feat['feature']}: {feat['value']} (impact: {feat.get('shap_value', 0):.3f})"
            for feat in top_features[:10]
        ])
        
        user_prompt = f"""Generate a concise explanation for why this claim has a 
        {denial_probability:.1%} denial risk.

        Top contributing factors:
        {features_text}

        Provide 2-3 sentences explaining the main risk factors and actionable recommendations."""
        
        return self.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )

