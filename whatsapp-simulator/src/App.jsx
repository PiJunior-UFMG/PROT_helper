import React, { useState, useEffect } from 'react';
import { Send, User, Plus, Bot, Wifi, WifiOff } from 'lucide-react';

export default function App() {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/webhook';
  const sseUrl = import.meta.env.VITE_SSE_URL || 'http://localhost:8000/simulator/stream';

  const [clients, setClients] = useState([
    { id: '1', name: 'Cliente A', phone: '+5531999990001' },
    { id: '2', name: 'Cliente B', phone: '+5531999990002' },
    { id: '3', name: 'Cliente C', phone: '+5531999990003' },
    { id: '4', name: 'Cliente D', phone: '+5531999990004' },
    { id: '5', name: 'Cliente E', phone: '+5531999990005' },

  ]);

  // Agora agrupamos as mensagens pelo NÚMERO DE TELEFONE
  const [messages, setMessages] = useState({});
  const [activeClientId, setActiveClientId] = useState(null);
  const [inputText, setInputText] = useState('');
  const [newClientPhone, setNewClientPhone] = useState('');
  const [isConnected, setIsConnected] = useState(false);

  const activeClient = clients.find(c => c.id === activeClientId);
  const activeMessages = activeClient && messages[activeClient.phone] ? messages[activeClient.phone] : [];

  // Conexão SSE para receber mensagens ativas do Backend
  useEffect(() => {
    const eventSource = new EventSource(sseUrl);

    eventSource.onopen = () => setIsConnected(true);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // O payload vem do backend: { to: "+5531999990002", text: "...", sender: "bot" }
      
      setMessages(prev => {
        const phone = data.to;
        const botMessage = {
          id: Date.now().toString() + Math.random().toString(),
          text: data.text,
          sender: 'bot',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        
        return {
          ...prev,
          [phone]: [...(prev[phone] || []), botMessage]
        };
      });
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      // O EventSource tenta reconectar automaticamente
    };

    return () => eventSource.close();
  }, [sseUrl]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || !activeClient) return;

    const userMessage = {
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Imprime a mensagem do usuário na tela
    setMessages(prev => ({
      ...prev,
      [activeClient.phone]: [...(prev[activeClient.phone] || []), userMessage]
    }));
    
    setInputText('');

    // Dispara o Webhook para a API
    const payload = {
      from: activeClient.phone,
      text: userMessage.text,
      timestamp: Date.now()
    };

    try {
      await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      // Diferente de antes, não esperamos resposta síncrona do bot aqui.
      // A resposta vai chegar via SSE (EventSource) quando o backend chamar send_message_simulator()
    } catch (error) {
      console.error("Erro ao chamar webhook:", error);
    }
  };

  const handleAddClient = (e) => {
    e.preventDefault();
    if (!newClientPhone.trim()) return;
    
    const newClient = {
      id: Date.now().toString(),
      name: `Cliente ${clients.length + 1}`,
      phone: newClientPhone
    };
    
    setClients([...clients, newClient]);
    setNewClientPhone('');
  };

  return (
    <div className="h-screen w-full flex items-center justify-center p-4">
      <div className="w-full max-w-6xl h-[90vh] bg-white rounded-lg shadow-2xl overflow-hidden flex border border-gray-300">
        
        {/* SIDEBAR */}
        <div className="w-1/3 bg-gray-50 border-r border-gray-200 flex flex-col">
          <div className="h-16 bg-gray-100 flex items-center justify-between px-4 font-semibold text-gray-700 border-b border-gray-200">
            <span>Perfis de Teste</span>
            <div className="flex items-center gap-2 text-xs" title="Status da conexão com o Backend">
              {isConnected ? (
                <span className="flex items-center gap-1 text-green-600 bg-green-100 px-2 py-1 rounded-full"><Wifi size={14}/> Online</span>
              ) : (
                <span className="flex items-center gap-1 text-red-600 bg-red-100 px-2 py-1 rounded-full"><WifiOff size={14}/> Offline</span>
              )}
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {clients.map(client => (
              <div 
                key={client.id}
                onClick={() => setActiveClientId(client.id)}
                className={`flex items-center gap-3 p-4 cursor-pointer border-b border-gray-100 transition-colors ${
                  activeClientId === client.id ? 'bg-blue-50' : 'hover:bg-gray-100'
                }`}
              >
                <div className="w-12 h-12 bg-gray-300 rounded-full flex items-center justify-center text-gray-600 shrink-0">
                  <User size={24} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-gray-900 truncate">{client.name}</h3>
                  <p className="text-sm text-gray-500 truncate">{client.phone}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 bg-white border-t border-gray-200">
            <form onSubmit={handleAddClient} className="flex gap-2">
              <input 
                type="text" 
                placeholder="Ex: +5511999990000" 
                className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                value={newClientPhone}
                onChange={(e) => setNewClientPhone(e.target.value)}
              />
              <button type="submit" className="p-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                <Plus size={20} />
              </button>
            </form>
          </div>
        </div>

        {/* ÁREA DE CHAT */}
        <div className="flex-1 flex flex-col bg-[#efeae2]">
          {activeClient ? (
            <>
              {/* Header do Chat */}
              <div className="h-16 bg-gray-100 flex items-center px-4 border-b border-gray-200 gap-3">
                <div className="w-10 h-10 bg-green-600 rounded-full flex items-center justify-center text-white shrink-0">
                  <Bot size={20} />
                </div>
                <div className="flex flex-col">
                  <span className="font-semibold text-gray-800">Seu Chatbot (API)</span>
                  <span className="text-xs text-gray-500">
                    Você está enviando mensagens como: <strong className="text-gray-700">{activeClient.phone}</strong>
                  </span>
                </div>
              </div>

              {/* Mensagens */}
              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
                {activeMessages.map(msg => (
                  <div 
                    key={msg.id} 
                    className={`max-w-[70%] rounded-lg p-2 shadow-sm relative ${
                      msg.sender === 'user' 
                        ? 'bg-[#d9fdd3] self-end rounded-tr-none' 
                        : 'bg-white self-start rounded-tl-none'
                    }`}
                  >
                    <p className="text-gray-800 text-sm leading-relaxed mb-3 whitespace-pre-wrap">{msg.text}</p>
                    <span className="text-[10px] text-gray-500 absolute bottom-1 right-2">
                      {msg.timestamp}
                    </span>
                  </div>
                ))}
              </div>

              {/* Input */}
              <div className="bg-gray-100 p-3 border-t border-gray-200">
                <form onSubmit={handleSendMessage} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    placeholder={`Mensagem como ${activeClient.name}...`}
                    className="flex-1 py-3 px-4 rounded-lg border-none focus:outline-none focus:ring-1 focus:ring-green-500 shadow-sm"
                  />
                  <button 
                    type="submit"
                    disabled={!inputText.trim()}
                    className="p-3 bg-green-600 text-white rounded-full hover:bg-green-700 disabled:opacity-50"
                  >
                    <Send size={20} className="ml-1" />
                  </button>
                </form>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-500 gap-4">
              <User size={64} className="text-gray-300" />
              <p>Selecione um perfil de teste na lateral.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}