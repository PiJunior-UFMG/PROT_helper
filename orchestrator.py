from database import AsyncSessionLocal
from schemas import ClientCache
from typing import Dict
from agents import get_message_context, extract_products_from_message, text_embedding

import asyncio
import numpy as np

async def manage_agent(sender_num: str, original_message: str, intention: str, cache: ClientCache):
    
    from whatsapp import send_message, update_client_summary
    
    reply = ""
    
    if intention == "compra":
        async with AsyncSessionLocal() as db:
            from models import User, Company, Product
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            
            user_summary = ""
            if cache and cache.id:
                db_user = await db.get(User, cache.id)
                if db_user and db_user.user_context:
                    user_summary = db_user.user_context

            # TODO: Buscar catálogo, extrair tags e chamar agente de recomendação
            reply = "🛒 [Resultado do agente de compras será processado aqui]"
            await update_client_summary(cache, db)

    elif intention == "venda":
        async with AsyncSessionLocal() as db:
            from models import User, Company, Product
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload 
            
            user_summary = ""
            if cache and cache.id:
                db_user = await db.get(User, cache.id)
                if db_user and db_user.user_context:
                    user_summary = db_user.user_context

            sub_intention = get_message_context(
                original_message, 
                "message_context_product.txt", 
                ["adicionar_produto", "alterar_produto", "remover_produto", "nao_entendi"],
                user_summary
            )

            if sub_intention == "adicionar_produto":
                products = extract_products_from_message(original_message, user_summary)

                if not products:
                    reply = "Não consegui identificar claramente os nomes dos produtos. Pode descrever de forma mais direta?"
                else:
                    if cache:
                        cache.suggested_products = products 
                        cache.step = "awaiting_product_confirmation"
                        cache.pending_operation = "adicionar" 
                    
                    lista_formatada = "\n- ".join(products)
                    reply = f"Identifiquei os seguintes produtos:\n\n{lista_formatada}\n\n*Posso confirmar e salvar no sistema?* (Sim / Não)"
                    
            elif sub_intention == "alterar_produto":
                reply = "Lógica de alterar em construção..."

            elif sub_intention == "remover_produto":
                reply = "Lógica de remover em construção..."

            else:
                stmt = select(Company).options(selectinload(Company.products)).where(Company.user_id == cache.id)
                result = await db.execute(stmt)
                company = result.scalars().first()
                
                if company and company.products:
                    lista_produtos = "\n".join([f"🔸 {p.product_name}" for p in company.products])
                    reply = (f"🏢 Seu catálogo atual:\n{lista_produtos}\n\n"
                             f"O que deseja fazer?")
                else:
                    reply = "🤔 Desculpe, não entendi bem. Seu catálogo está vazio. Me diga o nome do produto que deseja adicionar!"
            
            await update_client_summary(cache, db)
            # A chamada individual do send_message foi removida daqui

    elif intention == "executar_operacao_confirmada":
        print("[DEBUG] Entrou na intenção executar_operacao_confirmada")
        try:
            async with AsyncSessionLocal() as db:
                from models import Company, Product
                from sqlalchemy import select, text
                
                operacao = getattr(cache, 'pending_operation', 'adicionar')
                products_in_memory = cache.suggested_products if cache else []
                print(f"[DEBUG] Operação: {operacao}, Produtos: {products_in_memory}")
                
                stmt = select(Company).where(Company.user_id == cache.id)
                result = await db.execute(stmt)
                company = result.scalars().first()
                print(f"[DEBUG] Empresa encontrada: {company}")
                
                if not company:
                    reply = "⚠️ Nenhuma empresa encontrada no seu cadastro. Registre a empresa antes de gerenciar produtos."
                else:
                    if operacao == "adicionar":
                        for prod_name in products_in_memory:
                            embedding_vector = await asyncio.to_thread(text_embedding, prod_name)
                            new_product = Product(
                                company_id=company.company_id,
                                user_id=cache.id,
                                product_name=prod_name,
                                product_embedding=embedding_vector  # Passando a lista limpa da OpenAI
                            )
                            db.add(new_product)

                        print("[DEBUG] Fazendo commit no banco de dados...")
                        await db.commit()
                        print("[DEBUG] Commit realizado com sucesso!")
                        reply = f"✅ Sucesso! {len(products_in_memory)} produto(s) adicionado(s) ao seu catálogo."
                    
                    elif operacao == "alterar":
                        reply = "✅ Sucesso! Produto(s) alterado(s)."
                    
                    elif operacao == "remover":
                        reply = "✅ Sucesso! Produto(s) removido(s) do catálogo."

                if cache:
                    cache.suggested_products = []
                    cache.pending_operation = None
                    cache.step = "finished"
                    await update_client_summary(cache, db)
                    
        except Exception as e:
            print(f"\n[ERRO CRÍTICO NO BACKGROUND] Falha ao salvar no banco: {e}\n")
            import traceback
            traceback.print_exc()  # Imprime o erro completo na consola
            reply = f"❌ Ocorreu um erro ao processar sua solicitação no banco de dados."
            
    elif intention == "saudacao":
        pass

    else:
        reply = "Processamento concluído."

    print(f"[DEBUG] Fim do manage_agent. Mensagem a enviar (reply): {reply}")
    if reply:
        send_message(to_number=sender_num, messages=reply, cache=cache)
        print("[DEBUG] send_message executado com sucesso!")