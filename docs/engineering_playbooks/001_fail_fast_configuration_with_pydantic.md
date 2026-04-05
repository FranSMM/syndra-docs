## Playbook 1: "Fail-Fast" Configuration with Pydantic

**Usage:** Prevent the application from starting if critical environment variables are missing, avoiding runtime crashes deep in the stack.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Syndra"
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
```
