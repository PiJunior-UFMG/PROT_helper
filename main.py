import os
import uvicorn
import argparse
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware # 1. IMPORTANTE: Adicionado para o React

#import dashboard
import whatsapp
from database import create_tables

app = FastAPI()

# configurando cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Você pode trocar "*" por ["http://localhost:5173"] para maior segurança local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(whatsapp.router, prefix="/whatsapp", tags=["WhatsApp Bot"])


# 3. ATENÇÃO: IMPORTAÇÃO CIRCULAR
# Se o arquivo whatsapp.py tentar fazer `from main import simulator_queues`, o Python vai dar erro
# pois o main.py já importa o whatsapp.py ali em cima. 
# RECOMENDAÇÃO: Mova esta lista e a rota '/simulator/stream' para DENTRO do seu arquivo `whatsapp.py` 
# e troque `@app.get` por `@router.get`. (Não se esqueça de atualizar a URL no frontend para /whatsapp/simulator/stream).


async def initialize_db(create_db: bool):
    if create_db:
        await create_tables()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-server",
        action="store_true",
        help="Inicia o servidor Uvicorn."
    )
    parser.add_argument(
        "--create-db",
        action="store_true",
        help="Cria o banco de dados e as tabelas necessárias."
    )
    parser.add_argument(
        "--simulator",
        action="store_true",
        help="Ativa o modo simulador via SSE e desativa envios para o Twilio."
    )
    
    args = parser.parse_args()

    if args.simulator:
        os.environ["USE_SIMULATOR"] = "true"
        print("🔧 MODO SIMULADOR ATIVADO")

    if args.create_db:
        asyncio.run(initialize_db(args.create_db))

    if args.run_server:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")