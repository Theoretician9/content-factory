import enum

class IntegrationType(str, enum.Enum):
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    GOOGLE = "google"
    STRIPE = "stripe"
    SENDGRID = "sendgrid"
    TWILIO = "twilio"
    SLACK = "slack"
    DISCORD = "discord"

class IntegrationStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending" 