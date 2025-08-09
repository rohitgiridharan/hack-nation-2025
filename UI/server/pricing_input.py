from pydantic import BaseModel

class PricingInput(BaseModel):
    product_type: str
    customer_type: str
    day_of_week: str
    month: str
    price: float
    competitor_price: float
    price_gap: float
    promotion_flag: float
    marketing_spend: float
    economic_index: float
    seasonality_index: float
    trend_index: int

class TestBody(BaseModel):
    price: int