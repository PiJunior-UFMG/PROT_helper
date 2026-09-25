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
            # Lógica do Simulador React
            payload = {
                "to": to_number,
                "text": body,
                "sender": "bot"
            }
            for queue in simulator_queues:
                queue.put(payload)
                
            if cache is not None:
                add_to_history(cache, "Bot", body)
            print(f"[SIMULADOR] Mensagem enviada para {to_number}: {body}")
            
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
    background_tasks: BackgroundTasks, 
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
        
    if cache.step == 'awaiting_user_register':
        user_name = original_message.title()
        
        new_user = DBUser(user_name=user_name, user_phone=sender)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        cache.id = new_user.id
        cache.name = user_name
        # Muda o estado para aguardar a escolha do usuário
        cache.step = 'awaiting_user_choice'
        
        reply = (
            f"Prazer, {cache.name}! Cadastro de usuário realizado. ✅\n"
            f"*(Lembrando que você pode inserir mais informações no seu perfil posteriormente, nada é obrigatório agora).*\n\n"
            f"Para direcionar nosso atendimento, o que você gostaria de fazer?\n"
            f"🛒 *Comprar* produtos\n"
            f"🏢 Cadastrar sua empresa para *vender* produtos"
        )
        return answer_message(reply, cache)

    elif cache.step == 'awaiting_user_choice':
        msg_lower = original_message.lower()
        
        # Usa o histórico/mensagem para inferir a intenção. 
        # Aqui fazemos uma validação rápida por palavras-chave, 
        # mas você também pode usar sua função get_message_context da IA.
        if any(word in msg_lower for word in ["vender", "empresa", "cadastrar", "loja"]):
            intention = "vender"
        elif any(word in msg_lower for word in ["comprar", "adquirir", "buscar", "procurar"]):
            intention = "comprar"
        else:
            # Fallback para o classificador de IA caso a resposta seja muito solta
            intention = get_message_context(
                original_message, 
                "message_context_choice.txt", 
                ["vender", "comprar", "outro"]
            )
            
        if intention == "vender":
            cache.step = 'awaiting_company_register'
            return answer_message("Excelente! Para começar a vender, por favor, informe o **nome da sua empresa**:", cache)
        else:
            cache.step = 'buy_products'
            return answer_message("Perfeito! Vamos às compras 🛒. O que você está buscando hoje?", cache)

    elif cache.step == 'awaiting_company_register':
        company_name = original_message.strip()
        
        new_company = Company(company_name=company_name, user_id=cache.id)
        db.add(new_company)
        await db.commit()
        
        # Redireciona diretamente para o ciclo de cadastro de produtos
        cache.step = 'product_register'
        
        reply = (
            f"Empresa '{company_name}' cadastrada com sucesso! 🏢\n\n"
            f"Agora já podemos cadastrar o que você vai oferecer. Me descreva o primeiro **produto** que deseja registrar:"
        )
        return answer_message(reply, cache)

    elif cache.step == 'product_register':
        # Exemplo simplificado para o fluxo de registro de produtos
        cache.step = 'finished'
        await update_client_summary(cache, db)
        return answer_message("📦 Produto registrado com sucesso! Mais alguma coisa em que posso ajudar?", cache)

    elif cache.step == 'buy_products':
        # Exemplo simplificado para o fluxo de compra de produtos
        cache.step = 'finished'
        await update_client_summary(cache, db)
        return answer_message("🛒 Processo de compra atualizado. Como deseja prosseguir?", cache)
    
    # --- ESTADO NORMAL / FINALIZADO ---
    elif cache.step == 'finished':
        # Identifica a intenção global usando o classificador
        intention = get_message_context(
            original_message, 
            "message_context.txt", 
            ["saudacao", "produto", "compra", "verificacao"]
        )
        
        if intention == "produto":
            cache.step = "product_register"
            reply = "Entendido, vamos iniciar o registro de novos produtos. Me informe os detalhes do item:"
        elif intention == "compra":
            cache.step = "buy_products"
            reply = "Certo, vamos selecionar os produtos para compra. O que você procura?"
        elif intention == "saudacao":
            reply = f"Olá, {cache.name or 'novamente'}! Como posso ajudar você hoje?"
        elif intention == "verificacao":
            reply = "Verifiquei e não encontrei registros recentes por aqui."
        else:
            reply = "Desculpe, não compreendi muito bem. Poderia reformular?"

        await update_client_summary(cache, db)
        return answer_message(reply, cache)   
    
    return answer_message("Desculpe, ocorreu um erro de contexto.", cache)