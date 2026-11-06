from pydantic import BaseModel, ConfigDict


class KnowledgeArticleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    url: str
    content: str
    keywords: list[str]
