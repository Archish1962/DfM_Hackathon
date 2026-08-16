from .schema import MaterialProfile

PROFILES = {
    "Generic": MaterialProfile(name="Generic", min_draft_angle=1.0, marginal_draft_angle=2.0),
    "ABS": MaterialProfile(name="ABS", min_draft_angle=1.0, marginal_draft_angle=1.5),
    "PP": MaterialProfile(name="PP", min_draft_angle=0.5, marginal_draft_angle=1.0),
    "Nylon": MaterialProfile(name="Nylon", min_draft_angle=1.5, marginal_draft_angle=2.0)
}

def get_profile(name: str) -> MaterialProfile:
    """Returns the material profile for the given name, or a generic fallback."""
    return PROFILES.get(name, PROFILES["Generic"])
