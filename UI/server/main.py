import os
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Smart Pricing AI Backend")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class ShippingRequest(BaseModel):
    origin_zip: str
    destination_zip: str
    weight_kg: float
    num_boxes: int
    service_level: str

class ShippingResponse(BaseModel):
    origin_zip: str
    destination_zip: str
    weight_kg: float
    num_boxes: int
    service_level: str
    estimated_cost: float
    breakdown: Dict[str, float]
    provider: str
    message: str

class CompetitorRequest(BaseModel):
    query: str
    max_results: int = 3

class CompetitorResponse(BaseModel):
    query: str
    offers: List[Dict]
    provider: str
    message: str
    attemptedProviders: List[str]

class PricingRecommendation(BaseModel):
    sku: str
    currentPrice: float
    recommendedPrice: Optional[float] = None

class InvoicePricingRequest(BaseModel):
    items: List[Dict]
    buyer_segment: str
    buyer_country: str
    supplier_country: str

class InvoicePricingResponse(BaseModel):
    recommendations: List[Dict]
    provider: str
    message: str

# Ensure data directory exists
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)
recommendations_file = data_dir / "recommendations.json"

def load_recommendations() -> List[Dict]:
    if recommendations_file.exists():
        try:
            with open(recommendations_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading recommendations: {e}")
            return []
    return []

def save_recommendations(recommendations: List[Dict]):
    try:
        with open(recommendations_file, 'w') as f:
            json.dump(recommendations, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving recommendations: {e}")

def get_shipping_cost_with_openai(request: ShippingRequest) -> ShippingResponse:
    """Use OpenAI API to get actual shipping cost estimates"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    client = OpenAI(api_key=api_key)
    
    # Create a detailed prompt for shipping estimation
    prompt = f"""
    You are a shipping cost estimator. Please estimate the shipping cost for the following package:
    
    Origin: {request.origin_zip} (US zip code)
    Destination: {request.destination_zip} (US zip code)
    Weight: {request.weight_kg} kg
    Number of boxes: {request.num_boxes}
    Service level: {request.service_level}
    
    Please provide:
    1. Base shipping cost
    2. Any additional fees (fuel surcharge, handling, etc.)
    3. Total estimated cost
    
    Return your response as a JSON object with these fields:
    {{
        "base_cost": <number>,
        "fuel_surcharge": <number>,
        "handling_fee": <number>,
        "total_cost": <number>,
        "notes": "<any relevant notes>"
    }}
    
    Use realistic US shipping rates. For ground shipping, typical rates are $5-15 for local, $15-30 for regional, and $30-60 for long distance.
    """
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a shipping cost estimator. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        # Extract and parse the response
        content = response.choices[0].message.content
        logger.info(f"OpenAI response: {content}")
        
        # Try to extract JSON from the response
        try:
            # Look for JSON in the response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                shipping_data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI response: {e}")
            # Fallback to estimated calculation
            shipping_data = {
                "base_cost": 15.0,
                "fuel_surcharge": 2.0,
                "handling_fee": 3.0,
                "total_cost": 20.0,
                "notes": "Fallback calculation due to parsing error"
            }
        
        # Calculate breakdown
        breakdown = {
            "base_shipping": shipping_data.get("base_cost", 0),
            "fuel_surcharge": shipping_data.get("fuel_surcharge", 0),
            "handling_fee": shipping_data.get("handling_fee", 0)
        }
        
        total_cost = shipping_data.get("total_cost", sum(breakdown.values()))
        
        return ShippingResponse(
            origin_zip=request.origin_zip,
            destination_zip=request.destination_zip,
            weight_kg=request.weight_kg,
            num_boxes=request.num_boxes,
            service_level=request.service_level,
            estimated_cost=total_cost,
            breakdown=breakdown,
            provider="openai",
            message=shipping_data.get("notes", "AI-generated shipping estimate")
        )
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        # Fallback to basic calculation
        base_cost = 15.0 * request.weight_kg
        fuel_surcharge = base_cost * 0.12
        handling_fee = request.num_boxes * 3.0
        total_cost = base_cost + fuel_surcharge + handling_fee
        
        return ShippingResponse(
            origin_zip=request.origin_zip,
            destination_zip=request.destination_zip,
            weight_kg=request.weight_kg,
            num_boxes=request.num_boxes,
            service_level=request.service_level,
            estimated_cost=total_cost,
            breakdown={
                "base_shipping": base_cost,
                "fuel_surcharge": fuel_surcharge,
                "handling_fee": handling_fee
            },
            provider="fallback",
            message=f"Fallback calculation due to API error: {str(e)}"
        )

# Health check endpoint
@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

# Shipping cost estimation endpoint
@app.post("/api/shipping/estimate", response_model=ShippingResponse)
async def estimate_shipping(request: ShippingRequest):
    """Get shipping cost estimate using OpenAI API"""
    try:
        return get_shipping_cost_with_openai(request)
    except Exception as e:
        logger.error(f"Shipping estimation error: {e}")
        raise HTTPException(status_code=500, detail=f"Shipping estimation failed: {str(e)}")

# Existing competitor search functionality
def _extract_text_and_citations(response) -> tuple[str, list]:
    """Extract text and citations from OpenAI response"""
    text = getattr(response, 'output_text', '') or ''
    citations = []
    
    # Try to extract citations from response.output
    output = getattr(response, 'output', []) or []
    for item in output:
        contents = getattr(item, 'content', []) or []
        for content in contents:
            if hasattr(content, 'type') and getattr(content, 'type') == 'text':
                text_content = getattr(content, 'text', '')
                if text_content:
                    text = text_content
            elif hasattr(content, 'type') and getattr(content, 'type') == 'image':
                # Handle image content if needed
                pass
    
    # Try to extract citations from annotations
    annotations = getattr(response, 'annotations', []) or []
    for annotation in annotations:
        if hasattr(annotation, 'citations'):
            for citation in getattr(annotation, 'citations', []):
                citations.append({
                    'url': getattr(citation, 'url', ''),
                    'title': getattr(citation, 'title', ''),
                    'text': getattr(citation, 'text', '')
                })
    
    return text, citations

def _openai_web_search(query: str, max_results: int) -> List[dict]:
    """Use OpenAI web search to find product pages"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    
    try:
        # Direct REST call to OpenAI responses API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        force = os.getenv("OPENAI_WEBSEARCH_FORCE", "false").lower() in {"1", "true", "yes"}
        payload = {
            "model": os.getenv("OPENAI_WEBSEARCH_MODEL", "gpt-4o"),
            "tools": [{"type": "web_search"}],
            "tool_choice": "required" if force else "auto",
            "input": query,
        }
        resp = httpx.post("https://api.openai.com/v1/responses", headers=headers, json=payload, timeout=20.0)
        if resp.status_code >= 400:
            return []
        data = resp.json()
        
        # Mock response object for extraction
        class Obj(dict):
            def __getattr__(self, k):
                return self.get(k)
        response_obj = Obj(data)
        _text, citations = _extract_text_and_citations(response_obj)
        
        if not citations:
            return []
        out: List[dict] = []
        for c in citations[:max_results]:
            url = c.get("url") or ""
            if not url:
                continue
            title = c.get("title") or url
            out.append({"title": title, "href": url, "body": ""})
        return out
    except Exception:
        return []

def _duckduckgo_search(query: str, max_results: int) -> List[dict]:
    """Use DuckDuckGo search as fallback"""
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        results = []
        for r in ddgs.text(query, max_results=max_results, backend="lite"):
            results.append({
                "title": r.get("title", ""),
                "href": r.get("link", ""),
                "body": r.get("body", "")
            })
        return results
    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return []

@app.get("/api/pricing/competitors", response_model=CompetitorResponse)
async def get_competitor_offers(
    q: str = Query(..., description="Search query for product"),
    max_results: int = Query(3, description="Maximum number of results")
):
    """Get competitor offers using OpenAI web search with fallbacks"""
    attempted_providers = []
    
    # Try OpenAI web search first
    if os.getenv("OPENAI_API_KEY"):
        attempted_providers.append("openai-web_search")
        offers = _openai_web_search(q, max_results)
        if offers:
            return CompetitorResponse(
                query=q,
                offers=offers,
                provider="openai-web_search",
                message="Successfully found competitor offers using OpenAI web search",
                attemptedProviders=attempted_providers
            )
    
    # Fallback to DuckDuckGo
    attempted_providers.append("duckduckgo")
    offers = _duckduckgo_search(q, max_results)
    if offers:
        return CompetitorResponse(
            query=q,
            offers=offers,
            provider="duckduckgo",
            message="Found competitor offers using DuckDuckGo search",
            attemptedProviders=attempted_providers
        )
    
    # Final fallback to DuckDuckGo lite
    attempted_providers.append("duckduckgo-lite")
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        offers = []
        for r in ddgs.text(q, max_results=max_results, backend="lite"):
            offers.append({
                "title": r.get("title", ""),
                "href": r.get("link", ""),
                "body": r.get("body", "")
            })
        if offers:
            return CompetitorResponse(
                query=q,
                offers=offers,
                provider="duckduckgo-lite",
                message="Found competitor offers using DuckDuckGo lite",
                attemptedProviders=attempted_providers
            )
    except Exception as e:
        logger.error(f"DuckDuckGo lite error: {e}")
    
    return CompetitorResponse(
        query=q,
        offers=[],
        provider="duckduckgo-lite",
        message="Search failed or rate-limited; fallback produced no results",
        attemptedProviders=attempted_providers
    )

@app.get("/api/pricing/recommendations")
async def get_pricing_recommendations():
    """Get all pricing recommendations"""
    return load_recommendations()

@app.post("/api/pricing/recommendations")
async def add_pricing_recommendation(recommendation: PricingRecommendation):
    """Add or update a pricing recommendation"""
    recommendations = load_recommendations()
    
    # Check if SKU already exists
    existing_index = next((i for i, r in enumerate(recommendations) if r["sku"] == recommendation.sku), None)
    
    if existing_index is not None:
        # Update existing recommendation
        recommendations[existing_index].update(recommendation.dict())
    else:
        # Add new recommendation
        recommendations.append(recommendation.dict())
    
    save_recommendations(recommendations)
    return {"message": "Recommendation saved successfully", "sku": recommendation.sku}

def generate_pricing_with_openai(request: InvoicePricingRequest) -> InvoicePricingResponse:
    """Use OpenAI API to generate pricing recommendations for invoice items"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    client = OpenAI(api_key=api_key)
    
    # Create a detailed prompt for pricing analysis
    items_summary = "\n".join([
        f"- {item.get('sku', 'Unknown')}: {item.get('description', 'No description')} "
        f"(Current: ${float(item.get('unitPrice', 0)):.2f}, Qty: {int(item.get('quantity', 1))})"
        for item in request.items
    ])
    
    prompt = f"""
    You are a pricing analyst for life sciences and biotech products. Analyze the following invoice items and provide pricing recommendations:
    
    BUYER PROFILE:
    - Segment: {request.buyer_segment}
    - Country: {request.buyer_country}
    
    SUPPLIER COUNTRY: {request.supplier_country}
    
    INVOICE ITEMS:
    {items_summary}
    
    Please analyze each item and provide:
    1. Market analysis for the buyer segment
    2. Recommended pricing strategy
    3. Specific price recommendations for each SKU
    
    Return your response as a JSON object with this structure:
    {{
        "recommendations": [
            {{
                "sku": "SKU_CODE",
                "current_price": <current_price>,
                "recommended_price": <recommended_price>,
                "pricing_strategy": "<strategy_name>",
                "reasoning": "<detailed_explanation>",
                "market_factors": ["<factor1>", "<factor2>"],
                "confidence_level": "<high/medium/low>"
            }}
        ],
        "overall_strategy": "<overall_pricing_strategy>",
        "market_insights": "<general_market_analysis>"
    }}
    
    Consider:
    - Buyer segment pricing sensitivity
    - Geographic pricing differences
    - Product complexity and value
    - Competitive positioning
    - Volume discounts
    - Market demand
    """
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a pricing analyst. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        # Extract and parse the response
        content = response.choices[0].message.content
        logger.info(f"OpenAI pricing response: {content}")
        
        # Try to extract JSON from the response
        try:
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                pricing_data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI pricing response: {e}")
            # Fallback to basic recommendations
            pricing_data = {
                "recommendations": [
                    {
                        "sku": item.get("sku", "Unknown"),
                        "current_price": float(item.get("unitPrice", 0)),
                        "recommended_price": float(item.get("unitPrice", 0)) * 1.1,
                        "pricing_strategy": "standard_markup",
                        "reasoning": "Fallback calculation due to parsing error",
                        "market_factors": ["basic_markup"],
                        "confidence_level": "low"
                    }
                    for item in request.items
                ],
                "overall_strategy": "standard_markup",
                "market_insights": "Fallback analysis"
            }
        
        return InvoicePricingResponse(
            recommendations=pricing_data.get("recommendations", []),
            provider="openai",
            message=f"AI-generated pricing recommendations. {pricing_data.get('overall_strategy', '')}"
        )
        
    except Exception as e:
        logger.error(f"OpenAI pricing API error: {e}")
        # Fallback to basic recommendations
        fallback_recommendations = [
            {
                "sku": item.get("sku", "Unknown"),
                "current_price": float(item.get("unitPrice", 0)),
                "recommended_price": float(item.get("unitPrice", 0)) * 1.15,
                "pricing_strategy": "fallback_markup",
                "reasoning": f"Fallback calculation due to API error: {str(e)}",
                "market_factors": ["error_fallback"],
                "confidence_level": "low"
            }
            for item in request.items
        ]
        
        return InvoicePricingResponse(
            recommendations=fallback_recommendations,
            provider="fallback",
            message=f"Fallback pricing due to API error: {str(e)}"
        )

@app.post("/api/pricing/invoice", response_model=InvoicePricingResponse)
async def generate_invoice_pricing(request: InvoicePricingRequest):
    """Generate pricing recommendations for invoice items using OpenAI"""
    try:
        return generate_pricing_with_openai(request)
    except Exception as e:
        logger.error(f"Invoice pricing generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Pricing generation failed: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
