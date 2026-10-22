from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
from deep_translator import GoogleTranslator
import asyncio
import urllib.parse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dicionário para guardar quem está ligado
salas = {}
# Dicionário para guardar o histórico de mensagens
historico = {}

def dividir_texto(texto, limite=4500):
    """Divide textos grandes em partes menores para o Google Translate não falhar."""
    partes = []
    while len(texto) > limite:
        corte = texto.rfind('.', 0, limite)
        if corte == -1:
            corte = texto.rfind(' ', 0, limite)
        if corte == -1: 
            corte = limite
        
        partes.append(texto[:corte+1].strip())
        texto = texto[corte+1:].strip()
    
    if texto:
        partes.append(texto)
    return partes

def traduzir_texto(texto, origem, destino):
    if origem == destino:
        return texto
    try:
        partes = dividir_texto(texto)
        traducao_final = []
        
        for parte in partes:
            traducao_parte = GoogleTranslator(source=origem, target=destino).translate(parte)
            traducao_final.append(traducao_parte)
            
        return " ".join(traducao_final)
    except Exception as e:
        print(f"Erro na tradução: {e}")
        return f"[Erro ao traduzir para {destino}]"

@app.websocket("/ws/{sala}/{nome}/{idioma}")
async def websocket_endpoint(websocket: WebSocket, sala: str, nome: str, idioma: str):
    # Descodificar o nome e a sala (para e-mails e números com + ou @ funcionarem)
    nome = urllib.parse.unquote(nome) 
    sala = urllib.parse.unquote(sala)
    
    await websocket.accept()
    
    if sala not in salas:
        salas[sala] = []
    salas[sala].append({"ws": websocket, "user": nome, "lang": idioma})
    
    if sala not in historico:
        historico[sala] = []

    # Enviar o histórico de mensagens para quem acabou de entrar
    for msg in historico[sala]:
        texto_traduzido = await asyncio.to_thread(traduzir_texto, msg["text"], msg["lang"], idioma)
        await websocket.send_text(json.dumps({
            "remetente": msg["user"],
            "original": msg["text"],
            "traducao": texto_traduzido,
            "is_history": True
        }))

    try:
        while True:
            texto_recebido = await websocket.receive_text()
            
            # Guardar no histórico
            historico[sala].append({"user": nome, "text": texto_recebido, "lang": idioma})
            if len(historico[sala]) > 50:
                historico[sala].pop(0)

            # Enviar para todos na sala, traduzindo para o idioma de cada um
            for cliente in salas[sala]:
                destino_lang = cliente["lang"]
                traducao_cliente = await asyncio.to_thread(traduzir_texto, texto_recebido, idioma, destino_lang)
                
                mensagem_final = {
                    "remetente": nome,
                    "original": texto_recebido,
                    "traducao": traducao_cliente,
                    "is_history": False
                }
                await cliente["ws"].send_text(json.dumps(mensagem_final))
                
    except WebSocketDisconnect:
        salas[sala].remove({"ws": websocket, "user": nome, "lang": idioma})
        if len(salas[sala]) == 0:
            del salas[sala]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
