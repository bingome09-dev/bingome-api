from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import urllib.request
import urllib.parse
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

clientes_ligados = []

def traduzir_texto(texto, origem, destino):
    try:
        texto_codificado = urllib.parse.quote(texto)
        url = f"https://api.mymemory.translated.net/get?q={texto_codificado}&langpair={origem}|{destino}"
        with urllib.request.urlopen(url, timeout=10) as resposta:
            dados = json.loads(resposta.read().decode('utf-8'))
            return dados["responseData"]["translatedText"]
    except:
        return "[Erro na tradução]"

@app.websocket("/ws/{nome}/{idioma}")
async def websocket_endpoint(websocket: WebSocket, nome: str, idioma: str):
    await websocket.accept()
    clientes_ligados.append(websocket)
    try:
        while True:
            texto_recebido = await websocket.receive_text()
            destino = "en" if idioma == "pt" else "pt"
            traducao = traduzir_texto(texto_recebido, idioma, destino)
            mensagem_final = {
                "remetente": nome,
                "texto_original": texto_recebido,
                "traducao": traducao
            }
            for cliente in clientes_ligados:
                await cliente.send_text(json.dumps(mensagem_final))
    except WebSocketDisconnect:
        clientes_ligados.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
