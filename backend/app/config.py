from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_token: str = ""
    github_api_base: str = "https://api.github.com"
    db_path: str = "data/fixability.db"
    repos_csv_path: str = "repos.csv"
    text_score_weight: float = 0.65
    fixability_score_weight: float = 0.35
    max_concurrency: int = 15

    model_config = {"env_file": ".env", "env_prefix": ""}


settings = Settings()
