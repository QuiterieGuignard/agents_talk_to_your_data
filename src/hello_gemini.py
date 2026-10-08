from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0)

reponse = llm.invoke("Explique en deux phrases ce qu'est un data warehouse, pour un directeur marketing.")
print(reponse.text)