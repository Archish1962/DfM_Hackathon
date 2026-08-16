from pydantic import BaseModel

class MaterialProfile(BaseModel):
    name: str
    min_draft_angle: float
    marginal_draft_angle: float
    
    # We can add more thresholds here in the future
    # e.g., min_wall_thickness, max_wall_thickness
