from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MODEL_NAME: str = "resnet18"
    DEVICE: str = "cpu"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    MAX_IMAGE_SIZE_MB: int = 5

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
