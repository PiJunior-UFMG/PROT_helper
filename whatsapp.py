import os
import asyncio
import json
from typing import List, Union, Optional, Dict
from fastapi import APIRouter, Request, Response, Depends, BackgroundTasks
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv
from sqlalchemy.orm import selectinload
from fastapi.responses import StreamingResponse

# Imports do projeto
from database import get_db, AsyncSessionLocal
from models import User as DBUser
from models import Company
from agents import get_message_context, summary_messages
from schemas import ClientCache, ChatMessage
from orchestrator import manage_agent

router = APIRouter()

# configurações do twilio
load_dotenv()
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")

USE_SIMULATOR = os.getenv("USE_SIMULATOR", "false").lower() == "true"

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# configurações do cache
user_cache: Dict[str, ClientCache] = {}
simulator_queues = []

def add_to_history(cache: ClientCache, sender_type: str, content: str):
    """Adiciona uma mensagem estruturada ao histórico do cache do cliente."""
    cache.messages.append(ChatMessage(
        sender_type=sender_type,
        step=cache.step,
        content=content
    ))

async def update_client_summary(cache: ClientCache, db: Optional[AsyncSession] = None):
    """Gera o resumo geral do histórico de mensagens e atualiza o user_context no banco de dados."""
    if cache.id:
        resumo_geral = await summary_messages(cache.messages)
        
        if db:
            db_user = await db.get(DBUser, cache.id)
            if db_user:
                db_user.user_context = resumo_geral
                await db.commit()
        else:
            async with AsyncSessionLocal() as session:
                db_user = await session.get(DBUser, cache.id)
                if db_user:
                    db_user.user_context = resumo_geral
                    await session.commit()

def answer_message(body: str, cache: Optional[ClientCache] = None) -> Response:
    """
    Gera a resposta passiva (TwiML) para fechar a requisição HTTP atual.
    Uso: Respostas imediatas e confirmações de recebimento.
    """
    response = MessagingResponse()
    twiml_msg = response.message()
    twiml_msg.body(body)
    
    if cache is not None:
        add_to_history(cache, "Bot", body)
            
    return Response(content=str(response), media_type="application/xml")

def send_message(to_number: str, messages: Union[str, List[str]], cache: Optional[ClientCache] = None):
    """
    Envia uma ou mais mensagens ativamente. 
    Roteia para o Twilio (Produção) ou para as filas SSE (Simulador) baseado no .env.
    """
    if isinstance(messages, str):
        messages = [messages]

    for body in messages:
        if not body.strip():
            continue
            
        if USE_SIMULATOR:
            payload = {
                "to": to_number,
                "text": body,
                "sender": "bot"
            }            
            for queue in simulator_queues:
                queue.put_nowait(payload)
                
            if cache is not None:
                add_to_history(cache, "Bot", body)
        else:
            # Lógica do Twilio REST API
            try:
                twilio_client.messages.create(
                    from_=TWILIO_NUMBER,
                    body=body,
                    to=to_number
                )
                if cache is not None:
                    add_to_history(cache, "Bot", body)
            except Exception as e:
                print(f"[TWILIO] Erro ao enviar mensagem para {to_number}: {e}")

