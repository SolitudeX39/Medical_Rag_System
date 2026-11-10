import json
import logging
from typing import List, Dict, Any, Optional
import requests
import logging as logger
import os
from dotenv import load_dotenv
load_dotenv()


class OpenRouterRerank:
    def __init__(self, api_key= None, model ="nvidia/llama-nemotron-rerank-vl-1b-v2:free"):
        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://openrouter.ai/api/v1/rerank"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000"
            }
        
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_n = 5) -> List[Dict[str, Any]]:
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_n
        }
        try:
            response = requests.post(self.endpoint, headers=self.headers, json= payload)
            response.raise_for_status()
            results = response.json()

            final_results = []
            for result in results.get("results", []):
                document = result.get("document")
                source = document.get("text")
                result_index = result.get("index")
                score = result.get("relevance_score")
                final_results.append({
                    "index": result_index,
                    "score": score,
                    "source": source})
            return final_results
        except requests.exceptions.RequestException as e:
            logger.error(f"Reranking failed: {e}. Returning unranked fallback.")
            return [
                {
                    "index": i,
                    "score": 0.0,
                    "source": doc.get("text") if isinstance(doc, dict) else str(doc),
                }
                for i, doc in enumerate(documents[:top_n])
            ]