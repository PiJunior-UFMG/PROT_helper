from database import AsyncSessionLocal
from whatsapp import user_cache, send_message, update_client_summary

async def manage_agent(sender_num: str, original_message: str, intention: str):
    """
    Papel exclusivo: Despachar a execução para o agente de IA/DB responsável.
    Arquivo sugerido: orchestrator.py
    """
    # Se transferir para outro arquivo, o user_cache e send_message precisarão ser importados 
    # ou passados como argumento para evitar dependência circular.
    
    cache = user_cache.get(sender_num)
    reply = ""
    
    if intention == "compra":
        async with AsyncSessionLocal() as db:
            from models import User, Company, Product
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            
            # 1. Resgata o resumo histórico do usuário (adaptado para User e user_context)
            user_summary = ""
            if cache and cache.id:
                db_user = await db.get(User, cache.id)
                if db_user and db_user.user_context:
                    user_summary = db_user.user_context

            # --- ESPAÇO PARA IMPLEMENTAÇÃO ---
            # TODO: 2. Buscar catálogo geral (adaptar para Company/Product)
            # TODO: 3. Extrair intenções/tags da mensagem usando IA (extract_product_tags)
            # TODO: 4. Chamar agente de recomendação de produtos (recommend_products)
            # TODO: 5. Montar a variável 'reply' com as recomendações ou aviso de não encontrado
            
            reply = "🛒 [Resultado do agente de compras será processado aqui]"

            await update_client_summary(cache, db)

    elif intention == "venda":
        async with AsyncSessionLocal() as db:
            from models import User, Company, Product
            
            # 1. Resgata contexto histórico se necessário
            user_summary = ""
            if cache and cache.id:
                db_user = await db.get(User, cache.id)
                if db_user and db_user.user_context:
                    user_summary = db_user.user_context
            
            # --- ESPAÇO PARA IMPLEMENTAÇÃO ---
            # TODO: 1. Processar a mensagem para extrair os dados do produto que o cliente quer vender/cadastrar
            # TODO: 2. Validar se a empresa já está cadastrada
            # TODO: 3. Salvar o novo Product no banco associado à Company
            # TODO: 4. Formular a resposta de confirmação de cadastro
            
            reply = "📦 [Resultado do agente de cadastro/venda será processado aqui]"
            
            await update_client_summary(cache, db)

    elif intention == "saudacao":
        async with AsyncSessionLocal() as db:
            from models import User
            
            user_summary = ""
            client_name = "Usuário"
            
            if cache and cache.id:
                db_user = await db.get(User, cache.id)
                if db_user:
                    user_summary = db_user.user_context or ""
                    client_name = db_user.user_name

            # --- ESPAÇO PARA IMPLEMENTAÇÃO ---
            # TODO: 1. Chamar agente gerador de saudação proativa usando o user_summary
            
            reply = "👋 [Resultado do agente de saudação será processado aqui]"
            
            if cache:
                cache.step = "finished"
                await update_client_summary(cache, db)

    else:
        reply = "Processamento concluído."

    send_message(to_number=sender_num, messages=reply, cache=cache)