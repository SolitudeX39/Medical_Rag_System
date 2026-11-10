from langchain_core.embeddings import Embeddings
from google import genai
from google.genai import types
import os

try:
    from components.env import load_project_env
    load_project_env()
except ImportError:
    from dotenv import load_dotenv
    load_dotenv()


class GeminiEmbeddings(Embeddings):

    def __init__(self, api_key=None, model="gemini-embedding-2"):
        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("ต้องใส่ GOOGLE_API_KEY ในไฟล์ .env")
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def embed_documents(self, texts):
        embeddings = []
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_contents = [
                    types.Content(
                        parts=[types.Part(text=text)],
                        role="user",
                    )
                    for text in batch
                    ]
                    
            resp = self.client.models.embed_content(
                model=self.model,
                contents=batch_contents
            )

            embeddings.extend(e.values for e in resp.embeddings)

        return embeddings

    def embed_query(self, text):
        resp = self.client.models.embed_content(
            model=self.model,
            contents=[text]
        )
        return resp.embeddings[0].values