@router.get("/simulator/stream")
async def simulator_stream(request: Request):
    """Rota que o React escuta em background para receber mensagens do backend."""
    queue = asyncio.Queue()
    simulator_queues.append(queue)
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"data: {json.dumps(message)}\n\n"
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
        finally:
            if queue in simulator_queues:
                simulator_queues.remove(queue)
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("") # /whatsapp
async def whatsapp_bot(
    request: Request, 
    background_tasks: BackgroundTasks, # Injeção de dependência para tarefas em background
    db: AsyncSession = Depends(get_db)
):
    form_data = await request.form()
    original_message = form_data.get('Body', '').strip()
    lower_message = original_message.lower()
    sender = form_data.get('From', '')

    cache = user_cache.get(sender)
    
    # --- COMANDOS ESPECIAIS ---
    if lower_message == '#reset':
        user_cache.pop(sender, None)
        return answer_message("🔄 O seu cache de estado foi resetado.", None)
        
    elif lower_message.startswith('#del '):
        name_to_delete = original_message[5:].strip()
        stmt = select(DBUser).where(DBUser.user_name.ilike(name_to_delete))
        result = await db.execute(stmt)
        db_user = result.scalars().first()
        
        if db_user:
            if db_user.user_phone in user_cache:
                user_cache.pop(db_user.user_phone, None)
            await db.delete(db_user)
            await db.commit()
            return answer_message(f"🗑️ O usuário '{db_user.user_name}' foi apagado.", None)
        return answer_message(f"⚠️ Usuário não encontrado.", None)

    elif lower_message.startswith("#ch "):
        if not cache:
            return answer_message("⚠️ Nenhum cache ativo encontrado para alterar o step.")
        new_step = original_message[4:].strip()
        old_step = cache.step
        cache.step = new_step
        return answer_message(f"🔄 old_step: {old_step}, new_step: {new_step}", cache)
    
    # --- LÓGICA DE ESTADOS / AUTENTICAÇÃO ---
    if not cache:
        stmt = select(DBUser).where(DBUser.user_phone == sender)
        result = await db.execute(stmt)
        existing_user = result.scalars().first()
        
        if existing_user:
            cache = ClientCache(
                id=existing_user.id, 
                name=existing_user.user_name,
                num=existing_user.user_phone,
                step="finished"
            )
            user_cache[sender] = cache
        else:
            cache = ClientCache(num=sender, step="awaiting_user_register")
            user_cache[sender] = cache
            add_to_history(cache, "User", original_message)
            return answer_message("Olá! Seja bem-vindo. Para começarmos o seu cadastro, qual é o seu nome?", cache)
            
    add_to_history(cache, "User", original_message)

    # --- ROTEAMENTO DO FLUXO ---
    if cache.step == 'awaiting_user_register':
        user_name = original_message.title()
        
        new_user = DBUser(user_name=user_name, user_phone=sender)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        cache.id = new_user.id
        cache.name = user_name
        cache.step = 'finished'
        
        return answer_message(f"Prazer, {cache.name}! Seu cadastro foi feito. ✅\nComo posso ajudar hoje? (Diga se deseja comprar ou vender)", cache)

    elif cache.step == 'awaiting_company_register':
        company_name = original_message.strip()
        
        new_company = Company(company_name=company_name, user_id=cache.id)
        db.add(new_company)
        await db.commit()
        
        # Redireciona diretamente para o ciclo de cadastro de produtos
        cache.step = 'product_register'
        
        reply = (
            f"Empresa '{company_name}' cadastrada com sucesso! 🏢\n\n"
            f"Agora já podemos cadastrar o que você vai oferecer. Me descreva os produto que deseja registrar"
        )
        return answer_message(reply, cache)
    
    elif cache.step == 'awaiting_product_confirmation':
        msg_lower = original_message.lower()
        
        # Se o cliente confirmar (sim, pode, ok, confirmo)
        if any(word in msg_lower for word in ["sim", "pode", "confirmo", "isso", "ok", "certo"]):
            
            # Verifica qual operação estava guardada no cache
            operacao = getattr(cache, 'pending_operation', 'adicionar')
            
            if operacao == "adicionar":
                holding_msg = "⏳ Salvando seus produtos e gerando a busca inteligente. Isso pode levar alguns segundos..."
            elif operacao == "alterar":
                holding_msg = "⏳ Atualizando as informações dos seus produtos no sistema..."
            elif operacao == "remover":
                holding_msg = "⏳ Removendo os produtos selecionados do seu catálogo..."
            else:
                holding_msg = "⏳ Processando as alterações no seu catálogo..."
            
            # Manda para a fila do BackgroundTask com uma intenção genérica de execução
            background_tasks.add_task(manage_agent, sender, original_message, "executar_operacao_confirmada", cache)
            return answer_message(holding_msg, cache)
            
        # Se ele negar ou cancelar
        else:
            cache.step = "finished"
            if cache:
                cache.suggested_products = [] # Limpa a memória
                cache.pending_operation = None
            await update_client_summary(cache, db)
            return answer_message("❌ Operação no catálogo cancelada. O que você gostaria de fazer agora?", cache)

    elif cache.step == 'product_register':
        # O cliente está respondendo com os dados do produto. Enviamos para o agente classificar e processar.
        holding_msg = "⏳ Entendido! Estou analisando e processando as informações dos produtos..."
        background_tasks.add_task(manage_agent, sender, original_message, "venda", cache)
        return answer_message(holding_msg, cache)

    elif cache.step == 'buy_products':
        # O cliente está num fluxo direto de compra. Aciona o agente com intenção de "compra".
        holding_msg = "⏳ Buscando as melhores opções para o seu pedido..."
        background_tasks.add_task(manage_agent, sender, original_message, "compra", cache)
        return answer_message(holding_msg, cache)
    
    # --- ESTADO NORMAL / FINALIZADO ---
    elif cache.step == 'finished':
        # Identifica a intenção global usando o classificador
        intention = get_message_context(
            original_message, 
            "message_context.txt", 
            ["saudacao", "compra", "venda"]
        )
        
        if intention == "venda":
            stmt = (
                select(DBUser)
                .options(selectinload(DBUser.companies))
                .where(DBUser.user_phone == sender)
            )
            result = await db.execute(stmt)
            existing_user = result.scalars().first()

            # Verifica se o usuário existe e se possui empresas cadastradas
            if not existing_user or not existing_user.companies:
                cache.step = "awaiting_company_register"  
                reply = "Entendido, primeiro vamos iniciar o registro de sua empresa. Por favor, envie o nome da empresa:"
                return answer_message(reply, cache)
            else:
                # FIM DA GAMBIARRA: Apenas muda o step e pergunta o que ele quer fazer
                cache.step = "product_register"
                reply = "Entendido! Vamos gerenciar seu catálogo. Me descreva os produtos que você deseja adicionar, alterar ou remover:"
                await update_client_summary(cache, db)
                return answer_message(reply, cache)
        
        elif intention == "compra":
            holding_msg = "⏳ Entendido! Vou analisar seu pedido de compra no banco de dados, só um instante..."
            background_tasks.add_task(manage_agent, sender, original_message, "compra",cache)
            return answer_message(holding_msg, cache)
        
        elif intention == "saudacao":
            reply = f"👋 Olá, {cache.name or 'tudo bem'}! Como posso ajudar hoje?"
            
            # Atualiza o histórico da conversa e devolve a resposta final
            await update_client_summary(cache, db)
            return answer_message(reply, cache)
            
        else:
            reply = "Desculpe, não compreendi muito bem. Poderia reformular?"
            await update_client_summary(cache, db)
            return answer_message(reply, cache)   
    
    return answer_message("Desculpe, ocorreu um erro de contexto.", cache)